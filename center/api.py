import copy
import json
import os.path
from uuid import UUID
from typing import Literal
import random

from fastapi import APIRouter, Depends, Query
from loguru import logger
from starlette.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session

from auth import Auth
from business import Center, get_center_obj
from common import utils
from common.db.crud import center as center_crud
from common.db.crud.db_const import DB_Constant
from common.db.database import get_db
from common.define import Channel, TaskStatus, OrderStatus, AudioConstant
from common.define import SUPPORT_SERVICE
from common.schemas import center as center_schemas
from common.api import AudioInterface, CoffeeInterface
from common.define import Constant

# from common.dependencies import get_admin_token

user_handler = Auth()

router = APIRouter(
    prefix="/{}".format(Channel.center),
    tags=[Channel.center],
    # dependencies=[Depends(user_handler.check_token_from_asw)],
    dependencies=[Depends(user_handler.check_jwt_token)],
    responses={404: {"description": "Not found"}},
    on_startup=[get_center_obj]
)


# order
@router.post("/pos_order", description="create new order include drink and order number from pos")
async def new_pos_order(order: center_schemas.PosOrder, db: Session = Depends(get_db)):
    try:
        logger.info(f"order = {order}")
        support_formula_name = DB_Constant.support_formula_name()
        for drink in order.drinks:
            # assert drink.name in support_formula_name, 'drink [{}] not support, permitted {}'.format(drink.name, support_formula_name)
            for name in support_formula_name:
                if drink.name.lower() == name.lower():
                    drink.name = name
                    break
            else:
                assert False, 'drink [{}] not support, permitted {}'.format(drink.name, support_formula_name)
        AudioInterface.gtts('/richtech/resource/audio/voices/new_order2.mp3')
        center_crud.create_paid_order_from_pos(db, order)
        return center_crud.get_tasks_by_order_number(db, order.order_number)
    except Exception as e:
        logger.warning("create new order error={}".format(str(e)))
        return JSONResponse(status_code=400, content={'error': str(e)})


@router.post("/order", description="create new order include drink and order number from pad")
async def new_order(order: center_schemas.PadOrder, db: Session = Depends(get_db)):
    try:
        logger.info(f"order {order}")
        logger.info(f"order.dict() {order.dict()}")
        support_formula_name = DB_Constant.support_formula_name()
        for drink in order.drinks:
            # assert drink.name in support_formula_name, 'drink [{}] not support, permitted {}'.format(drink.name, support_formula_name)
            for name in support_formula_name:
                if drink.name.lower() == name.lower():
                    drink.name = name
                    break
            else:
                assert False, 'drink [{}] not support, permitted {}'.format(drink.name, support_formula_name)
        AudioInterface.gtts('/richtech/resource/audio/voices/new_order2.mp3')
        center_crud.create_paid_order_from_pad(db, order)
        return center_crud.get_tasks_by_order_number(db, order.order_number)
    except Exception as e:
        logger.warning("create new order error={}".format(str(e)))
        return JSONResponse(status_code=400, content={'error': str(e)})

@router.post("/test_center", description="create new order include drink and order number from pad")
async def test_center(formula: str, db: Session = Depends(get_db), center: Center = Depends(get_center_obj)):
    try:
        center_crud.delete_test_order()
        new_order_dict = {'order_number': f"TEST_{random.randint(100000, 999999)}", 'reference_id': 'test0000', 'status': 'completed', 'refund': 0, 'drinks': [{
            'reference_id': 'test1111',
            'receipt_number': 'TEST',
            'name': formula,
            'milk': '',
            'choose_beans': '',
            'discount': 0,
            'refund': 0,
            'option': {},
        }]}
        logger.debug(new_order_dict)
        order = center_schemas.PadOrder.parse_obj(new_order_dict)
        support_formula_name = DB_Constant.support_formula_name()
        for drink in order.drinks:
            # assert drink.name in support_formula_name, 'drink [{}] not support, permitted {}'.format(drink.name, support_formula_name)
            for name in support_formula_name:
                if drink.name.lower() == name.lower():
                    drink.name = name
                    break
            else:
                assert False, 'drink [{}] not support, permitted {}'.format(drink.name, support_formula_name)
        center_crud.create_paid_order_from_pad(db, order)
        order_dict = center_crud.get_tasks_by_order_number(db, order.order_number)
        if order_dict:
            return {"center_status": "ok", "flask_thread": center.task_thread.run_flag, "database": "ok"}
        else:
            return {"center_status": "not ok"}
    except Exception as e:
        logger.warning("create new order error={}".format(str(e)))
        return JSONResponse(status_code=400, content={'error': str(e)})


@router.post("/order/cancel", description="cancel order")
def cancel_order(order_number: center_schemas.CancelOrder, db: Session = Depends(get_db)):
    try:
        center_crud.cancel_order_by_order_number(db, order_number.order_number)
        waiting_tasks = center_crud.get_waiting_tasks_by_order_number(db, order_number.order_number)
        for task_uuid in waiting_tasks:
            center_crud.cancel_task_by_task_uuid(db, task_uuid)
            CoffeeInterface.cancel_drink(task_uuid)
        return JSONResponse(status_code=200, content="ok")
    except Exception as e:
        return JSONResponse(status_code=400, content=str(e))


@router.post("/task/cancel", description="cancel drink")
def cancel_task(task_uuid: center_schemas.CancelTask, db: Session = Depends(get_db)):
    try:
        center_crud.cancel_task_by_task_uuid(db, task_uuid.task_uuid)
        CoffeeInterface.cancel_drink(task_uuid.task_uuid)
        return JSONResponse(status_code=200, content="ok")
    except Exception as e:
        return JSONResponse(status_code=400, content=str(e))


@router.post("/order/get_order_by_task_uuid", description="return order info")
def get_order_by_task_uuid(task_uuid: UUID, db: Session = Depends(get_db)):
    try:
        return center_crud.get_order_by_task_uuid(db, task_uuid)
    except Exception as e:
        logger.warning("get_order_by_task_uuid failed, error={}".format(str(e)))
        return JSONResponse(status_code=400, content={'error': str(e)})


@router.post("/order/inner_paid", description="update status from unpaid to paid")
async def inner_paid_order(order_number, receipt_number, db: Session = Depends(get_db)):
    try:
        drinks, labels = center_crud.paid_order_by_number(db, order_number, receipt_number)
        AudioInterface.gtts(CoffeeInterface.choose_one_speech_text(AudioConstant.TextCode.new_order))
        return drinks
    except Exception as e:
        logger.warning("inner_update_order failed, error={}".format(str(e)))
        return JSONResponse(status_code=400, content={'error': str(e)})


@router.post("/inner_order", description="create new order include drink and order number from square pos")
async def inner_new_order(order: center_schemas.InnerOrder, db: Session = Depends(get_db)):
    try:
        support_formula_name = DB_Constant.support_formula_name()
        for drink in order.drinks:
            assert drink.formula in support_formula_name, 'drink [{}] not support, permitted {}'.format(drink.formula,
                                                                                                        support_formula_name)
        AudioInterface.gtts(CoffeeInterface.choose_one_speech_text(AudioConstant.TextCode.new_order))
        center_crud.inner_create_new_record(db, order)
        return JSONResponse(status_code=200, content={'message': 'ok'})
    except Exception as e:
        # raise e
        logger.warning("create new order error={}".format(str(e)))
        return JSONResponse(status_code=400, content={'error': str(e)})


@router.post("/order/inner_update", description="update one order by dict")
async def inner_update_order(update_order: center_schemas.InnerUpdateOrder, db: Session = Depends(get_db)):
    try:
        update_order = update_order.dict()
        if update_order.get('drinks'):
            drinks = update_order.pop('drinks')
            order_number = update_order.pop('order_number')
            center_crud.update_order_number(db, order_number, update_order)  # 先更新order表
            if drinks:
                for drink in drinks:
                    task_uuid = drink.pop('task_uuid')
                    center_crud.update_task_uuid(db, task_uuid, drink)
        # return center_crud.set_task_completed(db, task_uuid)
    except Exception as e:
        logger.warning("inner_update_order failed, error={}".format(str(e)))
        return JSONResponse(status_code=400, content={'error': str(e)})


@router.get("/order/{number}", description="return order info of one order number")
def get_one_order(number: str, inner: Literal[('0', '1')] = '0', db: Session = Depends(get_db)):
    try:
        return center_crud.get_one_order(db, number, int(inner))
    except Exception as e:
        logger.warning("get_one_order failed, error={}".format(str(e)))
        return JSONResponse(status_code=400, content={'error': str(e)})


@router.get("/{order_number}/status", description="return order status")
def get_order_status(order_number, db: Session = Depends(get_db)):
    try:
        return center_crud.get_order_status(db, order_number)
    except Exception as e:
        logger.warning("get order status failed, error={}".format(str(e)))
        return JSONResponse(status_code=400, content={'error': str(e)})


@router.get("/order", description="return all task status")
def get_order_list(local_offset=Query(None), start_time=Query(None), end_time=Query(None),
                   order_number=Query(None), db: Session = Depends(get_db)):
    try:
        if start_time:
            start_time = utils.local_to_utc(local_offset=int(local_offset),
                                            origin_time=start_time.strip() + ' 00:00:00')
        if end_time:
            end_time = utils.local_to_utc(local_offset=int(local_offset), origin_time=end_time.strip() + ' 23:59:59')
        return center_crud.get_all_order_tasks_by_time(db, start_time, end_time, order_number)
    except Exception as e:
        logger.warning("get order status failed, error={}".format(str(e)))
        return JSONResponse(status_code=400, content={'error': str(e)})


# task

@router.post("/order/task/status", description="update task status")
async def set_one_task_complete(task_uuid: UUID, status, db: Session = Depends(get_db)):
    try:
        return center_crud.update_task_status(db, task_uuid, status)
    except Exception as e:
        logger.warning("get order status failed, error={}".format(str(e)))
        return JSONResponse(status_code=400, content={'error': str(e)})


@router.post("/order/task/print", description="printer one task label")
async def print_label(task_uuid: UUID, obj: Center = Depends(get_center_obj), db: Session = Depends(get_db)):
    try:
        task = center_crud.get_task_uuid_instance(db, task_uuid)
        if task:
            label_msg = center_crud.generate_label_msg(task)
            obj.printer.print_label(label_msg)
    except Exception as e:
        logger.warning("get order status failed, error={}".format(str(e)))
        return JSONResponse(status_code=400, content={'error': str(e)})


@router.get('/temp/order', description='return all paid status')
def get_order_temp(local_offset=Query(None), start_time=Query(None), end_time=Query(None), order_number=Query(None),
                   obj: Center = Depends(get_center_obj), db: Session = Depends(get_db)):
    try:
        logger.debug('get_order_temp ')
        if start_time:
            start_time = utils.local_to_utc(local_offset=int(local_offset),
                                            origin_time=start_time.strip() + ' 00:00:00')
        if end_time:
            end_time = utils.local_to_utc(local_offset=int(local_offset),
                                          origin_time=end_time.strip() + ' 23:59:59')
        result = {}
        data = center_crud.get_all_paid_tasks_by_time(db, start_time, end_time, order_number)
        result['data'] = data
        return result
    except Exception as e:
        logger.warning('get order status failed, error={}'.format(str(e)))
        return JSONResponse(status_code=400, content={'error': str(e)})


@router.post("/order/task/status", description="update task status")
async def set_one_task_complete(task_uuid: UUID, status, obj: Center = Depends(get_center_obj), db: Session = Depends(get_db)):
    try:
        return center_crud.update_task_status(db, task_uuid, status)
    except Exception as e:
        logger.warning("get order status failed, error={}".format(str(e)))
        return JSONResponse(status_code=400, content={'error': str(e)})


@router.get("/order/task/frequent", description="return most frequest task by param")
async def set_one_task_complete(param: str, db: Session = Depends(get_db)):
    try:
        data = center_crud.get_frequent_tasks(db, param)
        result = dict(count=len(data), data=data)
        return result
    except Exception as e:
        logger.warning("get order status failed, error={}".format(str(e)))
        return JSONResponse(status_code=400, content={'error': str(e)})


@router.post("/service/restart", description="restart process in adam container")
async def restart_service(service: SUPPORT_SERVICE):
    try:
        cmd = 'supervisorctl restart {}'.format(service)
        utils.get_execute_cmd_result(cmd)
    except Exception as e:
        logger.warning("get order status failed, error={}".format(str(e)))
        return JSONResponse(status_code=400, content={'error': str(e)})


@router.get("/file/download", description="")
def download(path):
    logger.info('download')
    if os.path.exists(path):
        return FileResponse(path, filename='voice.mp3')
    return FileResponse('/richtech/resource/audio/voices/generate_failed1.mp3', filename='voice.mp3')


@router.get("/network")
async def network_status(obj: Center = Depends(get_center_obj)):
    try:
        network_normal = obj.get_order_thread.network
        if network_normal:
            return {'network_status': 'ok'}
        else:
            return {'network_status': 'not ok'}

    except Exception as e:
        logger.warning("get network status failed, error={}".format(str(e)))
        return JSONResponse(status_code=400, content={'error': str(e)})


@router.get("/setting", description="")
def get_constant_settings(db: Session = Depends(get_db)):
    constants = center_crud.get_constant_setting(db)
    result = {}
    if constants:
        for constant in constants:
            result[constant.name] = constant.param
    return result

@router.get("/setting/milk", description="")
def get_milk_clean_flag(obj: Center = Depends(get_center_obj)):
    # return {'clean_flag': obj.fresh_thread.clean_flag, 'milk_settings': obj.fresh_thread.milk_settings}
    return {'result': obj.fresh_thread.clean_flag}

@router.post("/setting/milk", description="")
def update_constant_settings(material_name, ignore=None, interval=None, clean_time=None, obj: Center = Depends(get_center_obj), db: Session = Depends(get_db)):
    constants = center_crud.get_constant_setting(db, name=material_name)
    if constants:
        milk_setting = copy.deepcopy(constants[0].param)
        if interval is not None:
            milk_setting['interval'] = int(interval)
            obj.fresh_thread.refresh_settings(material_name, interval=interval)
        if ignore is not None:
            milk_setting['ignore'] = int(ignore)
            obj.fresh_thread.refresh_settings(material_name, ignore=ignore)
        if clean_time is not None:
            milk_setting['clean_time'] = int(clean_time)
            obj.fresh_thread.refresh_settings(material_name, clean_time=clean_time)

        constants[0].param = milk_setting
        # db.commit()
        return 'ok'
    else:
        return JSONResponse(status_code=400, content={'err': 'no milk settings'})


@router.post("/setting/milk/last_time", description="")
def update_last_milk_time(material_names: list, obj: Center = Depends(get_center_obj)):
    obj.fresh_thread.update_last_time(material_names)
    return 'ok'
