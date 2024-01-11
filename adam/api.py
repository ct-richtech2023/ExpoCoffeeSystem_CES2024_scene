import time
from typing import Literal, List
from uuid import UUID, uuid4
import traceback
import string

from fastapi import APIRouter, Depends, BackgroundTasks
from loguru import logger
from starlette.responses import JSONResponse
from sqlalchemy.orm import Session

from business import get_adam_obj, Adam
from common import define, conf
from common.define import Channel, AdamTaskStatus
from common.myerror import MoveError
from common.api import AudioInterface, CoffeeInterface, ASWServerInterface, VisualDetectInterface
from common.db.crud import adam as adam_crud
from devices.coffee.constant import MachineStatus
from coffee_device import Coffee_Driver
from common.db.database import get_db

from mutagen.mp3 import MP3
import random

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


@router.post("/change_adam_status", summary="")
def change_adam_status(status: define.SUPPORT_ADAM_TASK_STATUS, adam: Adam = Depends(get_adam_obj)):
    try:
        if status == "following":
            VisualDetectInterface.stop_following()
            adam.goto_standby_pose()
            VisualDetectInterface.start_following()
            music_name = random.choice(music_list)
            audio = MP3(f'/richtech/resource/audio/musics/{music_name}')
            duration_in_seconds = audio.info.length
            logger.error("++++++++++++++++++++++++++++++++++++++++++++++++++")
            logger.error(f"duration_in_seconds  :{duration_in_seconds}")
            AudioInterface.music(music_name)
            adam.followCountdownTimer.edit_initial_time(duration_in_seconds)
            adam.followCountdownTimer.start()
            adam.change_adam_status(status)
            return adam.task_status
        elif status == "idle":
            adam.followCountdownTimer.stop()
            adam.change_adam_status(status)
            return adam.task_status
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/change_adam_status_idle", summary="")
def change_adam_status_idle(status: define.SUPPORT_ADAM_TASK_STATUS, adam: Adam = Depends(get_adam_obj)):
    try:
        if adam.task_status == "following":
            adam.change_adam_status(status)
        return adam.task_status
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/right_move", summary='right_move y[-400,0] z[400, 800]')
def right_move(pos: dict, adam: Adam = Depends(get_adam_obj)):
    if adam.task_status == "following":
        if adam.right.has_error:
            # logger.error(f"right arm error:{error}")
            adam.right.motion_enable()
            adam.right.clean_error()
            adam.right.clean_warn()
            adam.right.set_mode(0)
            adam.right.set_state()
        # logger.debug(f'pos: {pos}')
        pre_angles = adam.right.angles
        # logger.debug(f'right pre_angles: {pre_angles}')
        y = pos['y']
        z = pos['z']
        move_pos = {'x': 355, 'y': y, 'z': z, 'roll': 0, 'pitch': 60, 'yaw': 90}
        # logger.debug(f'right move_pos: {move_pos}')
        move_pos_list = list(move_pos.values())
        # logger.debug(f'right move_pos_list: {move_pos_list}')
        right_angles = adam.inverse(define.Arm.right, move_pos_list, pre_angles[:6])
        adam.right.set_servo_angle(angle=right_angles, speed=55, wait=False, radius=5)
        # return result


@router.post("/left_move", summary='left_move y[100,400] z[400, 800]')
def left_move(pos: dict, adam: Adam = Depends(get_adam_obj)):
    if adam.task_status == "following":
        if adam.left.has_error:
            # logger.error(f"left arm error:{adam.left.}")
            adam.left.motion_enable()
            adam.left.clean_error()
            adam.left.clean_warn()
            adam.left.set_mode(0)
            adam.left.set_state()
        # logger.debug(f'pos: {pos}')
        pre_angles = adam.left.angles
        # logger.debug(f'left pre_angles: {pre_angles}')
        y = pos['y']
        z = pos['z']
        move_pos = {'x': 355, 'y': y, 'z': z, 'roll': 0, 'pitch': 60, 'yaw': -90}
        # logger.debug(f'right move_pos: {move_pos}')
        move_pos_list = list(move_pos.values())
        # logger.debug(f'right move_pos_list: {move_pos_list}')
        left_angles = adam.inverse(define.Arm.left, move_pos_list, pre_angles[:6])
        adam.left.set_servo_angle(angle=left_angles, speed=55, wait=False, radius=5)
        # return "ok"

@router.post("/random_move", summary='右臂：[(-150, 500), (-350, 700)] 左臂[(350, 700), (150, 500)]')
def random_move(adam: Adam = Depends(get_adam_obj)):
    right_pos_list = [(-150, 500), (-350, 700), (-237, 452), (-263, 526), (-147, 678), (-186, 622), (-355, 543), (-376, 648), (-226, 724), (-250, 600)]
    left_pos_list = [(150, 500), (350, 700), (237, 452), (263, 526), (147, 678), (186, 622), (355, 543), (376, 648), (226, 724), (250, 600)]
    if adam.task_status == "following":
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

        time.sleep(0.3)


@router.post("/stop_move", summary='stop_move')
def stop_move(adam: Adam = Depends(get_adam_obj)):
    if adam.task_status == "following":
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


@router.get("/status", summary='get adam task status')
def get_status(adam: Adam = Depends(get_adam_obj)):
    # status_dict = adam.coffee_driver.query_status()
    status_dict = adam.coffee_thread.coffee_status
    logger.info('get adam task status')
    if "error" not in status_dict:
        status_dict["error"] = ""
    result = {'adam_status': adam.task_status, 'coffee_status': status_dict, 'error': adam.error_msg}
    # result = {'adam_status': adam.task_status, 'coffee_status': {'status_code': '455', 'status': 'Idle'}}
    return result


@router.get("/composition", summary='get_composition_by_option')
def get_composition(formula: str, sweetness: int = 0,
                    ice: define.SUPPORT_ICE_TYPE = define.IceType.no_ice, milk: Literal['Plant-based milk', 'Milk'] = define.MilkType.plant_based,
                    beans: define.SUPPORT_BEANS_TYPE = define.BeansType.high_roast,
                    adam: Adam = Depends(get_adam_obj)):
    logger.info('get_composition')
    try:
        if milk == 'Plant-based milk':
            milk = 'plant_milk'
        elif milk == 'Milk':
            milk = 'fresh_dairy'
        return adam.get_composition_by_option(formula, 'Medium Cup', sweetness, milk, beans, ice)
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/test_tap", summary="A-Q: 1-16 open, a-q: 1-16 closed, I: fully open, i: fully closed")
async def test_tap(command: str, adam: Adam = Depends(get_adam_obj)):
    logger.info('in test_tap')
    if adam.task_status in [define.AdamTaskStatus.idle, define.AdamTaskStatus.stopped, define.AdamTaskStatus.dead,
                            define.AdamTaskStatus.rolling]:
        logger.debug('before send')
        adam.ser.send_one_msg(command)
        logger.info('after send')
        logger.debug(f'send char {command}')
        return "ok"
    else:
        return JSONResponse(status_code=400, content={'error': 'Adam is busy now, status is {}'.format(adam.task_status)})


@router.post("/test_coffee_machine", summary="test_coffee_machine")
def test_coffee_machine(drink_num: int, adam: Adam = Depends(get_adam_obj)):
    if adam.task_status in [define.AdamTaskStatus.idle, define.AdamTaskStatus.stopped, define.AdamTaskStatus.dead,
                            define.AdamTaskStatus.rolling]:

        result = adam.coffee_driver.make_coffee(drink_num-1)
        return result
    else:
        return JSONResponse(status_code=400, content={'error': 'Adam is busy now, status is {}'.format(adam.task_status)})


@router.post("/random_dance", summary='let adam dance in music')
def random_dance(choice: int, adam: Adam = Depends(get_adam_obj)):
    logger.info('adam random_dance')
    adam.dance_random(choice)
    return 'ok'


@router.post("/zero", summary='adam goto zero position')
def zero(adam: Adam = Depends(get_adam_obj)):
    logger.info('goto zero position')
    return adam.stop_and_goto_zero(is_sleep=True)


@router.post("/standby_pose")
def standby_pose(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.goto_standby_pose()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/clean_milk_pipe", description='release_ice from ice_machine')
def clean_milk_pipe(materials: list, adam: Adam = Depends(get_adam_obj)):
    try:
        logger.info(materials)
        adam.clean_milk_pipe(materials)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/warm_up")
def warm_up(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.warm_up()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.get("/choose_speech", summary='choose_speech')
def choose_speech(type: str, formula: str = None, adam: Adam = Depends(get_adam_obj)):
    try:
        adam.choose_speech(type, formula)
        return "ok"
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/make_cold_drink", summary='make_cold_drink')
def make_cold_drink(formula: str, sweetness: int,
                    ice: define.SUPPORT_ICE_TYPE, milk: str, beans: str, task_uuid: UUID = None,
                    receipt_number: str = '', adam: Adam = Depends(get_adam_obj)):
    logger.info('make_cold_drink')
    try:
        adam.make_cold_drink(formula, sweetness, milk, beans, ice, receipt_number, task_uuid)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/make_hot_drink", summary='make_hot_drink')
def make_hot_drink(formula: str, sweetness: int,
                   ice: define.SUPPORT_ICE_TYPE, milk: str, beans: str, task_uuid: UUID = None,
                   receipt_number: str = '', adam: Adam = Depends(get_adam_obj)):
    logger.info('make_hot_drink')
    try:
        adam.make_hot_drink(formula, sweetness, milk, beans, ice, receipt_number, task_uuid)
        return 'ok'
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


# actions with left arm & right arm
@router.post("/pour", description="control adam's arm run to put the cup")
def pour(action: Literal['left', 'right'], adam: Adam = Depends(get_adam_obj)):
    try:
        adam.pour(action)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/pour_foam_cup", description="control adam's arm run to put the cup")
def pour_foam_cup(action: Literal['left', 'right'], adam: Adam = Depends(get_adam_obj)):
    try:
        adam.pour_foam_cup(action)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/stainless_cup_pour_foam", description='pour the espresso cup into the foam machine while it is on the base')
def stainless_cup_pour_foam(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.stainless_cup_pour_foam()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/pass_cup", description="Pass cup to right or left arm")
def pass_cup(action: Literal['from_left', 'from_right'], adam: Adam = Depends(get_adam_obj)):
    try:
        adam.pass_cup(action)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})
    except Exception as e:
        logger.debug(repr(e))
        logger.debug(str(e))


# left actions
@router.post("/take_hot_cup", description='take cup from left side of adam')
def take_hot_cup(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.take_hot_cup()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/take_coffee_machine", description='make coffee from coffee_machine')
def take_coffee_machine(formula: str, need_adjust: Literal['true', 'false'],
                        adam: Adam = Depends(get_adam_obj)):
    try:
        composition = adam.get_composition_by_option(formula, 'Medium Cup', 100, 'fresh_dairy')
        coffee_machine = composition.get('coffee_machine', {})
        logger.debug('coffee_machine = {}'.format(coffee_machine))
        need_adjust = True if need_adjust == 'true' else False
        adam.take_coffee_machine(coffee_machine, need_adjust=need_adjust)
        return 'ok'
    except Exception as e:
        raise e
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/take_ingredients", description='take cup from left side of adam')
def take_ingredients(arm: Literal['left', 'right'], formula: str, adam: Adam = Depends(get_adam_obj)):
    try:
        composition = adam.get_composition_by_option(formula, 'Medium Cup', 100, 'fresh_dairy')
        adam.take_ingredients(arm, composition.get('tap', {}))
        return 'ok'
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/take_ingredients_foam", description='take cup from left side of adam')
def take_ingredients_foam(arm: Literal['left', 'right'], formula: str, adam: Adam = Depends(get_adam_obj)):
    try:
        composition = adam.get_composition_by_option(formula, 'Medium Cup', 100, 'fresh_dairy')
        adam.take_ingredients_foam(arm, composition.get('tap', {}))
        return 'ok'
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/put_hot_cup", description='take cup from right side of adam')
def put_hot_cup(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.put_hot_cup()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


# right actions
@router.post("/take_cold_cup", description='take cup from right side of adam')
def take_cold_cup(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.take_cold_cup()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/take_foam_cup", description='take foam cup')
def take_foam_cup(arm: Literal['left', 'right'], is_move: Literal['true', 'false'], is_waiting: Literal['true', 'false'],
                  adam: Adam = Depends(get_adam_obj)):
    try:
        adam.take_foam_cup(arm, is_waiting=is_waiting, is_move=is_move)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/take_espresso_cup", description='take espresso cup from the right side of Adam')
def take_espresso_cup(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.take_espresso_cup()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/take_ice", description='take ice from ice_machine')
def take_ice(delay_time: float, adam: Adam = Depends(get_adam_obj)):
    try:
        time.sleep(3)
        adam.take_ice(delay_time)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/release_ice", description='release_ice from ice_machine')
def release_ice(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.release_ice()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/make_foam", description='take milk from tap and make foam')
def make_foam(formula: str, arm: Literal['left', 'right'], adam: Adam = Depends(get_adam_obj)):
    try:
        composition = adam.get_composition_by_option(formula, 'Medium Cup', 100, 'fresh_dairy')
        adam.make_foam(composition.get(define.Constant.MachineType.foam_machine, {}), arm)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})



@router.post("/clean_foamer", description='take cup from left side of adam')
def clean_foamer(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.clean_foamer()
        return 'ok'
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/put_foam_cup", description='take foam cup')
def put_foam_cup(arm: Literal['left', 'right'], adam: Adam = Depends(get_adam_obj)):
    try:
        adam.put_foam_cup(arm)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/clean_and_put_espresso_cup", description='take espresso cup')
def clean_and_put_espresso_cup(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.clean_and_put_espresso_cup()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})

@router.post("/get_current_position", description='gives the current position of the arm')
def get_current_position(arm: Literal['left', 'right'], adam: Adam = Depends(get_adam_obj)):
    try:
        current_position = adam.current_position(arm)
        return JSONResponse(status_code=200, content={'success': str(current_position)})
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})
    

@router.post("/put_cold_cup", description='take cup from right side of adam')
def put_cold_cup(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.put_cold_cup()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})

@router.post("/dance", summary='let adam dance in music')
def dance(adam: Adam = Depends(get_adam_obj)):
    logger.info('adam dance')
    adam.dance_in_thread()
    return 'ok'


@router.post("/dance1", summary='let adam dance in music')
def dance1(adam: Adam = Depends(get_adam_obj)):
    logger.info('adam dance')
    adam.dance1_in_thread()
    return 'ok'


@router.get("/tap_status", summary='get tap status')
def get_tap_status():
    logger.info('get_tap_status')
    result = adam_crud.get_all_status()
    logger.info(result)
    return result


@router.post("/clean_tap", summary='clean tap')
async def open_tap(name: str, action: Literal['0', '1'], background_tasks: BackgroundTasks, adam: Adam = Depends(get_adam_obj)):
    logger.info('in open tap')
    if adam.task_status in [define.AdamTaskStatus.idle, define.AdamTaskStatus.stopped, define.AdamTaskStatus.dead,
                            define.AdamTaskStatus.rolling]:
        tap_configs = CoffeeInterface.get_machine_config(machine=define.Constant.MachineType.tap)
        arduino_write_dict = {i.get('name'): i.get('arduino_write') for i in tap_configs}
        if action == '1':
            logger.debug('before send')
            adam.ser.send_one_msg(arduino_write_dict.get(name))
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
            adam.ser.send_one_msg(close_char)
            logger.info('after send')
            adam_crud.update_one_tap(name, 0)
        return adam_crud.get_all_status()[name]
    else:
        return JSONResponse(status_code=400,
                            content={'error': 'Adam is busy now, status is {}'.format(adam.task_status)})

@router.post("/arduino/close_cleaning")
def cleaning(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.ser.send_one_msg('i')
        adam_crud.init_tap()
        return adam_crud.get_all_status()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/arduino/one_msg")
def cleaning(char, adam: Adam = Depends(get_adam_obj)):
    try:
        adam.ser.send_one_msg(char[0])
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/clean_the_brewer", summary='clean_the_milk_froth')
def clean_the_brewer(background_tasks: BackgroundTasks, adam: Adam = Depends(get_adam_obj)):
    if adam.coffee_driver.query_status().get('status_code') != 255:
        AudioInterface.gtts('/richtech/resource/audio/voices/coffee_machine_busy.mp3')
        return JSONResponse(status_code=510, content={'error': 'Coffee machine is busy now, please wait sometime'})
    # adam.coffee_driver.select_clean(4)
    for i in range(6):
        if i != 4:
            is_clean_close = False
            adam.coffee_driver.select_clean(i + 1)
            while not is_clean_close:
                time.sleep(2)
                status_dict = adam.coffee_driver.query_status()
                if status_dict:
                    if status_dict["status_code"] == 255:
                        is_clean_close = True
                else:
                    time.sleep(1)
    CoffeeInterface.add_cleaning_history({"coffee_machine": 0}, 2)
    # clean_history = CoffeeInterface.get_last_one_clean_history()
    # background_tasks.add_task(ASWServerInterface.add_cleaning_history, clean_history)
    return 'ok'


@router.post("/clean_the_milk_froth", summary='clean_the_milk_froth')
def clean_the_milk_froth(adam: Adam = Depends(get_adam_obj)):
    if adam.coffee_driver.query_status().get('system_status') != MachineStatus.idle:
        AudioInterface.gtts('/richtech/resource/audio/voices/coffee_machine_busy.mp3')
        return JSONResponse(status_code=510, content={'error': 'Coffee machine is busy now, please wait sometime'})
    AudioInterface.gtts('/richtech/resource/audio/voices/coffee_machine_clean_button.mp3')
    adam.coffee_driver.clean_the_milk_froth()
    while True:
        if adam.coffee_driver.query_status().get('system_status') == MachineStatus.idle:
            break
        else:
            time.sleep(1)
    return 'ok'


@router.post("/stop", summary='adam stop all action')
def stop(adam: Adam = Depends(get_adam_obj)):
    logger.info('adam stop all action by http request')
    return adam.stop()


@router.post("/resume", summary='adam enable')
def resume(adam: Adam = Depends(get_adam_obj)):
    logger.info('adam enable')
    return adam.resume()


@router.post("/roll")
def roll(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.roll()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/open_gripper")
def open_gripper(which: Literal['left', 'right'], position: int, adam: Adam = Depends(get_adam_obj)):
    try:
        adam.goto_gripper_position(which, position)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/manual")
def manual(which: Literal['left', 'right'], action: Literal['close', 'open'], adam: Adam = Depends(get_adam_obj)):
    try:
        if action == 'open':
            return adam.manual(which, mode=2)
        else:
            return adam.manual(which, mode=0)
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/init")
def init(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.init_adam()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/coffee_status")
def roll(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.coffee_driver.query_status()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/coffee_make")
def roll(formula: str, adam: Adam = Depends(get_adam_obj)):
    try:
        composition = adam.get_composition_by_option(formula, 'Medium Cup', 100, 'fresh_dairy')
        coffee_machine = composition.get('coffee_machine', {})
        for name, config in coffee_machine.items():
            adam.coffee_driver.make_coffee_from_dict(config.get('coffee_make'))
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/query_coffee_status")
def query_coffee_status(adam: Adam = Depends(get_adam_obj)):
    try:
        result = Coffee_Driver(adam.coffee_device_name).query_status()
        return result
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/control_make_coffee")
def control_make_coffee(control_content: str, adam: Adam = Depends(get_adam_obj)):
    try:
        control_content = int(control_content, 16)
        result = Coffee_Driver(adam.coffee_device_name).make_coffee(control_content)
        return result
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.get("/get_dance_list", summary='get dance list')
def get_dance_list(db: Session = Depends(get_db)):
    try:
        logger.info('get dance_list')
        result = adam_crud.get_dance_list(db)
        logger.info(result)
        return result
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.get("/get_now_playing", summary='get_now_playing')
def get_now_playing(db: Session = Depends(get_db)):
    try:
        logger.info('get now_playing')
        result = adam_crud.get_now_playing(db)
        # logger.info(result)
        return result
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/update_dance", summary='update dance list')
def update_dance(dance_list: List, db: Session = Depends(get_db)):
    try:
        logger.info(f'update dance : {dance_list} ')
        adam_crud.init_dance(db)
        adam_crud.init_dance_display(db)
        adam_crud.update_dance(db, dance_list)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/update_single_dance", summary='update single dance')
def update_single_dance(dance_num: int, now_playing: int, db: Session = Depends(get_db)):
    try:
        logger.info('update single dance')
        adam_crud.update_single_dance(db, dance_num, now_playing)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/init_dance", summary='get dance list')
def init_dance(db: Session = Depends(get_db)):
    try:
        logger.info('init dance')
        adam_crud.init_dance(db)
        return 'ok'
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/proceed_dance", summary='proceed_dance')
def proceed_dance(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.dance_thread.proceed()
        return 'ok'
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/pause_dance", summary='pause_dance')
def pause_dance(adam: Adam = Depends(get_adam_obj)):
    try:
        try:
            adam.dance_thread.pause()
        except Exception as e:
            pass
        return adam.stop_and_goto_zero(is_sleep=True)
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/CountdownTime", summary='pause_dance')
def CountdownTime(time: int, adam: Adam = Depends(get_adam_obj)):
    try:
        adam.timing = time * 60
        adam.countdownTimer.edit_initial_time(adam.timing)
        adam.countdownTimer.start()
        return 'ok'
    except Exception as e:
        logger.error(traceback.formate_exc())
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/set_dance_time", summary='pause_dance')
def set_dance_time(time: int, adam: Adam = Depends(get_adam_obj)):
    try:
        adam.timing = time * 60
        adam.countdownTimer.set_time(adam.timing)
        return 'ok'
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/stop_CountdownTime", summary='stop_CountdownTime')
def stop_CountdownTime(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.countdownTimer.stop()
        # return 'ok'
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/stop_followCountdownTimer", summary='stop_CountdownTime')
def stop_followCountdownTimer(adam: Adam = Depends(get_adam_obj)):
    try:
        if adam.task_status == "following":
            adam.followCountdownTimer.stop()
        return 'ok'
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': str(e)})



@router.get("/get_setting_time", summary='get_setting_time')
def get_setting_time(adam: Adam = Depends(get_adam_obj)):
    try:
        return str(int(adam.timing / 60))
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/enable_visual_recognition", summary='enable_visual_recognition')
def enable_visual_recognition(state: int, adam: Adam = Depends(get_adam_obj)):
    try:
        if state == 0:
            adam.enable_visual_recognition = False
        else:
            adam.enable_visual_recognition = True
        return adam.enable_visual_recognition
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/open_idle_Interaction", summary='open idle Interaction')
def open_idle_Interaction(state: int, threshold: int, adam: Adam = Depends(get_adam_obj)):
    try:
        result_dict = {}
        result_dict['state'] = state
        result_dict['threshold'] = threshold
        conf.set_idle_Interaction(result_dict)
        return result_dict
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.get("/get_idle_Interaction_state", summary='open idle Interaction')
def get_idle_Interaction_state(adam: Adam = Depends(get_adam_obj)):
    try:
        result_dict = {}
        idle_dict = conf.get_idle_Interaction()
        result_dict['state'] = int(idle_dict['state'])
        result_dict['threshold'] = int(idle_dict['threshold'])
        return result_dict
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': str(e)})

