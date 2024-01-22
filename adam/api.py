import time
from typing import Literal, List
from uuid import UUID, uuid4
import traceback
import string
import random

from fastapi import APIRouter, Depends, BackgroundTasks
from loguru import logger
from starlette.responses import JSONResponse
from sqlalchemy.orm import Session

from business import get_adam_obj, Adam
from common import define, conf
from common.define import Channel, AdamTaskStatus, ThreadName
from common.myerror import MoveError
from common.api import AudioInterface, CoffeeInterface, ASWServerInterface, VisualDetectInterface
from common.db.crud import adam as adam_crud
from devices.coffee.constant import MachineStatus
from coffee_device import Coffee_Driver
from common.db.database import get_db
from common.schemas import coffee as coffee_schema
from dance_thread import DanceThread, FollowThread
from dance import dance_random

from mutagen.mp3 import MP3

router = APIRouter(
    prefix="/{}".format(Channel.adam),
    tags=[Channel.adam],
    # dependencies=[Depends(get_admin_token)],
    responses={404: {"description": "Not found"}},
    on_startup=[get_adam_obj]
)

music_list = ['Because_of_You_brief.mp3',
              'Break_The_Ice_brief.mp3',
              'Dance_The_Night_brief.mp3',
              'FLOWER_brief.mp3',
              'Saturday_night_fever_brief.mp3',
              'Shut_Down_brief.mp3',
              'Sugar_brief.mp3',
              'Worth_It_brief.mp3',
              'YMCA_brief.mp3',
              'YouNeverCanTell_brief.mp3']


@router.post("/change_adam_status", summary="开启或关闭视觉跟随", description='Turn visual following on or off')
def change_adam_status(status: define.SUPPORT_ADAM_TASK_STATUS, adam: Adam = Depends(get_adam_obj)):
    """
    开始或关闭视觉跟随 | turn on or turn off visual following
    """
    try:
        if status == "following":
            if adam.task_status == AdamTaskStatus.idle:
                adam.change_adam_status(status)
                VisualDetectInterface.stop_following()
                adam.goto_standby_pose()
                VisualDetectInterface.start_following()
                music_name = random.choice(music_list)
                audio = MP3(f'/richtech/resource/audio/musics/{music_name}')
                duration_in_seconds = audio.info.length
                logger.info("++++++++++++++++++++++++++++++++++++++++++++++++++")
                logger.info(f"duration_in_seconds  :{duration_in_seconds}")
                AudioInterface.music(music_name)
                if adam.task_status == AdamTaskStatus.idle:
                    if not adam.follow_thread.is_alive():
                        adam.follow_thread = FollowThread(duration_in_seconds)
                        adam.follow_thread.setDaemon(True)
                        adam.follow_thread.name = ThreadName.follow_thread
                    adam.follow_thread.proceed()
                    adam.follow_thread.start()
            return adam.task_status
        elif status == "idle":
            if adam.task_status == AdamTaskStatus.following:
                adam.follow_thread.stop_thread()
                adam.change_adam_status(status)
            return adam.task_status
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/change_adam_status_idle", summary="视觉跟随开启时，adam状态改成idle", description='When visual following is turned on, the adam status changes to idle.')
def change_adam_status_idle(status: define.SUPPORT_ADAM_TASK_STATUS, adam: Adam = Depends(get_adam_obj)):
    """
    视觉跟随开启情况下，adam状态改成idle | When visual following is turned on, the adam status changes to idle.
    """
    try:
        if adam.task_status == AdamTaskStatus.following:
            adam.change_adam_status(status)
        return adam.task_status
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/right_move", summary='右臂视觉跟随', description='right_move y:[-400,0] z:[400, 800]')
def right_move(pos: dict, adam: Adam = Depends(get_adam_obj)):
    """
    视觉跟随下，英伟达调用右臂运动 | Following the vision, NVIDIA calls the right arm movement
    """
    if adam.task_status == AdamTaskStatus.following:
        if adam.right.has_error:
            adam.right.motion_enable()
            adam.right.clean_error()
            adam.right.clean_warn()
            adam.right.set_mode(0)
            adam.right.set_state()
        pre_angles = adam.right.angles
        y = pos['y']
        z = pos['z']
        move_pos = {'x': 355, 'y': y, 'z': z, 'roll': 0, 'pitch': 60, 'yaw': 90}
        move_pos_list = list(move_pos.values())
        right_angles = adam.inverse(define.Arm.right, move_pos_list, pre_angles[:6])
        adam.right.set_servo_angle(angle=right_angles, speed=55, wait=False, radius=5)


@router.post("/left_move", summary='左臂视觉跟随', description='left_move y:[100,400] z:[400, 800]')
def left_move(pos: dict, adam: Adam = Depends(get_adam_obj)):
    """
    视觉跟随下，英伟达调用左臂运动 | Following vision, NVIDIA calls the left arm movement
    """
    if adam.task_status == AdamTaskStatus.following:
        if adam.left.has_error:
            adam.left.motion_enable()
            adam.left.clean_error()
            adam.left.clean_warn()
            adam.left.set_mode(0)
            adam.left.set_state()
        pre_angles = adam.left.angles
        y = pos['y']
        z = pos['z']
        move_pos = {'x': 355, 'y': y, 'z': z, 'roll': 0, 'pitch': 60, 'yaw': -90}
        move_pos_list = list(move_pos.values())
        left_angles = adam.inverse(define.Arm.left, move_pos_list, pre_angles[:6])
        adam.left.set_servo_angle(angle=left_angles, speed=55, wait=False, radius=5)


@router.post("/random_move", summary='随机运动', description='right arm:[(-150, 500), (-350, 700)] left arm:[(350, 700), (150, 500)]')
def random_move(adam: Adam = Depends(get_adam_obj)):
    """
    视觉跟随下，左右臂随机运动 | Following vision, the left and right arms move randomly
    """
    right_pos_list = [(-150, 500), (-350, 700), (-237, 452), (-263, 526), (-147, 678), (-186, 622), (-355, 543), (-376, 648), (-226, 724),
                      (-250, 600)]
    left_pos_list = [(150, 500), (350, 700), (237, 452), (263, 526), (147, 678), (186, 622), (355, 543), (376, 648), (226, 724), (250, 600)]
    if adam.task_status == AdamTaskStatus.following:
        if adam.left.has_error:
            adam.left.motion_enable()
            adam.left.clean_error()
            adam.left.clean_warn()
            adam.left.set_mode(0)
            adam.left.set_state()
        if adam.right.has_error:
            adam.right.motion_enable()
            adam.right.clean_error()
            adam.right.clean_warn()
            adam.right.set_mode(0)
            adam.right.set_state()

        right_pre_angles = adam.right.angles
        right_y, right_z = random.choice(right_pos_list)
        right_move_pos = {'x': 355, 'y': right_y, 'z': right_z, 'roll': 0, 'pitch': 60, 'yaw': 90}
        right_move_pos_list = list(right_move_pos.values())
        right_angles = adam.inverse(define.Arm.right, right_move_pos_list, right_pre_angles[:6])
        adam.right.set_servo_angle(angle=right_angles, speed=55, wait=False, radius=5)

        left_pre_angles = adam.left.angles
        left_y, left_z = random.choice(left_pos_list)
        left_move_pos = {'x': 355, 'y': left_y, 'z': left_z, 'roll': 0, 'pitch': 60, 'yaw': -90}
        left_move_pos_list = list(left_move_pos.values())
        left_angles = adam.inverse(define.Arm.left, left_move_pos_list, left_pre_angles[:6])
        adam.left.set_servo_angle(angle=left_angles, speed=55, wait=False, radius=5)


@router.post("/stop_move", summary='停止移动', description='stop move')
def stop_move(adam: Adam = Depends(get_adam_obj)):
    """
    视觉跟随，左右臂停止运动 | Visual follow-up, left and right arms stop moving
    """
    if adam.task_status == AdamTaskStatus.following:
        adam.env.adam.set_state(dict(state=4), dict(state=4))
        adam.left.motion_enable()
        adam.left.clean_error()
        adam.left.clean_warn()
        adam.left.set_mode(0)
        adam.left.set_state()
        adam.right.motion_enable()
        adam.right.clean_error()
        adam.right.clean_warn()
        adam.right.set_mode(0)
        adam.right.set_state()

        left_init_angle = [132.3, 8.7, -34.5, -45.9, 42.8, -38.7]
        right_init_angle = [-132, 8.7, -34.5, 45.9, 42.8, 38.7]
        adam.left.set_servo_angle(angle=left_init_angle, speed=30, wait=False, radius=5)
        adam.right.set_servo_angle(angle=right_init_angle, speed=30, wait=True, radius=5)
    return "ok"


@router.get("/status", summary='获取 Adam 任务状态和 Coffee 状态', description='get adam task status and coffee status')
def get_status(adam: Adam = Depends(get_adam_obj)):
    status_dict = adam.coffee_thread.coffee_status
    logger.info('get adam task status')
    # if "error" not in status_dict:
    #     status_dict["error"] = ""
    result = {'adam_status': adam.task_status, 'coffee_status': status_dict, 'error': adam.error_msg}
    return result


@router.get("/composition", summary='通过选项获取配方', description='get composition by option')
def get_composition(formula: str, sweetness: int = 0,
                    ice: define.SUPPORT_ICE_TYPE = define.IceType.no_ice, milk: Literal['Plant-based milk', 'Milk'] = define.MilkType.plant_based,
                    beans: define.SUPPORT_BEANS_TYPE = define.BeansType.high_roast,
                    adam: Adam = Depends(get_adam_obj)):
    logger.info('get_composition')
    try:
        coffee_record = coffee_schema.CoffeeRecord(task_uuid=1, receipt_number="rec", formula=formula, cup="cup", sweetness=sweetness, ice=ice,
                                                   milk=milk, beans=beans)
        return adam.get_composition_by_option(coffee_record)
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/test_tap", summary="测试龙头", description='test tap:[A-Q: 1-16 open, a-q: 1-16 closed, I: fully open, i: fully closed]')
async def test_tap(command: str, adam: Adam = Depends(get_adam_obj)):
    logger.info('in test_tap')
    if adam.task_status in [define.AdamTaskStatus.idle, define.AdamTaskStatus.stopped, define.AdamTaskStatus.dead, define.AdamTaskStatus.rolling]:
        logger.debug('before send')
        com = adam.ser.new_communication()
        adam.ser.send_one_msg(com, command)
        logger.info('after send')
        logger.debug(f'send char {command}')
        com.close_engine()
        return "ok"
    else:
        return JSONResponse(status_code=400, content={'error': 'Adam is busy now, status is {}'.format(adam.task_status)})


@router.post("/test_coffee_machine", summary="测试咖啡机", description='test_coffee_machine')
def test_coffee_machine(drink_num: int, adam: Adam = Depends(get_adam_obj)):
    if adam.task_status in [define.AdamTaskStatus.idle, define.AdamTaskStatus.stopped, define.AdamTaskStatus.dead, define.AdamTaskStatus.rolling]:

        result = adam.coffee_driver.make_coffee(drink_num - 1)
        return result
    else:
        return JSONResponse(status_code=400, content={'error': 'Adam is busy now, status is {}'.format(adam.task_status)})


@router.post("/random_dance", summary='随机跳舞', description='let adam dance in music')
def random_dance(choice: int, adam: Adam = Depends(get_adam_obj)):
    logger.info('adam random_dance')
    task_status = dance_random(adam, choice)
    return task_status


@router.post("/zero", summary='Adam回工作状态的零点', description='adam goto zero position')
def zero(idle: bool = True, adam: Adam = Depends(get_adam_obj)):
    logger.info('goto zero position')
    return adam.stop_and_goto_zero(is_sleep=True, idle=idle)


@router.post("/stop", summary='Adam软件急停', description='adam stop all action')
def stop(adam: Adam = Depends(get_adam_obj)):
    logger.info('adam stop all action by http request')
    return adam.stop()


@router.post("/standby_pose", summary='Adam回到作揖动作', description='adam goto standby_pose')
def standby_pose(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.goto_standby_pose()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/roll", summary='安全返回', description='adam roll back')
def roll(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.roll()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/open_gripper", summary='控制机械臂的夹爪开关', description='Control the gripper switch of the robotic arm')
def open_gripper(which: Literal['left', 'right'], position: int, adam: Adam = Depends(get_adam_obj)):
    try:
        adam.goto_gripper_position(which, position)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/manual", summary='开启或关闭手动', description='Turn manual on or off')
def manual(which: Literal['left', 'right'], action: Literal['close', 'open'], adam: Adam = Depends(get_adam_obj)):
    try:
        if action == 'open':
            return adam.manual(which, mode=2)
        else:
            return adam.manual(which, mode=0)
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/init", summary='初始化机械臂', description='Initialize the robot arm')
def init(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.env.init_adam()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/resume", summary='重新回到工作状态零点', description='Return to goto_work_zero')
def resume(adam: Adam = Depends(get_adam_obj)):
    logger.info('adam enable')
    return adam.resume()


@router.post("/coffee_status", summary='获取当前咖啡机状态', description='Get current coffee machine status')
def roll(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.coffee_driver.query_status()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/clean_milk_pipe", summary='清洗奶管', description='clean milk pipe')
def clean_milk_pipe(materials: list, adam: Adam = Depends(get_adam_obj)):
    try:
        if adam.task_status == AdamTaskStatus.idle:
            logger.info(materials)
            adam.clean_milk_pipe(materials)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.get("/choose_speech", summary='选择播报语音', description='choose_speech')
def choose_speech(type: str, formula: str = None, adam: Adam = Depends(get_adam_obj)):
    try:
        adam.choose_speech(type, formula)
        return "ok"
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/make_cold_drink", summary='制作冷咖', description='make_cold_drink')
def make_cold_drink(coffee_record: coffee_schema.CoffeeRecord, adam: Adam = Depends(get_adam_obj)):
    logger.info('make_cold_drink')
    try:
        adam.make_cold_drink(coffee_record)
        return 'ok'
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/make_hot_drink", summary='制作热咖', description='make_hot_drink')
def make_hot_drink(coffee_record: coffee_schema.CoffeeRecord, adam: Adam = Depends(get_adam_obj)):
    logger.info('make_hot_drink')
    try:
        adam.make_hot_drink(coffee_record)
        return 'ok'
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/pour_foam_cup", summary='【左->右】或者【右->左】倒入杯中', description="[Left->Right] or [Right->Left] pour into the cup")
def pour_foam_cup(action: Literal['left', 'right'], adam: Adam = Depends(get_adam_obj)):
    try:
        adam.pour_foam_cup(action)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/stainless_cup_pour_foam", summary='不锈钢杯倒入奶泡杯', description='Pour the espresso cup into foam machine')
def stainless_cup_pour_foam(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.stainless_cup_pour_foam()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


# left actions
@router.post("/take_hot_cup", summary='抓热杯', description='take cup from right side of adam')
def take_hot_cup(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.take_hot_cup()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/take_cold_cup", summary='抓冷杯', description='take cup from left side of adam')
def take_cold_cup(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.take_cold_cup()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/put_hot_cup", summary='放热杯', description='put cup from right side of adam')
def put_hot_cup(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.put_hot_cup()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/put_cold_cup", summary='放冷杯', description='put cup from left side of adam')
def put_cold_cup(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.put_cold_cup()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/take_ice", summary='接冰', description='take ice from ice_machine')
def take_ice(delay_time: float, adam: Adam = Depends(get_adam_obj)):
    try:
        time.sleep(3)
        adam.take_ice(delay_time)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/clean_foamer", summary='清理奶泡杯', description='clean foam cup')
def clean_foamer(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.clean_foamer()
        return 'ok'
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/put_foam_cup", summary='放置奶泡杯', description='put foam cup')
def put_foam_cup(arm: Literal['left', 'right'], adam: Adam = Depends(get_adam_obj)):
    try:
        adam.put_foam_cup(arm)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/clean_and_put_espresso_cup", summary='清洗并放置不锈钢杯', description='clean and put espresso cup')
def clean_and_put_espresso_cup(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.clean_and_put_espresso_cup()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/clean_tap", summary='打开或关闭龙头', description='Turn the tap on or off')
async def open_tap(name: str, action: Literal['0', '1'], adam: Adam = Depends(get_adam_obj)):
    logger.info('in open tap')
    if adam.task_status in [define.AdamTaskStatus.idle, define.AdamTaskStatus.stopped, define.AdamTaskStatus.dead,
                            define.AdamTaskStatus.rolling]:
        tap_configs = CoffeeInterface.get_machine_config(machine=define.Constant.MachineType.tap)
        arduino_write_dict = {i.get('name'): i.get('arduino_write') for i in tap_configs}
        com = adam.ser.new_communication()
        if action == '1':
            logger.debug('before send')
            adam.ser.send_one_msg(com, arduino_write_dict.get(name))
            logger.info('after send')
            logger.debug('send char {}'.format(arduino_write_dict.get(name)))
            adam_crud.update_one_tap(name, 1)
            CoffeeInterface.add_cleaning_history({name: 0}, 2)
            # clean_history = CoffeeInterface.get_last_one_clean_history()
            # background_tasks.add_task(ASWServerInterface.add_cleaning_history, clean_history)
        else:
            close_char = chr(ord(str(arduino_write_dict.get(name))) + 32)  # 数字字符转英文字符
            logger.debug('send char {}'.format(close_char))
            logger.info('before send')
            adam.ser.send_one_msg(com, close_char)
            logger.info('after send')
            adam_crud.update_one_tap(name, 0)
        com.close_engine()
        return adam_crud.get_all_status()[name]
    else:
        return JSONResponse(status_code=400, content={'error': 'Adam is busy now, status is {}'.format(adam.task_status)})


@router.post("/clean_the_brewer", summary='咖啡机自动清洗', description='Coffee machine automatic cleaning')
def clean_the_brewer(adam: Adam = Depends(get_adam_obj)):
    if status_dict := adam.coffee_driver.query_status():
        if status_dict.get("status_code", "") == 255 and status_dict.get("status_code", []) == []:
            for i in range(1, 7):
                if i != 5:
                    is_clean_close = False
                    adam.coffee_driver.select_clean(i)
                    while not is_clean_close:
                        time.sleep(2)
                        status_dict = adam.coffee_driver.query_status()
                        if status_dict:
                            if status_dict["status_code"] == 255:
                                is_clean_close = True
                        else:
                            time.sleep(1)
            CoffeeInterface.add_cleaning_history({"coffee_machine": 0}, 2)
            return 'ok'
        else:
            AudioInterface.gtts('/richtech/resource/audio/voices/coffee_machine_busy.mp3')
            return JSONResponse(status_code=510, content={'error': 'Coffee machine is busy now, please wait sometime'})


@router.get("/tap_status", summary='获取所有龙头状态', description='get all tap status')
def get_tap_status():
    logger.info('get_tap_status')
    result = adam_crud.get_all_status()
    logger.info(result)
    return result


@router.post("/set_idle_Interaction", summary='设置空闲交互阈值', description='set idle Interaction threshold')
def set_idle_Interaction(state: int, threshold: int):
    try:
        result_dict = {}
        result_dict['state'] = state
        result_dict['threshold'] = threshold
        conf.set_idle_Interaction(result_dict)
        return result_dict
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.get("/get_idle_Interaction_state", summary='获取空闲交互阈值', description='Get idle interaction threshold')
def get_idle_Interaction_state():
    try:
        result_dict = {}
        idle_dict = conf.get_idle_Interaction()
        result_dict['state'] = int(idle_dict['state'])
        result_dict['threshold'] = int(idle_dict['threshold'])
        return result_dict
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.get("/get_dance_list", summary='获取跳舞列表', description='Get dance list')
def get_dance_list(db: Session = Depends(get_db)):
    try:
        logger.info('get dance_list')
        result = adam_crud.get_dance_list(db)
        logger.info(result)
        return result
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.get("/get_now_playing", summary='获取跳舞当前播放歌曲', description='Get the currently playing song for dancing')
def get_now_playing(db: Session = Depends(get_db)):
    try:
        logger.info('get now_playing')
        result = adam_crud.get_now_playing(db)
        return result
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/update_dance", summary='更新跳舞列表', description='update dance list')
def update_dance(dance_list: List, db: Session = Depends(get_db)):
    try:
        logger.info(f'update dance : {dance_list} ')
        adam_crud.init_dance(db)
        adam_crud.init_dance_display(db)
        adam_crud.update_dance(db, dance_list)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/update_single_dance", summary='更新当前跳舞数据，指定正在播放', description='Update the current dance data and specify that it is currently playing')
def update_single_dance(dance_num: int, now_playing: int, db: Session = Depends(get_db)):
    try:
        logger.info('update single dance')
        adam_crud.update_single_dance(db, dance_num, now_playing)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/init_dance", summary='初始化dance table 数据', description='Initialize dance table data')
def init_dance(db: Session = Depends(get_db)):
    try:
        logger.info('init dance')
        adam_crud.init_dance(db)
        return 'ok'
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/set_dance_time", summary='设置跳舞时间', description='Set dance time')
def set_dance_time(time: int, adam: Adam = Depends(get_adam_obj)):
    try:
        adam.dance_time = time * 60
        if adam.dance_thread.is_alive():
            adam.dance_thread.total_duration = adam.dance_time
        return 'ok'
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/proceed_dance", summary='开启跳舞线程', description='Start dancing thread')
def proceed_dance(adam: Adam = Depends(get_adam_obj)):
    try:
        if adam.task_status == AdamTaskStatus.idle:
            if not adam.dance_thread.is_alive():
                adam.dance_thread = DanceThread()
                adam.dance_thread.setDaemon(True)
                adam.dance_thread.name = ThreadName.dance_thread
            adam.dance_thread.proceed(total_duration=adam.dance_time)
            adam.dance_thread.start()
        return 'ok'
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/stop_dance", summary='停止跳舞线程', description='stop dancing thread')
def stop_dance(adam: Adam = Depends(get_adam_obj)):
    try:
        if adam.task_status == AdamTaskStatus.dancing:
            adam.dance_thread.stop_thread()
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/pause_dance", summary='暂停跳舞线程', description='Pause dancing thread')
def pause_dance(adam: Adam = Depends(get_adam_obj)):
    try:
        try:
            if adam.task_status == AdamTaskStatus.dancing:
                adam.dance_thread.pause()
        except Exception as e:
            pass
        return adam.stop_and_goto_zero(is_sleep=True)
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.get("/get_setting_time", summary='获取跳舞设置时长', description='Get dance setting duration')
def get_setting_time(adam: Adam = Depends(get_adam_obj)):
    try:
        return str(int(adam.dance_time / 60))
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/enable_visual_recognition", summary='开启或关闭视觉识别', description='Turn visual recognition on or off')
def enable_visual_recognition(state: int, adam: Adam = Depends(get_adam_obj)):
    try:
        if state == 0:
            adam.enable_visual_recognition = False
        else:
            adam.enable_visual_recognition = True
        return adam.enable_visual_recognition
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': str(e)})

# +++++++++++++++++++++++++++++++++++++++++++

# @router.post("/take_ingredients", description='take cup from left side of adam')
# def take_ingredients(arm: Literal['left', 'right'], formula: str, adam: Adam = Depends(get_adam_obj)):
#     try:
#         composition = adam.get_composition_by_option(formula, 'Medium Cup', 100, 'fresh_dairy')
#         adam.take_ingredients(arm, composition.get('tap', {}))
#         return 'ok'
#     except Exception as e:
#         return JSONResponse(status_code=510, content={'error': repr(e)})
#
#
# @router.post("/take_ingredients_foam", description='take cup from left side of adam')
# def take_ingredients_foam(arm: Literal['left', 'right'], formula: str, adam: Adam = Depends(get_adam_obj)):
#     try:
#         composition = adam.get_composition_by_option(formula, 'Medium Cup', 100, 'fresh_dairy')
#         adam.take_ingredients_foam(arm, composition.get('tap', {}))
#         return 'ok'
#     except Exception as e:
#         return JSONResponse(status_code=510, content={'error': repr(e)})
#
#
# @router.post("/take_foam_cup", description='take foam cup')
# def take_foam_cup(arm: Literal['left', 'right'], is_move: Literal['true', 'false'], is_waiting: Literal['true', 'false'],
#                   adam: Adam = Depends(get_adam_obj)):
#     try:
#         adam.take_foam_cup(arm, is_waiting=is_waiting, is_move=is_move)
#         return 'ok'
#     except MoveError as e:
#         return JSONResponse(status_code=510, content={'error': str(e)})
#
#
# @router.post("/take_espresso_cup", description='take espresso cup from the right side of Adam')
# def take_espresso_cup(adam: Adam = Depends(get_adam_obj)):
#     try:
#         adam.take_espresso_cup()
#         return 'ok'
#     except MoveError as e:
#         return JSONResponse(status_code=510, content={'error': str(e)})
#
#
# @router.post("/make_foam", description='take milk from tap and make foam')
# def make_foam(formula: str, arm: Literal['left', 'right'], adam: Adam = Depends(get_adam_obj)):
#     try:
#         composition = adam.get_composition_by_option(formula, 'Medium Cup', 100, 'fresh_dairy')
#         adam.make_foam(composition.get(define.Constant.MachineType.foam_machine, {}), arm)
#         return 'ok'
#     except MoveError as e:
#         return JSONResponse(status_code=510, content={'error': str(e)})
#
#
# @router.post("/get_current_position", description='gives the current position of the arm')
# def get_current_position(arm: Literal['left', 'right'], adam: Adam = Depends(get_adam_obj)):
#     try:
#         current_position = adam.current_position(arm)
#         return JSONResponse(status_code=200, content={'success': str(current_position)})
#     except MoveError as e:
#         return JSONResponse(status_code=510, content={'error': str(e)})
#
#
# @router.post("/dance", summary='let adam dance in music')
# def dance(adam: Adam = Depends(get_adam_obj)):
#     logger.info('adam dance')
#     adam.dance_in_thread()
#     return 'ok'
#
#
# @router.post("/dance1", summary='let adam dance in music')
# def dance1(adam: Adam = Depends(get_adam_obj)):
#     logger.info('adam dance')
#     adam.dance1_in_thread()
#     return 'ok'
#
#
