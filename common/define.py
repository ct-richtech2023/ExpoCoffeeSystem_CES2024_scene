import enum
import os
import random
from typing import Literal
from common.db.database import get_db

class OrderStatus:
    unpaid = 'unpaid'
    paid = 'paid'
    processing = 'processing'
    waiting = 'waiting'
    completed = 'completed'
    failed = 'failed'
    exception = 'exception'


class TaskStatus:
    unpaid = 'unpaid'
    paid = 'paid'
    waiting = 'waiting'
    starting = 'starting'
    processing = 'processing'
    completed = 'completed'
    failed = 'failed'
    canceled = 'canceled'
    skipped = 'skipped'


class RefundStatus:
    # order
    no = 0
    part = 1
    all = 2

    # task
    refunded = 1


class DiscountStatus:
    no = 0
    resell = 1
    normal = 2


class ServicePort(enum.Enum):
    center = 9000
    coffee = 9001
    exception = 9002
    adam = 9003
    audio = 9004
    docs = 9090
    adminer = 8080


class ServiceHost:
    host = "0.0.0.0"
    localhost = '127.0.0.1'


class Channel:
    coffee = 'coffee'
    center = 'center'
    exception = 'exception'
    adam = 'adam'
    audio = 'audio'
    kinematics = 'kinematics'
    gpio = 'gpio'


class Arm:
    left = 'left'
    right = 'right'


class ProductEnv:
    indoor = 'indoor'
    outdoor = 'outdoor'


class CupSize:
    # 杯子尺寸，compoition表相关
    large_cup = 'Large Cup'
    medium_cup = 'Medium Cup'


class CupName:
    # 杯子名称 实际制作时使用的杯子名称
    hot_cup = 'hot_cup'
    cold_cup = 'cold_cup'


class MilkType:
    # 牛奶类型
    plant_based = 'plant_milk'
    milk = 'fresh_dairy'
    foam = 'foam'

class BeansType:
    # 咖啡豆类型
    medium_roast = 'medium_roast'
    high_roast = 'high_roast'


class TreacleType:
    # 糖浆种类
    sugar = 'sugar'
    vanilla_syrup = 'vanilla_syrup'
    chocolate_syrup = 'chocolate_syrup'
    sea_salt_foam = 'sea_salt_foam'
    green_tea_syrup = 'green_tea_syrup'


class IceType:
    # 冰选项
    no_ice = 'no_ice'
    light = 'light'
    more = 'more'


class ExceptionType:
    adam_init_failed = 'Adam init failed'
    coffee_device_init_failed = 'coffee device init failed'
    adam_initial_position_failed = 'Adam go to initial position failed'
    wake_init_failed = 'wake init failed'


class BaseErrorStatus:
    solved = 'solved'
    unsolved = 'unsolved'


class GetIngredientType:
    all = 'all'
    alarm = 'alarm'


class Service:
    milktea = 'milktea'
    center = 'center'
    exception = 'exception'
    adam = 'adam'
    audio = 'audio'
    wake = 'wake'


class AdamTaskStatus:
    # adam机器人状态
    idle = 'idle'
    making = 'making'
    warm = 'warm'
    dancing = 'dancing'
    stopped = 'stopped'
    rolling = 'rolling'
    dead = 'dead'
    restart = 'restart'
    following = 'following'


class PrePosition:
    ingredients = 'ingredients'
    make_ice = 'make-ice'
    shave_ice = 'shave-ice'


class MaterialType:
    cup = 'cup'
    coffee = 'coffee'  # 美式、冷咖、热水、热牛奶、拿铁
    # milk = 'milk'  # 奶
    treacle = 'treacle'  # 糖浆
    endless = 'endless'
    Milk = "Milk"
    Plant_based_milk = "Plant-based milk"


class Constant:
    db = next(get_db())

    class InUse:
        in_use = 1
        not_in_use = 0

    class FormulaType:
        hot = 'hot'
        cold = 'cold'

    class MachineType:
        coffee_machine = 'coffee_machine'
        foam_machine = 'foam_machine'
        tap = 'tap'
        power_box = 'power_box'
        bucket = 'bucket'
        ice_maker = 'ice_maker'
        cup = 'cup'
        cleaner = 'cleaner'

    class DisplayType:
        bucket = 'bucket'
        bottle = 'bottle'
        cup = 'cup'
        fruit = 'fruit'
        tap = 'tap'
        coffee_milk = 'coffee_milk'
        foam_coffee = 'foam_coffee'

    class ConstantSettingName:
        milk_fresh_time = 'milk_fresh_time'


class UserMsg:
    ACCESS_TOKEN_EXPIRE_MINUTES = 180
    login_error = 'please check your name or password'
    register_error = 'Account already exists'
    lack_square_msg = 'please bind your account with square first, user_id={}'


class AudioConstant:
    class Level:
        chat = 0
        normal = 1
        now = 9

    class SpeakStatus:
        waiting = 0
        said = 1

    class TextCode:
        new_order = 'new_order'
        start_makine = 'start_making'
        take_milktea = 'take_milktea'
        put_cup = 'put_cup'
        order_up = 'order_up'
        fail = 'fail'
        start_dancing = 'start_dancing'
        end_dancing = 'end_dancing'
        print_receipt = 'print_receipt'

        # printer_error = 'printer_error'
        time_out = 'time_out'
        no_cup = 'no_cup'
        not_take_away = 'not_take_away'
        manual_succeed = 'manual_succeed'
        manual_failed = 'manual_failed'
        generate_failed = 'generate_failed'

        LOCAL_CODE = {
            new_order: 3, start_makine: 3, take_milktea: 3, put_cup: 3, order_up: 3, fail: 3, start_dancing: 3,
            end_dancing: 3, print_receipt: 3, time_out: 1, no_cup: 1, not_take_away: 1, manual_succeed: 1,
            manual_failed: 1, generate_failed: 1
        }
        CODE_MSG = {
            time_out: 'has wait for milktea for 30min, please check and restart',
            no_cup: 'Where\'s my cup?',
            not_take_away: 'Please take the last cup away first!',
            manual_succeed: 'open manual mode successfully',
            manual_failed: 'open manual mode successfully',
            generate_failed: 'Sorry, generate voice failed'
        }

    @classmethod
    def get_mp3_file(cls, code):
        file_name = '{}{}.mp3'.format(code, random.randint(1, AudioConstant.TextCode.LOCAL_CODE.get(code)))
        path = os.path.join(audio_dir, 'voices', file_name)
        if os.path.exists(path):
            return path
        else:
            return AudioConstant.TextCode.CODE_MSG.get(code)


class ThreadName:
    left_pos_record = 'left_pos_record'
    right_pos_record = 'right_pos_record'
    coffee_thread = 'coffee_status'
    dance_thread = 'dance'
    follow_thread = 'follow'
    cup_detect = 'cup_detect'
    person_detect = 'cup_detect'


support_take_drinks = ['Shaken']
audio_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'resource/audio/'))
SUPPORT_ARM_TYPE = Literal[tuple([i for i in dir(Arm) if '__' not in i])]  # noqa
SUPPORT_PRODUCT_ENV_TYPE = Literal[tuple([i for i in dir(ProductEnv) if '__' not in i])]  # noqa
SUPPORT_CUP_NAME_TYPE = Literal[tuple([getattr(CupName, i) for i in dir(CupName) if '__' not in i])]  # noqa
SUPPORT_CUP_SIZE_TYPE = Literal[tuple([getattr(CupSize, i) for i in dir(CupSize) if '__' not in i])]  # noqa
SUPPORT_MILK_TYPE = Literal[tuple([getattr(MilkType, i) for i in dir(MilkType) if '__' not in i])]  # noqa
SUPPORT_ICE_TYPE = Literal[tuple([getattr(IceType, i) for i in dir(IceType) if '__' not in i])]  # noqa
SUPPORT_BEANS_TYPE = Literal[tuple([getattr(BeansType, i) for i in dir(BeansType) if '__' not in i])]  # noqa
SUPPORT_SERVICE = Literal[tuple([i for i in dir(Service) if '__' not in i])]  # noqa
POSITION_PARAM = ['x', 'y', 'z', 'roll', 'pitch', 'yaw']
ANGLE_PARAM = ['j1', 'j2', 'j3', 'j4', 'j5', 'j6']
SUPPORT_ERROR_TYPE = Literal[tuple([getattr(ExceptionType, i) for i in dir(ExceptionType) if '__' not in i])]  # noqa
SUPPORT_BASE_ERROR_STATUS = Literal[tuple([getattr(BaseErrorStatus, i) for i in dir(BaseErrorStatus) if '__' not in i])]  # noqa
BIN_PATH = '/richtech/resource/adam/kinematics'
# BIN_PATH = '/home/adam/projects/cloutea/cloutea_v1/resource/adam/kinematics'
CLOUFFEE_DESCRIPTION = "all interface port {}".format(" ".join(["{}:{}".format(i.name, i.value) for i in ServicePort]))

SUPPORT_ORDER_STATUS = Literal[tuple([getattr(OrderStatus, i) for i in dir(OrderStatus) if '__' not in i])]  # noqa

SUPPORT_MATERIAL_TYPE = Literal[tuple([getattr(MaterialType, i) for i in dir(MaterialType) if '__' not in i])]
SUPPORT_MACHINE_TYPE = Literal[tuple([getattr(Constant.MachineType, i) for i in dir(Constant.MachineType) if '__' not in i])]
SUPPORT_FORMULA_TYPE = Literal[tuple([getattr(Constant.FormulaType, i) for i in dir(Constant.FormulaType) if '__' not in i])]

SUPPORT_DISPLAY_TYPE = Literal[tuple([getattr(Constant.DisplayType, i) for i in dir(Constant.DisplayType) if '__' not in i])]

SUPPORT_DISCOUNT_STATUS = Literal[tuple([getattr(DiscountStatus, i) for i in dir(DiscountStatus) if '__' not in i])]  # noqa
SUPPORT_REFUND_STATUS = Literal[tuple([getattr(RefundStatus, i) for i in dir(RefundStatus) if '__' not in i])]  # noqa
SUPPORT_TASK_STATUS = Literal[tuple([getattr(TaskStatus, i) for i in dir(TaskStatus) if '__' not in i])]  # noqa

SUPPORT_ADAM_TASK_STATUS = Literal[tuple([getattr(AdamTaskStatus, i) for i in dir(AdamTaskStatus) if '__' not in i])]  # noqa

# SUPPORT_MATERIAL_NAME = Literal[DB_Constant.get_all_material_name]
# SUPPORT_INUSE_MATERIAL_NAME = Literal[DB_Constant.get_all_material_name]
# SUPPORT_FORMULA_NAME = Literal[DB_Constant.get_all_formula_name]
# SUPPORT_MATERIAL_CONFIG_NAME = Literal[DB_Constant.get_all_material_config_name]
