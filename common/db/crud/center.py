import datetime
import uuid
from typing import List

from loguru import logger

from sqlalchemy import or_, func
from common.schemas import center as center_schema
from common.db.tables import center as center_table
from common.define import OrderStatus, TaskStatus, AudioConstant
from common.utils import format_option
from common.api import AudioInterface, CoffeeInterface
from common.db.database import MySuperContextManager

from common.myerror import DBError

task_table = center_table.Task
order_table = center_table.Order
user_table = center_table.User
task_table_name = task_table.__tablename__
order_table_name = order_table.__tablename__


def cancel_order_by_order_number(db, order_number):
    if order_number:
        record = db.query(order_table).filter(order_table.order_number == order_number).first()
        if record:
            record.status = TaskStatus.canceled
            db.add(record)
            logger.info(
                'set order_number={} status {} -> {}'.format(record.order_number, TaskStatus.waiting, TaskStatus.canceled))


def cancel_task_by_task_uuid(db, task_uuid):
    if task_uuid:
        record = db.query(task_table).filter(task_table.task_uuid == task_uuid).first()
        if record:
            record.status = TaskStatus.canceled
            db.add(record)
            logger.info(
                'set task_uuid={} status {} -> {}'.format(record.task_uuid, TaskStatus.waiting, TaskStatus.canceled))


def get_order_by_task_uuid(db, task_uuid):
    if order_number := db.query(task_table).filter(task_table.task_uuid == task_uuid).first():
        if record := db.query(order_table).filter(order_table.order_number == order_number.order_number).first():
            return record.to_dict()
    return {}


def delete_test_order():
    with MySuperContextManager() as db:
        if order_record := db.query(order_table).filter(order_table.order_number.like("TEST%")).first():
            db.delete(order_record)
        if task_record := db.query(task_table).filter(task_table.order_number.like("TEST%")).first():
            db.delete(task_record)


def create_paid_order_from_pad(db, order: center_schema.PadOrder):
    if check_order_is_exist(db, order.order_number):
        raise Exception('already exist order_number={}'.format(order.order_number))
    proces_order = db.query(order_table).filter(order_table.status.in_([OrderStatus.processing,
                                                                        OrderStatus.paid,
                                                                        OrderStatus.waiting])).order_by(order_table.create_time.asc()).first()
    if proces_order:
        print('exist process order', proces_order.id)
        create_time = proces_order.create_time
    else:
        print('no process order')
        create_time = datetime.datetime.now()

    new_order_dict = order.dict()
    if order_number := new_order_dict.get("order_number", ""):
        if not (order_number.startswith("P_") or order_number.startswith("TEST_")):
            new_order_dict["order_number"] = "POS_" + order_number
    new_order_dict['create_time'] = create_time
    db.add(order_table.implement(new_order_dict))
    for i, drink in enumerate(order.drinks):
        formula = drink.name
        if order_number.startswith("TEST_"):
            task_uuid = '923e314f-1723-3b8c-9f23-f93903455263'
        else:
            task_uuid = uuid.uuid3(uuid.NAMESPACE_DNS, "{} {} {}".format(order.order_number, i, formula))
        # if milk := drink.milk:
        #     if milk.lower() == "Plant-based milk".lower():
        #         milk = "plant_milk"
        #     elif milk.lower() == "Milk".lower():
        #         milk = "fresh_dairy"
        if choose_beans := drink.choose_beans:
            if choose_beans.lower() == "Medium roast coffee beans".lower():
                choose_beans = "medium_roast"
            elif choose_beans.lower() == "High roast coffee beans".lower():
                choose_beans = "high_roast"
        # order_number = order.order_number
        # if not order_number.startswith("P_"):
        #     order_number = "POS_"+order_number
        # # 如果字符串不以 "P_" 开头
        task = {
            'order_number': new_order_dict["order_number"],
            'receipt_number': drink.receipt_number,
            'reference_id': drink.reference_id,
            'task_uuid': task_uuid,
            'formula': formula,
            'cup': format_option(drink.option.get('cup', 'Med')),
            'sweetness': int(drink.option.get('sweetness', 100)),
            'ice': format_option(drink.option.get('ice', 'light')),
            'milk': drink.milk,
            'beans': choose_beans,
            'discount': drink.discount,
            'unit_money': 0,
            'refund': drink.refund,
            'status': OrderStatus.completed if order_number.startswith("TEST_") else OrderStatus.paid,
            'create_time': create_time
        }

        task_value = task_table(**task)
        db.add(task_value)
        # old_tased = False
        #     for ks = db.query(task_table).filter(task_table.receipt_number == task_value.receipt_number).all()
        #         # if old_tasks:
        #         #     failold_task in old_tasks:
        #         if old_task.status == TaskStatus.failed:
        #             failed = True
        #             old_task.status = TaskStatus.paid
        #             old_order = db.query(order_table).filter(order_table.order_number == old_task.order_number).first()
        #             old_order.status = TaskStatus.paid
        #             db.add(old_task)
        #             db.add(old_order)
        #     if not failed:
        #         AudioInterface.gtts('there are no failed {} with receipt number  {}'.format(task_value.formula, '-'.join(list(task_value.receipt_number))))
        # else:
        #     db.add(task_value)

    db.commit()


def create_new_record_from_pad(db, order: center_schema.Order):
    if check_order_is_exist(db, order.order_number):
        raise Exception('already exist order_number={}'.format(order.order_number))

    db.add(order_table.implement(order.dict()))
    for i, drink in enumerate(order.drinks):
        formula = drink.name
        task_uuid = uuid.uuid3(uuid.NAMESPACE_DNS, "{} {} {}".format(order.order_number, i, formula))
        task = {
            'order_number': order.order_number,
            'task_uuid': task_uuid,
            'formula': formula,
            'cup': drink.cup,
            'sweetness': drink.sweetness,
            'ice': drink.ice,
            'milk': drink.milk
        }
        task_value = task_table(**task)
        db.add(task_value)

    db.commit()


def get_waiting_tasks_by_order_number(db, order_number) -> dict:
    """查询订单下的任务"""
    order_record = db.query(order_table).filter(order_table.order_number == order_number).first()
    if not order_record:
        raise Exception('not exist order_number={}'.format(order_number))
    task_records = db.query(task_table).filter(
        task_table.order_number == order_number).order_by(task_table.id.asc()).all()
    waiting_tasks = [record.task_uuid for record in task_records
                     if record.status in [TaskStatus.waiting]]
    return waiting_tasks


def get_tasks_by_order_number(db, order_number) -> dict:
    """查询订单下的任务"""
    order_record = db.query(order_table).filter(order_table.order_number == order_number).first()
    if not order_record:
        raise Exception('not exist order_number={}'.format(order_number))
    task_records = db.query(task_table).filter(
        task_table.order_number == order_number).order_by(task_table.id.asc()).all()
    processing = [record.task_uuid for record in task_records
                  if record.status in [TaskStatus.waiting, TaskStatus.processing]]
    complete = [record.task_uuid for record in task_records if
                record.status in [TaskStatus.completed, TaskStatus.skipped, TaskStatus.canceled]]
    return {
        'order_number': order_number,
        'receipt_number': task_records[0].receipt_number if task_records else '',
        'table': order_record.table,
        'processing': processing,
        'complete': complete,
    }


def inner_create_new_record(db, order: center_schema.InnerOrder):
    if check_order_is_exist(db, order.order_number):
        raise Exception('already exist order_number={}'.format(order.order_number))

    db.add(order_table.implement(order.dict()))
    print_list = []
    now = datetime.datetime.now()

    for i, drink in enumerate(order.drinks):
        task_uuid = uuid.uuid3(uuid.NAMESPACE_DNS, "{} {} {}".format(order.order_number, i, drink.formula))
        discount = drink.discount
        refund = drink.refund
        added_task = db.query(task_table).filter(task_table.receipt_number == drink.receipt_number,
                                                 task_table.create_time >= now - datetime.timedelta(days=1)).first()
        status = TaskStatus.skipped if discount == 1 else TaskStatus.paid
        status = TaskStatus.skipped if added_task else status
        status = TaskStatus.canceled if refund == 1 else status
        task = {
            'order_number': order.order_number,
            'reference_id': drink.reference_id,
            'receipt_number': drink.receipt_number,
            'task_uuid': task_uuid,
            'formula': drink.formula,
            'cup': format_option(drink.option.get('cup', 'Med')),
            'sweetness': int(drink.option.get('sweetness', 100)),
            'ice': format_option(drink.option.get('ice', 'light')),
            'milk': format_option(drink.option.get('milk', '')),
            'beans': format_option(drink.option.get('beans', '')),
            'discount': discount,
            'refund': refund,
            'status': status
        }
        task_value = task_table(**task)
        db.add(task_value)
        if status == TaskStatus.skipped:
            AudioInterface.gtts('skipped')

        # if status == TaskStatus.paid:
        #     print_drink = {
        #         'name': drink.formula,
        #         'options': {
        #             'ice': format_option(drink.option.get('ice')),
        #             'milk': format_option(drink.option.get('milk')),
        #             'sweetness': int(drink.option.get('sweetness')),
        #             'extra': drink.option.get('extra')
        #         },
        #         'receipt': drink.receipt_number,
        #         'task_uuid': task_uuid
        #     }
        #     print_list.append(print_drink)

    db.commit()
    return print_list


def get_one_order(db, order_number, inner) -> dict:
    logger.debug('get_one_order, db={}'.format(id(db)))
    order = db.query(order_table).filter(order_table.order_number == order_number).first()
    if order:
        order_response = {'order_number': order.order_number,
                          'table': order.table, 'status': order.status}
        tasks = db.query(task_table).filter(task_table.order_number == order.order_number).all()
        db.commit()
        if inner == 0:
            order_response['drinks'] = [{'task_id': task.task_uuid, 'status': task.status,
                                         'formula': task.formula} for task in tasks]
        elif inner == 1:
            order_response['drinks'] = [
                {'task_id': task.task_uuid, 'formula': task.formula, 'refund': task.refund, 'discount': task.discount}
                for task in tasks]
        return order_response
    else:
        db.commit()
        return {}


def get_all_order_tasks_by_time(db, start_time: datetime = None, end_time: datetime = None,
                                order_number: str = None) -> List[center_schema.TaskStatus]:
    """根据时间段查询所有订单下的任务"""
    logger.info("get_all_order_tasks")
    condition = [task_table.status != TaskStatus.unpaid]
    if start_time:
        condition.append(task_table.create_time >= start_time)
    if end_time:
        condition.append(task_table.create_time <= end_time)
    if order_number:
        condition.append(task_table.order_number == order_number)
    records = db.query(task_table).filter(*condition).order_by(task_table.id.asc()).all()
    # logger.info("get_orders  records==={}".format(records))
    record_list = [center_schema.TaskStatus.from_orm(record) for record in records]
    # logger.info("get_orders record_list==={}".format(record_list))
    return record_list


# def get_all_paid_tasks_by_time(db, start_time: datetime = None, end_time: datetime = None,
#                                order_number: str = None) -> List:
#     """根据时间段查询所有订单下的任务"""
#     logger.info("get_all_order_tasks")
#     condition = [task_table.status == TaskStatus.paid]
#     if start_time:
#         condition.append(task_table.create_time >= start_time)
#     if end_time:
#         condition.append(task_table.create_time <= end_time)
#     if order_number:
#         condition.append(task_table.order_number == order_number)
#     records = db.query(task_table).filter(*condition).order_by(task_table.id.asc()).all()
#     # logger.info("get_orders  records==={}".format(records))
#     result = []
#     for record in records:
#         schema_dict = center_schema.TaskStatus.from_orm(record).dict()
#         schema_dict['create_data'] = record.create_time.strftime("%B %d,%Y")
#         schema_dict['create_time'] = record.create_time.strftime("%I:%M:%S %p")
#         result.append(schema_dict)
#     return result


def get_frequent_tasks(db, param):
    or_conditions = [order_table.phone == param, order_table.mail == param, order_table.name == param]
    start_time = datetime.date.today() - datetime.timedelta(days=180)
    order_numbers = db.query(order_table.order_number).filter(order_table.create_time > start_time,
                                                              # order_table.status != TaskStatus.unpaid,
                                                              or_(*or_conditions)).all()
    order_numbers = [x[0] for x in order_numbers]
    result = {}
    if order_numbers:
        tasks = db.query(task_table).filter(task_table.order_number.in_(order_numbers)).order_by(
            task_table.create_time.desc()).all()
        for task in tasks:
            if result.get(task.formula) is None:
                result[task.formula] = dict(formula=task.formula, count=1, cup=task.cup, sweetness=task.sweetness,
                                            ice=task.ice, milk=task.milk)
            else:
                result[task.formula]['count'] += 1
    return sorted(result.values(), key=lambda x: x['count'], reverse=True)


def get_order_status(db, order_number):
    record = db.query(order_table).filter(order_table.order_number == order_number).first()
    return record.status


def paid_order_by_number(db, order_number, receipt_number):
    drinks = []
    print_labels = []
    if old_order := db.query(order_table).filter(order_table.order_number == order_number).first():
        if old_order.status == OrderStatus.unpaid:
            # old_order.status = OrderStatus.waiting
            old_order.status = OrderStatus.paid
        tasks = db.query(task_table).filter(task_table.order_number == order_number).all()
        for task in tasks:
            if task.status == TaskStatus.unpaid:
                # task.status = TaskStatus.waiting
                task.status = TaskStatus.paid
                print_labels.append(generate_label_msg(task))
            task.receipt_number = receipt_number
            extra = []
            task_dict = dict(name=task.formula, option={'cup': task.cup, 'ice': task.ice,
                                                        'sweetness': task.sweetness, 'milk': task.milk,
                                                        'extra': extra})
            drinks.append(task_dict)
        # db.commit()
        logger.info('paid order [{}]'.format(order_number))
    return drinks, print_labels


def update_task_status(db, task_uuid, status) -> center_schema.Task:
    if task_record := db.query(task_table).filter(task_table.task_uuid == task_uuid).first():
        task_record.status = status
        # if status == TaskStatus.completed:
        #     AudioInterface.gtts(
        #         "receipt {}, your {} is ready.".format('-'.join(list(task_record.receipt_number)), task_record.formula))
        if status == TaskStatus.failed:
            AudioInterface.gtts(
                "Sorry {}, your {} is failed.".format('-'.join(list(task_record.receipt_number)), task_record.formula))

        if status in [TaskStatus.processing, TaskStatus.completed, TaskStatus.failed]:
            order_completed = True
            order_tasks = db.query(task_table).filter(task_table.order_number == task_record.order_number).all()
            for task in order_tasks:
                if task.status in [TaskStatus.paid, TaskStatus.waiting, TaskStatus.processing]:
                    order_completed = False
                    break
            order = db.query(order_table).filter(order_table.order_number == task_record.order_number).first()
            if order_completed:
                order.status = TaskStatus.completed
                AudioInterface.gtts(CoffeeInterface.choose_one_speech_text(AudioConstant.TextCode.order_up))
            else:
                order.status = OrderStatus.processing
        db.add(task_record)
        db.commit()
        logger.info('set task_uuid={} status={}'.format(task_uuid, OrderStatus.completed))
        return task_record
    else:
        raise Exception('set task complete failed, not exist task_uuid={} in {} table'.format(
            task_uuid, task_table_name))


def check_order_is_exist(db, order_number: str) -> bool:
    record = db.query(order_table).filter(order_table.order_number == order_number).first()
    return True if record else False


def update_task_uuid(db, task_uuid: uuid.UUID, update_dict: dict):
    if record := db.query(task_table).filter(task_table.task_uuid == task_uuid).first():
        if record.status == TaskStatus.unpaid:
            return None  # unpaid task cannot be updated

        if update_dict.get('status') in [TaskStatus.skipped,
                                         TaskStatus.canceled] and record.status != TaskStatus.waiting:
            update_dict.pop('status')  # only waiting -> skipped/canceled

        for key, value in update_dict.items():
            setattr(record, key, value)
        db.add(record)
        logger.info('update table={} task_uuid={} value={}'.format(task_table_name, task_uuid, update_dict))


def update_order_number(db, order_number, update_dict: dict):
    if record := db.query(order_table).filter(order_table.order_number == order_number).first():
        for key, value in update_dict.items():
            setattr(record, key, value)
        db.add(record)
        logger.info('update table={} order_number={} value={}'.format(order_table_name, order_number, update_dict))


def get_task_uuid_instance(db, task_uuid: uuid.UUID) -> task_table:
    record = db.query(task_table).filter(task_table.task_uuid == task_uuid).first()
    return record


def get_next_task(db) -> task_table:
    next_order = db.query(order_table).filter(order_table.status == OrderStatus.paid).order_by(
        order_table.id.asc()).first()
    if next_order:
        logger.debug('next_order={}'.format(next_order.order_number))
        next_task = db.query(task_table).filter(task_table.order_number == next_order.order_number, task_table.status == TaskStatus.paid).order_by(
            task_table.id.asc()).first()
        if next_task:
            logger.debug('next_task={}'.format(next_task.task_uuid))
            # 订单下有已支付的任务，按id递增的顺序返回
            return next_task
        else:
            # 已支付订单下没有已支付的任务，订单状态更新为waiting
            next_order.status = OrderStatus.waiting
            # db.commit()
    return None


def generate_label_msg(task: task_table) -> dict:
    extra = []
    label_msg = {
        'name': task.formula,
        'options': {
            'ice': task.ice,
            'milk': task.milk,
            'sweetness': task.sweetness,
            'extra': extra
        },
        'receipt': task.receipt_number,
        'task_uuid': task.task_uuid
    }
    return label_msg


def get_user_by_sn(db, sn: str) -> user_table:
    user = db.query(user_table).filter(user_table.sn == sn).first()
    return user


def add_user(db, user: center_schema.RegisterRequest):
    if get_user_by_sn(db, user.sn):
        raise Exception('already exist sn={}'.format(user.sn))
    new_user = user_table.implement(user.dict())
    new_user.id = str(uuid.uuid1())
    db.add(new_user)
    return new_user.id


def get_constant_setting(db, name=None, type=None) -> List[center_table.ConstantSetting]:
    conditions = []
    if name:
        conditions.append(center_table.ConstantSetting.name == name)
    if type:
        conditions.append(center_table.ConstantSetting.type == type)

    constants = db.query(center_table.ConstantSetting).filter(*conditions).all()
    if constants:
        return constants
