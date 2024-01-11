import os
import traceback
from uuid import UUID, uuid4
from pathlib import Path

from fastapi import Depends, UploadFile
from sqlalchemy.orm import Session
from fastapi import APIRouter
from loguru import logger
from starlette.responses import JSONResponse, FileResponse
from typing import Literal, List

from common import define
from common.api import AudioInterface, CenterInterface
from common.db.database import get_db
from common.db.crud import coffee as coffee_crud
from common.db.crud.db_const import DB_Constant
from business import get_coffee_obj, Business
from common.myerror import DBError
from common.schemas.coffee import NewMaterialCurrent, UpdateMaterialCurrent, NewFormula, NewMachineConfig, \
    UpdateGpioConfig

import time

router = APIRouter(
    prefix="/{}".format(define.Channel.coffee),
    tags=[define.Channel.coffee],
    responses={404: {"description": "Not found"}},
    on_startup=[get_coffee_obj]
)


@router.post("/make", description="control coffee machine to make drink")
def make(formula: str, sweetness: int, ice: define.SUPPORT_ICE_TYPE,
         milk: str, beans: str, discount: float, unit_money: float, cup=define.CupSize.medium_cup,
         task_uuid: UUID = None, receipt_number: str = '', create_time=None,
         coffee: Business = Depends(get_coffee_obj), db: Session = Depends(get_db)):
    try:
        support_formula_name = DB_Constant.support_formula_name()
        assert formula in support_formula_name, 'drink [{}] not support, permitted {}'.format(formula,
                                                                                              support_formula_name)

        new_dict = {
            'task_uuid': task_uuid,
            'receipt_number': receipt_number,
            'formula': formula,
            'cup': cup,
            'sweetness': sweetness,
            'ice': ice,
            'milk': milk,
            'beans': beans,
            'discount': discount,
            'unit_money': unit_money
        }
        if create_time:
            new_dict['create_time'] = create_time
        if task_uuid:
            if status := coffee_crud.get_task_uuid_status(db, task_uuid):  # coffee exist
                if status in [define.TaskStatus.completed, define.TaskStatus.canceled, define.TaskStatus.skipped]:
                    AudioInterface.gtts(
                        "{} {} with uuid={} cannot be made.".format(status, formula, str(task_uuid)[-4:]))
                    return JSONResponse(status_code=400,
                                        content="{} {} with uuid end_with={} cannot be made.".format(status, formula,
                                                                                                     task_uuid))
                else:
                    update_dict = dict(status=define.TaskStatus.waiting)
                    coffee_crud.update_coffee_by_task_uuid(db, task_uuid, update_dict)
            else:
                logger.info('adding coffee with task_uuid')
                coffee_crud.add_new_coffee_task(db, new_dict)
        else:
            task_uuid = uuid4()
            logger.debug('This is debug make! Generate a random uuid={}'.format(task_uuid))
            coffee_crud.add_new_coffee_task(db, new_dict)
        msg = 'make formula={}, task_uuid={}'.format(formula, task_uuid)
        coffee.start_make_coffee_thread(msg)
        return msg
    except Exception as e:
        logger.error("make failed, traceback={}".format(traceback.format_exc()))
        return JSONResponse(status_code=400, content=str(e))


@router.post("/test_coffee", description="test coffee")
def test_coffee(coffee: Business = Depends(get_coffee_obj), db: Session = Depends(get_db)):
    try:
        coffee_dict = {}
        task_uuid = '923e314f-1723-3b8c-9f23-f93903455263'
        coffee_crud.delete_coffee_task(task_uuid)
        new_dict = {
            'task_uuid': '923e314f-1723-3b8c-9f23-f93903455263',
            'receipt_number': 'TEST',
            'formula': 'Latte',
            'cup': 'Medium Cup',
            'sweetness': 100,
            'ice': 'no_ice',
            'milk': '',
            'beans': '',
            'discount': 0,
            'unit_money': 0,
            'status': define.TaskStatus.completed
        }
        coffee_crud.add_new_coffee_task(db, new_dict)
        coffee_dict['database'] = 'ok'
        coffee_dict['coffee_dict'] = 'ok'
        coffee_dict['make_thread'] = coffee.make_coffee_thread.test_run_flag
        return coffee_dict
    except Exception as e:
        logger.error("make failed, traceback={}".format(traceback.format_exc()))
        return JSONResponse(status_code=400, content=str(e))


@router.get("/current_task_status", description="current task status")
def current_task_status(coffee: Business = Depends(get_coffee_obj)):
    return coffee.make_coffee_thread.current_task_status


@router.post("/pause_making", description="current task status")
def pause_making(coffee: Business = Depends(get_coffee_obj)):
    return coffee.make_coffee_thread.pause()


@router.post("/proceed_making", description="current task status")
def proceed_making(coffee: Business = Depends(get_coffee_obj)):
    return coffee.make_coffee_thread.proceed()


@router.get("/task/next", description="next waiting coffee record")
def get_next(db: Session = Depends(get_db)):
    next_uuid = coffee_crud.exist_next_record(db)
    if next_uuid:
        return next_uuid
    else:
        return ''


@router.put("/task/failed", description="set one task failed")
def task_failed(task_uuid: UUID = None, coffee: Business = Depends(get_coffee_obj)):
    return coffee.set_task_uuid_failed(task_uuid)


@router.post("/drink/cancel", description="cancel drink")
def cancel_drink(task_uuid: UUID = None, db: Session = Depends(get_db)):
    try:
        if coffee_crud.cancel_drink_by_task_uuid(db, task_uuid):
            return 'ok'
    except Exception as e:
        return JSONResponse(status_code=400, content=str(e))


@router.put("/stop", description="stop all action")
def stop(coffee: Business = Depends(get_coffee_obj)):
    return coffee.stop()


@router.put("/resume", description="resume to work")
def resume(coffee: Business = Depends(get_coffee_obj)):
    return coffee.resume()


@router.post("/material/add", description="add a new material")
def new_material(material: NewMaterialCurrent, db: Session = Depends(get_db)):
    logger.info(f"into new_material:{material.dict()}")
    material_dict = material.dict()
    img = material_dict.get("img")
    if img:
        try:
            suffix = img.split('.')[1]
            new_file_path = f"/richtech/resource/coffee/imgs/material/{material_dict['name']}.{suffix}"
            os.rename(img, new_file_path)
        except Exception as e:
            return JSONResponse(status_code=400, content={'error': 'no image uploaded'})
    try:
        material_dict["img"] = new_file_path
        material_dict["count"] = 0
        if material_dict.get("display_type", "") == "tap":
            material_dict["unit"] = "ml"
            material_dict["batch"] = 50
        logger.info(f"into new_material:{material_dict}")
        coffee_crud.add_material(db, material_dict)
    except DBError as e:
        os.remove(img)
        return JSONResponse(status_code=400, content={'error': str(e)})
    return 'ok'


@router.get("/material/get", description="get material by name or get all material")
def get_material(name=None, in_use: Literal['0', '1'] = None, db: Session = Depends(get_db)):
    return_data = []
    in_use = in_use if in_use is None else int(in_use)
    materials = coffee_crud.get_material(db, name, in_use)
    for material in materials:
        dd = material.to_dict()
        dd["left"] = int(dd["left"])
        # if dd['name'] == 'cold_water':
        #     dd['name'] = 'green_tea_syrup'
        return_data.append(dd)
    return return_data


@router.post("/material/update", description="update a material")
def update_material_by_id(update: UpdateMaterialCurrent, db: Session = Depends(get_db)):
    try:
        logger.debug(update.dict())
        coffee_crud.update_material_by_id(db, update.dict())
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return 'ok'


@router.post("/material/use", description="update a material")
async def use_material(name: str, quantity: float = 0, db: Session = Depends(get_db)):
    try:
        material = coffee_crud.use_material(db, name, quantity)
        if material and material.left <= material.alarm:
            AudioInterface.gtts('please replace {}, {} {} left.'.format(name, material.left, material.unit))
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return 'ok'


@router.post("/material/bean_out", description="set coffee bean left 0")
async def bean_out(db: Session = Depends(get_db)):
    try:
        material = coffee_crud.get_material(db, 'bean')
        if material:
            material[0].left = 0
            db.commit()
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return 'ok'


@router.post("/material/bean_reset", description="reset count of coffee bean")
async def bean_reset(db: Session = Depends(get_db)):
    try:
        material = coffee_crud.get_material(db, 'bean')
        if material:
            material[0].left = material[0].capacity
            db.commit()
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return 'ok'


# @router.post("/material/off_use", description=" off_use a material")
# def off_use(name: str):
#     update_dict = dict(in_use=define.Constant.IN_USE.not_in_use)
#     try:
#         milktea_crud.update_material(db, name, update_dict)
#     except DBError as e:
#         return JSONResponse(status_code=400, content={'error': str(e)})
#     return 'ok'
#
#
# @router.post("/material/on_use", description="on_use a material")
# def on_use(name: str):
#     update_dict = dict(in_use=define.Constant.IN_USE.in_use)
#     try:
#         milktea_crud.update_material(db, name, update_dict)
#     except DBError as e:
#         return JSONResponse(status_code=400, content={'error': str(e)})
#     return 'ok'


@router.post("/material/reset", description="reset a material")
async def on_use(names: List[str], db: Session = Depends(get_db)):
    coffee_crud.reset_material(db, names)
    return 'ok'


@router.post("/formula/add", description="add a new formula")
def new_formula(formula: NewFormula, db: Session = Depends(get_db)):
    logger.info(f"into new_formula{formula.dict()}")
    formula_dict = formula.dict()
    img = formula_dict.get("img", {})
    if img:
        try:
            suffix = img.split('.')[1]
            new_file_path = f"/richtech/resource/coffee/imgs/formula/{formula_dict['name']}.{suffix}"
            os.rename(img, new_file_path)
        except Exception as e:
            os.remove(img)
            return JSONResponse(status_code=400, content={'error': 'no image uploaded'})
    try:
        formula_dict["img"] = new_file_path
        coffee_crud.insert_menu_with_composition(db, formula_dict)
    except DBError as e:
        os.remove(new_file_path)
        logger.error(e)
        return JSONResponse(status_code=400, content={'error': str(e)})
    return 'ok'


@router.post("/formula/update", description="update formula")
def update_formula(formula: NewFormula, db: Session = Depends(get_db)):
    logger.info(f"into update_formula{formula.dict()}")
    coffee_machine = formula.dict().get("coffee_machine", {})
    drink_num = formula.dict().get("drink_num",{})
    if coffee_machine != 0 and drink_num == 0:
        return JSONResponse(status_code=400, content={'error': "drink_num cannot be 0"})
    try:
        coffee_crud.update_menu_with_composition(db, formula.dict())
    except DBError as e:
        logger.error(f"update_formula api : {e}")
        return JSONResponse(status_code=400, content={'error': str(e)})
    return 'ok'


@router.get("/formula/get", description="get formula")
def get_formula(name=None, cup: define.SUPPORT_CUP_SIZE_TYPE = None,
                in_use: Literal['0', '1'] = None, db: Session = Depends(get_db)):
    in_use = in_use if in_use is None else int(in_use)
    return_data = coffee_crud.get_all_formula(db, name, cup, in_use)
    return return_data


@router.get("/formula/image/download", description="")
async def download(path: str):
    logger.info('download path={}'.format(path))
    if os.path.exists(path):
        return FileResponse(path)
        # return FileResponse(path, filename=os.path.basename(formula.img))
    return JSONResponse(status_code=400, content={'error': 'file {} not exist'.format(path)})


@router.post("/formula/image/upload", description="")
async def upload(type: int, img: UploadFile, id: int = None, db: Session = Depends(get_db)):
    logger.info('upload')
    if str(type) == '1':
        if id is not None:
            try:
                formula = coffee_crud.get_formula(db, formula_id=id)
                if formula:
                    formula = formula[0]
                    filename = '{}{}'.format(id, Path(img.filename).suffix)
                    path = os.path.join('/richtech/resource/coffee/imgs/formula', filename)
                    with open(path, 'wb') as f:
                        f.write(img.file.read())
                    formula.img = path
                    db.commit()
            except DBError as db_error:
                return JSONResponse(status_code=400, content={'error': str(db_error)})
        else:
            filename = f'formula_temp{Path(img.filename).suffix}'
            path = os.path.join('/richtech/resource/coffee/imgs/formula', filename)
            with open(path, 'wb') as f:
                f.write(img.file.read())
        return path
    elif str(type) == '2':
        if id is not None:
            try:
                materials = coffee_crud.get_material(db, material_id=id)
                if materials:
                    material = materials[0]
                    filename = '{}{}'.format(id, Path(img.filename).suffix)
                    path = os.path.join('/richtech/resource/coffee/imgs/material', filename)
                    with open(path, 'wb') as f:
                        f.write(img.file.read())
                    material.img = path
                    db.commit()
            except DBError as db_error:
                return JSONResponse(status_code=400, content={'error': str(db_error)})
        else:
            filename = f'material_temp{Path(img.filename).suffix}'
            path = os.path.join('/richtech/resource/coffee/imgs/material', filename)
            with open(path, 'wb') as f:
                f.write(img.file.read())
        return path
    else:
        return JSONResponse(status_code=400, content={'error': 'param [type] error'})
    return JSONResponse(status_code=400, content={'error': 'error id'})


@router.post("/formula/off_use", description=" off_use a material")
def formula_off_use(name: str, cup: define.SUPPORT_CUP_SIZE_TYPE, db: Session = Depends(get_db)):
    update_dict = dict(in_use=define.Constant.InUse.not_in_use)
    try:
        coffee_crud.update_formula(db, name, cup, update_dict)
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return 'ok'


@router.post("/formula/on_use", description="on_use a material")
def formula_on_use(name: str, cup: define.SUPPORT_CUP_SIZE_TYPE, db: Session = Depends(get_db)):
    update_dict = dict(in_use=define.Constant.InUse.in_use)
    try:
        coffee_crud.update_formula(db, name, cup, update_dict)
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return 'ok'


@router.delete("/formula/delete", description="delete a formula")
def delete_formula(formula_id: int, db: Session = Depends(get_db)):
    try:
        if coffee_crud.delete_formula_in_use(db, formula_id):
            return 'success'
    except:
        return JSONResponse(status_code=510, content={'error': 'Delete failed'})


@router.get("/composition/get", description="get composition of a formula")
def get(formula: str, cup: define.SUPPORT_CUP_SIZE_TYPE, formula_in_use: Literal['0', '1'] = None, db: Session = Depends(get_db)):
    composition = coffee_crud.get_composition_by_formula(db, formula, cup, formula_in_use)
    return composition


@router.post("/composition/update", description="update count in composition")
def get(formula: str, cup: define.SUPPORT_CUP_SIZE_TYPE,
        material: str, count, db: Session = Depends(get_db)):
    try:
        coffee_crud.update_composition_count(db, formula, cup, material, count)
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return 'ok'


@router.post("/machine/add", description="add a new formula")
def new_machine(machine: NewMachineConfig, db: Session = Depends(get_db)):
    try:
        coffee_crud.add_machine_config(db, machine.dict())
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return 'ok'


@router.get("/machine/get", description="get gpio config")
def get(name: str = None, machine: str = None, db: Session = Depends(get_db)):
    return_data = []
    configs = coffee_crud.get_machine_config(db, name, machine)
    for config in configs:
        return_data.append(config.to_dict())
    return return_data


@router.post("/machine/update", description="update gpio config")
def update_gpio(name: str, update: UpdateGpioConfig, db: Session = Depends(get_db)):
    try:
        coffee_crud.update_machine_config_by_name(db, name, update.dict())
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return 'ok'


@router.get("/speech/add", description="add one text into database")
def text(text: str, code: str, db: Session = Depends(get_db)):
    try:
        return coffee_crud.add_text(db, text, code)
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})


@router.get("/speech/random", description="get one text from database")
def text(code: str, db: Session = Depends(get_db)):
    try:
        text = coffee_crud.choose_one_speech_text(db, code)
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return text


@router.get("/speech/get_all", description="get all text by code")
def get_all_texts(code=None, db: Session = Depends(get_db)):
    try:
        texts = coffee_crud.get_all_text(db, code)
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return texts


@router.post("/speech/update/", description="update text record by id")
def update_text(text_id, text: str, db: Session = Depends(get_db)):
    try:
        texts = coffee_crud.update_text_by_id(db, text_id, text=text)
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return texts


@router.delete("/speech/delete/", description="update text record by id")
def update_text(text_id, db: Session = Depends(get_db)):
    try:
        coffee_crud.delete_text_by_id(db, text_id)
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return 'ok'


@router.get("/machine/get_all_machine_states", description="get all text by code")
def get_all_machine_states(db: Session = Depends(get_db)):
    try:
        machine_states_list = coffee_crud.get_machine_states_by_id(db)
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return {"data": machine_states_list}


@router.get("/espresso/get", description="get composition of a formula")
def get_espresso(formula: str,  db: Session = Depends(get_db)):
    espresso = coffee_crud.get_espresso_by_formula(db, formula)
    return espresso


@router.post("/clean_history", description="add_clean_history")
def add_clean_history(cleaning_dict: dict, cleaning_method: Literal['1', '2'], db: Session = Depends(get_db)):
    logger.info(f"cleaning_dict == {cleaning_dict} , cleaning_method == {cleaning_method}")
    try:
        coffee_crud.add_cleaning_history(db, cleaning_dict=cleaning_dict, cleaning_method=cleaning_method)
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return 'ok'


@router.get("/clean_history/get_last_one", description="get_clean_history")
def get_last_one_clean_history(db: Session = Depends(get_db)):
    try:
        cleaning_history = coffee_crud.get_last_one_cleaning_history(db)
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return cleaning_history


@router.get("/update_detect_by_name", description="get_clean_history")
def update_detect_by_name(name: str = None, status: int = None, task_uuid: UUID = None, db: Session = Depends(get_db)):
    try:
        coffee_crud.update_detect_by_name(db, name=name, status=status, task_uuid=task_uuid)
    except DBError as e:
        logger.error(e)
        return JSONResponse(status_code=400, content={'error': str(e)})
    return 'ok'


@router.get("/get_detect_all_data", description="get_clean_history")
async def get_detect_all_data(name: str = None, db: Session = Depends(get_db)):
    try:
        record_list = coffee_crud.get_detect_all_data(db, name=name)
    except DBError as e:
        logger.error(traceback.format_exc())
        return JSONResponse(status_code=400, content={'error': str(e)})
    return record_list


@router.get("/get_current_completed_drink", description="get current completed drink")
def get_current_completed_drink(db: Session = Depends(get_db)):
    try:
        if record_list := coffee_crud.get_detect_all_data(db, name="cup_stand"):
            logger.info("into record")
            for record in record_list:
                if record["detail"]:
                    drink_info = coffee_crud.get_coffee_by_task_uuid(db, task_uuid=record["detail"])
                    order_info = CenterInterface.get_order_by_task_uuid(record["detail"])
                    if reference_id := order_info.get("reference_id", ""):
                        if len(reference_id) > 4:
                            order_info["reference_id"] = reference_id[-4:]
                    record["detail"] = {"drink_info": drink_info, "order_info": order_info}
        return record_list
    except DBError as e:
        logger.error(traceback.format_exc())
        # logger.warning(str(e))
        return JSONResponse(status_code=400, content={'error': str(e)})


@router.post("/add_formula_duration", description="add_formula_duration")
def add_formula_duration(formula, duration, left_status, right_status, db: Session = Depends(get_db)):
    try:
        coffee_crud.add_formula_duration(db, formula, duration, left_status, right_status)
    except DBError as e:
        logger.error(traceback.format_exc())
        return JSONResponse(status_code=400, content={'error': str(e)})
    return "ok"


@router.get("/get_formula_duration", description="get_formula_duration")
def get_formula_duration(formula: str = None, db: Session = Depends(get_db)):
    try:
        if formula:
            record_list = coffee_crud.get_formula_duration(db, formula)
        else:
            record_list = coffee_crud.get_formula_duration(db)
    except DBError as e:
        logger.error(traceback.format_exc())
        return JSONResponse(status_code=400, content={'error': str(e)})
    return record_list


@router.get("/get_idle_interaction", description="get_idle_interaction")
def get_idle_interaction(db: Session = Depends(get_db)):
    try:
        record_list = coffee_crud.get_idle_interaction(db)
    except DBError as e:
        logger.error(traceback.format_exc())
        return JSONResponse(status_code=400, content={'error': str(e)})
    return record_list