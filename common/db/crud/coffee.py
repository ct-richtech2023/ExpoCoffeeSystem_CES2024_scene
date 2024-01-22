import json
import os
import uuid
import string
from typing import List

from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from common.define import TaskStatus, AudioConstant, audio_dir
from common.db.tables import center as center_table
from common.db.tables import coffee as coffee_table
from common.db.tables import adam as adam_table
from common.schemas import coffee as coffee_schema
from common.myerror import DBError
from common.define import Constant
from common.db.database import MySuperContextManager
import random


def cancel_drink_by_task_uuid(db, task_uuid):
    if task_uuid:
        record = db.query(coffee_table.Coffee).filter(coffee_table.Coffee.task_uuid == task_uuid).first()
        if record:
            record.status = TaskStatus.canceled
            db.add(record)
            logger.warning('set task_uuid={} status {} -> {}'.format(record.task_uuid, TaskStatus.waiting, TaskStatus.canceled))


def add_cleaning_history(db, cleaning_dict: dict, cleaning_method: int):
    # cleaning_method   1:Automatic; 2:Manual
    if cleaning_method:
        for key, value in cleaning_dict.items():
            history = coffee_table.AddCleaningHistory(**{"name": key, "cleaning_method": cleaning_method,
                                                         "timelength": value})
            db.add(history)


def update_detect_by_name(db, name, status=None, task_uuid=None):
    if record := db.query(coffee_table.Detect).filter(coffee_table.Detect.name == name).first():
        record.status = status
        if task_uuid:
            record.detail = task_uuid
        db.add(record)
        # logger.info(f'update name={name} status={status} detail={task_uuid}')


def get_detect_all_data(db, name=None):
    record_list = []
    if name:
        if records := db.query(coffee_table.Detect).filter(coffee_table.Detect.name.like(f'%{name}%')).order_by(coffee_table.Detect.id.asc()).all():
            for record in records:
                record_list.append(record.to_dict())
    else:
        if records := db.query(coffee_table.Detect).order_by(coffee_table.Detect.id.asc()).all():
            for record in records:
                record_list.append(record.to_dict())
    return record_list


def get_coffee_by_task_uuid(db, task_uuid):
    if record := db.query(coffee_table.Coffee).filter(coffee_table.Coffee.task_uuid == task_uuid).first():
        return record.to_dict()
    else:
        return {}


# Coffee
def get_task_uuid_status(db, task_uuid):
    if record := db.query(coffee_table.Coffee).filter(coffee_table.Coffee.task_uuid == task_uuid).first():
        return record.status


def add_new_coffee_task(db, value: dict):
    record = coffee_table.Coffee(**value)
    db.add(record)
    logger.info('add_new_coffee_task task={}'.format(value))


def delete_coffee_task(task_uuid):
    with MySuperContextManager() as db:
        if record := db.query(coffee_table.Coffee).filter(coffee_table.Coffee.task_uuid == task_uuid).first():
            db.delete(record)


def get_one_waiting_record(task_uuid=None) -> coffee_schema.CoffeeRecord:
    with MySuperContextManager() as db:
        if task_uuid:
            if record := db.query(coffee_table.Coffee).filter(coffee_table.Coffee.task_uuid == task_uuid).order_by(
                    coffee_table.Coffee.id.asc()).first():
                return coffee_schema.CoffeeRecord.from_orm(record)
        else:
            if record := db.query(coffee_table.Coffee).filter(
                    coffee_table.Coffee.status == TaskStatus.waiting).order_by(coffee_table.Coffee.create_time.asc(),
                                                                               coffee_table.Coffee.id.asc()).first():
                return coffee_schema.CoffeeRecord.from_orm(record)


def get_one_processing_record(db) -> coffee_schema.CoffeeRecord:
    if record := db.query(coffee_table.Coffee).filter(coffee_table.Coffee.status == TaskStatus.processing).order_by(
            coffee_table.Coffee.create_time.asc(),
            coffee_table.Coffee.id.asc()).first():
        return coffee_schema.CoffeeRecord.from_orm(record)


def exist_next_record(db):
    if record := db.query(coffee_table.Coffee).filter(coffee_table.Coffee.status == TaskStatus.waiting).order_by(
            coffee_table.Coffee.id.asc()).first():
        return record.task_uuid


def update_coffee_by_task_uuid(db, task_uuid, update_dict: dict):
    if record := db.query(coffee_table.Coffee).filter(coffee_table.Coffee.task_uuid == task_uuid).first():
        for key, value in update_dict.items():
            setattr(record, key, value)
        db.add(record)
        logger.info('update task_uuid={} value={}'.format(task_uuid, update_dict))


def init_all_records_device_and_status(db):
    if records := db.query(coffee_table.Coffee).filter(coffee_table.Coffee.status != TaskStatus.completed).filter(
            coffee_table.Coffee.status != TaskStatus.failed).all():
        for record in records:
            record.status = TaskStatus.waiting
            db.add(record)
            logger.warning('set task_uuid={} status {} -> {}'.format(
                record.task_uuid, TaskStatus.processing, TaskStatus.waiting))


# MaterialCurrent
def add_material(db, new_dict):
    if new_dict['display_type'] == 'tap':
        tap_status = db.query(adam_table.TapStatus).filter_by(material_name=new_dict['name']).first()
        if not tap_status:
            tap = adam_table.TapStatus(**{"material_name": new_dict['name'], "status": 0})
            db.add(tap)
        machineConfig = db.query(coffee_table.MachineConfig).filter_by(name=new_dict['name']).first()
        uppercase_alphabet = string.ascii_uppercase
        arduino_write = ""
        if new_dict['sort'] < 9:
            arduino_write = uppercase_alphabet[new_dict['sort'] - 1]
        else:
            arduino_write = uppercase_alphabet[new_dict['sort']]
        if not machineConfig:
            machineDict = {
                "name": new_dict['name'],
                "machine": new_dict['display_type'],
                "num": new_dict['sort'],
                "arduino_write": arduino_write,
                "delay_time": 1,
                "type": "time"
            }
            machine = coffee_table.MachineConfig(**machineDict)
            db.add(machine)
        ConstantSettingName = db.query(center_table.ConstantSetting).filter_by(name=new_dict['name']).first()
        if not ConstantSettingName:
            constantSettingDict = {
                "name": new_dict['name'],
                "param": {"interval": 30, "ignore": 1, "clean_time": 5}
            }
            constantSetting = center_table.ConstantSetting(**constantSettingDict)
            db.add(constantSetting)

    new_dict.pop('id')
    material = coffee_table.MaterialCurrent(**new_dict)
    old_material = get_material(db, name=material.name)
    if old_material:
        raise DBError('add error, material={} has already exist'.format(material.name))
    else:
        db.add(material)

    db.commit()
    logger.info('add_new_material, dict={}'.format(new_dict))


def get_material(db, name=None, in_use=None, material_id=None) -> List[coffee_table.MaterialCurrent]:
    conditions = []
    if name:
        conditions.append(coffee_table.MaterialCurrent.name == name)
    if in_use is not None:
        conditions.append(coffee_table.MaterialCurrent.in_use == in_use)
    if material_id is not None:
        conditions.append(coffee_table.MaterialCurrent.id == material_id)
    materials = db.query(coffee_table.MaterialCurrent).filter(*conditions).order_by(
        coffee_table.MaterialCurrent.id.asc()).all()
    return materials


def get_milk_material(db, in_use=1) -> dict:
    conditions = []
    conditions.append(coffee_table.MaterialCurrent.type._in("Plant-based milk", "Milk"))
    if in_use is not None:
        conditions.append(coffee_table.MaterialCurrent.in_use == in_use)
    materials = db.query(coffee_table.MaterialCurrent).filter(*conditions).order_by(
        coffee_table.MaterialCurrent.id.asc()).all()
    milk_dict = {}
    for material in materials:
        milk_dict[material.type] = material.to_dict()
    return milk_dict


def use_material(db, name, quantity) -> coffee_table.MaterialCurrent:
    material = db.query(coffee_table.MaterialCurrent).filter_by(name=name, in_use=Constant.InUse.in_use).first()
    if material:
        material.count += 1
        material.left = round(material.left - quantity * material.batch, 2)
        material.left = 0 if material.left < 0 else material.left
        return material
    else:
        raise DBError(' there is no material named {} in use'.format(name))


def update_material_by_id(db, update_dict):
    material = db.query(coffee_table.MaterialCurrent).filter(
        coffee_table.MaterialCurrent.id == update_dict['id']).first()
    if material:
        compositions = db.query(coffee_table.Composition).filter(
            coffee_table.Composition.material == material.name).all()
        if compositions:
            for composition in compositions:
                composition.material = update_dict['name']
        machine = db.query(coffee_table.MachineConfig).filter(
            coffee_table.MachineConfig.name == material.name).first()
        if machine:
            machine.name = update_dict['name']
        tapStatus = db.query(adam_table.TapStatus).filter(
            adam_table.TapStatus.material_name == material.name).first()
        if tapStatus:
            tapStatus.material_name = update_dict['name']
        constantSetting = db.query(center_table.ConstantSetting).filter(
            center_table.ConstantSetting.name == material.name).first()
        if constantSetting:
            constantSetting.name = update_dict['name']
        for k, v in update_dict.items():
            if v != None and k != 'id' and k != 'img':
                setattr(material, k, v)


def update_material(db, name, update_dict):
    material = db.query(coffee_table.MaterialCurrent).filter(coffee_table.MaterialCurrent.name == name).first()
    if material:
        for k, v in update_dict.items():
            if v != None:
                setattr(material, k, v)
    else:
        raise DBError('there are no material named {}'.format(name))


def reset_material(db, names: List):
    for name in names:
        if name == 'green_tea_syrup':
            name = 'cold_water'
        material = db.query(coffee_table.MaterialCurrent).filter(coffee_table.MaterialCurrent.name == name).first()
        if material:
            history = coffee_table.AddMaterialHistory(name=material.name, before_add=material.left,
                                                      count=material.count,
                                                      add=round(material.capacity - material.left))
            db.add(history)
            material.left = material.capacity
            material.count = 0
        else:
            raise DBError('there are no material named {}'.format(material))


def update_material_volume(db, name, volume):
    if record := db.query(coffee_table.MaterialCurrent).filter(coffee_table.MaterialCurrent.name == name).first():
        record.count += 1
        record.left -= volume
        record.left = 0 if record.left < 0 else record.left
        db.add(record)
        return record.left


def get_material_capacity_left(db) -> List[coffee_schema.MaterialCurrentRecord]:
    if records := db.query(coffee_table.MaterialCurrent).all():
        records = [coffee_schema.MaterialCurrentRecord.from_orm(record) for record in records]
        return records


def reset_material_capacity(db, name):
    if record := db.query(coffee_table.MaterialCurrent).filter(coffee_table.MaterialCurrent.name == name).first():
        orm_record = coffee_schema.MaterialCurrentRecord.from_orm(record)
        history_record = coffee_table.AddMaterialHistory(**orm_record.dict())
        db.add(history_record)
        record.count = 0
        record.left = record.capacity
        db.add(record)


# init
def init_data(db, file):
    logger.warning('init data ..............')
    with open(file, 'r') as f:
        for line in f.readlines():
            if not line.startswith('--') and line != ('\n'):
                try:
                    db.execute(line)
                    db.commit()
                except IntegrityError:
                    db.rollback()


def init_service(db):
    logger.warning('start service, clean queue msg')
    db.query(coffee_table.Coffee).filter(
        coffee_table.Coffee.status.in_([TaskStatus.waiting, TaskStatus.processing])).delete()
    db.commit()


# Formula
def add_formula(db, new_dict):
    """
    new_dict:  {name: str, type: str, in_use: int, composition: dict}
    """
    composition_dict = new_dict.pop('composition')
    formula = coffee_table.Formula(**new_dict)
    old_formula = get_formula(db, formula.name, formula.cup)
    if old_formula:
        raise DBError('add error, formula={} has already exist'.format(formula.name))
    else:
        cup_obj = get_material(db, formula.cup, Constant.InUse.in_use)
        if not cup_obj:
            db.rollback()
            raise DBError('add error, there are no cup named {}'.format(formula.cup))
        db.add(formula)
        for material, count in composition_dict.items():
            material_obj = get_material(db, material)
            if material_obj:
                old_composition = db.query(coffee_table.Composition).filter_by(formula=formula.name,
                                                                               cup=formula.cup,
                                                                               material=material).first()
                if old_composition:
                    db.rollback()
                    raise DBError(
                        'composition formula={}, cup={}, material={} has already exist, please update/delete it'.format(
                            formula.name, formula.cup, material))

                composition = coffee_table.Composition(formula=formula.name, cup=formula.cup,
                                                       material=material, count=count)
                db.add(composition)
            else:
                db.rollback()
                raise DBError('add error, there no material named {}'.format(material))
        db.commit()
    logger.info('add_formula, dict={}'.format(new_dict))


def insert_menu_with_composition(db, menu_data: dict):
    # 提取菜单属性
    menu_attributes = {
        "name": menu_data["name"],
        "cup": menu_data["cup"],
        "with_ice": menu_data["with_ice"],
        "with_foam": menu_data["foam_type"] if menu_data["with_foam"] != 0 else menu_data["with_foam"],
        "with_milk": menu_data["with_milk"],
        "choose_beans": menu_data["choose_beans"],
        "type": menu_data["type"],
        "in_use": menu_data["in_use"],
        "img": menu_data["img"]
    }

    cup_composition = {
        "formula": menu_data["name"],
        "cup": menu_data["cup"],
        "material": menu_data["type"] + "_cup",
        "count": 1,
        "extra": ""
    }

    # 创建菜单记录并插入到formula表中
    old_formula = get_formula(db, menu_data["name"], menu_data["cup"])
    if old_formula:
        if old_formula[0].in_use == -1:
            old_formula[0].in_use = 1
            old_formula[0].img = menu_data["img"]
        else:
            raise DBError('add error, formula={} has already exist'.format(menu_data["name"]))
    else:
        old_formula = get_formula_ilike_name(db, menu_data["name"])
        if old_formula:
            raise DBError('add error, formula={} has already exist'.format(menu_data["name"]))
        else:
            menu = coffee_table.Formula(**menu_attributes)
            db.add(menu)

    if menu_data["coffee_machine"] == 1:
        coffee_material = {
            "name": menu_data["name"],
            "img": "",
            "display": menu_data["name"],
            "capacity": 5000,
            "alarm": 500,
            "left": 5000,
            "count": 0,
            "unit": "ml",
            "batch": 0,
            "sort": None,
            "display_type": "",
            "type": "coffee",
            "machine": "coffee_machine",
            "extra": "",
            "in_use": 1
        }
        material = coffee_table.MaterialCurrent(**coffee_material)
        db.add(material)

    # 提取菜单配方数据
    composition_data = menu_data["composition"]
    # if menu_data["coffee_machine"] == 1:
    #     composition_data.append(coffee_composition)
    composition_data.append(cup_composition)
    if composition_data:
        # 创建配方记录并插入到composition表中
        for composition in composition_data:
            try:
                extra = ""
                if composition["extra"]:
                    extra = json.loads(composition["extra"])
            except Exception as e:
                raise DBError(f'json.loads(composition["extra"]) {e} and {composition["extra"]}')
            composition_attributes = {
                "formula": menu_data["name"],
                "cup": menu_data["cup"],
                "material": composition["material"],
                "count": composition["count"],
                "extra": composition["extra"] if extra else None
                # "extra": json.dumps(composition["extra"]) if composition["extra"] else None
            }
            composition_record = coffee_table.Composition(**composition_attributes)
            db.add(composition_record)

            if composition["material"] == "foam":
                material_foam = db.query(coffee_table.MaterialCurrent).filter(
                    coffee_table.MaterialCurrent.name == "foam").first()
                if material_foam is None:
                    foam_material = {
                        "name": "foam",
                        "img": "",
                        "display": "foam",
                        "capacity": 9999,
                        "alarm": 0,
                        "left": 9999,
                        "count": 0,
                        "unit": "ml",
                        "batch": 0,
                        "sort": None,
                        "display_type": "",
                        "type": "endless",
                        "machine": "foam_machine",
                        "extra": "",
                        "in_use": 1
                    }
                    foam_materialCurrent = coffee_table.MaterialCurrent(**foam_material)
                    db.add(foam_materialCurrent)
                    # db.commit()
            if extra:
                if not extra.get("foam_composition", {}):
                    first_key = list(extra.keys())[0]
                    first_value = extra[first_key]
                foam_coffee = extra.get("foam_composition", {}).get("foam_coffee", {})
                if foam_coffee:
                    espresso = db.query(coffee_table.Espresso).filter(
                        coffee_table.Espresso.formula == "foam_coffee").first()
                    if espresso:
                        espresso.drink_type = foam_coffee - 1
                    else:
                        espresso_dict = {}
                        espresso_dict["drink_type"] = foam_coffee - 1
                        espresso_dict["formula"] = "foam_coffee"
                        espresso = coffee_table.Espresso(**espresso_dict)
                        db.add(espresso)

                    material_foam_coffee = db.query(coffee_table.MaterialCurrent).filter(
                        coffee_table.MaterialCurrent.name == "foam_coffee").first()
                    if material_foam_coffee is None:
                        foam_coffee_material = {
                            "name": "foam_coffee",
                            "img": "",
                            "display": "foam_coffee",
                            "capacity": 9999,
                            "alarm": 0,
                            "left": 9999,
                            "count": 0,
                            "unit": "ml",
                            "batch": 0,
                            "sort": None,
                            "display_type": "",
                            "type": "coffee",
                            "machine": "coffee_machine",
                            "extra": "",
                            "in_use": 1
                        }
                        foam_coffee_materialCurrent = coffee_table.MaterialCurrent(**foam_coffee_material)
                        db.add(foam_coffee_materialCurrent)

    espresso = db.query(coffee_table.Espresso).filter(coffee_table.Espresso.formula == menu_data["name"]).first()
    if espresso:
        if espresso.drink_type != first_value:
            espresso.drink_type = first_value
    else:
        espresso_dict = {}
        if menu_data["coffee_machine"] == 1:
            espresso_dict["drink_type"] = first_value - 1
            espresso_dict["formula"] = menu_data["name"]
            espresso = coffee_table.Espresso(**espresso_dict)
            db.add(espresso)

    db.commit()


def update_menu_with_composition(db, menu_data: dict):
    # 解析菜单数据
    formula_id = menu_data.get("id")
    formula_name = menu_data.get("name")
    formula_cup = menu_data.get("cup")
    composition_data = menu_data.get("composition")
    coffee_machine = menu_data.get("coffee_machine")
    formula_type = menu_data.get("type")

    if menu_data.get("with_foam") == 1:
        menu_data["with_foam"] = menu_data.get("foam_type")

    # 查询菜单
    formula = db.query(coffee_table.Formula).filter(coffee_table.Formula.id == formula_id).first()

    if not formula:
        # return None
        raise DBError('not formula')

    if formula.name != formula_name:
        old_formula = get_formula_ilike_name(db, formula_name)
        if old_formula:
            raise DBError('update error, formula={} has already exist'.format(menu_data["name"]))

    cup_composition_record = db.query(coffee_table.Composition).filter(coffee_table.Composition.formula == formula.name,
                                                                       coffee_table.Composition.material.like(
                                                                           "%_cup")).first()

    if cup_composition_record:
        cup_composition = {
            "id": cup_composition_record.id,
            "formula": formula_name,
            "cup": formula_cup,
            "material": formula_type + "_cup",
            "count": 1,
            "extra": ""
        }
    else:
        cup_composition = {
            "id": 0,
            "formula": formula_name,
            "cup": formula_cup,
            "material": formula_type + "_cup",
            "count": 1,
            "extra": ""
        }
    composition_data.append(cup_composition)

    first_value = None
    composition_id_list = []
    for composition in composition_data:
        composition_id = composition.get("id", {})
        if composition_id:
            composition_id_list.append(composition_id)
            composition["formula"] = formula_name
            composition_record = db.query(coffee_table.Composition).filter(coffee_table.Composition.id == composition_id).first()
            if composition_record:
                # 更新配方属性
                for attr, value in composition.items():
                    if attr != "id" and attr != "type":
                        setattr(composition_record, attr, value)
        else:
            composition_attributes = {
                "formula": formula_name,
                "cup": formula_cup,
                "material": composition["material"],
                "count": composition["count"],
                "extra": composition["extra"] if composition["extra"] else None
            }
            composition_record = coffee_table.Composition(**composition_attributes)
            db.add(composition_record)
        if composition.get("material") == "foam":
            extra = json.loads(composition["extra"])
            if foam_coffee := extra.get("foam_composition", {}).get("foam_coffee", {}):
                espresso = db.query(coffee_table.Espresso).filter(
                    coffee_table.Espresso.formula == "foam_coffee").first()
                if espresso:
                    espresso.drink_type = foam_coffee - 1
                else:
                    espresso_dict = {}
                    espresso_dict["drink_type"] = foam_coffee - 1
                    espresso_dict["formula"] = "foam_coffee"
                    espresso = coffee_table.Espresso(**espresso_dict)
                    db.add(espresso)

                material_foam_coffee = db.query(coffee_table.MaterialCurrent).filter(
                    coffee_table.MaterialCurrent.name == "foam_coffee").first()
                if material_foam_coffee is None:
                    foam_coffee_material = {
                        "name": "foam_coffee",
                        "img": "",
                        "display": "foam_coffee",
                        "capacity": 9999,
                        "alarm": 0,
                        "left": 9999,
                        "count": 0,
                        "unit": "ml",
                        "batch": 0,
                        "sort": None,
                        "display_type": "foam_coffee",
                        "type": "coffee",
                        "machine": "coffee_machine",
                        "extra": "",
                        "in_use": 1
                    }
                    foam_coffee_materialCurrent = coffee_table.MaterialCurrent(**foam_coffee_material)
                    db.add(foam_coffee_materialCurrent)
        if composition["extra"]:
            extra = json.loads(composition["extra"])
            if not extra.get("foam_composition", {}):
                first_key = list(extra.keys())[0]
                first_value = extra[first_key]

    if coffee_machine == 1:
        material = db.query(coffee_table.MaterialCurrent).filter(
            coffee_table.MaterialCurrent.name == formula.name).first()
        if material:
            material.name = formula_name
            material.display = formula_name
            db.add(material)
        else:
            coffee_material = {
                "name": formula_name,
                "img": "",
                "display": formula_name,
                "capacity": 5000,
                "alarm": 500,
                "left": 5000,
                "count": 0,
                "unit": "ml",
                "batch": 0,
                "sort": None,
                "display_type": "",
                "type": "coffee",
                "machine": "coffee_machine",
                "extra": "",
                "in_use": 1
            }
            material = coffee_table.MaterialCurrent(**coffee_material)
            db.add(material)

        drink_num = first_value
        espresso = db.query(coffee_table.Espresso).filter(coffee_table.Espresso.formula == formula.name).first()
        if espresso:
            espresso.formula = formula_name
            espresso.drink_type = drink_num - 1
            db.add(espresso)
        else:
            espresso_dict = {}
            espresso_dict["drink_type"] = drink_num - 1
            espresso_dict["formula"] = formula_name
            espresso = coffee_table.Espresso(**espresso_dict)
            db.add(espresso)
            db.commit()
    elif coffee_machine == 0:
        espresso = db.query(coffee_table.Espresso).filter(coffee_table.Espresso.formula == formula.name).first()
        if espresso:
            db.delete(espresso)

    composition_formulas = db.query(coffee_table.Composition).filter(
        coffee_table.Composition.formula == formula.name).all()
    for composition_formula in composition_formulas:
        if composition_formula.id not in composition_id_list:
            db.delete(composition_formula)

    # 更新菜单属性
    for attr, value in menu_data.items():
        if attr != "id" and attr != "composition" and attr != "img" and attr != "foam_type":
            setattr(formula, attr, value)


def get_all_formula(db, name=None, cup=None, in_use=None):
    conditions = []
    if name:
        conditions.append(coffee_table.Formula.name == name)
    if cup:
        conditions.append(coffee_table.Formula.cup == cup)
    if in_use is not None:
        conditions.append(coffee_table.Formula.in_use == in_use)
    formulas = db.query(coffee_table.Formula).filter(*conditions).order_by(coffee_table.Formula.id.asc()).all()
    # formula_list = []
    return_data = []
    for formula in formulas:
        formula_dict = formula.to_dict()
        formula_recipe = []

        if int(formula_dict['with_foam']) == 0:
            formula_dict['foam_type'] = 0
        else:
            formula_dict['foam_type'] = formula_dict['with_foam']
            formula_dict['with_foam'] = 1
        espresso = db.query(coffee_table.Espresso).filter(coffee_table.Espresso.formula == formula.name).first()
        if espresso:
            formula_dict['coffee_machine'] = 1
            formula_dict['drink_num'] = espresso.drink_type + 1
        else:
            formula_dict['coffee_machine'] = 0
            formula_dict['drink_num'] = 0

        # 获取菜单配方
        compositions = db.query(coffee_table.Composition).filter(
            coffee_table.Composition.formula == formula.name,
            coffee_table.Composition.cup == formula.cup
        ).all()
        for composition in compositions:
            # extra = ""
            # if composition.extra:
            #     foam_composition_list = []
            #     extra = json.loads(composition.extra)
            #     for key, value in extra['foam_composition'].items():
            #         foam_composition_list.append({key: value})
            #     extra.pop('foam_composition')
            #     extra['foam_composition'] = foam_composition_list
            recipe = {
                "id": composition.id,  # 添加id字段
                "type": "",
                "material": composition.material,
                "count": composition.count,
                "extra": json.loads(composition.extra) if composition.extra else ""
                # "extra": extra
            }
            material_display = db.query(coffee_table.MaterialCurrent).filter(
                coffee_table.MaterialCurrent.name == composition.material).first()
            if material_display:
                recipe["type"] = material_display.display_type
            formula_recipe.append(recipe)
        formula_dict["composition"] = formula_recipe
        return_data.append(formula_dict)
    return return_data


def get_formula(db, name=None, cup=None, in_use=None, formula_id=None) -> List[coffee_table.Formula]:
    conditions = []
    if formula_id:
        conditions.append(coffee_table.Formula.id == formula_id)
    if name:
        conditions.append(coffee_table.Formula.name == name)
    if cup:
        conditions.append(coffee_table.Formula.cup == cup)
    if in_use:
        conditions.append(coffee_table.Formula.in_use == in_use)
    formulas = db.query(coffee_table.Formula).filter(*conditions).all()
    return formulas


def get_formula_ilike_name(db, name=None) -> List[coffee_table.Formula]:
    formula = db.query(coffee_table.Formula).filter(coffee_table.Formula.name.ilike(name)).first()
    return formula


def update_formula(db, name, cup, update_dict):
    formula = db.query(coffee_table.Formula).filter_by(name=name, cup=cup).first()
    if formula:
        for k, v in update_dict.items():
            if v != None:
                setattr(formula, k, v)
        # db.commit()
    else:
        raise DBError('there are no formula named {} with cup={}'.format(name, cup))


# def delete_formula(db, name, cup):
#     try:
#         db.query(coffee_table.Formula).filter_by(name=name, cup=cup).delete()
#         db.query(coffee_table.Composition).filter_by(formula=name, cup=cup).delete()
#         db.commit()
#         return 1, 'success'
#     except DBError as e:
#         db.rollback()
#         raise DBError(e)


def delete_formula_in_use(db, formula_id: int):
    # 查询菜单
    formula = db.query(coffee_table.Formula).filter(coffee_table.Formula.id == formula_id).first()
    if not formula:
        return False
    # 更新in_use字段
    formula.in_use = -1

    compositions = db.query(coffee_table.Composition).filter(coffee_table.Composition.formula == formula.name).all()
    if compositions:
        for composition in compositions:
            db.delete(composition)

    espressos = db.query(coffee_table.Espresso).filter(coffee_table.Espresso.formula == formula.name).all()
    if espressos:
        for espresso in espressos:
            db.delete(espresso)

    materials = db.query(coffee_table.MaterialCurrent).filter(coffee_table.MaterialCurrent.name == formula.name).all()
    if materials:
        for material in materials:
            db.delete(material)


# Composition
def add_composition(db, formula_name, cup, composition_list):
    """
    material_list: [{'name':'milk', 'count':80}]
    """
    formula = get_formula(db, formula_name)
    if not formula:
        raise DBError('no formula names={}, please check again'.format(formula_name))
    for material in composition_list:
        material_name = material.get('name')
        material_obj = get_material(db, name=material_name)
        if not material_obj:
            db.rollback()
            raise DBError('no material names={}, please check again'.format(material_name))
        old_composition = db.query(coffee_table.Composition).filter_by(formula=formula_name,
                                                                       cup=cup,
                                                                       material=material_name).first()
        if old_composition:
            db.rollback()
            raise DBError(
                'composition formula={}, material={} has already exist, please update/delete it'.format(formula_name,
                                                                                                        material_name))
        composition = coffee_table.Composition(formula=formula_name, material=material_name, cup=cup,
                                               count=material.get('count'))
        db.add(composition)
    db.commit()
    logger.info('add_composition, formula={}, composition{}'.format(formula_name, composition_list))


def get_composition_by_formula(db, formula, cup, formula_in_use=None) -> dict:
    """
    return: {'material': {'count': 100, 'left':100, 'type': 'base_milktea', 'machine': 'tap_l', 'in_use': 1}}
    """
    formula_obj = get_formula(db, formula, cup, formula_in_use)
    if not formula_obj:
        return {}
    compositions = db.query(coffee_table.Composition).filter_by(formula=formula, cup=cup).all()
    return_data = {}
    for composition in compositions:
        materials = get_material(db, composition.material)
        logger.info('search {}, result={}'.format(composition.material, materials))
        if materials:
            material = materials[0]
            material_data = dict(count=composition.count, left=material.left, type=material.type,
                                 machine=material.machine, in_use=material.in_use)
            if material.machine == 'foam_machine':
                material_data['extra'] = json.loads(composition.extra)
            if material.machine == 'coffee_machine':
                material_data['extra'] = json.loads(composition.extra)
                material_data['coffee_make'] = get_espresso_by_formula(db, formula)
            return_data[composition.material] = material_data
    return_data["milk_dict"] = get_milk_material(db)
    return return_data


def update_composition_count(db, formula, cup, material, count):
    composition = db.query(coffee_table.Composition).filter_by(formula=formula, cup=cup, material=material).first()
    if composition:
        composition.count = count
        # db.commit()
    else:
        raise ('there are no composition of formula={}, cup={}, material={}'.format(formula, cup, material))


def delete_composition(db, formula, material=None):
    if material:
        db.query(coffee_table.Composition).filter_by(formula=formula, material=material).delete()
    else:
        db.query(coffee_table.Composition).filter_by(formula=formula).delete()
    db.commit()


# Machine_Config
def get_machine_config(db, name=None, machine=None) -> List[coffee_table.MachineConfig]:
    conditions = []
    if name:
        conditions.append(coffee_table.MachineConfig.name == name)
    if machine:
        conditions.append(coffee_table.MachineConfig.machine == machine)
    configs = db.query(coffee_table.MachineConfig).filter(*conditions).all()
    return configs


# Espresso
def get_espresso_by_formula(db, formula):
    espresso = db.query(coffee_table.Espresso).filter_by(formula=formula).first()
    if espresso:
        return espresso.to_coffee_dict()


# SpeechText
def choose_one_speech_text(db, code: str):
    if code in AudioConstant.TextCode.LOCAL_CODE.keys():
        file_name = '{}{}.mp3'.format(code, random.randint(1, AudioConstant.TextCode.LOCAL_CODE.get(code)))
        path = os.path.join(audio_dir, 'voices', file_name)
        if os.path.exists(path):
            return path

    speech_texts = db.query(coffee_table.SpeechText).filter_by(code=code).all()
    if speech_texts:
        return random.choice(speech_texts).text
    else:
        return ''


def get_machine_states_by_id(db, return_id=None):
    conditions = []
    if return_id:
        conditions.append(coffee_table.MachineStates.return_id == return_id)
    machine_states_list = db.query(coffee_table.MachineStates).filter(*conditions).all()
    result = []
    for machine_states in machine_states_list:
        result.append(machine_states.to_dict())
    return result


def get_report_uuids(db):
    result = []
    records = db.query(coffee_table.Report).filter(coffee_table.Report.report == 0).all()
    for record in records:
        result.append(record.task_uuid)
    return result


def get_one_report_uuids():
    with MySuperContextManager() as db:
        record = db.query(coffee_table.Report).filter(coffee_table.Report.report == 0).order_by(
            coffee_table.Report.id.asc()).first()
        if record:
            return record.task_uuid
        return None


def add_report(db, task_uuid):
    record = db.query(coffee_table.Report).filter(coffee_table.Report.task_uuid == task_uuid).first()
    if record:
        record.report = 0
    else:
        record = coffee_table.Report(task_uuid=task_uuid, report=0)
    db.add(record)
    db.commit()
    return record


def done_report(task_uuid):
    with MySuperContextManager() as db:
        record = db.query(coffee_table.Report).filter(coffee_table.Report.task_uuid == task_uuid).first()
        if record:
            record.report = 1
        else:
            record = coffee_table.Report(task_uuid=task_uuid, report=1)
        db.add(record)
        return record


# @rollback_on_exception
def get_one_cleaning_history(db) -> coffee_table.AddCleaningHistory:
    record = db.query(coffee_table.AddCleaningHistory).filter(coffee_table.AddCleaningHistory.flag == 0).order_by(
        coffee_table.AddCleaningHistory.id.asc()).first()
    if record:
        return record
    return None


# @rollback_on_exception
def update_cleaning_history(db, id):
    record = db.query(coffee_table.AddCleaningHistory).filter(coffee_table.AddCleaningHistory.id == id,
                                                              coffee_table.AddCleaningHistory.flag == 0).first()
    if record:
        record.flag = 1
        db.add(record)


def init_detect(db):
    records_to_update = db.query(coffee_table.Detect).filter(coffee_table.Detect.name.like('%cup_stand%')).all()
    for record in records_to_update:
        record.status = 0
