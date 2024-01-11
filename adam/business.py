import json
import math
import os
import random
import threading
import time
import csv
import traceback
from copy import deepcopy
from typing import Literal

from loguru import logger
from serial import Serial
from xarm.wrapper import XArmAPI

from common import define, utils, conf
from common.api import ExceptionInterface, AudioInterface, CoffeeInterface, CenterInterface, ASWServerInterface, VisualDetectInterface
from common.define import ExceptionType, Arm, AdamTaskStatus, audio_dir
from common.schemas import adam as adam_schema
from common.schemas import common as common_schema
from common.schemas import total as total_schema
from common.db.crud import adam as adam_crud
from common.db.database import MySuperContextManager
from common.myerror import MoveError, FormulaError, MaterialError, CoffeeError, StopError
from init import EnvConfig
from back import RecordThread
from coffee_device import Coffee_Driver
from devices.coffee.constant import MachineStatus as CoffeeMachineStatus, COFFEE_STATUS, SPEAK_STATUS
from devices.conveyer import TakeConveyer, Conveyer
from check import CheckThread

from devices.coffee.serial_device import Serial_Pump

from detect_cup import DetectCupStandThread
from detect_person import DetectPersonThread  # 英伟达

from dance import DanceThread, CountdownTimer, FollowCountdownTimer

def get_adam_obj():
    """
    Adam对象只创建一次
    """
    if not Adam.Instance:
        Adam.Instance = Adam()
    return Adam.Instance


class Adam:
    Instance = None

    def __init__(self):
        # adam所处环境的配置
        self.machine_config = total_schema.MachineConfig(**conf.get_machine_config())
        # adam机器人本身的配置
        self.adam_config = adam_schema.AdamConfig(**conf.get_adam_config())
        self.env = EnvConfig(self.machine_config, self.adam_config)
        self.left, self.right = self.env.left, self.env.right

        self.tap_device_name = self.env.machine_config.adam.tap_device
        self.coffee_device_name = self.env.machine_config.adam.coffee_device
        self.ser = Serial_Pump(self.tap_device_name)

        self.is_goto_work_zero = False

        adam_crud.init_tap()
        self.ser.send_one_msg('i')

        connect_coffee_fail_count = 0

        self.coffee_driver = None  # remove later

        # Comment back in to allow the coffee machine to work
        for i in range(5):
            try:
                logger.info('in {}th connect coffee machine'.format(i + 1))
                self.coffee_driver = Coffee_Driver(self.coffee_device_name)
                # self.coffee_status = self.coffee_driver.last_status
                break
            except Exception as e:
                logger.warning('connect error , {}'.format(str(e)))
                connect_coffee_fail_count += 1
                time.sleep(1)
        if connect_coffee_fail_count >= 5:
            logger.error('Failed to connect to the coffee machine. Please check the device name.')
            AudioInterface.gtts('Failed to connect to the coffee machine. Please check the device name.')
            exit(-1)
        self.task_status = None

        # 程序上电就会强制回零点
        self.check_adam_goto_initial_position()
        self.task_status = AdamTaskStatus.idle
        self.cup_env = self.env.machine_config.cup_env
        self.current_cup_name = define.CupName.hot_cup
        self.ice_num = 0
        self.put_hot_cup_index = 0
        self.put_cold_cup_index = 0

        self.left_record = RecordThread(self.left, self.env.get_record_path('left'), 'left arm')
        self.right_record = RecordThread(self.right, self.env.get_record_path('right'), 'right arm')
        self.left_roll_end = True
        self.right_roll_end = True
        self.init_record()
        self.thread_lock = threading.Lock()

        # Comment back in to allow the coffee machine to work
        self.coffee_thread = QueryCoffeeThread(self.coffee_driver)
        self.coffee_thread.setDaemon(True)
        self.coffee_thread.start()

        # # detect cup 视觉识别杯子识别
        # self.detect_cup_thread = DetectCupStandThread()
        # self.detect_cup_thread.setDaemon(True)
        # self.detect_cup_thread.start()
        #
        # # detect person 视觉识别人物识别
        # self.detect_person_thread = DetectPersonThread()
        # self.detect_person_thread.setDaemon(True)
        # self.detect_person_thread.start()

        # dance threading 跳舞线程
        self.dance_thread = DanceThread()
        self.dance_thread.setDaemon(True)
        self.dance_thread.start()

        self.put_foam_flag = False  # put foam cup sign 放奶泡杯标志

        self.error_msg = []

        self.is_coffee_finished = False  # coffee completed sign 咖啡完成标志

        # self.open_idle_Interaction = False  # idle interaction turn on state 空闲交互开启状态
        # self.threshold = 0  # Idle interaction start probability  空闲交互启动概率

        self.timing = 20 * 60  # Countdown time 倒计时时间  Unit: s
        self.countdownTimer = CountdownTimer()  # countdown object 倒计时对象

        self.followCountdownTimer = FollowCountdownTimer()  # follow countdown object 跟随倒计时对象

        self.enable_visual_recognition = False  # visual identity open sign 视觉识别开启标识

        AudioInterface.gtts('/richtech/resource/audio/voices/ready.mp3')

    def init_record(self):
        """
        init record thread
        pause until get an order
        """
        self.left_record.setDaemon(True)
        self.right_record.setDaemon(True)
        self.left_record.clear()
        self.right_record.clear()
        self.left_record.start()
        self.left_record.pause()
        self.right_record.start()
        self.right_record.pause()

    def manual_before_start(self):
        AudioInterface.gtts('/richtech/resource/audio/voices/init_manual_on.mp3', True)
        self.manual(Arm.left)
        self.manual(Arm.right)
        time.sleep(15)
        AudioInterface.gtts('/richtech/resource/audio/voices/init_manual_off.mp3', True)
        time.sleep(3)
        self.manual(Arm.left, 0)
        self.manual(Arm.right, 0)

    def test_arduino(self, char):
        self.arduino.arduino.open()
        self.arduino.arduino.send_one_msg(char)
        self.arduino.arduino.close()

    # left actions
    def take_hot_cup(self):
        """
        右手取热咖杯子，一旦取杯子就认为开始做咖啡了
        """
        logger.info('take_hot_cup')
        pose_speed = 500
        angle_speed = 200

        cup_config = self.get_cup_config(define.CupName.hot_cup)
        self.current_cup_name = cup_config.name
        logger.info('now take {} cup'.format(cup_config.name))
        cup_pose = deepcopy(cup_config.pose)
        which = Arm.right

        # self.safe_set_state(Arm.right, 0)
        # time.sleep(0.1)
        #
        # self.goto_initial_position_direction(which, 0, wait=False, speed=pose_speed)

        def take_cup():
            # 计算旋转手臂到落杯器的角度
            up_take_pose = deepcopy(cup_pose)
            self.goto_gripper_position(which, self.env.gripper_open_pos)  # 先张开夹爪
            self.goto_angles(which, adam_schema.Angles.list_to_obj([-237.4, -25.6, -29.2, 75.2, 110.5, -215.9]), wait=True, speed=angle_speed)
            self.goto_temp_point(which, z=cup_pose.z, speed=pose_speed, wait=True)  # 运动到抓杯位置
            self.goto_gripper_position(which, cup_config.clamp, wait=True)  # 闭合夹爪
            logger.info(f'take cup with clamp = {cup_config.clamp}')
            self.env.one_arm(which).set_collision_sensitivity(cup_config.collision_sensitivity)  # 设置灵敏度，根据实际效果确定是否要注释
            self.safe_set_state(Arm.right, 0)
            time.sleep(0.5)
            
            code, gripper_pose = self.env.one_arm(which).get_gripper_position()  # first获取夹爪的张合度 CT
            logger.info(f'first take cup with clamp = {gripper_pose}')
            self.goto_temp_point(which, z=cup_pose.z + 170, speed=150, wait=True)  # 向上拔杯子
            code1, gripper_pose1 = self.env.one_arm(which).get_gripper_position()  # second获取夹爪的张合度 CT
            logger.info(f'second take cup with clamp = {gripper_pose1}')
            self.env.one_arm(which).set_collision_sensitivity(
                self.env.adam_config.same_config.collision_sensitivity)  # 恢复灵敏度，与上方设置灵敏度一起注释或一起放开
            self.safe_set_state(Arm.right, 0)
            time.sleep(0.5)
            return gripper_pose, gripper_pose1

        is_gripper_flag = True  # CT gripper or not
        take_cup_num = 0
        try:
            while is_gripper_flag:
                gripper_pose, gripper_pose1 = take_cup()
                if gripper_pose1 < cup_config.clamp + 4:
                    logger.info('++++++++++++++++++++++++++++++++++++++++++++++++++++++')
                    logger.info('take cup fail，gripper_pose = {}'.format(gripper_pose1))
                    take_cup_num += 1
                    if take_cup_num > 5:
                        AudioInterface.gtts(f'{which} arm take cup fail')
                        self.stop(f'{which} arm take cup fail')
                        # raise MoveError(f'{which} arm take cup fail')
                    cup_config.clamp -= 10  # 每次没有抓起来都会将夹爪张合度-3

                    # is_gripper_flag = False  # test use

                else:
                    logger.info('++++++++++++++++++++++++++++++++++++++++++++++++++++++')
                    logger.info('take cup success，gripper_pose = {}'.format(gripper_pose1))
                    is_gripper_flag = False

            self.goto_angles(which, adam_schema.Angles.list_to_obj([-209.4, -22.6, -39.0, 90.3, 89.5, -28.3]), wait=False, speed=angle_speed)
            # self.goto_initial_position_direction(which, 0, wait=True, speed=pose_speed)  # Do not change the wait the false. Changing it to false will make the arm move slow when going to the coffee machine

            # After grabbing the cup, open the jaws a little
            # self.goto_gripper_position(which, cup_config.clamp + 200, wait=True)

            CoffeeInterface.post_use(define.CupName.hot_cup, 1)  # 热咖杯子数量-1

        except Exception as e:
            self.stop(str(e))

    def take_coffee_machine(self, composition: dict, formula=None, cmd_sent=False, type=None, need_adjust=False, is_take_espresso_cup=False,
                            is_take_hot_cup=False):
        """
        "latte": {
            "count": 60,
            "coffee_make": {"drinkType": 1, "volume": 60, "coffeeTemperature": 2, "concentration": 1, "hotWater": 0,
                        "waterTemperature": 0, "hotMilk": 0, "foamTime": 0, "precook": 0, "moreEspresso": 0,
                        "coffeeMilkTogether": 0, "adjustOrder": 1}
            }Espresso
        """
        logger.info('take_coffee_machine with composition = {}'.format(composition))
        pose_speed = 300  # 800
        angle_speed = 50
        coffee_pose = deepcopy(self.env.machine_config.coffee_machine.pose)
        before_coffee_pose = deepcopy(coffee_pose)
        before_coffee_pose.x = 663.7
        before_coffee_pose.y = -567.7
        before_coffee_pose.z = 181.1
        before_coffee_pose.roll = 0
        cup_config = self.get_cup_config(define.CupName.hot_cup)
        which = Arm.right
        if composition:
            self.coffee_thread.pause()

            if is_take_espresso_cup:
                # judge espresso cup does it exist
                # ********************************
                if self.enable_visual_recognition:
                    check_cup = True
                    start_time = time.time()
                    play_num = 1
                    while check_cup:
                        espresso_cup_list = CoffeeInterface.get_detect_all_data("espresso_cup")
                        logger.info(f"espresso_cup_list {espresso_cup_list}")
                        if espresso_cup_list[0]["status"] == "1":
                            check_cup = False
                            # break
                        if check_cup == True:
                            time.sleep(4)
                            if time.time() - start_time > 10 * play_num:
                                play_num += 1
                                AudioInterface.gtts('espresso cup is not there, please check')
                # ********************************

            def goto_coffee_pose(coffee_pose):
                logger.info("There is coffee_pose: {}".format(coffee_pose))
                if is_take_hot_cup:
                    logger.info("Now grabbing the hot cup")
                    self.take_hot_cup()
                if is_take_espresso_cup:
                    logger.info("Now grabbing the espresso cup")
                    self.take_espresso_cup()
                if need_adjust:  # Need to remove need_adjust in the future, not using anymore
                    self.goto_point(which, before_coffee_pose, speed=pose_speed,
                                    wait=False)  # If a hot drink was ordered this motion will move very slow if the last wait in take_hot_cup is False.
                    self.goto_point(which, coffee_pose, wait=True, speed=pose_speed)
                    # self.goto_gripper_position(which, self.env.gripper_open_pos)
                else:
                    self.goto_point(which, before_coffee_pose, speed=pose_speed,
                                    wait=False)  # If a hot drink was ordered this motion will move very slow if the last wait in take_hot_cup is False.
                    self.goto_point(which, coffee_pose, wait=True, speed=pose_speed)

                if conf.get_idle_Interaction()['state']:
                    self.idle_interaction(formula, type)

            def make_coffee(composition):
                for name, config in composition.items():
                    check_thread = CheckThread(self.env.one_arm(which), self.stop)
                    self.coffee_thread.pause()
                    try:
                        check_thread.start()
                        coffee_dict = config.get('coffee_make')
                        self.coffee_thread.pause()

                        status_dict = self.coffee_driver.query_status()
                        if status_dict == {}:
                            while True:
                                time.sleep(1)
                                status_dict = self.coffee_driver.query_status()
                                if status_dict != {}:
                                    break
                        status_code = status_dict.get('status_code')
                        status = status_dict.get('status')
                        error_code = status_dict.get('error_code', '')
                        error = status_dict.get('error', '')
                        logger.info(f"status_dict:{status_dict}")
                        logger.info(f'coffee_dict["drinkType"]:{coffee_dict["drinkType"]}')
                        while True:
                            if status_code == 255 and error == '':
                                start_time = time.time()
                                send_flag = self.coffee_driver.make_coffee(coffee_dict["drinkType"])
                                end_time = None
                                if send_flag:
                                    end_time = time.time() - start_time
                                    # CoffeeInterface.add_formula_duration(formula, int(end_time),1,1)
                                    break
                            if error_code:
                                # 制作过程中有报错信息，立刻抛出异常
                                logger.error(error)
                                # if error_code in [15, 16, 17, 18, 19, 20, 21, 23, 24, 25, 26, 27, 28, 29, 30, 75]:
                                AudioInterface.gtts(f"error is {error},Wait 5 minutes")
                                wait_num = 0
                                while True:
                                    if wait_num > 30:
                                        raise CoffeeError(
                                            f'Failed to make coffee. The coffee machine error is {error}')
                                    time.sleep(10)
                                    wait_num += 1
                                    logger.info(f"waiting process error ,time:{wait_num * 10}")
                                    status_dict = self.coffee_driver.query_status()
                                    logger.info(f"status_dict:{status_dict}")
                                    status_code = status_dict.get('status_code')
                                    status = status_dict.get('status')
                                    error_code = status_dict.get('error_code', '')
                                    error = status_dict.get('error', '')
                                    if status_code == 255 and error_code == '':
                                        logger.debug('Preparing to remake coffee')
                                        send_flag = self.coffee_driver.make_coffee(coffee_dict["drinkType"])
                                        if send_flag:
                                            break
                                break
                            if status_code != 255:
                                AudioInterface.gtts(f"The coffee machine is {status},Wait 5 minutes")
                                wait_num = 0
                                while True:
                                    if wait_num > 30:
                                        raise CoffeeError(
                                            f'Failed to make coffee. The coffee machine error is {status}')
                                    time.sleep(10)
                                    wait_num += 1
                                    logger.info(f"waiting process error ,time:{wait_num * 10}")
                                    status_dict = self.coffee_driver.query_status()
                                    logger.info(f"status_dict:{status_dict}")
                                    status_code = status_dict.get('status_code')
                                    status = status_dict.get('status')
                                    error_code = status_dict.get('error_code', '')
                                    if status_code == 255 and error_code == '':
                                        logger.debug('Preparing to remake coffee')
                                        send_flag = self.coffee_driver.make_coffee(coffee_dict["drinkType"])
                                        if send_flag:
                                            break
                                break
                        self.coffee_thread.proceed()
                        self.is_coffee_finished = True
                    except CoffeeError as e:
                        if isinstance(e, CoffeeError):
                            AudioInterface.gtts(str(e))
                        self.stop(str(e))
                    except Exception as e:
                        logger.error(traceback.format_exc())
                        logger.error(str(e))
                        raise e
                    finally:
                        check_thread.stop()

            step1_thread = [threading.Thread(target=goto_coffee_pose, args=(coffee_pose,)),
                            threading.Thread(target=make_coffee, args=(composition,))]
            logger.info("Begin the thread")
            for t in step1_thread:
                t.start()
            for t in step1_thread:
                t.join()
            logger.info("The threads are done")

            try:
                self.check_adam_status('take_coffee_machine', status=AdamTaskStatus.making)  # 判断机械臂在子线程中是否有动作失败，有错误及时抛出异常
                logger.info("No issues with the status")
                self.goto_point(which, before_coffee_pose, speed=150, wait=True)
                # self.goto_angles(which, adam_schema.Angles.list_to_obj([-209.4, -22.6, -39.0, 90.3, 89.5, -28.3]), wait=False, speed=angle_speed) # Right arm zero position
                # init_pose = self.initial_position(which)
                # self.goto_point(which, init_pose, wait=True, speed=pose_speed, radius=0)  # 做完咖啡回退 After filling the cup with coffee, the arm moves away from the coffee machine into a safe position for it to return to initial position.
                logger.info("Take_coffee_machine is done")
            except StopError as stop_err:
                raise stop_err
            except MoveError as e:
                raise e
            except Exception as e:
                raise e

    def take_ingredients(self, arm, composition: dict):
        """
        从龙头接糖浆等配料，根据arm参数决定左手接还是右手接
        arm: left or right 左手或右手
        composition: {'material_name': quantity, 'chocolate_syrup': 100}
        """
        logger.info('{} arm take_ingredients {}'.format(arm, composition))
        try:
            if composition:
                pose_speed = 300  # 500
                tap_pose = deepcopy(self.env.machine_config.gpio.tap.pose)
                which = arm
                tap_pose.roll = self.get_xy_initial_angle(which, tap_pose.x, tap_pose.y)
                take_pose = deepcopy(tap_pose)
                # take_pose.z = 140  # 170
                first_run_flag = True
                self.thread_lock.acquire()
                for name, quantity in composition.items():
                    if first_run_flag:
                        self.goto_initial_position_direction(which, tap_pose.roll, wait=False, speed=pose_speed)
                        self.goto_point(which, take_pose, wait=True, speed=pose_speed)  # 运动到龙头下方位置
                        self.check_adam_pos(which, [take_pose.x, take_pose.y, take_pose.z, take_pose.roll, take_pose.pitch,
                                                    take_pose.yaw], 'take_ingredients open port')
                        first_run_flag = False
                        move = True
                    CoffeeInterface.post_use(name, quantity)
                logger.debug('arduino open_dict = {}'.format(composition))
                check_thread = CheckThread(self.env.one_arm(which), self.stop)
                try:
                    check_thread.start()
                    self.ser.open_port_together_by_speed(composition)
                    CenterInterface.update_last_milk_time(list(composition.keys()))
                finally:
                    check_thread.stop()

                self.thread_lock.release()
        except Exception as e:
            raise e

    def take_ingredients_foam(self, arm, composition: dict):
        """
        从龙头接糖浆等配料，根据arm参数决定左手接还是右手接
        arm: left or right 左手或右手
        composition: {'material_name': quantity, 'chocolate_syrup': 100}
        """
        logger.info('{} arm take_ingredients {}'.format(arm, composition))
        try:
            pose_speed = 300  # 500
            tap_pose = deepcopy(self.env.machine_config.gpio.tap.pose)
            which = arm
            tap_pose.roll = self.get_xy_initial_angle(which, tap_pose.x, tap_pose.y)
            take_pose = deepcopy(tap_pose)
            first_run_flag = True
            self.thread_lock.acquire()
            for name, quantity in composition.items():
                if first_run_flag:
                    self.goto_point(which, take_pose, wait=True, speed=pose_speed)  # 运动到龙头下方位置
                    self.check_adam_pos(which, [take_pose.x, take_pose.y, take_pose.z, take_pose.roll, take_pose.pitch,
                                                take_pose.yaw], 'take_ingredients open port')
                    first_run_flag = False
                CoffeeInterface.post_use(name, quantity)
            logger.debug('arduino open_dict = {}'.format(composition))
            check_thread = CheckThread(self.env.one_arm(which), self.stop)

            try:
                check_thread.start()
                self.ser.open_port_together_by_speed(composition)
                CenterInterface.update_last_milk_time(list(composition.keys()))
            finally:
                check_thread.stop()
            self.thread_lock.release()
        except Exception as e:
            raise e

    def put_cold_cup(self, cup=None, task_uuid=None):
        logger.info('put_cold_cup')
        pose_speed = 125  # 250
        # **********************************************
        if not self.enable_visual_recognition:
            put_config = [i for i in self.env.machine_config.put if i.name == define.CupName.cold_cup][0]
            put_pose = deepcopy(put_config.pose)
            which = self.env.left_or_right(put_pose.y)  # Arm.left
            self.put_cold_cup_index = 0
            # put_pose.y += self.put_cold_cup_index * 140
            if self.put_cold_cup_index == 0:
                table = "right_cup_stand4"
            # elif self.put_cold_cup_index == 1:
            #     table = "right_cup_stand5"
            # elif self.put_cold_cup_index == 2:
            #     table = "right_cup_stand6"
            # self.put_cold_cup_index = (self.put_cold_cup_index + 1) % 3
        # **********************************************

        # Check whether there is an empty space in the cup holder
        # **********************************************
        if self.enable_visual_recognition:
            table = None
            put_pose = None
            which = None
            check_cup = True
            start_time = time.time()
            play_num = 1
            while check_cup:
                cup_stand_list = CoffeeInterface.get_detect_all_data("right_cup")
                logger.info(f"cup_stand_list {cup_stand_list}")
                for cup_stand in cup_stand_list:
                    if cup_stand["status"] == "0":
                        for position in self.env.machine_config.put_position:
                            if position.table == cup_stand["name"]:
                                table = cup_stand["name"]
                                put_pose = deepcopy(position.pose)
                                which = self.env.left_or_right(put_pose.y)  # Arm.right
                                check_cup = False
                                break
                    if check_cup == False:
                        break
                if check_cup == True:
                    time.sleep(3)
                    if time.time() - start_time > 10 * play_num:
                        play_num += 1
                        AudioInterface.gtts('/richtech/resource/audio/voices/no_place.mp3')
        # **********************************************

        weight = self.adam_config.gripper_config['pour_ice'].tcp_load.weight
        tool_gravity = list(self.adam_config.gripper_config['pour_ice'].tcp_load.center_of_gravity.dict().values())

        temp_pose = deepcopy(put_pose)
        temp_pose.x -= 300
        self.goto_point(which, temp_pose, speed=pose_speed, wait=False)  # 放杯位置后上方
        self.goto_point(which, put_pose, wait=False, speed=pose_speed)  # 运动到放杯位置上方
        self.goto_temp_point(which, z=put_pose.z - 40, wait=True, speed=50)
        self.goto_gripper_position(which, self.env.gripper_open_pos, wait=True)  # 张开夹爪
        self.goto_temp_point(which, x=put_pose.x - 200, wait=False, speed=pose_speed)  # 放完向后退
        self.goto_point(which, self.initial_position(which), wait=False, speed=pose_speed)  # 回零点

        # Update the data in the detect table
        CoffeeInterface.update_detect_by_name(table, 1, task_uuid)

    # right actions
    def take_cold_cup(self):
        """
        左手取冷咖杯子，一旦取杯子就认为开始做咖啡了
        """
        pose_speed = 500
        angle_speed = 200
        logger.info('take_cold_cup')

        cup_config = self.get_cup_config(define.CupName.cold_cup)
        self.current_cup_name = cup_config.name
        logger.info('now take {} cup'.format(cup_config.name))
        cup_pose = deepcopy(cup_config.pose)

        which = Arm.left

        # self.safe_set_state(Arm.left, 0)
        # time.sleep(0.1)
        # self.goto_initial_position_direction(which, 0, wait=False, speed=pose_speed)

        def take_cup():
            # 计算旋转手臂到落杯器的角度
            cup_pose.roll = self.get_xy_initial_angle(which, cup_pose.x, cup_pose.y)
            self.goto_gripper_position(which, self.env.gripper_open_pos)  # 先张开夹爪
            self.goto_angles(which, adam_schema.Angles.list_to_obj([245.7, -39.3, -36.2, -79.8, 124.3, 198.5]), wait=True, speed=angle_speed)
            self.goto_temp_point(which, z=cup_pose.z, speed=pose_speed, wait=True)  # 运动到抓杯位置
            self.goto_gripper_position(which, cup_config.clamp, wait=True)  # 闭合夹爪
            logger.info('take cup with clamp = {}'.format(cup_config.clamp))
            self.env.one_arm(which).set_collision_sensitivity(cup_config.collision_sensitivity)  # 设置灵敏度，根据实际效果确定是否要注释
            self.safe_set_state(Arm.left, 0)
            time.sleep(0.5)
            code, gripper_pose = self.env.one_arm(which).get_gripper_position()  # first获取夹爪的张合度 CT
            logger.info(f'first take cup with clamp = {gripper_pose}')
            self.goto_temp_point(which, z=cup_pose.z + 170, speed=pose_speed, wait=True)  # 向上拔杯子
            code1, gripper_pose1 = self.env.one_arm(which).get_gripper_position()  # second获取夹爪的张合度 CT
            logger.info(f'second take cup with clamp = {gripper_pose1}')
            self.env.one_arm(which).set_collision_sensitivity(
                self.env.adam_config.same_config.collision_sensitivity)  # 恢复灵敏度，与上方设置灵敏度一起注释或一起放开
            self.safe_set_state(Arm.left, 0)
            time.sleep(0.5)
            return gripper_pose, gripper_pose1

        is_gripper_flag = True  # CT gripper or not
        take_cup_num = 0
        try:
            while is_gripper_flag:
                gripper_pose, gripper_pose1 = take_cup()
                # if gripper_pose < cup_config.clamp + 3 and gripper_pose1 < cup_config.clamp + 3:
                if gripper_pose1 < cup_config.clamp:
                    logger.info('++++++++++++++++++++++++++++++++++++++++++++++++++++++')
                    logger.info('take cup fail，gripper_pose = {}'.format(gripper_pose))
                    take_cup_num += 1
                    if take_cup_num > 5:
                        AudioInterface.gtts(f'{which} arm take cup fail')
                        self.stop(f'{which} arm take cup fail')
                    cup_config.clamp -= 3  # 每次没有抓起来都会将夹爪张合度-3

                    # is_gripper_flag = False

                else:
                    logger.info('++++++++++++++++++++++++++++++++++++++++++++++++++++++')
                    logger.info('take cup success，gripper_pose = {}'.format(gripper_pose))
                    is_gripper_flag = False

            self.goto_angles(which, adam_schema.Angles.list_to_obj([209.4, -22.7, -39, -90.3, 89.5, 28.3]), wait=False,
                             speed=pose_speed)  # Zero position for the left arm
            # self.goto_initial_position_direction(which, 0, wait=False, speed=pose_speed)

            # After grabbing the cup, open the jaws a little
            # self.goto_gripper_position(which, cup_config.clamp + 200, wait=True)

            CoffeeInterface.post_use(define.CupName.cold_cup, 1)  # 冷咖杯子数量-1
        except Exception as e:
            logger.info("Exception is {}".format(e))
            self.stop('error in take_cold_cup: {}'.format(str(e)))

    def take_foam_cup_judge(self, arm):
        logger.info('take_foam_cup_judge')
        cup_config = self.get_cup_config(define.CupName.cold_cup)
        foam_cup_config = deepcopy(self.env.machine_config.shaker)
        take_pose = deepcopy(foam_cup_config.pose.take)
        pose_speed = 500  # 800
        which = arm

        weight = self.adam_config.gripper_config['pour_ice'].tcp_load.weight
        tool_gravity = list(self.adam_config.gripper_config['pour_ice'].tcp_load.center_of_gravity.dict().values())
        self.right.set_tcp_load(weight=weight, center_of_gravity=tool_gravity)

        self.goto_initial_position_direction(which, 0, wait=False, speed=pose_speed)  # 转向奶泡杯方向

        # judge foam cup does it exist
        # *****************************
        if self.enable_visual_recognition:
            check_cup = True
            start_time = time.time()
            play_num = 1
            while check_cup:
                foam_cup_list = CoffeeInterface.get_detect_all_data("foam_cup")
                logger.info(f"foam_cup_list {foam_cup_list}")
                if foam_cup_list[0]["status"] == "1":
                    check_cup = False
                    # break
                if check_cup == True:
                    time.sleep(5)
                    if time.time() - start_time > 10 * play_num:
                        play_num += 1
                        AudioInterface.gtts('foam cup is not there, please check')

        # *****************************

        def take_cup():
            self.goto_gripper_position(which, self.env.gripper_open_pos)  # 张开夹爪
            if which == Arm.left:
                take_pose.roll = 90
                self.goto_point(which, take_pose, speed=pose_speed, wait=False)
                self.goto_temp_point(which, z=take_pose.z - 125, speed=pose_speed, wait=True)
            else:
                take_pose.roll = -90
                self.goto_point(which, take_pose, speed=pose_speed, wait=False)
                self.goto_temp_point(which, x=take_pose.x + 2.5, y=take_pose.y - 8.5, z=take_pose.z - 125, speed=pose_speed, wait=True)
            self.goto_gripper_position(which, 120, wait=True)  # 闭合夹爪
            self.env.one_arm(which).set_collision_sensitivity(cup_config.collision_sensitivity)  # 设置灵敏度，根据实际效果确定是否要注释
            self.safe_set_state(which, 0)
            time.sleep(0.5)
            code, gripper_pose = self.env.one_arm(which).get_gripper_position()  # first获取夹爪的张合度 CT
            logger.info(f'first take foam cup with clamp = {gripper_pose}')
            self.goto_temp_point(which, z=take_pose.z + 50, speed=pose_speed, wait=True)  # 向上运动5cm
            time.sleep(0.5)
            code1, gripper_pose1 = self.env.one_arm(which).get_gripper_position()  # second获取夹爪的张合度 CT
            logger.info(f'second take foam cup with clamp = {gripper_pose1}')
            self.env.one_arm(which).set_collision_sensitivity(self.env.adam_config.same_config.collision_sensitivity)  # 恢复灵敏度，与上方设置灵敏度一起注释或一起放开
            self.safe_set_state(which, 0)
            time.sleep(0.5)
            return gripper_pose, gripper_pose1

        is_gripper_flag = True  # CT gripper or not
        take_cup_num = 0
        try:
            while is_gripper_flag:
                gripper_pose, gripper_pose1 = take_cup()
                if gripper_pose < 123 and gripper_pose1 < 123:
                    logger.info('++++++++++++++++++++++++++++++++++++++++++++++++++++++')
                    logger.info('take foam cup fail，gripper_pose = {}'.format(gripper_pose))
                    AudioInterface.gtts(f'{which} arm take foam cup fail,waiting 5s again')
                    time.sleep(5)
                    take_cup_num += 1
                    if take_cup_num > 3:
                        AudioInterface.gtts(f'{which} arm take foam cup fail')
                        # raise Exception(f'clean tube fail,update clean time')  # 抛出异常，返回false
                        self.stop(f'{which} arm take foam cup fail')

                    # is_gripper_flag = False

                else:
                    logger.info('++++++++++++++++++++++++++++++++++++++++++++++++++++++')
                    logger.info('take foam cup success，gripper_pose = {}'.format(gripper_pose))
                    is_gripper_flag = False
            return True
        except Exception as e:
            logger.info("Exception is {}".format(e))
            return False

    def take_foam_cup(self, arm, is_move=True, is_waiting=True):
        logger.info('take_foam_cup')
        foam_cup_config = deepcopy(self.env.machine_config.shaker)
        take_pose = deepcopy(foam_cup_config.pose.take)
        pose_speed = 500  # 300
        which = arm

        if is_move:
            self.goto_initial_position_direction(which, 0, wait=False, speed=pose_speed)  # 转向奶泡杯方向

            # judge foam cup does it exist
            # *****************************
            if self.enable_visual_recognition:
                check_cup = True
                start_time = time.time()
                play_num = 1
                while check_cup:
                    foam_cup_list = CoffeeInterface.get_detect_all_data("foam_cup")
                    logger.info(f"foam_cup_list {foam_cup_list}")
                    if foam_cup_list[0]["status"] == "1":
                        check_cup = False
                        # break
                    if check_cup == True:
                        time.sleep(5)
                        if time.time() - start_time > 10 * play_num:
                            play_num += 1
                            AudioInterface.gtts('foam cup is not there, please check')
            # *****************************

            self.goto_gripper_position(which, self.env.gripper_open_pos)  # 张开夹爪
            if which == Arm.left:
                take_pose.roll = 90
                self.goto_point(which, take_pose, speed=pose_speed, wait=False)
                self.goto_temp_point(which, z=take_pose.z - 125, speed=pose_speed, wait=True)
            else:
                take_pose.roll = -90
                self.goto_point(which, take_pose, speed=pose_speed, wait=False)
                self.goto_temp_point(which, x=take_pose.x + 2.5, y=take_pose.y - 8.5, z=take_pose.z - 125, speed=pose_speed, wait=True)
        if is_waiting:
            self.goto_gripper_position(which, 0, wait=True)  # 闭合夹爪
            self.goto_temp_point(which, z=take_pose.z + 50, speed=pose_speed, wait=False)  # 向上运动5cm

    def take_espresso_cup(self):
        logger.info('take_espresso_cup')
        pose_speed = 500  # 800
        angle_speed = 200  # 200
        which = Arm.right
        espresso_config = deepcopy(self.env.machine_config.espresso)
        take_pose = deepcopy(espresso_config.pose.take)

        self.goto_initial_position_direction(which, 0, wait=False, speed=pose_speed)

        def take_cup():
            self.goto_gripper_position(which, self.env.gripper_open_pos)
            temp_pose = deepcopy(take_pose)
            temp_pose.x = 548.8
            temp_pose.y = -549.5
            temp_pose.z = 250.1
            self.goto_point(which, temp_pose, speed=pose_speed, wait=True)
            self.goto_angles(which, adam_schema.Angles.list_to_obj([-149.3, 30.2, -101.9, 116.4, 35.5, 147.4]), wait=True, speed=angle_speed)
            self.goto_temp_point(which, x=take_pose.x, y=take_pose.y, z=take_pose.z, speed=pose_speed, wait=True)
            self.goto_gripper_position(which, 100, True)

            code, gripper_pose = self.env.one_arm(which).get_gripper_position()  # first获取夹爪的张合度 CT
            logger.info(f'first take espresso cup with clamp = {gripper_pose}')
            self.goto_temp_point(which, z=take_pose.z + 100, speed=pose_speed, wait=True)  # 向上运动5cm

            code1, gripper_pose1 = self.env.one_arm(which).get_gripper_position()  # second获取夹爪的张合度 CT
            logger.info(f'second take espresso cup with clamp = {gripper_pose1}')
            self.env.one_arm(which).set_collision_sensitivity(self.env.adam_config.same_config.collision_sensitivity)  # 恢复灵敏度，与上方设置灵敏度一起注释或一起放开
            self.safe_set_state(which, 0)
            time.sleep(0.5)
            return gripper_pose, gripper_pose1

        is_gripper_flag = True  # CT gripper or not
        take_cup_num = 0
        try:
            # while is_gripper_flag:
            #     gripper_pose, gripper_pose1 = take_cup()
            #     if gripper_pose < 123 and gripper_pose1 < 123:
            #         logger.info('++++++++++++++++++++++++++++++++++++++++++++++++++++++')
            #         logger.info('take espresso cup fail，gripper_pose = {}'.format(gripper_pose))
            #         AudioInterface.gtts(f'{which} arm take espresso cup fail,waiting 5s again')
            #         time.sleep(5)
            #         take_cup_num += 1
            #         if take_cup_num > 3:
            #             AudioInterface.gtts(f'{which} arm take espresso cup fail')
            #             # raise Exception(f'take espresso cup failed')  # 抛出异常，返回false
            #             self.stop(f'{which} arm take espresso cup fail')

            #         is_gripper_flag = False

            #     else:
            #         logger.info('++++++++++++++++++++++++++++++++++++++++++++++++++++++')
            #         logger.info('take espresso cup success，gripper_pose = {}'.format(gripper_pose))
            #         is_gripper_flag = False
            take_cup()
            self.goto_angles(which, adam_schema.Angles.list_to_obj([-163.0, 32.9, -99.3, 115.9, 51.0, -34.1]), wait=False, speed=angle_speed)
            return True
        except Exception as e:
            logger.info("Exception is {}".format(e))
            return False

    def clean_and_put_espresso_cup(self):
        logger.info('clean_espresso_cup')
        pose_speed = 200  # 400
        angle_speed = 100  # 100
        which = Arm.right
        espresso_config = deepcopy(self.env.machine_config.shaker)
        take_pose = deepcopy(espresso_config.pose.clean)
        time.sleep(2)
        self.goto_temp_point(which, x=500, y=10.5, z=400, wait=False, speed=pose_speed)
        self.goto_angles(which, adam_schema.Angles.list_to_obj([-159.6, 72, -116.9, 49.6, 29.6, -173.9]), wait=True, speed=angle_speed)
        check_thread = CheckThread(self.env.one_arm(which), self.stop)
        try:
            check_thread.start()
            if self.task_status == AdamTaskStatus.making:
                self.ser.send_one_msg('L')
                time.sleep(2)
                self.ser.send_one_msg('l')
                time.sleep(2)
        finally:
            check_thread.stop()
        self.goto_angles(which, adam_schema.Angles.list_to_obj([-155.9, 9.9, -55.1, 101.3, 31.3, -218]), wait=False, speed=80)
        self.goto_point(which, adam_schema.Pose.list_to_obj([778.6, -538.1, 302.8, 23.1, -87.8, 157.5]), wait=False, speed=pose_speed)
        self.goto_temp_point(which, z=157.4, wait=True, speed=pose_speed)
        self.goto_gripper_position(which, 850, wait=True)
        self.goto_temp_point(which, x=626.3, z=262.5, wait=False, speed=pose_speed)
        self.goto_angles(which, adam_schema.Angles.list_to_obj([-209.4, -22.6, -39.0, 90.3, 89.5, -28.3]), wait=False, speed=angle_speed)
        # self.goto_initial_position_direction(which, 0, wait=True, speed=pose_speed)

    def take_espresso_ingredients(self, arm, composition: dict):
        """
        从龙头接糖浆等配料，根据arm参数决定左手接还是右手接
        arm: left or right 左手或右手
        composition: {'material_name': quantity, 'chocolate_syrup': 100}
        """
        logger.info('{} arm take_ingredients {}'.format(arm, composition))
        try:
            pose_speed = 50  # 500
            tap_pose = deepcopy(self.env.machine_config.gpio.tap.pose)
            which = arm
            tap_pose.roll = self.get_xy_initial_angle(which, tap_pose.x, tap_pose.y)
            take_pose = deepcopy(tap_pose)
            if which == Arm.right:
                take_pose.x += 10
                take_pose.z = 200  # 龙头下方位置
            else:
                take_pose.z = 140  # 170
            first_run_flag = True
            self.thread_lock.acquire()
            move = False

            material_names = list(composition.keys())

            for name, quantity in composition.items():
                if first_run_flag:
                    self.goto_initial_position_direction(which, tap_pose.roll, wait=False, speed=pose_speed)
                    self.goto_point(which, take_pose, wait=True, speed=pose_speed)  # 运动到龙头下方位置
                    self.check_adam_pos(which, [take_pose.x, take_pose.y, take_pose.z, take_pose.roll, take_pose.pitch,
                                                take_pose.yaw], 'take_ingredients open port')
                    first_run_flag = False
                    move = True
                CoffeeInterface.post_use(name, quantity)
            logger.debug('arduino open_dict = {}'.format(composition))
            sea_salt_foam_count = composition.pop('sea_salt_foam', 0)  # 尝试从字典里删除海盐奶盖相关内容,没有就设为0
            vanilla_syrup_count = composition.pop('vanilla_syrup', 0)
            vanilla_cream_count = composition.pop('vanilla_cream', 0)
            check_thread = CheckThread(self.env.one_arm(which), self.stop)

            try:
                check_thread.start()
                self.ser.open_port_together_by_speed(composition)
                if sea_salt_foam_count > 0:
                    # 如果大于0，说明要接奶盐奶盖
                    self.ser.open_port_together_by_speed({'sea_salt_foam': sea_salt_foam_count})  # 再接海盐奶盖

                if vanilla_syrup_count > 0:
                    # 如果大于0，说明要接奶盐奶盖
                    self.ser.open_port_together_by_speed({'vanilla_syrup': vanilla_syrup_count})  # 再接海盐奶盖

                if vanilla_cream_count > 0:
                    # 如果大于0，说明要接奶盐奶盖
                    self.ser.open_port_together_by_speed({'vanilla_cream': vanilla_cream_count})  # 再接海盐奶盖
            finally:
                check_thread.stop()

            self.thread_lock.release()
        except Exception as e:
            raise e

    def take_ice(self, delay_time):
        """
        delay_time 接冰停顿时间
        see coffee_machine.yaml -> task_option for more detail
        """
        logger.info('take_ice with delay_time = {}'.format(delay_time))

        pose_speed = 350  # 500
        which = Arm.left
        before_dispense_pose = deepcopy(self.env.machine_config.ice_maker[1].pose)
        dispense_pose = deepcopy(self.env.machine_config.ice_maker[2].pose)

        self.goto_point(which, before_dispense_pose, wait=False, speed=pose_speed)

        self.goto_point(which, dispense_pose, wait=True, speed=100)

        check_thread = CheckThread(self.env.one_arm(which), self.stop)
        check_thread.start()
        time.sleep(delay_time)  # 等待接冰
        check_thread.stop()

        self.goto_point(which, before_dispense_pose, wait=False, speed=pose_speed)
        # 设置成True后，防止直接进入下一步After setting to True, prevent directly entering the next step.
        self.goto_initial_position_direction(which, 0, wait=True, speed=pose_speed)  # 返回工作零点

    def release_ice(self):
        pass

    #     logger.info('clean_ice with task status={}'.format(self.task_status))

    #     if self.task_status == AdamTaskStatus.idle:
    #         ice_pose = deepcopy(self.env.machine_config.ice_maker[0].pose)
    #         which = Arm.right
    #         pose_speed = 250
    #         ice_pose.z += 80
    #         ice_pose.roll -= 93
    #         self.goto_initial_position_direction(which, 0, wait=False, speed=pose_speed)
    #         self.goto_point(which, ice_pose, wait=True, speed=pose_speed)  # 运动到过渡位置
    #         self.goto_temp_point(which, , wait=True, speed=pose_speed)
    #         self.goto_point(which, ice_pose, wait=True, speed=pose_speed)
    #         self.goto_initial_position_direction(which, 0, wait=False, speed=pose_speed)  # 返回工作零点
    #         init_angle = [-132, 8.7, -34.5, 45.9, 42.8, 38.7]
    #         self.goto_angles(which, adam_schema.Angles.list_to_obj(init_angle), wait=True)

    def clean_milk_pipe(self, materials):
        angle_speed = 20
        tap_pose = deepcopy(self.env.machine_config.gpio.tap.pose)

        logger.info('clean_milk_tap with task status={}'.format(self.task_status))
        logger.info('clean_milk_tap with materials={}'.format(materials))

        open_dict = {}
        for material in materials:
            open_dict[material[0]] = material[1]
        logger.info(f'open_dict={open_dict}')
        logger.info(f'self.task_status={self.task_status}')
        logger.info(f'AdamTaskStatus={AdamTaskStatus.idle}')
        if self.task_status == AdamTaskStatus.idle:
            self.change_adam_status(AdamTaskStatus.making)
            if self.take_foam_cup_judge(Arm.left):
                for key, value in open_dict.items():
                    which = Arm.left
                    self.take_ingredients_foam(which, {key: value})
                    self.goto_angles(which, adam_schema.Angles.list_to_obj([164.1, 54.2, -92.2, -5.2, 35.4, -42.2]), wait=True,
                                     speed=angle_speed + 40)
                    self.goto_angles(which, adam_schema.Angles.list_to_obj([161.9, 85.4, -143, -29.6, 34.4, -210.4]), wait=True, speed=angle_speed)
                    if self.task_status == AdamTaskStatus.making:
                        self.ser.send_one_msg('L')
                        time.sleep(2)
                        self.ser.send_one_msg('l')
                        time.sleep(2)
                    self.goto_temp_point(which, z=135, wait=True, speed=200)
                    self.goto_angles(which, adam_schema.Angles.list_to_obj([158.0, 73.4, -120.8, -37.4, 24.2, -22.2]), wait=True,
                                     speed=angle_speed + 20)
                    # add cleaning_history
                    CoffeeInterface.add_cleaning_history({key: value}, 1)
                    # clean_history = CoffeeInterface.get_last_one_clean_history()
                    # ASWServerInterface.add_cleaning_history(clean_history)

                self.put_foam_cup(Arm.left, wait=True)
                self.goto_initial_position_direction(Arm.left, 0, wait=True, speed=500)
                self.goto_standby_pose()
            self.change_adam_status(AdamTaskStatus.idle)

    def make_foam(self, composition: dict, type: str):
        """
        右手先到龙头处接奶，再到奶泡机打发
        composition: {'foam': {'foam_composition': {'tap01': 3.5, 'foam_coffee': 4}, 'foam_time': 7}}
        """
        logger.info('make_foam with composition = {}'.format(composition))

        if composition:
            foam_time = composition.get('foam', {}).get('foam_time', 15)  # 从字典获取奶泡的制作时间
            self.ser.send_one_msg('M')
            time.sleep(foam_time)  # 30  # 等待制作奶泡，前一步wait必为True   #此时需要去抓冷杯，准备制作咖啡，无需等待
            self.ser.send_one_msg('m')
            time.sleep(0.1)

    def clean_foamer(self):
        """清洗调酒壶"""
        logger.info('clean_foamer')
        pose_speed = 300  # 300
        angle_speed = 80  # 80
        which = Arm.right
        self.goto_point(which, adam_schema.Pose.list_to_obj([632.6, 3.2, 158.0, -75.4, -86.9, -53.8]), wait=True, speed=pose_speed)
        check_thread = CheckThread(self.env.one_arm(which), self.stop)
        try:
            check_thread.start()
            if self.task_status == AdamTaskStatus.making:
                self.ser.send_one_msg('L')
                time.sleep(2)
                self.ser.send_one_msg('l')
                time.sleep(3)
        finally:
            check_thread.stop()

        self.goto_point(which, adam_schema.Pose.list_to_obj([622.5, -10.2, 245.4, -56.5, -89.4, -45.8]), wait=False, speed=pose_speed)
        self.goto_point(which, adam_schema.Pose.list_to_obj([587.3, -13.6, 238.2, -82.6, 52.2, 5.1]), wait=True, speed=pose_speed)
        self.goto_point(which, adam_schema.Pose.list_to_obj([413.5, 2.4, 300.1, -11.8, 90.0, 78.2]), wait=True, speed=pose_speed)

    def put_foam_cup(self, which, wait=False):
        logger.info('put_foam_cup')
        foam_cup_config = deepcopy(self.env.machine_config.shaker)
        take_pose = deepcopy(foam_cup_config.pose.take)
        pose_speed = 300  # 800
        if which == Arm.left:
            take_pose.roll = 90
            self.goto_point(which, take_pose, speed=pose_speed, wait=True)
            self.goto_temp_point(which, z=take_pose.z - 125, speed=pose_speed, wait=False)
        else:
            take_pose.roll = -90
            self.goto_point(which, take_pose, speed=pose_speed, wait=False)
            self.goto_temp_point(which, x=take_pose.x + 2.5, y=take_pose.y - 8.5, z=take_pose.z - 125, speed=pose_speed, wait=True)
        if wait:  # This wait is no longer needed. But no time to remove
            self.goto_gripper_position(which, self.env.gripper_open_pos, wait=True)
        else:
            self.goto_gripper_position(which, self.env.gripper_open_pos, wait=True)  # 闭合夹爪

    def put_hot_cup(self, cup=None, task_uuid=None):
        logger.info('put_hot_cup')
        pose_speed = 125
        # **********************************************
        if not self.enable_visual_recognition:
            put_config = [i for i in self.env.machine_config.put if i.name == define.CupName.hot_cup][0]
            put_pose = deepcopy(put_config.pose)
            which = self.env.left_or_right(put_pose.y)  # Arm.left
            self.put_hot_cup_index = 0
            # put_pose.y += self.put_hot_cup_index * 140
            if self.put_hot_cup_index == 0:
                table = "left_cup_stand1"
            # elif self.put_hot_cup_index == 1:
            #     table = "left_cup_stand2"
            # elif self.put_hot_cup_index == 2:
            #     table = "left_cup_stand3"
            # self.put_hot_cup_index = (self.put_hot_cup_index + 1) % 3
        # **********************************************

        # Check whether there is an empty space in the cup holder
        # **********************************************
        if self.enable_visual_recognition:
            table = None
            put_pose = None
            which = None
            check_cup = True
            start_time = time.time()
            play_num = 0
            while check_cup:
                cup_stand_list = CoffeeInterface.get_detect_all_data("left_cup")
                logger.info(f"cup_stand_list {cup_stand_list}")
                for cup_stand in cup_stand_list:
                    if cup_stand["status"] == "0":
                        for position in self.env.machine_config.put_position:
                            if position.table == cup_stand["name"]:
                                table = cup_stand["name"]
                                put_pose = deepcopy(position.pose)
                                which = self.env.left_or_right(put_pose.y)  # Arm.left
                                check_cup = False
                                break
                    if check_cup == False:
                        break
                if check_cup == True:
                    time.sleep(3)
                    if time.time() - start_time > 10 * play_num:
                        play_num += 1
                        AudioInterface.gtts('/richtech/resource/audio/voices/no_place.mp3')
        # **********************************************

        # put_pose.roll = self.get_xy_initial_angle(which, put_pose.x, put_pose.y)

        weight = self.adam_config.gripper_config['pour_ice'].tcp_load.weight
        tool_gravity = list(self.adam_config.gripper_config['pour_ice'].tcp_load.center_of_gravity.dict().values())

        temp_pose = deepcopy(put_pose)
        temp_pose.x -= 200
        self.goto_point(which, temp_pose, speed=pose_speed, wait=False)  # 放杯位置后上方
        self.goto_point(which, put_pose, wait=False, speed=pose_speed)  # 运动到放杯位置上方
        self.goto_temp_point(which, z=put_pose.z - 50, wait=True, speed=50)
        self.goto_gripper_position(which, self.env.gripper_open_pos, wait=True)  # 张开夹爪
        self.goto_temp_point(which, x=put_pose.x - 200, z=put_pose.z + 50, wait=False, speed=pose_speed)  # 放完向后退
        self.goto_point(which, self.initial_position(which), wait=False, speed=pose_speed)  # 回零点

        # Update the data in the detect table
        CoffeeInterface.update_detect_by_name(table, 1, task_uuid)

    # action with left arm & right arm
    def pour(self, action):
        """倒入杯中"""
        logger.info('pour')
        pose_speed = 50

        try:
            if action == 'right':  # 目前都是ice
                roll = self.get_xy_initial_angle(Arm.right, 550, -100)
                left_pose = adam_schema.Pose.list_to_obj([470, -7, 400, 90, 90, 0])  # x = 430, y=0, z = 340
                self.goto_point(Arm.left, left_pose, wait=False, speed=pose_speed)  # 左手位置
                tcp_offset = list(self.adam_config.gripper_config['pour_ice'].tcp_offset.dict().values())
                weight = self.adam_config.gripper_config['pour_ice'].tcp_load.weight
                tool_gravity = list(
                    self.adam_config.gripper_config['pour_ice'].tcp_load.center_of_gravity.dict().values())
                self.right.set_tcp_offset(offset=tcp_offset)  # 右手根据调酒壶设置偏移和载重
                self.right.set_tcp_load(weight=weight, center_of_gravity=tool_gravity)
                self.safe_set_state(Arm.right, 0)
                time.sleep(0.5)
                self.goto_point(Arm.right, adam_schema.Pose.list_to_obj([495, -55, 475, roll, 90, 0]),
                                speed=pose_speed, wait=False)  # 右手位置 x = 465, y = -70, z=420
                self.goto_tool_position(which=Arm.right, x=0, y=50, z=0, yaw=-178, speed=pose_speed,
                                        wait=True)  # 倒入杯中，边转边往内 y was 85 speed was 400 yaw = -125
                curr_pose = self.right.position
                self.goto_temp_point(Arm.right, z=curr_pose[2] + 10, speed=pose_speed, wait=True)
                tcp_offset = list(self.adam_config.gripper_config['default'].tcp_offset.dict().values())
                weight = self.adam_config.gripper_config['default'].tcp_load.weight
                tool_gravity = list(
                    self.adam_config.gripper_config['default'].tcp_load.center_of_gravity.dict().values())
                self.right.set_tcp_offset(offset=tcp_offset)  # 恢复默认偏移和载重
                self.right.set_tcp_load(weight=weight, center_of_gravity=tool_gravity)
                self.safe_set_state(Arm.right, 0)
                time.sleep(0.5)
                return
            elif action == 'left':
                roll = self.get_xy_initial_angle(Arm.left, 550, 100)
                right_pose = adam_schema.Pose.list_to_obj([490, 27, 340, 90, 90, 0])  # x = 430, y=0, z = 340
                self.goto_point(Arm.right, right_pose, wait=False, speed=pose_speed)  # 左手位置
                tcp_offset = list(self.adam_config.gripper_config['pour_ice'].tcp_offset.dict().values())
                weight = self.adam_config.gripper_config['pour_ice'].tcp_load.weight
                tool_gravity = list(
                    self.adam_config.gripper_config['pour_ice'].tcp_load.center_of_gravity.dict().values())
                self.left.set_tcp_offset(offset=tcp_offset)  # 右手根据调酒壶设置偏移和载重
                self.left.set_tcp_load(weight=weight, center_of_gravity=tool_gravity)
                self.safe_set_state(Arm.left, 0)
                time.sleep(0.5)
                self.goto_point(Arm.left, adam_schema.Pose.list_to_obj([495, 55, 475, roll, 90, 0]),
                                speed=pose_speed, wait=False)  # 右手位置 x = 465, y = -70, z=420
                self.goto_tool_position(which=Arm.left, x=0, y=50, z=0, yaw=178, speed=pose_speed,
                                        wait=True)  # 倒入杯中，边转边往内 y was 85 speed was 400 yaw = -125
                curr_pose = self.left.position
                self.goto_temp_point(Arm.left, z=curr_pose[2] + 10, speed=pose_speed, wait=True)
                tcp_offset = list(self.adam_config.gripper_config['default'].tcp_offset.dict().values())
                weight = self.adam_config.gripper_config['default'].tcp_load.weight
                tool_gravity = list(
                    self.adam_config.gripper_config['default'].tcp_load.center_of_gravity.dict().values())
                self.left.set_tcp_offset(offset=tcp_offset)  # 恢复默认偏移和载重
                self.left.set_tcp_load(weight=weight, center_of_gravity=tool_gravity)
                self.safe_set_state(Arm.left, 0)
                time.sleep(0.5)
        finally:
            logger.info('set back tcp_offset to default')
            default_tcp_offset = list(self.adam_config.gripper_config['default'].tcp_offset.dict().values())
            default_weight = self.adam_config.gripper_config['default'].tcp_load.weight
            default_tool_gravity = list(
                self.adam_config.gripper_config['default'].tcp_load.center_of_gravity.dict().values())
            if action == 'right':
                self.right.set_tcp_offset(offset=default_tcp_offset)
                self.right.set_tcp_load(weight=default_weight, center_of_gravity=default_tool_gravity)
                time.sleep(0.5)
                self.safe_set_state(Arm.right, 0)
                time.sleep(0.5)
            else:
                self.left.set_tcp_offset(offset=default_tcp_offset)
                self.left.set_tcp_load(weight=default_weight, center_of_gravity=default_tool_gravity)
                time.sleep(0.5)
                self.safe_set_state(Arm.left, 0)
                time.sleep(0.5)

        # action with left arm & right arm

    def pour_foam_cup(self, action):
        """倒入杯中"""
        logger.info('pour')
        pose_speed = 300  # 200
        angle_speed = 25

        try:
            if action == 'right':  # 目前都是ice
                weight = self.adam_config.gripper_config['pour_ice'].tcp_load.weight
                tool_gravity = list(self.adam_config.gripper_config['default'].tcp_load.center_of_gravity.dict().values())
                self.right.set_tcp_load(weight=weight, center_of_gravity=tool_gravity)
                self.safe_set_state(Arm.right, 0)
                time.sleep(0.5)

                self.goto_temp_point(Arm.right, z=300, speed=350, wait=False)

                # Move both arms into a position ready to pour and receive the pour
                def left_action():
                    self.goto_point(Arm.left, adam_schema.Pose.list_to_obj([478.7, 15.3, 310, 90.0, 90.0, 0.0]), wait=True, speed=pose_speed + 25)

                def right_action():
                    self.goto_point(Arm.right, adam_schema.Pose.list_to_obj([652.1, -9.9, 460.0, -90.0, 90.0, 0.0]), speed=pose_speed,
                                    wait=True)  # 右手位置 x = 465, y = -70, z=420

                thread_list = [threading.Thread(target=right_action), threading.Thread(target=left_action)]
                for t in thread_list:
                    t.start()
                for t in thread_list:
                    t.join()

                # This joint motion is the pour
                self.goto_angles(Arm.right, adam_schema.Angles.list_to_obj([-128.5, 39.5, -62.8, 0.1, 26.2, -92.5]), wait=True, speed=angle_speed)

                curr_pose = self.right.position
                self.goto_temp_point(Arm.right, z=curr_pose[2] + 10, speed=pose_speed, wait=True)
                tcp_offset = list(self.adam_config.gripper_config['default'].tcp_offset.dict().values())
                weight = self.adam_config.gripper_config['default'].tcp_load.weight
                tool_gravity = list(self.adam_config.gripper_config['default'].tcp_load.center_of_gravity.dict().values())
                self.right.set_tcp_offset(offset=tcp_offset)  # 恢复默认偏移和载重
                self.right.set_tcp_load(weight=weight, center_of_gravity=tool_gravity)
                self.safe_set_state(Arm.right, 0)
                time.sleep(0.5)
            elif action == 'left':
                pass

                ### Pour left should not be used in this system ###

                # roll = self.get_xy_initial_angle(Arm.left, 550, 100)
                # right_pose = adam_schema.Pose.list_to_obj([490, 27, 340, 90, 90, 0])  # x = 430, y=0, z = 340
                # self.goto_point(Arm.right, right_pose, wait=False, speed=pose_speed)  # 左手位置
                # tcp_offset = list(self.adam_config.gripper_config['pour_ice'].tcp_offset.dict().values())
                # weight = self.adam_config.gripper_config['pour_ice'].tcp_load.weight
                # tool_gravity = list(
                #     self.adam_config.gripper_config['pour_ice'].tcp_load.center_of_gravity.dict().values())
                # self.left.set_tcp_offset(offset=tcp_offset)  # 右手根据调酒壶设置偏移和载重
                # self.left.set_tcp_load(weight=weight, center_of_gravity=tool_gravity)
                # self.safe_set_state(Arm.left, 0)
                # time.sleep(0.5)
                # self.goto_point(Arm.left, adam_schema.Pose.list_to_obj([495, 55, 475, roll, 90, 0]),
                #                 speed=pose_speed, wait=False)  # 右手位置 x = 465, y = -70, z=420
                # self.goto_tool_position(which=Arm.left, x=0, y=50, z=0, yaw=178, speed=pose_speed,
                #                         wait=True)  # 倒入杯中，边转边往内 y was 85 speed was 400 yaw = -125
                # curr_pose = self.left.position
                # self.goto_temp_point(Arm.left, z=curr_pose[2] + 10, speed=200, wait=True)
                # tcp_offset = list(self.adam_config.gripper_config['default'].tcp_offset.dict().values())
                # weight = self.adam_config.gripper_config['default'].tcp_load.weight
                # tool_gravity = list(
                #     self.adam_config.gripper_config['default'].tcp_load.center_of_gravity.dict().values())
                # self.left.set_tcp_offset(offset=tcp_offset)  # 恢复默认偏移和载重
                # self.left.set_tcp_load(weight=weight, center_of_gravity=tool_gravity)
                # self.safe_set_state(Arm.left, 0)
                # time.sleep(0.5)
        finally:
            logger.info('set back tcp_offset to default')
            default_tcp_offset = list(self.adam_config.gripper_config['default'].tcp_offset.dict().values())
            default_weight = self.adam_config.gripper_config['default'].tcp_load.weight
            default_tool_gravity = list(
                self.adam_config.gripper_config['default'].tcp_load.center_of_gravity.dict().values())
            if action == 'right':
                self.right.set_tcp_offset(offset=default_tcp_offset)
                self.right.set_tcp_load(weight=default_weight, center_of_gravity=default_tool_gravity)
                time.sleep(0.5)
                self.safe_set_state(Arm.right, 0)
                time.sleep(0.5)
            else:
                self.left.set_tcp_offset(offset=default_tcp_offset)
                self.left.set_tcp_load(weight=default_weight, center_of_gravity=default_tool_gravity)
                time.sleep(0.5)
                self.safe_set_state(Arm.left, 0)
                time.sleep(0.5)

    def pass_cup(self, action, switch=0):
        logger.info('pass_cup')
        speed = 'slow_take'
        if action == 'from_right':
            self.goto_gripper_position(Arm.left, 800, wait=True)

            def left_action():
                self.goto_point(Arm.left, common_schema.Pose.list_to_obj([300, 300, 340, 30, 90, 0]), wait=True,
                                speed=300)
                self.goto_point(Arm.left, common_schema.Pose.list_to_obj([390, 30, 350, 90, 90, 0]), wait=False,
                                speed=200)
                self.goto_point(Arm.left, common_schema.Pose.list_to_obj([390, -5, 340, 90, 90, 0]), wait=True,
                                speed=200)  # y=0
                while True:
                    logger.debug(" TEST WHILE LOOP")
                    current_position = self.current_position(Arm.left)
                    cur_pos = str(current_position)
                    list1 = cur_pos.split(" ")
                    list2 = list1[1].split("=")
                    left_y = float(list2[1])
                    if left_y == -5:
                        self.goto_gripper_position(Arm.left, 410, wait=True)
                        self.goto_gripper_position(Arm.right, 800, wait=True)
                        # global is_grabbed
                        is_grabbed = 1
                        break
                    else:
                        time.sleep(1)

                if is_grabbed == 1:
                    self.goto_point(Arm.right, common_schema.Pose.list_to_obj([300, -300, 300, -30, 90, 0]), wait=False,
                                    speed=300)
                    self.goto_initial_position_direction(Arm.right, 0, wait=False)
                    self.goto_point(Arm.left, common_schema.Pose.list_to_obj([300, 300, 300, 30, 90, 0]), wait=False,
                                    speed=300)
                    self.goto_initial_position_direction(Arm.left, 0, wait=False)

            def right_action():
                if switch == 0:
                    logger.debug('switch =========================0')
                    self.goto_point(Arm.right, common_schema.Pose.list_to_obj([300, -300, 260, -30, 90, 0]), wait=False,
                                    speed=300)
                    self.goto_point(Arm.right, common_schema.Pose.list_to_obj([385, -30, 260, -90, 90, 0]), wait=False,
                                    speed=300)

                    self.goto_point(Arm.right, common_schema.Pose.list_to_obj([385, 0, 260, -90, 90, 0]), wait=True,
                                    speed=300)  # y = 0
                    self.check_adam_pos(Arm.right, [385, 0, 260, -90, 90, 0], 'pass cup switch 0')

                if switch == 1:
                    logger.debug('switch =========================1')
                    self.goto_point(Arm.right, common_schema.Pose.list_to_obj([300, -300, 315, -30, 90, 0]), wait=False,
                                    speed=400)
                    self.goto_point(Arm.right, common_schema.Pose.list_to_obj([385, -30, 315, -90, 90, 0]), wait=False,
                                    speed=400)

                    self.goto_point(Arm.right, common_schema.Pose.list_to_obj([385, 0, 315, -90, 90, 0]), wait=True,
                                    speed=400)
                    self.check_adam_pos(Arm.right, [385, 0, 315, -90, 90, 0], 'pass cup switch 1')

            thread_list = [threading.Thread(target=left_action), threading.Thread(target=right_action)]
            for t in thread_list:
                t.start()
            for t in thread_list:
                t.join()

        # FROM LEFT TO RIGHT
        if action == 'from_left':
            speed = 200
            self.goto_gripper_position(Arm.right, 800, wait=False)

            def right_action():
                self.goto_point(Arm.right, common_schema.Pose.list_to_obj([300, -300, 315, -30, 90, 0]), wait=False,
                                speed=speed)
                self.goto_point(Arm.right, common_schema.Pose.list_to_obj([385, -30, 315, -90, 90, 0]), wait=False,
                                speed=speed)
                self.goto_point(Arm.right, common_schema.Pose.list_to_obj([385, 0, 315, -90, 90, 0]), wait=True,
                                speed=speed)

            def left_action():
                self.goto_point(Arm.left, common_schema.Pose.list_to_obj([300, 300, 280, 30, 90, 0]), wait=False,
                                speed=speed)
                self.goto_point(Arm.left, common_schema.Pose.list_to_obj([390, 30, 280, 90, 90, 0]), wait=False,
                                speed=speed)
                self.goto_point(Arm.left, common_schema.Pose.list_to_obj([390, 0, 280, 90, 90, 0]), wait=True,
                                speed=speed)

                while True:
                    logger.debug(" TEST WHILE LOOP")

                    current_position = self.current_position(Arm.right)
                    cur_pos = str(current_position)

                    list1 = cur_pos.split(" ")

                    list2 = list1[1].split("=")

                    right_y = float(list2[1])
                    if right_y == -0.0:
                        self.goto_gripper_position(Arm.right, 330, wait=True)
                        self.goto_gripper_position(Arm.left, 800, wait=True)
                        # global is_grabbed
                        is_grabbed = 1
                        break
                    else:
                        time.sleep(1)

                if is_grabbed == 1:
                    self.goto_point(Arm.left, common_schema.Pose.list_to_obj([300, 300, 300, 30, 90, 0]), wait=False,
                                    speed=speed)
                    self.goto_initial_position_direction(Arm.left, 0, wait=False)
                    self.goto_point(Arm.right, common_schema.Pose.list_to_obj([300, -300, 300, -30, 90, 0]), wait=False,
                                    speed=speed)
                    self.goto_initial_position_direction(Arm.right, 0, wait=False, speed=200)

            thread_list = [threading.Thread(target=right_action), threading.Thread(target=left_action)]
            for t in thread_list:
                t.start()
            for t in thread_list:
                t.join()

    # whole make actions
    def make_hot_drink(self, formula, sweetness, milk, beans, ice, receipt_number, task_uuid):
        """{'coffee_machine':
        {'americano':
        {'count': 360,
        'coffee_make': {
        'drinkType': 4, 'volume': 32, 'coffeeTemperature': 2,
        'concentration': 2, 'hotWater': 175, 'waterTemperature': 0,
        'hotMilk': 0, 'foamTime': 0, 'precook': 0, 'moreEspresso': 0,
        'coffeeMilkTogether': 0, 'adjustOrder': 1}
        }},
        'cup': {'hot_cup': 1}}

        {'coffee_machine':
        {'double_espresso':
        {'count': 45, 'coffee_make':
        {'drinkType': 21, 'volume': 32, 'coffeeTemperature': 2,
        'concentration': 2, 'hotWater': 0, 'waterTemperature': 0,
        'hotMilk': 0, 'foamTime': 0, 'precook': 0, 'moreEspresso': 0,
        'coffeeMilkTogether': 0, 'adjustOrder': 1}
        }}, 'cup': {'hot_cup': 1}}
        """
        start_time = int(time.time())
        AudioInterface.gtts('/richtech/resource/audio/voices/start_making4.mp3')
        logger.debug('start in make_hot_drink')
        composition = self.get_composition_by_option(formula, define.CupSize.medium_cup, sweetness, milk, beans, ice)
        logger.info(f"into make_hot_drink  :{composition}")
        self.is_coffee_finished = False

        self.left_record.clear()  # start a new task, delete the previous log file
        self.right_record.clear()

        self.change_adam_status(AdamTaskStatus.making)

        try:
            self.right_record.proceed()  # 记录关节位置线程开启
            self.left_record.proceed()
            # self.take_hot_cup()
            self.check_adam_status('make_hot_drink take_hot_cup', status=AdamTaskStatus.making)
            self.take_coffee_machine(composition.get("coffee_machine", {}), formula=formula, type="hot", need_adjust=True, is_take_hot_cup=True)
            self.check_adam_status('make_hot_drink take_coffee_machine', status=AdamTaskStatus.making)
            # AudioInterface.gtts("receipt {}, your {} is ready.".format('-'.join(list(receipt_number)), formula))
            AudioInterface.gtts(f'/richtech/resource/audio/voices/ready_{formula}.mp3')
            self.put_hot_cup(task_uuid=task_uuid)
            self.check_adam_status('make_hot_drink put_hot_cup', status=AdamTaskStatus.making)
            self.change_adam_status(AdamTaskStatus.idle)
            self.right_record.pause()
            self.left_record.pause()
        except StopError as stop_err:
            raise stop_err
        except Exception as e:
            self.stop(str(e))
        finally:
            self.is_coffee_finished = False
            get_make_time = int(time.time()) - start_time
            logger.info(f"{formula} making use time is : {get_make_time}")

    # Motions for the New York installation

    def test_tap(self, composition):
        self.ser.open_port_together_by_speed(composition)

    def stainless_cup_pour_foam(self):
        pose_speed = 300
        angle_speed = 50
        which = Arm.right
        self.goto_point(which, adam_schema.Pose.list_to_obj([539.7, -79.8, 254.3, -60.0, 90.0, 0.0]), wait=True, speed=pose_speed)
        time.sleep(0.1)
        self.goto_angles(which, adam_schema.Angles.list_to_obj([-150.5, 34.4, -58.0, 61.4, 19.2, -129.8]), wait=True, speed=angle_speed)

    def back_to_initial(self, arm):
        which = arm
        pose_speed = 400  # 600
        if which == Arm.left:
            self.goto_temp_point(which, y=200, wait=False, speed=pose_speed)
        else:
            self.goto_temp_point(which, y=-200, wait=False, speed=pose_speed)
        self.goto_initial_position_direction(which, 0, wait=True, speed=pose_speed)

    def raise_foam_cup(self):
        pose_speed = 500
        self.goto_gripper_position(Arm.right, 0, wait=True)
        self.goto_temp_point(Arm.right, z=300, wait=False, speed=pose_speed)


    def choose_speech(self, type, formula=None):
        if type == 'coffee_knowledge':
            AudioInterface.gtts(f'/richtech/resource/audio/voices/coffee_knowledge_transition1.mp3')
            for i in range(5):
                self.check_adam_status('make coffee waiting', status=AdamTaskStatus.making)
                time.sleep(1)
            num = random.randint(1, 48)
            AudioInterface.gtts(f'/richtech/resource/audio/voices/coffee_knowledge{num}.mp3')
        elif type == 'mood':
            num_t = random.randint(1, 2)
            AudioInterface.gtts(f'/richtech/resource/audio/voices/mood_transition{num_t}.mp3')
            for i in range(5):
                self.check_adam_status('make coffee waiting', status=AdamTaskStatus.making)
                time.sleep(1)
            num = random.randint(1, 34)
            AudioInterface.gtts(f'/richtech/resource/audio/voices/mood{num}.mp3')
        elif type == 'dance_transition':
            AudioInterface.gtts(f'/richtech/resource/audio/voices/dance_transition1.mp3')
        elif type == 'coffee_introduction':
            AudioInterface.gtts(f'/richtech/resource/audio/voices/coffee_introduction_transition1.mp3')
            time.sleep(1)
            AudioInterface.gtts(f'/richtech/resource/audio/voices/coffee_introduction_{formula}.mp3')

    def left_round(self):
        """left arm draw a circle"""
        left_pos_A = {'x': 310, 'y': 550, 'z': 250, 'roll': 0, 'pitch': 90, 'yaw': 0}
        left_pos_B = [360, 600, 250, 0, 90, 0]
        left_pos_C = [360, 500, 250, 0, 90, 0]
        self.left.set_position(**left_pos_A, speed=100, wait=True)
        while True:
            self.check_adam_status('left_round', status=AdamTaskStatus.making)
            if self.is_coffee_finished:
                return
            self.left.move_circle(left_pos_B, left_pos_C, percent=100, speed=100, wait=True)

    def left_interaction_dance1(self):
        """left arm draw a circle"""
        # 抱胸位置
        right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
        left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}

        left1 = {'x': 370, 'y': 90, 'z': 616, 'roll': -57, 'pitch': 9, 'yaw': -157}
        left1_up = {'x': 370, 'y': 90, 'z': 766, 'roll': -57, 'pitch': 9, 'yaw': -157}
        left2 = {'x': 420, 'y': 110, 'z': 616, 'roll': -57, 'pitch': 9, 'yaw': -157}
        left2_up = {'x': 420, 'y': 110, 'z': 766, 'roll': -57, 'pitch': 9, 'yaw': -157}
        left3 = {'x': 470, 'y': 130, 'z': 616, 'roll': -57, 'pitch': 9, 'yaw': -157}
        left3_up = {'x': 470, 'y': 130, 'z': 766, 'roll': -57, 'pitch': 9, 'yaw': -157}
        left4 = {'x': 520, 'y': 150, 'z': 616, 'roll': -57, 'pitch': 9, 'yaw': -157}
        left4_up = {'x': 520, 'y': 150, 'z': 766, 'roll': -57, 'pitch': 9, 'yaw': -157}

        left5 = {'x': 74, 'y': 806, 'z': 1050, 'roll': 0, 'pitch': 0, 'yaw': 0}
        left5_down = {'x': 74, 'y': 806, 'z': 950, 'roll': 0, 'pitch': 0, 'yaw': 0}

        speed = 170

        self.choose_speech("dance_transition")
        for i in range(3):
            self.check_adam_status('left_interaction_dance', status=AdamTaskStatus.making)
            if self.is_coffee_finished:
                return
            time.sleep(1)
        self.check_adam_status('left_interaction_dance', status=AdamTaskStatus.making)
        if self.is_coffee_finished:
            return
        self.left.set_position(**left_init, wait=True, speed=300, radius=50)
        self.check_adam_status('left_interaction_dance', status=AdamTaskStatus.making)
        if self.is_coffee_finished:
            return
        self.left.set_position(**left1, wait=True, speed=300, radius=50)
        self.check_adam_status('left_interaction_dance', status=AdamTaskStatus.making)
        if self.is_coffee_finished:
            return
        AudioInterface.music('relax.mp3')
        self.left.set_position(**left1_up, wait=False, speed=speed, radius=50)
        self.check_adam_status('left_interaction_dance', status=AdamTaskStatus.making)
        if self.is_coffee_finished:
            return
        self.left.set_position(**left2, wait=False, speed=speed, radius=50)
        self.check_adam_status('left_interaction_dance', status=AdamTaskStatus.making)
        if self.is_coffee_finished:
            return
        self.left.set_position(**left2_up, wait=False, speed=speed, radius=50)
        self.check_adam_status('left_interaction_dance', status=AdamTaskStatus.making)
        if self.is_coffee_finished:
            return
        self.left.set_position(**left3, wait=False, speed=speed, radius=50)
        self.check_adam_status('left_interaction_dance', status=AdamTaskStatus.making)
        if self.is_coffee_finished:
            return
        self.left.set_position(**left3_up, wait=False, speed=speed, radius=50)
        self.check_adam_status('left_interaction_dance', status=AdamTaskStatus.making)
        if self.is_coffee_finished:
            return
        self.left.set_position(**left4, wait=False, speed=speed, radius=50)
        self.check_adam_status('left_interaction_dance', status=AdamTaskStatus.making)
        if self.is_coffee_finished:
            return
        self.left.set_position(**left4_up, wait=False, speed=speed, radius=50)
        self.check_adam_status('left_interaction_dance', status=AdamTaskStatus.making)
        if self.is_coffee_finished:
            return
        self.left.set_position(**left5, wait=False, speed=180, radius=50)
        self.check_adam_status('left_interaction_dance', status=AdamTaskStatus.making)
        if self.is_coffee_finished:
            return
        for i in range(8):
            self.check_adam_status('left_interaction_dance', status=AdamTaskStatus.making)
            if self.is_coffee_finished:
                return
            self.left.set_position(**left5, wait=False, speed=300, radius=50)
            self.left.set_position(**left5_down, wait=False, speed=300, radius=50)

        self.check_adam_status('left_interaction_dance', status=AdamTaskStatus.making)
        if self.is_coffee_finished:
            return
        self.left.set_position(**left_init, wait=True, speed=250, radius=50)

    def left_interaction_dance(self):
        # 抱胸位置
        right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
        left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}

        left1 = {'x': 341, 'y': 16, 'z': 777, 'roll': -58, 'pitch': 16, 'yaw': -178}
        left2 = {'x': 341, 'y': 16, 'z': 777, 'roll': -43, 'pitch': 16, 'yaw': -178}

        left3 = {'x': 341, 'y': 86, 'z': 777, 'roll': -58, 'pitch': 16, 'yaw': -178}
        left4 = {'x': 341, 'y': 86, 'z': 777, 'roll': -43, 'pitch': 16, 'yaw': -178}

        left5 = {'x': 341, 'y': 136, 'z': 777, 'roll': -58, 'pitch': 16, 'yaw': -178}
        left6 = {'x': 341, 'y': 136, 'z': 777, 'roll': -43, 'pitch': 16, 'yaw': -178}

        left7 = {'x': 341, 'y': 186, 'z': 777, 'roll': -58, 'pitch': 16, 'yaw': -178}
        left8 = {'x': 341, 'y': 186, 'z': 777, 'roll': -43, 'pitch': 16, 'yaw': -178}

        def reduce_sound():
            for i in range(100, -1, -1):
                os.system(f"amixer set PCM {i}%")
                time.sleep(0.05)

        def recover_sound():
            os.system(f"amixer set PCM 100%")

        speed = 150
        self.choose_speech("dance_transition")
        self.left.set_position(**left_init, wait=True, speed=speed, radius=50)
        AudioInterface.music('She.mp3')
        self.left.set_position(**left1, wait=False, speed=200, radius=50)
        for i in range(4):
            self.left.set_position(**left1, wait=False, speed=speed, radius=50)
            self.left.set_position(**left2, wait=False, speed=speed, radius=50)

        for i in range(7):
            if self.is_coffee_finished:
                reduce_sound()
                AudioInterface.stop()
                recover_sound()
                return
            self.left.set_position(**left3, wait=False, speed=speed + 100, radius=50)
            self.left.set_position(**left4, wait=False, speed=speed, radius=50)
            self.left.set_position(**left5, wait=False, speed=speed, radius=50)
            self.left.set_position(**left6, wait=False, speed=speed, radius=50)
            self.left.set_position(**left7, wait=False, speed=speed, radius=50)
            self.left.set_position(**left8, wait=True, speed=speed, radius=50)

        self.left.set_position(**left1, wait=False, speed=200, radius=50)

    def left_random_action(self, formula):

        num = random.randint(0, 2)
        if num == 0:
            self.choose_speech("coffee_introduction", formula)
        elif num == 1:
            self.choose_speech("coffee_knowledge", formula)
        elif num == 2:
            self.choose_speech("mood", formula)

        left_init = {'x': 355, 'y': 200, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}

        # 左手往上抬
        left_Pos1 = {'x': 355, 'y': 200, 'z': 750, 'roll': 0, 'pitch': 60, 'yaw': -90}

        def left_up(speed):
            self.left.set_position(**left_init, wait=False, speed=speed, radius=50)
            self.left.set_position(**left_Pos1, wait=True, speed=speed, radius=50)

        # 左手往前伸出
        left_Pos2 = {'x': 455, 'y': 200, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}

        def left_front(speed):
            self.left.set_position(**left_init, wait=False, speed=speed, radius=50)
            self.left.set_position(**left_Pos2, wait=False, speed=speed, radius=50)

        # 左手往左上运动
        left_Pos3 = {'x': 355, 'y': 300, 'z': 750, 'roll': 0, 'pitch': 60, 'yaw': -90}

        def left_left_up(speed):
            self.left.set_position(**left_init, wait=False, speed=speed, radius=50)
            self.left.set_position(**left_Pos3, wait=False, speed=speed, radius=50)

        while True:
            logger.debug(f"self.is_coffee_finished : {self.is_coffee_finished}")
            self.check_adam_status('left_random_action', status=AdamTaskStatus.making)
            if self.is_coffee_finished:
                break
            left_left_up(90)
            self.check_adam_status('left_random_action', status=AdamTaskStatus.making)
            if self.is_coffee_finished:
                break
            left_front(90)
            self.check_adam_status('left_random_action', status=AdamTaskStatus.making)
            if self.is_coffee_finished:
                break
            left_up(90)

    def right_random_action(self, formula):

        self.choose_speech("coffee_introduction", formula)

        right_init = {'x': 355, 'y': -200, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}

        # 右手往上抬
        right_Pos1 = {'x': 355, 'y': -200, 'z': 850, 'roll': 0, 'pitch': 60, 'yaw': 90}

        def right_up(speed):
            self.right.set_position(**right_init, wait=False, speed=speed, radius=50)
            self.right.set_position(**right_Pos1, wait=True, speed=speed, radius=50)

        # 右手往前伸出
        right_Pos2 = {'x': 555, 'y': -200, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}

        def right_front(speed):
            self.right.set_position(**right_init, wait=False, speed=speed, radius=50)
            self.right.set_position(**right_Pos2, wait=False, speed=speed, radius=50)

        # 右手往右上运动
        right_Pos3 = {'x': 355, 'y': -300, 'z': 850, 'roll': 0, 'pitch': 60, 'yaw': 90}

        def right_right_up(speed):
            self.right.set_position(**right_init, wait=False, speed=speed, radius=50)
            self.right.set_position(**right_Pos3, wait=False, speed=speed, radius=50)

        while True:
            logger.debug(f"self.is_coffee_finished : {self.is_coffee_finished}")
            self.check_adam_status('right_random_action', status=AdamTaskStatus.making)
            if self.is_coffee_finished:
                break
            right_right_up(90)
            self.check_adam_status('right_random_action', status=AdamTaskStatus.making)
            if self.is_coffee_finished:
                break
            right_front(90)
            self.check_adam_status('right_random_action', status=AdamTaskStatus.making)
            if self.is_coffee_finished:
                break
            right_up(90)

    def idle_interaction(self, formula, type):
        """
        空闲互动 idle interaction
        formula : 饮品名称 formula name
        type: 饮品类型 formula type 1.cold 2.hot
        """
        if conf.get_idle_Interaction()['state']:
            random_number = random.random()
            threshold = conf.get_idle_Interaction()['threshold'] / 100
            logger.info(f"random_number={random_number}")
            logger.info(f"threshold={threshold}")
            if random_number < threshold:
                if type == 'hot':
                    num = random.randint(0, 1)
                    if num == 0:
                        left_thread = threading.Thread(target=self.left_interaction_dance)  # dance
                        left_thread.start()
                        left_thread.join()
                    elif num == 1:
                        left_thread = threading.Thread(target=self.left_random_action, args=(formula,))  # coffee introduction
                        left_thread.start()
                        left_thread.join()
                elif type == 'cold':
                    speech_list = ['coffee_introduction', 'mood', 'coffee_knowledge']
                    speech_num = random.randint(0, 2)
                    num = random.randint(0, 0)
                    if num == 0:
                        left_threads = [threading.Thread(target=self.left_round),
                                        threading.Thread(target=self.choose_speech, args=(speech_list[speech_num], formula))]
                        for t in left_threads:
                            t.start()
                        for t in left_threads:
                            t.join()

    def make_cold_drink(self, formula, sweetness, milk, beans, ice, receipt_number, task_uuid):
        """
        make_cold_drink
        """
        start_time = int(time.time())
        # AudioInterface.gtts2("Got it, I'm making your drink now!")
        AudioInterface.gtts('/richtech/resource/audio/voices/start_making4.mp3')
        logger.debug('start in make_cold_drink')
        composition = self.get_composition_by_option(formula, define.CupSize.medium_cup, sweetness, milk, beans, ice)
        logger.debug(f'composition={composition}')
        put_cup_flag = Arm.left  # 放杯标志，由此判断是左手放杯还是右手放杯
        sent_flag = False  # 咖啡机指令发送标志
        self.is_coffee_finished = False

        self.left_record.clear()  # start a new task, delete the previous log file
        self.right_record.clear()

        self.left_record.proceed()
        self.right_record.proceed()  # 记录关节位置线程开启

        self.change_adam_status(AdamTaskStatus.making)
        try:
            # step 1 : 两个线程：左手（需要咖啡味奶泡就去那奶泡杯接配料），右手（需要咖啡机原液就去接）
            def left_step1():
                if composition.get(define.Constant.MachineType.foam_machine, {}).get('foam', {}).get('foam_composition', {}).get('foam_coffee', {}):
                    if not self.take_foam_cup_judge(Arm.left):
                        self.stop("take foam cup fail")
                    self.check_adam_status('make_cold_drink take_foam_cup', status=AdamTaskStatus.making)
                    foam_composition = deepcopy(
                        composition.get(define.Constant.MachineType.foam_machine, {}).get('foam', {}).get('foam_composition', {}))
                    foam_composition.pop('foam_coffee')
                    # if self.enable_visual_recognition:
                    #     self.detect_cup_thread.pause()  # close detect_cup_thread
                    self.take_ingredients_foam(Arm.left, foam_composition)
                    self.check_adam_status('make_cold_drink take_ingredients_foam', status=AdamTaskStatus.making)
                    self.put_foam_cup(Arm.left)
                    self.check_adam_status('make_cold_drink put_foam_cup', status=AdamTaskStatus.making)
                    self.put_foam_flag = True
                    self.goto_temp_point(Arm.left, y=20, wait=False)
                    self.goto_angles(Arm.left, adam_schema.Angles.list_to_obj([209.1, -41.9, -24.7, -90.4, 89.2, 23.3]), wait=True)
                    # self.back_to_initial(Arm.left)
                    self.check_adam_status('make_cold_drink back_to_initial', status=AdamTaskStatus.making)
                    # if self.enable_visual_recognition:
                    #     self.detect_cup_thread.proceed()  # open detect_cup_thread

                self.take_cold_cup()
                self.check_adam_status('make_cold_drink take_cold_cup', status=AdamTaskStatus.making)
                if delay_time := composition.get(define.Constant.MachineType.ice_maker, {}).get("ice", 0):
                    if delay_time != 0:
                        self.take_ice(delay_time)
                        self.check_adam_status('make_cold_drink take_ice', status=AdamTaskStatus.making)

                if not composition.get(define.Constant.MachineType.foam_machine, {}):
                    # if self.enable_visual_recognition:
                    #     self.detect_cup_thread.pause()  # close detect_cup_thread
                    self.take_ingredients(Arm.left, composition.get(define.Constant.MachineType.tap, {}))
                    self.check_adam_status('make_cold_drink take_ingredients', status=AdamTaskStatus.making)
                    self.goto_initial_position_direction(Arm.left, 0, wait=True, speed=800)
                    self.check_adam_status('make_cold_drink goto_initial_position_direction', status=AdamTaskStatus.making)
                    # if self.enable_visual_recognition:
                    #     self.detect_cup_thread.proceed()  # open detect_cup_thread

                # 冷咖在等待咖啡机制作时空闲互动 idle interaction
                if conf.get_idle_Interaction()['state']:
                    if composition.get(define.Constant.MachineType.coffee_machine, {}):
                        self.idle_interaction(formula, "cold")
                    else:
                        self.is_coffee_finished = True
                        AudioInterface.stop()

            def right_step1():
                if foam_machine := composition.get(define.Constant.MachineType.foam_machine, {}):
                    if foam_coffee := foam_machine.get('foam', {}).get('foam_composition', {}).get('foam_coffee', {}):
                        # self.take_espresso_cup()
                        espresso_composition = {"foam_coffee": {"coffee_make": {"drinkType": foam_coffee - 1}}}
                        self.take_coffee_machine(espresso_composition, formula, sent_flag, is_take_espresso_cup=True)
                        self.check_adam_status('make_cold_drink take_coffee_machine', status=AdamTaskStatus.making)
                        if composition.get(define.Constant.MachineType.foam_machine, {}):
                            while not self.put_foam_flag:
                                logger.info(f"waiting put_foam_cup success")
                                time.sleep(1)
                            self.stainless_cup_pour_foam()
                            self.check_adam_status('make_cold_drink stainless_cup_podef make_cold_drinkur_foam', status=AdamTaskStatus.making)
                    else:
                        if not self.take_foam_cup_judge(Arm.right):
                            self.stop("take foam cup fail")
                        self.check_adam_status('make_cold_drink take_foam_cup', status=AdamTaskStatus.making)
                        # if self.enable_visual_recognition:
                        #     self.detect_cup_thread.pause()  # close detect_cup_thread
                        self.take_ingredients_foam(Arm.right, foam_machine.get('foam', {}).get('foam_composition', {}))
                        self.check_adam_status('make_cold_drink take_ingredients_foam', status=AdamTaskStatus.making)
                        self.put_foam_cup(Arm.right, wait=True)
                        self.check_adam_status('make_cold_drink put_foam_cup', status=AdamTaskStatus.making)
                        # if self.enable_visual_recognition:
                        #     self.detect_cup_thread.proceed()  # open detect_cup_thread
                elif composition.get(define.Constant.MachineType.coffee_machine, {}):
                    self.take_coffee_machine(composition.get(define.Constant.MachineType.coffee_machine, {}), formula, sent_flag,
                                             is_take_espresso_cup=True)
                    self.check_adam_status('make_cold_drink take_coffee_machine', status=AdamTaskStatus.making)

                # 无需右手配合时，空闲互动  Idle interaction when coordination with the right hand is not required
                else:
                    if conf.get_idle_Interaction()['state']:
                        random_number = random.random()
                        threshold = conf.get_idle_Interaction()['threshold'] / 100
                        logger.info(f"random_number={random_number}")
                        logger.info(f"threshold={threshold}")
                        if random_number < threshold:
                            left_thread = threading.Thread(target=self.right_random_action, args=(formula,))
                            left_thread.start()
                            left_thread.join()

            if self.task_status != AdamTaskStatus.making:
                raise Exception("AdamTaskStatus is not making")
            step1_thread = [threading.Thread(target=left_step1), threading.Thread(target=right_step1)]
            for t in step1_thread:
                t.start()
            for t in step1_thread:
                t.join()

            # step 2 : 三个线程：左手(有配料去接配料)，右手(不锈钢杯需要清洗就去清洗)，有奶泡就开始制作奶泡
            def make_foam_step():
                if composition.get(define.Constant.MachineType.foam_machine, {}):
                    self.make_foam(composition.get(define.Constant.MachineType.foam_machine, {}), "cold")
                    self.check_adam_status('make_cold_drink make_foam', status=AdamTaskStatus.making)

            def right_step2():
                if composition.get(define.Constant.MachineType.foam_machine, {}).get('foam', {}).get('foam_composition', {}).get('foam_coffee', {}):
                    self.clean_and_put_espresso_cup()
                    self.check_adam_status('make_cold_drink clean_and_put_espresso_cup', status=AdamTaskStatus.making)
                    self.take_foam_cup(Arm.right, True, False)
                    self.check_adam_status('make_cold_drink take_foam_cup', status=AdamTaskStatus.making)

            def left_step2():
                if composition.get(define.Constant.MachineType.foam_machine, {}).get('foam', {}).get('foam_composition', {}).get('foam_coffee', {}):
                    time.sleep(
                        8)  # The time the left arm waits while the right arm cleans the espresso cup. The smaller the sleep time, the more likely for both arms to collide since the left arm has no idea where the right arm is.
                    # This statement is only true if the drink uses espresso milk foam. If the composition for the drink uses foam_coffee, then this statement will run.
                if composition.get(define.Constant.MachineType.foam_machine, {}):
                    # if self.enable_visual_recognition:
                    #     self.detect_cup_thread.pause()  # close detect_cup_thread
                    self.take_ingredients(Arm.left, composition.get(define.Constant.MachineType.tap, {}))
                    self.check_adam_status('make_cold_drink take_ingredients', status=AdamTaskStatus.making)
                    self.goto_initial_position_direction(Arm.left, 0, wait=True, speed=800)
                    self.check_adam_status('make_cold_drink goto_initial_position_direction', status=AdamTaskStatus.making)
                    # if self.enable_visual_recognition:
                    #     self.detect_cup_thread.proceed()  # open detect_cup_thread

            if self.task_status != AdamTaskStatus.making:
                raise Exception("AdamTaskStatus is not making")
            step2_thread = [threading.Thread(target=make_foam_step), threading.Thread(target=right_step2), threading.Thread(target=left_step2)]
            for t in step2_thread:
                t.start()
            for t in step2_thread:
                t.join()

            self.check_adam_status('make_cold_drink pour_foam_cup', status=AdamTaskStatus.making)
            # step 3 : 如果判断需要咖啡原液，则将其导入左手冷杯中
            if not composition.get(define.Constant.MachineType.foam_machine, {}).get('foam', {}):
                if composition.get(define.Constant.MachineType.coffee_machine, {}):
                    self.pour_foam_cup('right')
                    self.check_adam_status('make_cold_drink pour_foam_cup', status=AdamTaskStatus.making)

            self.check_adam_status('make_cold_drink pour_foam_cup', status=AdamTaskStatus.making)
            # step 4 :
            if foam_machine := composition.get(define.Constant.MachineType.foam_machine, {}):
                if foam_machine.get('foam', {}).get('foam_composition', {}).get('foam_coffee', {}):
                    self.take_foam_cup(Arm.right, False, True)
                    self.check_adam_status('make_cold_drink take_foam_cup', status=AdamTaskStatus.making)
                else:
                    self.raise_foam_cup()
                    self.check_adam_status('make_cold_drink raise_foam_cup', status=AdamTaskStatus.making)

                self.pour_foam_cup("right")
                self.check_adam_status('make_cold_drink pour_foam_cup', status=AdamTaskStatus.making)

                # AudioInterface.gtts(receipt {}, your {} is ready.".format('-'.join(list(receipt_number)), formula))
                AudioInterface.gtts(f'/richtech/resource/audio/voices/ready_{formula}.mp3')
                def left_step4():
                    self.goto_initial_position_direction(Arm.left, 0, wait=False, speed=250)
                    self.put_cold_cup(task_uuid=task_uuid)
                    self.check_adam_status('make_cold_drink put_cold_cup', status=AdamTaskStatus.making)

                def right_step4():
                    if composition.get(define.Constant.MachineType.foam_machine, {}):
                        time.sleep(1)
                        self.clean_foamer()
                        self.check_adam_status('make_cold_drink clean_foamer', status=AdamTaskStatus.making)
                        self.put_foam_cup(Arm.right)
                        self.check_adam_status('make_cold_drink put_foam_cup', status=AdamTaskStatus.making)
                        self.back_to_initial(Arm.right)
                        self.check_adam_status('make_cold_drink back_to_initial', status=AdamTaskStatus.making)
                    elif composition.get(define.Constant.MachineType.coffee_machine, {}):
                        self.clean_and_put_espresso_cup()
                        self.check_adam_status('make_cold_drink clean_and_put_espresso_cup', status=AdamTaskStatus.making)

                if self.task_status != AdamTaskStatus.making:
                    raise Exception("AdamTaskStatus is not making")
                step4_thread = [threading.Thread(target=left_step4), threading.Thread(target=right_step4)]
                for t in step4_thread:
                    t.start()
                for t in step4_thread:
                    t.join()
            else:
                # AudioInterface.gtts(receipt {}, your {} is ready.".format('-'.join(list(receipt_number)), formula))
                AudioInterface.gtts(f'/richtech/resource/audio/voices/ready_{formula}.mp3')
                def left_step3():
                    self.goto_initial_position_direction(Arm.left, 0, wait=False, speed=250)
                    self.put_cold_cup(task_uuid=task_uuid)
                    self.check_adam_status('make_cold_drink put_cold_cup', status=AdamTaskStatus.making)

                def right_step3():
                    if composition.get(define.Constant.MachineType.coffee_machine, {}):
                        self.clean_and_put_espresso_cup()
                        self.check_adam_status('make_cold_drink clean_and_put_espresso_cup', status=AdamTaskStatus.making)

                if self.task_status != AdamTaskStatus.making:
                    raise Exception("AdamTaskStatus is not making")
                step3_thread = [threading.Thread(target=left_step3), threading.Thread(target=right_step3)]
                for t in step3_thread:
                    t.start()
                for t in step3_thread:
                    t.join()

            self.check_adam_status('make_cold_drink done')  # 判断机械臂在子线程中是否有动作失败，有错误及时抛出异常
            self.left_record.pause()
            self.right_record.pause()
            self.change_adam_status(AdamTaskStatus.idle)

        except StopError as stop_err:
            self.stop(stop_err)
        except MoveError as e:
            self.stop(e)
        except Exception as e:
            self.stop(e)
        finally:
            self.is_coffee_finished = False
            get_make_time = int(time.time()) - start_time
            logger.info(f"{formula} making use time is : {get_make_time}")

    def _goto_work_zero_use_set_position_with_true(self):
        left_p = self.initial_position(Arm.left).dict()
        right_p = self.initial_position(Arm.right).dict()
        left_p.update({'wait': True, 'speed': 300})
        right_p.update({'wait': True, 'speed': 300})
        lcode, rcode = self.env.adam.set_position(left_p, right_p)
        if lcode != 0 or rcode != 0:  # move has error, stop adam
            self.stop('error in _goto_work_zero_use_set_position_with_true: lcode={}, rcode={}'.format(lcode, rcode))

    def get_composition_by_option(self, formula, cup, sweetness=0, milk=define.MilkType.milk, beans=define.BeansType.high_roast,
                                  ice='no_ice') -> dict:
        """
        根据饮品名称查询配方表，返回不同机器处需要的物料名称和数量。同时根据选项对糖量等进行微调
        return:{
                'coffee_machine': {'coffee': {'count':60, 'coffee_make':{...}}}, # 用咖啡机的
                'bucket': {'americano': 320}, # 用保温桶的
                'power_box': {'sugar_power': 1}, # 要蘸糖粉的
                'foam_machine': {"foam": {"foam_composition": {"fresh_dairy":450 }, "foam_time":45} },# 奶泡
                'tap': {sugar':10, 'white_chocolate_syrup': 20, 'cold_coffee': 150}, # 用龙头的
                'ice_machine': {'ice': 0}, # 用制冰机的
                'cup': {'hot_cup': 1}
                }
        """
        composition = CoffeeInterface.get_formula_composition(formula, cup, define.Constant.InUse.in_use)
        if not composition:
            # 校验方案是否支持
            msg = 'there are no formula named {} in use, please check again'.format(formula)
            AudioInterface.gtts(msg)
            logger.error(msg)
            raise FormulaError(msg)
        result = {}
        lack = ''
        for name, material in composition.items():
            if material.get('in_use') == define.Constant.InUse.not_in_use:
                # 校验材料是否支持
                msg = 'material {} is not in use, please check again'.format(name)
                AudioInterface.gtts(msg)
                logger.error(msg)
                raise MaterialError(msg)
            if material.get('left') < material.get('count'):
                # 校验材料是否充足
                lack += ' ' + name

            machine_name = material.get('machine')

            # 根据选项更新数量
            if name == define.TreacleType.sugar:
                # 根据甜度调整糖的用量
                result.setdefault(machine_name, {})[name] = material.get('count') * sweetness / 100
            if name == 'ice':
                # 根据选项更新冰的等待系数
                # result.setdefault(machine_name, {})[name] = self.get_ice_percent(ice)
                result.setdefault(machine_name, {})[name] = material.get('count')
            elif name in ["Plant-based milk", "Milk"]:
                if milk == define.MilkType.milk:
                    # 使用动物奶油
                    result.setdefault(machine_name, {})["Milk"] = material.get('count')
                elif milk == define.MilkType.plant_based:
                    # 使用植物奶油
                    result.setdefault(machine_name, {})["Plant-based milk"] = material.get('count')
            elif machine_name == define.Constant.MachineType.coffee_machine:
                if extra := material.get('extra'):
                    if len(extra) > 1:
                        for key, value in extra.items():
                            if key == beans:
                                coffee_make = material.get('coffee_make')
                                coffee_make["drinkType"] = value - 1
                        logger.info(f"coffee_make  {coffee_make}")
                        coffee_data = dict(count=material.get('count'), coffee_make=coffee_make)
                        result.setdefault(machine_name, {})[name] = coffee_data
                    else:
                        # 咖啡机类型的全部要增加咖啡机制作配方字典
                        coffee_data = dict(count=material.get('count'), coffee_make=material.get('coffee_make'))
                        result.setdefault(machine_name, {})[name] = coffee_data
                else:
                    # 咖啡机类型的全部要增加咖啡机制作配方字典
                    coffee_data = dict(count=material.get('count'), coffee_make=material.get('coffee_make'))
                    result.setdefault(machine_name, {})[name] = coffee_data
            elif machine_name == define.Constant.MachineType.foam_machine:
                foam_data = dict(foam_composition=material.get('extra', {}).get('foam_composition', {}),
                                 foam_time=material.get('extra', {}).get('foam_time', 45))
                for tap_name, tap_time in foam_data["foam_composition"].copy().items():
                    if tap_name in ["Plant-based milk", "Milk"]:
                        if milk == define.MilkType.milk:
                            # 使用动物奶油
                            foam_data["foam_composition"]["Milk"] = foam_data["foam_composition"].pop(tap_name)
                        elif milk == define.MilkType.plant_based:
                            # 使用植物奶油
                            foam_data["foam_composition"]["Plant-based milk"] = foam_data["foam_composition"].pop(tap_name)
                result.setdefault(machine_name, {})[name] = foam_data
            else:
                result.setdefault(machine_name, {})[name] = material.get('count')
        logger.debug('composition is {}'.format(result))
        if lack:
            AudioInterface.gtts('material {} not enough please add them first'.format(lack))
            raise MaterialError('material {} not enough please add them first'.format(lack))
        return result

    def get_cup_config(self, cup_name) -> total_schema.GetCupConfig:
        cup_config = deepcopy([i for i in self.env.machine_config.get if i.name == cup_name][0])
        return cup_config

    def get_ice_percent(self, ice):
        delay_percent = 1
        if ice == define.IceType.no_ice:
            delay_percent = self.machine_config.task_option.ice_type.no_ice
        elif ice == define.IceType.light:
            delay_percent = self.machine_config.task_option.ice_type.light
        if ice == define.IceType.more:
            delay_percent = self.machine_config.task_option.ice_type.more
        return delay_percent

    def get_initial_position(self):
        # 回到作揖状态下
        left_pre_angles = [148.5, 20, -46.3, -52.1, 74.7, -23.9]
        right_pre_angles = [-148.5, 20, -46.3, 52.1, 74.7, 23.9]
        left_position = [355, 100, 630, 0, 60, -90]
        right_position = [355, -100, 630, 0, 60, 90]
        left_angles = self.inverse(define.Arm.left, left_position, left_pre_angles)
        right_angles = self.inverse(define.Arm.right, right_position, right_pre_angles)
        return left_angles, right_angles

    def stop_and_goto_zero(self, is_sleep=False):
        """
        Adam软件急停并回工作状态的零点
        """
        if is_sleep:
            time.sleep(1)
        if self.task_status in [AdamTaskStatus.making, AdamTaskStatus.stopped, AdamTaskStatus.rolling,
                                AdamTaskStatus.dead, AdamTaskStatus.warm, AdamTaskStatus.restart]:
            return {'msg': 'not ok', 'status': self.task_status}
        elif self.task_status == AdamTaskStatus.idle:
            self.goto_work_zero(speed=30, open_gripper=False)
            logger.debug('adam is idle now, return in stop_and_goto_zero')
            return {'msg': 'ok', 'status': self.task_status}
        else:
            logger.debug('adam is dancing now, stop and goto zero')
            self.env.adam.set_state(dict(state=4), dict(state=4))
            self.task_status = AdamTaskStatus.making  # temp
            VisualDetectInterface.stop_following()
            # 停止播放音乐
            AudioInterface.stop()
            with MySuperContextManager() as db:
                adam_crud.init_dance(db)
            logger.warning("adam stop and wait 5 seconds")
            time.sleep(5)
            self.left.motion_enable()
            self.left.clean_error()
            self.left.clean_warn()
            self.left.set_state(0)
            self.right.motion_enable()
            self.right.clean_error()
            self.right.clean_warn()
            self.right.set_state(0)

            self.goto_work_zero(speed=30)
            logger.warning("adam stop and goto zero finish")
            print(f"self.task_status: {self.task_status}")
            self.task_status = AdamTaskStatus.idle
            return {'msg': 'ok', 'status': self.task_status}

    def goto_work_zero(self, speed=50, open_gripper=True):
        """Adam 回工作状态下零点"""
        # 回到工作状态下的零点
        left_pre_angles = [209.35, -26.49, -63.1, -90, 89.35, 0.41]
        left_position = list(self.initial_position(define.Arm.left).dict().values())
        left_angles = self.inverse(define.Arm.left, left_position, left_pre_angles)
        right_pre_angles = [-209.35, -26.49, -63.1, 90, 89.35, -0.41]
        right_position = list(self.initial_position(define.Arm.right).dict().values())
        right_angles = self.inverse(define.Arm.right, right_position, right_pre_angles)

        if open_gripper:
            self.goto_gripper_position(Arm.left, self.env.gripper_open_pos, wait=False)
            self.goto_gripper_position(Arm.right, self.env.gripper_open_pos, wait=False)
        if not self.task_status or self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling,
                                                            AdamTaskStatus.dead]:
            # first run, self.task_status is None
            lcode, rcode = self.env.adam.set_servo_angle(dict(angle=left_angles, speed=speed, wait=True),
                                                         dict(angle=right_angles, speed=speed, wait=True))
            self.is_goto_work_zero = True
            if lcode != 0 or rcode != 0:
                # self.stop()
                raise MoveError('adam goto angle_left={} angle_right={} fail, code={},{}'.
                                format(left_angles, right_angles, lcode, rcode))

    def stop(self, err='something error'):
        """
        Adam软件急停, 关闭所有gpio。如果急停按钮一直闭合，则无法关闭gpio
        """
        self.change_adam_status(AdamTaskStatus.stopped)
        self.error_msg.append({'time': time.strftime("%Y-%m-%d %H:%M:%S"), 'err': err})
        if self.task_status != AdamTaskStatus.rolling:
            self.env.adam.set_state(dict(state=4), dict(state=4))
        self.coffee_driver.cancel_make()
        self.ser.send_one_msg('i')
        try:
            logger.debug('before release thread lock in stop')
            self.thread_lock.release()
            logger.debug('released')
        except Exception as e:
            pass

        adam_crud.init_tap()
        # 停止播放音乐
        AudioInterface.stop()
        AudioInterface.gtts(CoffeeInterface.choose_one_speech_text(define.AudioConstant.TextCode.fail))
        logger.warning("adam stop because {}".format(err))
        raise StopError(err)

    def resume(self):
        self.left.motion_enable()
        self.left.clean_error()
        self.left.clean_warn()
        self.left.set_state()
        self.right.motion_enable()
        self.right.clean_error()
        self.right.clean_warn()
        self.right.set_state()
        self.goto_work_zero(speed=30)
        return 'ok'

    def goto_standby_pose(self):
        """
        回到作揖动作
        """
        left_angles, right_angles = self.get_initial_position()
        logger.info(
            'left_angles={}, right_angles={} in goto_standby_pose with status={}'.format(left_angles, right_angles,
                                                                                         self.task_status))
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead]:
            logger.info('goto_standby_pose')
            self.goto_gripper_position(Arm.left, 10, wait=False)
            self.goto_gripper_position(Arm.right, 10, wait=False)
            self.env.adam.set_servo_angle(dict(angle=left_angles, speed=20, wait=True),
                                          dict(angle=right_angles, speed=20, wait=True))
            self.left_record.pause()
            self.right_record.pause()

    def goto_point(self, which, pose: adam_schema.Pose, wait=True, speed=None, radius=50, timeout=None,
                   roll_flag=False):
        """
        运动到点，可以指定速度比例，否则以machine.yml中的默认速度来运动
        """
        if speed:
            speed = speed
        else:
            speed = self.env.default_arm_speed
        arm = self.env.one_arm(which)
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead] or roll_flag:
            logger.debug('{} arm goto pose={} at {} speed, wait={}'.format(which, pose.dict(), speed, wait))
            code = arm.set_position(**pose.dict(), speed=speed, wait=wait, radius=radius, timeout=timeout)
            if code not in [0, 100]:
                logger.error('{} arm goto pose={} fail, code={}'.format(which, pose.dict(), code))
                self.stop('{} arm goto pose={} fail, code={}'.format(which, pose.dict(), code))
                raise MoveError('{} arm goto pose={} fail, code={}'.format(which, pose.dict(), code))
        return [round(i, 2) for i in arm.angles[:6]]

    def goto_XYZ_point(self, which, pose: adam_schema.Pose, wait=True, speed=None, roll_flag=False):
        """
        运动到点，只要xyz，三个参数可以指定速度比例，否则以machine.yml中的默认速度来运动
        """
        if speed:
            speed = speed
        else:
            speed = self.env.default_arm_speed
        arm = self.env.one_arm(which)
        pose_dict = {'x': pose.x, 'y': pose.y, 'z': pose.z}
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead] or roll_flag:
            logger.debug('{} arm goto_XYZ_point pose={} at {} speed, wait={}'.format(which, pose_dict, speed, wait))
            code = arm.set_position(**pose_dict, speed=speed, wait=wait, radius=50)
            if code != 0:
                logger.error('{} arm goto_XYZ_point pose={} fail, code={}'.format(which, pose_dict, code))
                self.stop('{} arm goto_XYZ_point pose={} fail, code={}'.format(which, pose_dict, code))
                raise MoveError('{} arm goto_XYZ_point pose={} fail, code={}'.format(which, pose_dict, code))
        return [round(i, 2) for i in arm.angles[:6]]

    def goto_temp_point(self, which, x=None, y=None, z=None, roll=None, pitch=None, yaw=None, wait=True, speed=None,
                        mvacc=None, roll_flag=False):
        """
        一些中间位置，可以只传一个位置参数，而不需要传全部
        """
        if speed:
            speed = speed
        else:
            speed = self.env.default_arm_speed
        arm = self.env.one_arm(which)
        pose_dict = {'x': x, 'y': y, 'z': z, 'roll': roll, 'pitch': pitch, 'yaw': yaw}
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead] or roll_flag:
            logger.debug('{} arm goto_temp_point pose={} at {} speed, wait={}'.format(which, pose_dict, speed, wait))
            code = arm.set_position(**pose_dict, speed=speed, wait=wait, radius=50, mvacc=mvacc)
            if code != 0:
                logger.error('{} arm goto_temp_point pose={} fail, code={}'.format(which, pose_dict, code))
                self.stop('{} arm goto_temp_point pose={} fail, code={}'.format(which, pose_dict, code))
                raise MoveError('{} arm goto_temp_point pose={} fail, code={}'.format(which, pose_dict, code))
        return [round(i, 2) for i in arm.angles[:6]]

    def goto_gripper_position(self, which, pos, wait=False, roll_flag=False):
        # 控制机械臂的夹爪开关
        arm = self.env.one_arm(which)
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead] or roll_flag:
            arm.set_gripper_enable(True)
            arm.set_gripper_mode(0)
            code = arm.set_gripper_position(pos, wait=wait, speed=self.env.default_gripper_speed)
            if code != 0:
                logger.error('{} arm goto_gripper_position pose={} fail, code={}'.format(which, pos, code))
                self.stop('{} arm goto_gripper_position pose={} fail, code={}'.format(which, pos, code))
                raise MoveError('{} arm goto_gripper_position pose={} fail, code={}'.format(which, pos, code))

    def goto_tool_position(self, which, x=0, y=0, z=0, roll=0, pitch=0, yaw=0,
                           speed=None, wait=False, roll_flag=False):
        # 控制机械臂的夹爪开关
        arm = self.env.one_arm(which)
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead] or roll_flag:
            code = arm.set_tool_position(x=x, y=y, z=z, roll=roll, pitch=pitch, yaw=yaw, speed=speed, wait=wait)
            if code != 0:
                logger.error('{} arm goto_tool_position fail, code={}'.format(which, code))
                self.stop('{} arm goto_tool_position fail, code={}'.format(which, code))
                raise MoveError('{} arm goto_tool_position fail, code={}'.format(which, code))

    def goto_angles(self, which, angles: adam_schema.Angles, wait=True, speed=50, roll_flag=False, relative=False):
        angle_list = list(dict(angles).values())
        arm = self.env.one_arm(which)
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead] or roll_flag:
            logger.info('{} arm set_servo_angle from {} to {}'.format(which, arm.angles[:6], angle_list))
            return_code = arm.set_servo_angle(angle=angle_list, speed=speed, wait=wait, relative=relative)
            now_angles = arm.angles
            if return_code != 0:
                self.stop('{} arm goto angle={} fail, code={}'.format(which, angle_list, return_code))
                raise MoveError('{} arm goto angle={} fail, code={}'.format(which, angle_list, return_code))
            return now_angles

    def goto_relative_angles(self, which, angles: list, wait=True, speed=50):
        # 相对运动，一般情况下请勿调用
        arm = self.env.one_arm(which)
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead]:
            logger.info('{} arm goto relative angles {}'.format(which, angles))
            return_code = arm.set_servo_angle(angle=angles, speed=speed, wait=wait, relative=True)
            now_angles = arm.angles
            if return_code != 0:
                self.stop('{} arm goto angle={} fail, code={}'.format(which, angles, return_code))
                raise MoveError('{} arm goto angle={} fail, code={}'.format(which, angles, return_code))
            return now_angles

    def safe_set_state(self, which, state=0):
        arm = self.env.one_arm(which)
        if arm.state != 4:
            self.env.one_arm(which).set_state(state)

    def open_gpio(self, which, number, delay_time, roll_flag=False):
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead] or roll_flag:
            logger.debug('open gpio for {} seconds in open_gpio'.format(delay_time))
            self.env.one_arm(which).set_cgpio_digital(number, 1)
            time.sleep(delay_time)
            self.env.one_arm(which).set_cgpio_digital(number, 0)
            logger.debug('close gpio and wait for 2s in open_gpio')
            time.sleep(2)
            logger.debug('after wait 2s in open_gpio')
            logger.info('open {} gpio={} for {} seconds ends'.format(which, number, delay_time))

    def check_adam_goto_initial_position(self):
        # 检测adam是否回到零点，若有报错，adam服务直接退出
        try:
            logger.info('adam goto initial position before work')
            os.system('chmod +x /richtech/resource/adam/kinematics/*')
            self.goto_work_zero(speed=20, open_gripper=True)
            self.goto_gripper_position(Arm.left, 0, wait=False)
            self.goto_gripper_position(Arm.right, 0, wait=False)
            left_angles, right_angles = self.get_initial_position()
            logger.info('left_angles={}, right_angles={}'.format(left_angles, right_angles))
            self.env.adam.set_servo_angle(dict(angle=left_angles, speed=20, wait=True),
                                          dict(angle=right_angles, speed=20, wait=True))
            assert utils.compare_value(self.left.angles[:6], left_angles, abs_tol=1), \
                "left goto initial {} failed, current={}".format(left_angles, self.left.angles[:6])
            assert utils.compare_value(self.right.angles[:6], right_angles, abs_tol=1), \
                "right goto initial {} failed, current={}".format(right_angles, self.right.angles[:6])
            ExceptionInterface.clear_error(ExceptionType.adam_initial_position_failed)
        except Exception as e:
            ExceptionInterface.add_error(ExceptionType.adam_initial_position_failed, str(e))
            logger.error(traceback.format_exc())
            logger.error('{}, err={}'.format(ExceptionType.adam_initial_position_failed, str(e)))
            self.env.adam.motion_enable(left={'enable': True}, right={'enable': True})
            self.env.adam.clean_warn()
            self.env.adam.clean_error()
            time.sleep(1)
            self.env.adam.set_mode(dict(mode=2), dict(mode=2))
            time.sleep(0.5)
            self.env.adam.set_state(dict(state=0), dict(state=0))
            logger.warning("open teach mode")
            time.sleep(9.5)
            exit(-1)

    def check_adam_status(self, desc, status=AdamTaskStatus.making):
        logger.info('check after {}, status is {}'.format(desc, self.task_status))
        if self.task_status != status:
            raise MoveError('move error in {}'.format(desc))
        if self.env.one_arm(Arm.left).state == 4:
            raise MoveError('left move error in {}'.format(desc))
        if self.env.one_arm(Arm.right).state == 4:
            raise MoveError('right move error in {}'.format(desc))

    def check_adam_pos(self, which, pos, desc):
        arm = self.env.one_arm(which)
        real_pos = arm.position
        passed = utils.compare_value(real_pos[:3], pos[:3], 1)
        logger.info('{} arm check_adam_pos {}, pos={}, actual={}, passed={}'.format(which, desc, pos, real_pos, passed))
        if not passed:
            raise MoveError('move error in {} position compare not passed'.format(desc))
        else:
            return True

    def inverse(self, which, pose_list: list, q_pre_list: list = None):
        pose_list = [str(i) for i in pose_list]
        q_pre_list = [str(i) for i in q_pre_list or [0] * 6]
        tcp_list = [str(i) for i in self.env.get_tcp_offset(which).dict().values()]
        world_list = [str(i) for i in self.env.get_world_offset(which).dict().values()]
        param_str = "{} {} {} {}".format(
            ' '.join(pose_list), ' '.join(tcp_list), ' '.join(world_list), ' '.join(q_pre_list))
        cmd = '{}/ik {} '.format(define.BIN_PATH, param_str)
        ret = utils.get_execute_cmd_result(cmd)
        logger.debug('inverse {} input: pose={}, q_pre={}, result: {}'.format(which, pose_list, q_pre_list, ret))
        angle_list = ret.strip().split(' ')
        logger.info('cmd={}, ret={}'.format(cmd, angle_list))
        return [round(float(i), 2) for i in angle_list]

    def current_position(self, which) -> adam_schema.Pose:
        arm = self.env.one_arm(which)
        value = dict(zip(define.POSITION_PARAM, arm.position))
        logger.debug('{} arm current pose={}'.format(which, value))
        return adam_schema.Pose(**value)

    def current_angles(self, which) -> adam_schema.Angles:
        arm = self.env.one_arm(which)
        value = dict(zip(define.ANGLE_PARAM, arm.angles))
        logger.debug('{} arm current pose={}'.format(which, value))
        return adam_schema.Angles(**value)

    def gripper_is_open(self, which):
        arm = self.env.one_arm(which)
        code, pos = arm.get_gripper_position()
        if code == 0:
            if abs(pos - self.env.gripper_open_pos) <= 10:
                return True
            else:
                return False
        else:
            logger.error('{} arm gripper out of control with code {}'.format(which, code))
            raise Exception('{} arm gripper out of control with code {}'.format(which, code))

    def change_adam_status(self, status):
        """
        只有在跳舞的时候，切换为制作状态，才会触发强制停止并回工作零点
        """
        if status == AdamTaskStatus.making and self.task_status == AdamTaskStatus.dancing:
            self.stop_and_goto_zero()
            self.task_status = AdamTaskStatus.making
        elif self.task_status == AdamTaskStatus.rolling or self.task_status == AdamTaskStatus.restart:
            # if adam is rolling, can not change status by this function, need to change status in roll thread
            pass
        else:
            self.task_status = status

    def get_xy_initial_angle(self, which, x, y) -> float:
        src = self.initial_center_point(which)
        x0, y0 = src['x'], src['y']
        return math.atan2(y0 - y, x - x0) / math.pi * 180

    def initial_center_point(self, which):
        y = common_schema.AdamArm.initial_y
        y = abs(y) if which == Arm.left else -abs(y)
        z = 250
        return {'x': 0, 'y': y, 'z': z}

    def center_to_tcp_length(self, which):
        # 工作零点的x坐标如何计算
        gripper_name = getattr(self.env.adam_config.different_config, which).gripper
        return self.env.adam_config.gripper_config[gripper_name].tcp_offset.z + common_schema.AdamArm.line6

    def initial_position(self, which) -> adam_schema.Pose:
        # 计算工作零点的位姿
        center_position = self.initial_center_point(which)
        center_position['x'] = self.center_to_tcp_length(which)
        center_position.update(dict(roll=0, pitch=90, yaw=0))
        return adam_schema.Pose(**center_position)

    def initial_position_direction(self, which, angle):
        """
        自定义initial_position为默认的工作零点，angle表示在中转点转动一个角度
        机械臂在中转点附近有很大的工作空间
        """
        center_position = self.initial_center_point(which)  # [0, +-550, 250]
        line = self.center_to_tcp_length(which)
        x = round(line * math.cos(-math.radians(angle)) + center_position['x'], 2)
        y = round(line * math.sin(-math.radians(angle)) + center_position['y'], 2)
        position = {'x': x, 'y': y, 'z': center_position['z'], 'roll': angle, 'pitch': 90, 'yaw': 0}
        logger.debug('{} arm initial angle={} position={}'.format(which, angle, position))
        return adam_schema.Pose(**position)

    def goto_initial_position_direction(self, which, angle, wait=True, speed=None):
        pose = self.initial_position_direction(which, angle)
        return self.goto_point(which, pose, wait=wait, speed=speed)

    def warm_up(self):
        warm_speed = 20
        self.goto_work_zero()
        left_init_angle = [132.3, 8.7, -34.5, -45.9, 42.8, -38.7]
        right_init_angle = [-132, 8.7, -34.5, 45.9, 42.8, 38.7]
        left_heart_angle = [30, 29, -59, 0, 60, 0, 0]
        right_heart_angle = [-30, 28, -59, 0, 60, 180, 0]
        self.left_record.clear()
        self.left_record.proceed()
        self.right_record.clear()
        self.right_record.proceed()
        self.goto_standby_pose()
        if self.task_status != AdamTaskStatus.idle:
            return 'not ok, now is {}'.format(self.task_status)
        else:
            self.change_adam_status(AdamTaskStatus.warm)
        try:
            # 全是相对运动，第一步位置必须固定
            self.goto_angles(Arm.left, angles=adam_schema.Angles.list_to_obj(left_init_angle), speed=warm_speed,
                             wait=False)
            self.goto_angles(Arm.right, angles=adam_schema.Angles.list_to_obj(right_init_angle), speed=warm_speed,
                             wait=True)

            self.goto_relative_angles(Arm.left, angles=[-180, 0, 0, 0, 0, 0], speed=warm_speed, wait=False)
            self.goto_relative_angles(Arm.right, angles=[180, 0, 0, 0, 0, 0], speed=warm_speed, wait=False)
            self.goto_relative_angles(Arm.left, angles=[90, 0, 0, 0, 0, 0], speed=warm_speed, wait=False)
            self.goto_relative_angles(Arm.right, angles=[-90, 0, 0, 0, 0, 0], speed=warm_speed, wait=True)
            self.goto_relative_angles(Arm.left, angles=[0, -90, 30, -135, 0, 0], speed=warm_speed,
                                      wait=False)  # -> [42.3, -81.3, -4.5, -180.9, 42.8, -38.7]
            self.goto_relative_angles(Arm.right, angles=[0, -90, 30, 135, 0, 0], speed=warm_speed, wait=False)
            self.goto_relative_angles(Arm.left, angles=[0, 30, -30, 135, -60, 0], speed=warm_speed,
                                      wait=False)  # -> [42.3, -51.3, -34.5, -45.9, -17.2, -38.7]
            self.goto_relative_angles(Arm.right, angles=[0, 30, -30, -135, -60, 0], speed=warm_speed, wait=True)
            self.goto_relative_angles(Arm.left, angles=[0, 30, 0, 0, 0, 0], speed=int(warm_speed / 2), wait=False)
            self.goto_relative_angles(Arm.right, angles=[0, 30, 0, 0, 0, 0], speed=int(warm_speed / 2), wait=False)
            self.goto_relative_angles(Arm.left, angles=[0, 0, -40, 200, 0, 0], speed=warm_speed, wait=False)
            self.goto_relative_angles(Arm.right, angles=[0, 0, -40, -200, 0, 0], speed=warm_speed, wait=True)
            self.goto_relative_angles(Arm.left, angles=[0, 30, 0, 0, 0, 0], speed=int(warm_speed / 2), wait=False)
            self.goto_relative_angles(Arm.right, angles=[0, 30, 0, 0, 0, 0], speed=int(warm_speed / 2), wait=False)
            self.goto_relative_angles(Arm.left, angles=[0, 0, -30, -100, 0, 0], speed=warm_speed, wait=False)
            self.goto_relative_angles(Arm.right, angles=[0, 0, -30, 100, 0, 0], speed=warm_speed, wait=True)
            self.goto_relative_angles(Arm.left, angles=[0, 30, 0, 0, 0, 0], speed=int(warm_speed / 2), wait=False)
            self.goto_relative_angles(Arm.right, angles=[0, 30, 0, 0, 0, 0], speed=int(warm_speed / 2), wait=False)
            self.goto_relative_angles(Arm.left, angles=[0, 0, -30, -100, 0, 0], speed=warm_speed, wait=False)
            self.goto_relative_angles(Arm.right, angles=[0, 0, -30, 100, 0, 0], speed=warm_speed, wait=True)
            self.goto_relative_angles(Arm.left, angles=[0, 30, 0, 0, 0, 0], speed=int(warm_speed / 2), wait=False)
            self.goto_relative_angles(Arm.right, angles=[0, 30, 0, 0, 0, 0], speed=int(warm_speed / 2), wait=False)
            self.goto_relative_angles(Arm.left, angles=[0, 0, -50, 0, 45, 0], speed=warm_speed, wait=False)
            self.goto_relative_angles(Arm.right, angles=[0, 0, -50, 0, 45, 0], speed=warm_speed, wait=True)
            self.goto_angles(Arm.left, angles=adam_schema.Angles.list_to_obj(left_heart_angle), speed=warm_speed,
                             wait=False)
            self.goto_angles(Arm.right, angles=adam_schema.Angles.list_to_obj(right_heart_angle), speed=warm_speed + 5,
                             wait=False)
            self.goto_angles(Arm.left, angles=adam_schema.Angles.list_to_obj(left_init_angle),
                             speed=warm_speed, wait=False)
            self.goto_angles(Arm.right, angles=adam_schema.Angles.list_to_obj(right_init_angle),
                             speed=warm_speed + 5, wait=True)

            self.left_record.pause()
            self.right_record.pause()

        except Exception as e:
            logger.warning('sth err in warm up, err={}'.format(e))
            err_count = adam_crud.get_warm_up_err_time()
            if err_count >= 2:
                AudioInterface.gtts('start error, please shut down and contact the manager')
            adam_crud.update_one_tap('warm_up', err_count + 1)
            exit(-1)
        else:
            logger.info('every thing is ok in warm up')
            adam_crud.update_one_tap('warm_up', 0)
            self.change_adam_status(AdamTaskStatus.idle)
            return 'ok'

    def back(self, which, file_path):
        """
        rollback according to the records in file
        """
        logger.info('before {} record thread rollback'.format(which))
        arm = self.env.one_arm(which)
        arm.motion_enable(enable=True)
        arm.set_mode(0)
        arm.set_state(state=0)
        time.sleep(0.5)
        arm.set_gripper_enable(True)
        arm.set_gripper_mode(0)
        arm.set_gripper_position(self.env.gripper_open_pos, wait=True)  # open gripper first
        arm.set_gripper_position(400, wait=True)  # open gripper first
        logger.info('{} record thread rolling back'.format(which))
        if not os.path.exists(file_path):
            return 0, 'do not neet to end after roll back'

        roll_pos = []
        with open(file_path) as f:
            p_csv = csv.reader(f)
            pos = list(p_csv)
            for i in range(len(pos)):
                line = list(map(float, pos[i]))
                if i == 0:
                    roll_pos.append(line)
                elif line == roll_pos[-1]:
                    continue
                else:
                    roll_pos.append(line)

        count = len(roll_pos)
        logger.debug('start rolling')
        init_position = self.initial_position(which)
        compare = [init_position.x, init_position.y, init_position.z]
        while arm.connected and arm.state != 4:
            if count == 1 or count % 10 == 0:
                logger.debug('the last rolling')
                code = arm.set_servo_angle(angle=roll_pos[count - 1], radius=2, wait=True, speed=20)
                if code != 0:
                    return 2, 'roll back error'
            elif count > 0:
                code = arm.set_servo_angle(angle=roll_pos[count - 1], radius=2, wait=False, speed=20)
                if code != 0:
                    return 2, 'roll back error'
            count = count - 1
            if count == 0:
                self.goto_initial_position_direction(which, 0, wait=True, speed=20)  # 回零点
                while True:
                    print(arm.position[:3])
                    end = utils.compare_value(arm.position[:3], compare, abs_tol=1)
                    if end:
                        time.sleep(0.5)
                        check1 = utils.compare_value(arm.position[:3], compare, abs_tol=1)
                        time.sleep(0.5)
                        check2 = utils.compare_value(arm.position[:3], compare, abs_tol=1)
                        time.sleep(0.5)
                        check3 = utils.compare_value(arm.position[:3], compare, abs_tol=1)
                        time.sleep(0.5)
                        check4 = utils.compare_value(arm.position[:3], compare, abs_tol=1)
                        if check1 and check2 and check3 and check4:
                            logger.info(' {} arm really end'.format(which))
                            break
                        else:
                            logger.info('not real')
                    else:
                        time.sleep(1)
                break
        else:
            return 2, 'state is 4, do not change adam status'
        logger.info('{} record thread rollback complete'.format(which))
        return 1, 'need to end after roll'  # not use now

    def roll(self):
        logger.warning('adam prepare to roll back')
        AudioInterface.gtts('/richtech/resource/audio/voices/start_roll.mp3', True)
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.dead]:
            return 'don\'t need to roll back'
        self.change_adam_status(AdamTaskStatus.rolling)
        time.sleep(17)  # wait for someone to be ready to take the cup and shaker
        self.left_roll_end = False
        self.right_roll_end = False

        def roll_end():
            logger.debug('try to roll end with left_roll_end={}, right_roll_end={}'.format(self.left_roll_end,
                                                                                           self.right_roll_end))
            if self.left_roll_end and self.right_roll_end:
                logger.debug('real roll end, change Adam status to idle')
                self.task_status = AdamTaskStatus.restart
                self.error_msg.clear()

        def dead(which):
            self.task_status = AdamTaskStatus.dead
            arm = self.env.one_arm(which)
            time.sleep(5)
            logger.debug('wait after 5s, before manual in dead')
            if arm.state == 4:
                arm.set_state(state=0)
            default_weight = self.adam_config.gripper_config['default'].tcp_load.weight
            default_tool_gravity = list(
                self.adam_config.gripper_config['default'].tcp_load.center_of_gravity.dict().values())
            arm.set_tcp_load(weight=default_weight, center_of_gravity=default_tool_gravity)  # 恢复默认设置夹爪载重
            arm.motion_enable(enable=True)
            arm.clean_warn()
            arm.clean_error()
            arm.set_mode(mode=2)
            arm.set_state(state=0)
            for i in range(3):
                logger.debug('start try open manual mode for {} time in dead'.format(i))
                arm.set_state(state=0)
                arm.motion_enable(enable=True)
                arm.clean_warn()
                arm.clean_error()
                arm.set_mode(mode=2)
                arm.set_state(state=0)
                logger.debug('end try open manual mode for {} time in dead'.format(i))
                time.sleep(1)
            if self.left.mode != 2 or self.right.mode != 2:
                AudioInterface.gtts(define.AudioConstant.get_mp3_file(define.AudioConstant.TextCode.manual_failed))
                logger.warning('failed to open manual mode')
            else:
                AudioInterface.gtts(define.AudioConstant.get_mp3_file(define.AudioConstant.TextCode.manual_succeed))
                logger.info('open manual mode successfully')

        def left_roll():
            lflag, msg = self.back(Arm.left, self.env.get_record_path(Arm.left))
            logger.debug('left back flag = {}, {}'.format(lflag, msg))
            if lflag == 0:
                self.left_roll_end = True
                roll_end()
            elif lflag == 1:
                self.left_roll_end = True
                roll_end()
            else:
                logger.warning('left roll back failed')
                self.env.adam.set_state(dict(state=4), dict(state=4))
                dead(Arm.left)
            logger.warning('adam left arm roll back end')

        def right_roll():
            rflag, msg = self.back(Arm.right, self.env.get_record_path(Arm.right))
            logger.debug('right back flag = {}, {}'.format(rflag, msg))
            if rflag == 0:
                self.right_roll_end = True
                roll_end()
            elif rflag == 1:
                self.right_roll_end = True
                roll_end()
            else:
                logger.warning('right roll back failed')
                self.env.adam.set_state(dict(state=4), dict(state=4))
                dead(Arm.right)
            logger.warning('adam right arm roll back end')

        thread_list = [
            threading.Thread(target=left_roll),
            threading.Thread(target=right_roll)
        ]
        for t in thread_list:
            t.start()
        for t in thread_list:
            t.join()
        return 'ok'

    def manual(self, which, mode=2):
        arm = self.env.one_arm(which)
        arm.set_state(state=0)
        arm.motion_enable(enable=True)
        time.sleep(0.5)
        arm.clean_warn()
        arm.clean_error()
        arm.set_mode(mode=mode)
        arm.set_state(state=0)
        return arm.mode

    def init_adam(self):
        self.env.init_adam()

    def dance_random(self, choice):
        default_speed = 600

        def dance1():
            # hi
            AudioInterface.music('hi.mp3')

            if self.task_status == AdamTaskStatus.dancing:
                self.right.set_position(x=156.8, y=-708, z=1256, roll=-1.7, pitch=-11.9, yaw=175, speed=800, wait=True)
                for i in range(4):
                    self.right.set_position(x=149, y=-402, z=1185, roll=27.7, pitch=-11.2, yaw=175, speed=800,
                                            wait=False)
                    self.right.set_position(x=156.8, y=-708, z=1256, roll=-1.7, pitch=-11.9, yaw=175, speed=800,
                                            wait=False)
                self.right.set_servo_angle(angle=[-132.32, 8.69, -34.49, 45.93, 42.84, 38.71], speed=40, wait=True)

        def dance2():
            # heart
            AudioInterface.music('whistle.mp3')
            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_servo_angle(
                    left={'angle': [141.3, 17.2, -41.7, -58.5, 71.1, -24.1], 'speed': 50, 'wait': True},  # init
                    right={'angle': [-141.3, 17.2, -41.7, 58.5, 71.1, 24.1], 'speed': 50, 'wait': True}
                )

            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 0, 'y': 60, 'z': 930, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 450, 'wait': True},
                    right={'x': 0, 'y': -60, 'z': 930, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 200, 'wait': True}
                )

            for i in range(3):
                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(
                        left={'x': 0, 'y': 160, 'z': 930, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 350,
                              'wait': False},
                        right={'x': 0, 'y': 40, 'z': 930, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 350,
                               'wait': False}
                    )
                    self.env.adam.set_position(
                        left={'x': 0, 'y': -40, 'z': 930, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 350,
                              'wait': False},
                        right={'x': 0, 'y': -160, 'z': 930, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 350,
                               'wait': False}
                    )
            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 0, 'y': 60, 'z': 930, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 250, 'wait': True},
                    right={'x': 0, 'y': -60, 'z': 930, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 250, 'wait': True}
                )
                #
            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_servo_angle(
                    left={'angle': [148.5, 20, -46.3, -52.1, 74.7, -23.9], 'speed': 20, 'wait': True},
                    right={'angle': [-148.5, 20, -46.3, 52.1, 74.7, 23.9], 'speed': 27, 'wait': True},
                )

        def dance3():
            # cheer

            def get_position_value(position, **kwargs):
                v = ['x', 'y', 'z', 'roll', 'pitch', 'yaw']
                value = dict(zip(v, position))
                kwargs.setdefault('speed', 1000)
                kwargs.setdefault('mvacc', 1000)
                return dict(value, **kwargs)

            def set_adam_position(point_name, left_speed=None, right_speed=None, wait=False, mvacc=None, radius=10):
                left_speed = left_speed or default_speed
                right_speed = right_speed or default_speed
                left = get_position_value(data[Arm.left][point_name]['position'],
                                          wait=wait, radius=radius, speed=left_speed, mvacc=mvacc)
                right = get_position_value(data[Arm.right][point_name]['position'],
                                           wait=wait, radius=radius, speed=right_speed, mvacc=mvacc)
                self.env.adam.set_position(left, right)

            def get_next_point_speed(point_name):
                left_p, right_p = self.env.adam.position
                [x1, y1, z1] = left_p[:3]
                [x2, y2, z2] = data[Arm.left][point_name]['position'][:3]
                left_d = ((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2) ** 0.5
                [x1, y1, z1] = right_p[:3]
                [x2, y2, z2] = data[Arm.right][point_name]['position'][:3]
                right_d = ((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2) ** 0.5
                if left_d > right_d:
                    s = int(left_d / right_d * default_speed)
                    return default_speed, s
                else:
                    s = int(left_d / right_d * default_speed)
                    return s, default_speed

            data = utils.read_resource_json('/adam/data/dance.json')
            AudioInterface.music('wa.mp3')
            set_adam_position('zero', wait=True)
            # 同时运动到挥手位置
            left_speed, right_speed = get_next_point_speed('huang-you')
            set_adam_position('huang-you', left_speed=left_speed, right_speed=right_speed)
            # 左右挥手
            start_hui_time = time.perf_counter()
            for i in range(3):
                set_adam_position('huang-zuo', left_speed=1000, right_speed=1000, mvacc=1000)
                set_adam_position('huang-you', left_speed=1000, right_speed=1000, mvacc=1000)
            set_adam_position('huang-you', wait=True)
            logger.info('hui-show used time={}'.format(time.perf_counter() - start_hui_time))
            # 挥手后回到初始位置
            left_speed, right_speed = get_next_point_speed('zero')
            set_adam_position('zero', left_speed=left_speed, right_speed=right_speed, wait=True)

        def dance4():
            logger.info('dance4!!!')
            AudioInterface.music('YouNeverCanTell.mp3')
            for i in range(4):
                # 两者手臂左右晃动
                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(
                        right={'x': 310, 'y': -550, 'z': 250, 'roll': 11, 'pitch': 90, 'yaw': 11, 'speed': 400,
                               'wait': True},
                        left={'x': 310, 'y': 550, 'z': 250, 'roll': -11, 'pitch': 90, 'yaw': -11, 'speed': 400,
                              'wait': True}
                    )

                for i in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.env.adam.set_position(  #
                            right={'x': 336, 'y': -187, 'z': 631, 'roll': -33, 'pitch': -4, 'yaw': -42, 'speed': 400,
                                   'wait': False},
                            left={'x': 336, 'y': 247, 'z': 521, 'roll': 33, 'pitch': 4, 'yaw': 42, 'speed': 400,
                                  'wait': True}
                        )
                        self.env.adam.set_position(
                            right={'x': 336, 'y': -247, 'z': 521, 'roll': -33, 'pitch': -4, 'yaw': -42, 'speed': 400,
                                   'wait': False},
                            left={'x': 336, 'y': 187, 'z': 631, 'roll': 33, 'pitch': 4, 'yaw': 42, 'speed': 400,
                                  'wait': True}
                        )
                # 胸前两只手臂左右摇晃
                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(
                        right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 400,
                               'wait': True},
                        left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 400,
                              'wait': True}
                    )

                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(
                        left={'x': 395, 'y': 105, 'z': 763, 'roll': 0, 'pitch': 0, 'yaw': -90, 'speed': 400,
                              'wait': False},
                        right={'x': 395, 'y': -105, 'z': 763, 'roll': -0, 'pitch': 0, 'yaw': 90, 'speed': 400,
                               'wait': True}
                    )

                for i in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.env.adam.set_position(  #
                            right={'x': 395, 'y': -300, 'z': 863, 'roll': 0, 'pitch': -40, 'yaw': 90, 'speed': 400,
                                   'wait': False},
                            left={'x': 395, 'y': -10, 'z': 763, 'roll': 0, 'pitch': 40, 'yaw': -90, 'speed': 400,
                                  'wait': True}
                        )
                        self.env.adam.set_position(
                            right={'x': 395, 'y': 10, 'z': 763, 'roll': 0, 'pitch': 40, 'yaw': 90, 'speed': 400,
                                   'wait': False},
                            left={'x': 395, 'y': 300, 'z': 863, 'roll': 0, 'pitch': -40, 'yaw': -90, 'speed': 400,
                                  'wait': True}
                        )

                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(
                        right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 400,
                               'wait': False},
                        left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 400,
                              'wait': True}
                    )
                # 动作剪刀手
                for i in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.env.adam.set_position(
                            left={'x': 395, 'y': 107, 'z': 429, 'roll': -70, 'pitch': 82, 'yaw': -154, 'speed': 400,
                                  'wait': False},
                            right={'x': 283, 'y': -107, 'z': 830, 'roll': 34, 'pitch': 10, 'yaw': 177, 'speed': 400,
                                   'wait': True}
                        )
                        self.env.adam.set_position(
                            right={'x': 395, 'y': -107, 'z': 429, 'roll': 70, 'pitch': 82, 'yaw': 154, 'speed': 400,
                                   'wait': False},
                            left={'x': 283, 'y': 107, 'z': 830, 'roll': -34, 'pitch': 0, 'yaw': -177, 'speed': 400,
                                  'wait': True}
                        )

        def dance5():
            logger.info('dance5!!!')

            self.task_status = AdamTaskStatus.dancing
            self.env.adam.set_tcp_offset(dict(offset=[0] * 6), dict(offset=[0] * 6))
            self.env.adam.set_state(dict(state=0), dict(state=0))
            default_speed = 600
            start_time = time.perf_counter()

            left_angles, right_angles = self.get_initial_position()
            logger.info('left_angles={}, right_angles={}'.format(left_angles, right_angles))
            self.env.adam.set_servo_angle(dict(angle=left_angles, speed=20, wait=True),
                                          dict(angle=right_angles, speed=20, wait=True))
            AudioInterface.music('dance.mp3')

            def get_position_value(position, **kwargs):
                v = ['x', 'y', 'z', 'roll', 'pitch', 'yaw']
                value = dict(zip(v, position))
                kwargs.setdefault('speed', 1000)
                kwargs.setdefault('mvacc', 1000)
                return dict(value, **kwargs)

            def set_adam_position(point_name, left_speed=None, right_speed=None, wait=False, mvacc=None, radius=10):
                left_speed = left_speed or default_speed
                right_speed = right_speed or default_speed
                left = get_position_value(data[Arm.left][point_name]['position'],
                                          wait=wait, radius=radius, speed=left_speed, mvacc=mvacc)
                right = get_position_value(data[Arm.right][point_name]['position'],
                                           wait=wait, radius=radius, speed=right_speed, mvacc=mvacc)
                self.env.adam.set_position(left, right)

            def get_next_point_speed(point_name):
                left_p, right_p = self.env.adam.position
                [x1, y1, z1] = left_p[:3]
                [x2, y2, z2] = data[Arm.left][point_name]['position'][:3]
                left_d = ((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2) ** 0.5
                [x1, y1, z1] = right_p[:3]
                [x2, y2, z2] = data[Arm.right][point_name]['position'][:3]
                right_d = ((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2) ** 0.5
                if left_d > right_d:
                    s = int(left_d / right_d * default_speed)
                    return default_speed, s
                else:
                    s = int(left_d / right_d * default_speed)
                    return s, default_speed

            data = utils.read_resource_json('/adam/data/dance1.json')
            for i in range(6):
                if self.task_status == AdamTaskStatus.making:
                    break
                # 回到舞蹈初始点
                set_adam_position('zero')
                # hello
                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(None, get_position_value(data[Arm.right]['hello1']['position'], wait=True))
                # hello 2次
                for i in range(2):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.env.adam.set_position(None, get_position_value(data[Arm.right]['hello2']['position']))
                        self.env.adam.set_position(None, get_position_value(data[Arm.right]['hello1']['position']))

                # # 回到舞蹈初始点
                if self.task_status == AdamTaskStatus.dancing:
                    set_adam_position('zero', wait=True)
                # # 同时运动到挥手位置
                if self.task_status == AdamTaskStatus.dancing:
                    left_speed, right_speed = get_next_point_speed('huang-you')
                    set_adam_position('huang-you', left_speed=left_speed, right_speed=right_speed)
                # # 左右挥手
                if self.task_status == AdamTaskStatus.dancing:
                    start_hui_time = time.perf_counter()
                for i in range(6):
                    if self.task_status == AdamTaskStatus.dancing:
                        set_adam_position('huang-zuo', left_speed=1000, right_speed=1000, mvacc=1000)
                        set_adam_position('huang-you', left_speed=1000, right_speed=1000, mvacc=1000)
                if self.task_status == AdamTaskStatus.dancing:
                    set_adam_position('huang-you', wait=True)
                logger.info('hui-show used time={}'.format(time.perf_counter() - start_hui_time))
                # 挥手后回到初始位置
                left_speed, right_speed = get_next_point_speed('zero')
                if self.task_status == AdamTaskStatus.dancing:
                    set_adam_position('zero', left_speed=left_speed, right_speed=right_speed, wait=True)
                # 切菜
                if self.task_status == AdamTaskStatus.dancing:
                    set_adam_position('qian_shen', wait=True)
                fu_du = 50
                for i in range(8):
                    left_position = deepcopy(data[Arm.left]['qie-cai']['position'])
                    right_position = deepcopy(data[Arm.right]['qie-cai']['position'])
                    if i % 2 == 0:
                        left_position[2] += fu_du
                        right_position[2] -= fu_du
                    else:
                        left_position[2] -= fu_du
                        right_position[2] += fu_du
                    y_pian = [0, -50, -100, -50, 0, 50, 100, 50]
                    left_position[1] += y_pian[i]
                    right_position[1] += y_pian[i]
                    left = get_position_value(left_position, radius=50)
                    right = get_position_value(right_position, radius=50)
                    if self.task_status == AdamTaskStatus.dancing:
                        self.env.adam.set_position(left, right)
                # zero
                if self.task_status == AdamTaskStatus.dancing:
                    set_adam_position('zero', wait=True)
                # 画圆
                # 比爱心
                if self.task_status == AdamTaskStatus.dancing:
                    set_adam_position('ai-zhong', left_speed=400, right_speed=400)
                    set_adam_position('ai', left_speed=400, right_speed=400)
                # 爱心左右移动
                for i in range(2):
                    if self.task_status == AdamTaskStatus.dancing:
                        set_adam_position('ai-left')
                        set_adam_position('ai-right')
                # 回到标准爱心位置
                if self.task_status == AdamTaskStatus.dancing:
                    set_adam_position('ai')
                # 回到舞蹈初始点
                if self.task_status == AdamTaskStatus.dancing:
                    set_adam_position('ai-zhong', left_speed=400, right_speed=400)
                    set_adam_position('zero', left_speed=400, right_speed=400, wait=True)
                    set_adam_position('prepare', wait=True)
                logger.info('dance use_time={}'.format(time.perf_counter() - start_time))

        def dance6():
            logger.info('dance6!!!')
            AudioInterface.music('Saturday_night_fever_dance.mp3')

            for i in range(7):
                # 抱胸姿势
                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(  #
                        right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 800,
                               'wait': False},
                        left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 800,
                              'wait': True}
                    )
                # 右手胸前摇晃
                for i in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.right.set_position(x=355, y=-100, z=630, roll=0, pitch=60, yaw=90, speed=800, wait=True)
                        self.right.set_position(x=515, y=-161, z=593, roll=64, pitch=17.7, yaw=126, speed=800,
                                                wait=True)

                # 左右手交替胸前摇晃
                for i in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.env.adam.set_position(
                            right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 800,
                                   'wait': False},
                            left={'x': 515, 'y': 161, 'z': 593, 'roll': -64, 'pitch': 17.7, 'yaw': -126, 'speed': 800,
                                  'wait': True}
                        )
                        self.env.adam.set_position(
                            right={'x': 515, 'y': -161, 'z': 593, 'roll': 64, 'pitch': 17.7, 'yaw': 126, 'speed': 800,
                                   'wait': False},
                            left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 800,
                                  'wait': True}
                        )
                # 两只手交替往前伸出
                for i in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.env.adam.set_position(
                            left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 800,
                                  'wait': False},
                            right={'x': 505, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 800,
                                   'wait': True}
                        )
                        self.env.adam.set_position(
                            left={'x': 505, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 800,
                                  'wait': False},
                            right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 800,
                                   'wait': True}
                        )
                # 右手挥手
                for i in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.right.set_position(x=245, y=-437, z=908, roll=22, pitch=-5, yaw=1, speed=800, wait=False)
                        self.right.set_position(x=278, y=-242, z=908, roll=-15, pitch=1, yaw=-1, speed=800, wait=False)
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(x=355, y=-100, z=630, roll=0, pitch=60, yaw=90, speed=800, wait=True)

                # 左手挥手
                for i in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.left.set_position(x=245, y=437, z=908, roll=-22, pitch=-5, yaw=1, speed=800, wait=False)
                        self.left.set_position(x=278, y=242, z=908, roll=15, pitch=1, yaw=-1, speed=800, wait=False)
                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(
                        left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 800,
                              'wait': False},
                        right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 800,
                               'wait': True}
                    )

        def dance7bk():
            logger.info('dance7!!!')
            AudioInterface.music('Because_of_You.mp3')

            for i in range(1):
                right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
                left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
                # 右拍手
                right_Pos1 = {'x': 326, 'y': -320, 'z': 1049, 'roll': 0, 'pitch': 0, 'yaw': 90}
                left_Pos1 = {'x': 326, 'y': -20, 'z': 1049, 'roll': 0, 'pitch': 0, 'yaw': -90}
                right_Pos2 = {'x': 326, 'y': -260, 'z': 1049, 'roll': 0, 'pitch': 0, 'yaw': 90}
                left_Pos2 = {'x': 326, 'y': -80, 'z': 1049, 'roll': 0, 'pitch': 0, 'yaw': -90}
                # 左拍手
                right_Pos3 = {'x': 326, 'y': 20, 'z': 1049, 'roll': 0, 'pitch': 0, 'yaw': 90}
                left_Pos3 = {'x': 326, 'y': 320, 'z': 1049, 'roll': 0, 'pitch': 0, 'yaw': -90}
                right_Pos4 = {'x': 326, 'y': 80, 'z': 1049, 'roll': 0, 'pitch': 0, 'yaw': 90}
                left_Pos4 = {'x': 326, 'y': 260, 'z': 1049, 'roll': 0, 'pitch': 0, 'yaw': -90}
                speed = 300
                speed1 = 350
                speed2 = 500
                self.right.set_position(**right_init, wait=False, speed=speed1, radius=50)
                self.left.set_position(**left_init, wait=True, speed=speed1, radius=50)

                # 左右肩的上方拍手动作
                self.right.set_position(**right_Pos1, wait=False, speed=500, radius=50)
                self.left.set_position(**left_Pos1, wait=True, speed=500, radius=50)
                for _ in range(3):
                    self.right.set_position(**right_Pos1, wait=False, speed=100, radius=50)
                    self.left.set_position(**left_Pos1, wait=True, speed=100, radius=50)
                    self.right.set_position(**right_Pos2, wait=False, speed=500, radius=50)
                    self.left.set_position(**left_Pos2, wait=True, speed=500, radius=50)
                self.right.set_position(**right_init, wait=False, speed=speed1, radius=50)
                self.left.set_position(**left_init, wait=True, speed=speed1, radius=50)
                self.right.set_position(**right_Pos3, wait=False, speed=500, radius=50)
                self.left.set_position(**left_Pos3, wait=True, speed=500, radius=50)
                for _ in range(3):
                    self.right.set_position(**right_Pos3, wait=False, speed=100, radius=50)
                    self.left.set_position(**left_Pos3, wait=True, speed=100, radius=50)
                    self.right.set_position(**right_Pos4, wait=False, speed=500, radius=50)
                    self.left.set_position(**left_Pos4, wait=True, speed=500, radius=50)

                self.left.set_position(**left_init, wait=False, speed=speed1, radius=50)
                self.right.set_position(**right_init, wait=True, speed=speed1, radius=50)

                # 敲鼓动作
                right_Pos5 = {'x': 428, 'y': -116, 'z': 378, 'roll': -84, 'pitch': 84, 'yaw': -12}
                left_Pos5 = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
                right_Pos6 = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
                left_Pos6 = {'x': 428, 'y': 116, 'z': 378, 'roll': 84, 'pitch': 84, 'yaw': 12}

                for i in range(3):
                    self.left.set_position(**left_Pos5, wait=False, speed=speed1, radius=50)
                    self.right.set_position(**right_Pos5, wait=True, speed=speed1, radius=50)
                    self.right.set_position(**right_Pos6, wait=False, speed=speed1, radius=50)
                    self.left.set_position(**left_Pos6, wait=True, speed=speed1, radius=50)

                # 左右手交替护胸口
                # self.right.set_position(**right_init, wait=False, speed=speed1, radius=50)
                # self.left.set_position(**left_init, wait=True, speed=speed1, radius=50)
                right_Pos14 = {'x': 441, 'y': -99, 'z': 664, 'roll': 36, 'pitch': 33, 'yaw': 153}
                left_Pos14 = {'x': 555, 'y': 198, 'z': 240, 'roll': 100, 'pitch': 75, 'yaw': 41}

                right_Pos15 = {'x': 274, 'y': -20, 'z': 664, 'roll': 36, 'pitch': 33, 'yaw': 153}

                right_Pos16 = {'x': 555, 'y': -198, 'z': 240, 'roll': -100, 'pitch': 75, 'yaw': -41}
                left_Pos16 = {'x': 441, 'y': 99, 'z': 664, 'roll': -36, 'pitch': 33, 'yaw': -153}

                left_Pos17 = {'x': 274, 'y': 20, 'z': 664, 'roll': -36, 'pitch': 33, 'yaw': -153}
                self.right.set_position(**right_Pos14, wait=False, speed=350, radius=50)
                self.left.set_position(**left_Pos14, wait=True, speed=500, radius=50)
                for i in range(2):
                    self.right.set_position(**right_Pos15, wait=False, speed=400, radius=50)
                    self.right.set_position(**right_Pos14, wait=True, speed=250, radius=50)
                self.right.set_position(**right_Pos16, wait=False, speed=500, radius=50)
                self.left.set_position(**left_Pos16, wait=True, speed=600, radius=50)
                for i in range(2):
                    self.left.set_position(**left_Pos17, wait=False, speed=400, radius=50)
                    self.left.set_position(**left_Pos16, wait=True, speed=250, radius=50)
                self.right.set_position(**right_init, wait=False, speed=speed1, radius=50)
                self.left.set_position(**left_init, wait=True, speed=speed1, radius=50)

                # # 敲鼓动作
                # right_Pos5 = {'x': 428, 'y': -116, 'z': 378, 'roll': -84, 'pitch': 84, 'yaw': -12}
                # left_Pos5 = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
                # right_Pos6 = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
                # left_Pos6 = {'x': 428, 'y': 116, 'z': 378, 'roll': 84, 'pitch': 84, 'yaw': 12}
                #
                # for i in range(3):
                #     self.left.set_position(**left_Pos5, wait=False, speed=speed1, radius=50)
                #     self.right.set_position(**right_Pos5, wait=True, speed=speed1, radius=50)
                #     self.right.set_position(**right_Pos6, wait=False, speed=speed1, radius=50)
                #     self.left.set_position(**left_Pos6, wait=True, speed=speed1, radius=50)

                # 敬礼动作
                right_angle1 = [-59.2, -16.7, -35.8, 126.4, -2.1, -20.5]
                left_angle1 = [152.4, 1, -31.9, -27.6, 8.1, -53.1]
                right_angle2 = [-152.4, 1, -31.9, 27.6, 8.1, 53.1]
                left_angle2 = [59.2, -16.7, -35.8, -126.4, -2.1, 20.5]
                for i in range(3):
                    self.left.set_servo_angle(angle=left_angle1, speed=60, wait=False)
                    self.right.set_servo_angle(angle=right_angle1, speed=80, wait=True)
                    self.left.set_servo_angle(angle=left_angle2, speed=80, wait=False)
                    self.right.set_servo_angle(angle=right_angle2, speed=60, wait=True)

                # 摇摆动作
                self.right.set_position(**right_init, wait=False, speed=speed1, radius=50)
                self.left.set_position(**left_init, wait=True, speed=speed1, radius=50)
                right_Pos7 = {'x': 400, 'y': -100, 'z': 1000, 'roll': 0, 'pitch': 0, 'yaw': 90}
                left_Pos7 = {'x': 400, 'y': 100, 'z': 1000, 'roll': 0, 'pitch': 0, 'yaw': -90}
                right_Pos8 = {'x': 400, 'y': -100, 'z': 850, 'roll': 0, 'pitch': 0, 'yaw': 90}
                left_Pos8 = {'x': 400, 'y': 100, 'z': 850, 'roll': 0, 'pitch': 0, 'yaw': -90}
                self.right.set_position(**right_Pos7, wait=True, speed=speed1, radius=50)
                self.right.set_position(**right_Pos8, wait=True, speed=speed1, radius=50)
                self.left.set_position(**left_Pos7, wait=True, speed=speed1, radius=50)
                self.left.set_position(**left_Pos8, wait=True, speed=speed1, radius=50)
                # right_Pos9 = {'x': 400, 'y': -199, 'z': 850, 'roll': 0, 'pitch': 0, 'yaw': 90}
                # left_Pos9 = {'x': 400, 'y': -1, 'z': 850, 'roll': 0, 'pitch': 0, 'yaw': -90}
                # right_Pos10 = {'x': 400, 'y': 1, 'z': 850, 'roll': 0, 'pitch': 0, 'yaw': 90}
                # left_Pos10 = {'x': 400, 'y': 199, 'z': 850, 'roll': 0, 'pitch': 0, 'yaw': -90}
                # for i in range(3):
                #     self.right.set_position(**right_Pos9, wait=False, speed=speed1, radius=50)
                #     self.left.set_position(**left_Pos9, wait=True, speed=speed1, radius=50)
                #     self.right.set_position(**right_Pos10, wait=False, speed=speed1, radius=50)
                #     self.left.set_position(**left_Pos10, wait=True, speed=speed1, radius=50)
                # self.right.set_position(**right_Pos8, wait=False, speed=speed1, radius=50)
                # self.left.set_position(**left_Pos8, wait=True, speed=speed1, radius=50)

                right_pos_A = {'x': 500, 'y': -100, 'z': 850, 'roll': 0, 'pitch': 0, 'yaw': 90}
                left_pos_A = {'x': 500, 'y': 100, 'z': 850, 'roll': 0, 'pitch': 0, 'yaw': -90}
                right_pos_B = [440, -40, 850, 0, 0, 90]
                right_pos_C = [440, -160, 850, 0, 0, 90]
                self.right.set_position(**right_pos_A, speed=100, wait=False)
                self.right.move_circle(right_pos_B, right_pos_C, percent=300, speed=100, wait=False)
                self.right.move_circle(right_pos_C, right_pos_B, percent=300, speed=100, wait=False)

                left_pos_B = [440, 160, 850, 0, 0, -90]
                left_pos_C = [440, 40, 850, 0, 0, -90]
                self.left.set_position(**left_pos_A, speed=100, wait=False)
                self.left.move_circle(left_pos_B, left_pos_C, percent=300, speed=100, wait=False)
                self.left.move_circle(left_pos_C, left_pos_B, percent=300, speed=100, wait=False)

                # 亚当肚子前方拍手动作
                right_Pos11 = {'x': 724, 'y': -137, 'z': 514, 'roll': 90, 'pitch': 0, 'yaw': 90}
                left_Pos11 = {'x': 724, 'y': 137, 'z': 514, 'roll': -90, 'pitch': 0, 'yaw': -90}
                right_Pos12 = {'x': 724, 'y': -80, 'z': 514, 'roll': 90, 'pitch': 0, 'yaw': 90}
                left_Pos12 = {'x': 724, 'y': 80, 'z': 514, 'roll': -90, 'pitch': 0, 'yaw': -90}
                # self.right.set_position(**right_Pos11, wait=False, speed=600, radius=50)
                # self.left.set_position(**left_Pos11, wait=False, speed=600, radius=50)
                for _ in range(5):
                    self.right.set_position(**right_Pos11, wait=False, speed=speed1, radius=50)
                    self.left.set_position(**left_Pos11, wait=True, speed=speed1, radius=50)
                    self.right.set_position(**right_Pos12, wait=False, speed=speed1, radius=50)
                    self.left.set_position(**left_Pos12, wait=True, speed=speed1, radius=50)

                right_Pos14 = {'x': 724, 'y': -80, 'z': 564, 'roll': 90, 'pitch': 0, 'yaw': 90}
                left_Pos14 = {'x': 724, 'y': 80, 'z': 464, 'roll': -90, 'pitch': 0, 'yaw': -90}
                right_Pos15 = {'x': 724, 'y': -80, 'z': 464, 'roll': 90, 'pitch': 0, 'yaw': 90}
                left_Pos15 = {'x': 724, 'y': 80, 'z': 564, 'roll': -90, 'pitch': 0, 'yaw': -90}
                for _ in range(3):
                    self.right.set_position(**right_Pos14, wait=False, speed=100, radius=50)
                    self.left.set_position(**left_Pos14, wait=False, speed=100, radius=50)
                    self.right.set_position(**right_Pos15, wait=False, speed=100, radius=50)
                    self.left.set_position(**left_Pos15, wait=False, speed=100, radius=50)

                self.right.set_position(**right_Pos12, wait=False, speed=100, radius=50)
                self.left.set_position(**left_Pos12, wait=True, speed=100, radius=50)

                # 一个手和两个手往前指
                self.right.set_position(**right_init, wait=False, speed=speed1, radius=50)
                self.left.set_position(**left_init, wait=True, speed=speed1, radius=50)
                right_Pos13 = {'x': 817, 'y': -118, 'z': 646, 'roll': 90, 'pitch': 0, 'yaw': 90}
                left_Pos13 = {'x': 817, 'y': 118, 'z': 646, 'roll': -90, 'pitch': 0, 'yaw': -90}
                self.right.set_position(**right_Pos13, wait=True, speed=speed1, radius=50)
                self.left.set_position(**left_Pos13, wait=True, speed=speed1, radius=50)

        def dance7():
            logger.info('dance9!!!')
            # AudioInterface.music_fade_out('Because_of_You.mp3')
            AudioInterface.music('Because_of_You.mp3')

            for i in range(1):
                right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
                left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
                # 右拍手
                right_Pos1 = {'x': 326, 'y': -320, 'z': 1049, 'roll': 0, 'pitch': 0, 'yaw': 90}
                left_Pos1 = {'x': 326, 'y': -20, 'z': 1049, 'roll': 0, 'pitch': 0, 'yaw': -90}
                right_Pos2 = {'x': 326, 'y': -260, 'z': 1049, 'roll': 0, 'pitch': 0, 'yaw': 90}
                left_Pos2 = {'x': 326, 'y': -80, 'z': 1049, 'roll': 0, 'pitch': 0, 'yaw': -90}
                # 左拍手
                right_Pos3 = {'x': 326, 'y': 20, 'z': 1049, 'roll': 0, 'pitch': 0, 'yaw': 90}
                left_Pos3 = {'x': 326, 'y': 320, 'z': 1049, 'roll': 0, 'pitch': 0, 'yaw': -90}
                right_Pos4 = {'x': 326, 'y': 80, 'z': 1049, 'roll': 0, 'pitch': 0, 'yaw': 90}
                left_Pos4 = {'x': 326, 'y': 260, 'z': 1049, 'roll': 0, 'pitch': 0, 'yaw': -90}
                speed1 = 100
                speed2 = 200
                speed3 = 300
                speed4 = 400
                speed5 = 500
                speed7 = 700
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_init, wait=False, speed=speed5, radius=50)
                    self.left.set_position(**left_init, wait=True, speed=speed5, radius=50)

                # 左右肩的上方拍手动作
                # self.right.set_position(**right_Pos1, wait=False, speed=speed5, radius=50)
                # self.left.set_position(**left_Pos1, wait=True, speed=speed5, radius=50)
                for _ in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.right.set_position(**right_Pos1, wait=False, speed=speed5, radius=50)
                        self.left.set_position(**left_Pos1, wait=True, speed=speed5, radius=50)
                        self.right.set_position(**right_Pos2, wait=False, speed=speed5, radius=50)
                        self.left.set_position(**left_Pos2, wait=True, speed=speed5, radius=50)
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_init, wait=False, speed=speed5, radius=50)
                    self.left.set_position(**left_init, wait=True, speed=speed5, radius=50)
                # self.right.set_position(**right_Pos3, wait=False, speed=speed5, radius=50)
                # self.left.set_position(**left_Pos3, wait=True, speed=speed5, radius=50)
                for _ in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.right.set_position(**right_Pos3, wait=False, speed=speed5, radius=50)
                        self.left.set_position(**left_Pos3, wait=True, speed=speed5, radius=50)
                        self.right.set_position(**right_Pos4, wait=False, speed=speed5, radius=50)
                        self.left.set_position(**left_Pos4, wait=True, speed=speed5, radius=50)

                if self.task_status == AdamTaskStatus.dancing:
                    self.left.set_position(**left_init, wait=False, speed=speed5, radius=50)
                    self.right.set_position(**right_init, wait=True, speed=speed5, radius=50)

                # 敲鼓动作
                right_Pos5 = {'x': 428, 'y': -116, 'z': 378, 'roll': -84, 'pitch': 84, 'yaw': -12}
                left_Pos5 = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
                right_Pos6 = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
                left_Pos6 = {'x': 428, 'y': 116, 'z': 378, 'roll': 84, 'pitch': 84, 'yaw': 12}

                for i in range(5):
                    if self.task_status == AdamTaskStatus.dancing:
                        # self.right.set_position(**right_Pos5, wait=False, speed=speed5, radius=50)
                        self.left.set_position(**left_Pos5, wait=False, speed=speed5, radius=50)
                        self.right.set_position(**right_Pos5, wait=True, speed=speed5, radius=50)
                        self.right.set_position(**right_Pos6, wait=False, speed=speed5, radius=50)
                        self.left.set_position(**left_Pos6, wait=True, speed=speed5, radius=50)

                # self.left.set_position(**left_init, wait=False, speed=speed5, radius=50)
                # self.right.set_position(**right_init, wait=True, speed=speed5, radius=50)

                # 左右手交替护胸口
                # self.right.set_position(**right_init, wait=False, speed=speed1, radius=50)
                # self.left.set_position(**left_init, wait=True, speed=speed1, radius=50)
                right_Pos14 = {'x': 441, 'y': -99, 'z': 664, 'roll': 36, 'pitch': 33, 'yaw': 153}
                left_Pos14 = {'x': 555, 'y': 198, 'z': 240, 'roll': 100, 'pitch': 75, 'yaw': 41}

                right_Pos15 = {'x': 274, 'y': -20, 'z': 664, 'roll': 36, 'pitch': 33, 'yaw': 153}

                right_Pos16 = {'x': 555, 'y': -198, 'z': 240, 'roll': -100, 'pitch': 75, 'yaw': -41}
                left_Pos16 = {'x': 441, 'y': 99, 'z': 664, 'roll': -36, 'pitch': 33, 'yaw': -153}

                left_Pos17 = {'x': 274, 'y': 20, 'z': 664, 'roll': -36, 'pitch': 33, 'yaw': -153}
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos14, wait=False, speed=speed5, radius=50)
                    self.left.set_position(**left_Pos14, wait=True, speed=speed5, radius=50)
                for i in range(2):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.right.set_position(**right_Pos15, wait=False, speed=speed5, radius=50)
                        self.right.set_position(**right_Pos14, wait=True, speed=speed5, radius=50)
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos16, wait=False, speed=speed5, radius=50)
                    self.left.set_position(**left_Pos16, wait=True, speed=speed5, radius=50)
                for i in range(2):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.left.set_position(**left_Pos17, wait=False, speed=speed5, radius=50)
                        self.left.set_position(**left_Pos16, wait=True, speed=speed5, radius=50)
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_init, wait=False, speed=speed5, radius=50)
                    self.left.set_position(**left_init, wait=True, speed=speed5, radius=50)

                # # 敲鼓动作
                # right_Pos5 = {'x': 428, 'y': -116, 'z': 378, 'roll': -84, 'pitch': 84, 'yaw': -12}
                # left_Pos5 = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
                # right_Pos6 = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
                # left_Pos6 = {'x': 428, 'y': 116, 'z': 378, 'roll': 84, 'pitch': 84, 'yaw': 12}
                #
                # for i in range(3):
                #     self.left.set_position(**left_Pos5, wait=False, speed=speed1, radius=50)
                #     self.right.set_position(**right_Pos5, wait=True, speed=speed1, radius=50)
                #     self.right.set_position(**right_Pos6, wait=False, speed=speed1, radius=50)
                #     self.left.set_position(**left_Pos6, wait=True, speed=speed1, radius=50)

                # 敬礼动作
                right_angle1 = [-59.2, -16.7, -35.8, 126.4, -2.1, -20.5]
                left_angle1 = [152.4, 1, -31.9, -27.6, 8.1, -53.1]
                right_angle2 = [-152.4, 1, -31.9, 27.6, 8.1, 53.1]
                left_angle2 = [59.2, -16.7, -35.8, -126.4, -2.1, 20.5]
                for i in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.left.set_servo_angle(angle=left_angle1, speed=90, wait=False)
                        self.right.set_servo_angle(angle=right_angle1, speed=90, wait=True)
                        self.left.set_servo_angle(angle=left_angle2, speed=90, wait=False)
                        self.right.set_servo_angle(angle=right_angle2, speed=90, wait=True)

                # 加油
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_init, wait=False, speed=speed5, radius=50)
                    self.left.set_position(**left_init, wait=True, speed=speed5, radius=50)
                right_Pos7 = {'x': 400, 'y': -100, 'z': 1000, 'roll': 0, 'pitch': 0, 'yaw': 90}
                left_Pos7 = {'x': 400, 'y': 100, 'z': 1000, 'roll': 0, 'pitch': 0, 'yaw': -90}
                right_Pos8 = {'x': 400, 'y': -100, 'z': 850, 'roll': 0, 'pitch': 0, 'yaw': 90}
                left_Pos8 = {'x': 400, 'y': 100, 'z': 850, 'roll': 0, 'pitch': 0, 'yaw': -90}
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos7, wait=True, speed=speed5, radius=50)
                    self.right.set_position(**right_Pos8, wait=True, speed=speed5, radius=50)
                    self.left.set_position(**left_Pos7, wait=True, speed=speed5, radius=50)
                    self.left.set_position(**left_Pos8, wait=True, speed=speed5, radius=50)
                # right_Pos9 = {'x': 400, 'y': -199, 'z': 850, 'roll': 0, 'pitch': 0, 'yaw': 90}
                # left_Pos9 = {'x': 400, 'y': -1, 'z': 850, 'roll': 0, 'pitch': 0, 'yaw': -90}
                # right_Pos10 = {'x': 400, 'y': 1, 'z': 850, 'roll': 0, 'pitch': 0, 'yaw': 90}
                # left_Pos10 = {'x': 400, 'y': 199, 'z': 850, 'roll': 0, 'pitch': 0, 'yaw': -90}
                # for i in range(3):
                #     self.right.set_position(**right_Pos9, wait=False, speed=speed1, radius=50)
                #     self.left.set_position(**left_Pos9, wait=True, speed=speed1, radius=50)
                #     self.right.set_position(**right_Pos10, wait=False, speed=speed1, radius=50)
                #     self.left.set_position(**left_Pos10, wait=True, speed=speed1, radius=50)
                # self.right.set_position(**right_Pos8, wait=False, speed=speed1, radius=50)
                # self.left.set_position(**left_Pos8, wait=True, speed=speed1, radius=50)

                # 逆时针画圈
                right_pos_A = {'x': 500, 'y': -100, 'z': 850, 'roll': 0, 'pitch': 0, 'yaw': 90}
                left_pos_A = {'x': 500, 'y': 100, 'z': 850, 'roll': 0, 'pitch': 0, 'yaw': -90}
                right_pos_B = [440, -40, 850, 0, 0, 90]
                right_pos_C = [440, -160, 850, 0, 0, 90]
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_pos_A, speed=100, wait=False)
                    self.right.move_circle(right_pos_B, right_pos_C, percent=300, speed=100, wait=False)
                    self.right.move_circle(right_pos_C, right_pos_B, percent=300, speed=100, wait=False)
                # 顺时针画圈
                left_pos_B = [440, 160, 850, 0, 0, -90]
                left_pos_C = [440, 40, 850, 0, 0, -90]
                if self.task_status == AdamTaskStatus.dancing:
                    self.left.set_position(**left_pos_A, speed=100, wait=False)
                    self.left.move_circle(left_pos_B, left_pos_C, percent=300, speed=100, wait=False)
                    self.left.move_circle(left_pos_C, left_pos_B, percent=300, speed=100, wait=False)

                # 亚当肚子前方拍手动作
                right_Pos11 = {'x': 724, 'y': -137, 'z': 514, 'roll': 90, 'pitch': 0, 'yaw': 90}
                left_Pos11 = {'x': 724, 'y': 137, 'z': 514, 'roll': -90, 'pitch': 0, 'yaw': -90}
                right_Pos12 = {'x': 724, 'y': -80, 'z': 514, 'roll': 90, 'pitch': 0, 'yaw': 90}
                left_Pos12 = {'x': 724, 'y': 80, 'z': 514, 'roll': -90, 'pitch': 0, 'yaw': -90}
                # self.right.set_position(**right_Pos11, wait=False, speed=600, radius=50)
                # self.left.set_position(**left_Pos11, wait=False, speed=600, radius=50)
                for _ in range(5):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.right.set_position(**right_Pos11, wait=False, speed=speed5, radius=50)
                        self.left.set_position(**left_Pos11, wait=True, speed=speed5, radius=50)
                        self.right.set_position(**right_Pos12, wait=False, speed=speed5, radius=50)
                        self.left.set_position(**left_Pos12, wait=True, speed=speed5, radius=50)

                # 上下搓手
                right_Pos14 = {'x': 724, 'y': -80, 'z': 564, 'roll': 90, 'pitch': 0, 'yaw': 90}
                left_Pos14 = {'x': 724, 'y': 80, 'z': 464, 'roll': -90, 'pitch': 0, 'yaw': -90}
                right_Pos15 = {'x': 724, 'y': -80, 'z': 464, 'roll': 90, 'pitch': 0, 'yaw': 90}
                left_Pos15 = {'x': 724, 'y': 80, 'z': 564, 'roll': -90, 'pitch': 0, 'yaw': -90}
                for _ in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.right.set_position(**right_Pos14, wait=False, speed=speed1, radius=50)
                        self.left.set_position(**left_Pos14, wait=False, speed=speed1, radius=50)
                        self.right.set_position(**right_Pos15, wait=False, speed=speed1, radius=50)
                        self.left.set_position(**left_Pos15, wait=False, speed=speed1, radius=50)

                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos12, wait=False, speed=speed5, radius=50)
                    self.left.set_position(**left_Pos12, wait=True, speed=speed5, radius=50)

                # 一个手和两个手往前指
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_init, wait=False, speed=speed5, radius=50)
                    self.left.set_position(**left_init, wait=True, speed=speed5, radius=50)
                right_Pos13 = {'x': 817, 'y': -118, 'z': 646, 'roll': 90, 'pitch': 0, 'yaw': 90}
                left_Pos13 = {'x': 817, 'y': 118, 'z': 646, 'roll': -90, 'pitch': 0, 'yaw': -90}
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos13, wait=True, speed=speed5, radius=50)
                    self.left.set_position(**left_Pos13, wait=True, speed=speed5, radius=50)

                def reduce_sound():
                    for i in range(100, -1, -1):
                        os.system(f"amixer set PCM {i}%")
                        time.sleep(0.08)

                def init_adam():
                    if self.task_status == AdamTaskStatus.dancing:
                        self.right.set_position(**right_init, wait=False, speed=100, radius=50)
                        self.left.set_position(**left_init, wait=True, speed=100, radius=50)

                if self.task_status == AdamTaskStatus.dancing:
                    step_thread = [threading.Thread(target=reduce_sound), threading.Thread(target=init_adam)]
                    for t in step_thread:
                        t.start()
                    for t in step_thread:
                        t.join()

        def dance8():
            # os.system("amixer set PCM 80%")
            logger.info('dance8!!!')
            # AudioInterface.music('BLACKPINK_Shut_Down.mp3')

            # 抱胸位置
            right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
            left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}

            # 左右手初始位置
            def init_adam(speed):
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_init, wait=False, speed=speed, radius=50)
                    self.left.set_position(**left_init, wait=True, speed=speed, radius=50)

            # 平举上
            right_Pos1 = {'x': 380, 'y': -70, 'z': 700, 'roll': -90, 'pitch': 90, 'yaw': 0}
            left_Pos1 = {'x': 380, 'y': 70, 'z': 700, 'roll': 90, 'pitch': 90, 'yaw': 0}
            # 平举下
            right_Pos2 = {'x': 380, 'y': -70, 'z': 450, 'roll': -90, 'pitch': 90, 'yaw': 0}
            left_Pos2 = {'x': 380, 'y': 70, 'z': 450, 'roll': 90, 'pitch': 90, 'yaw': 0}

            # 双手平举
            def raise_down(speed):
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos1, wait=False, speed=speed, radius=50)
                    self.left.set_position(**left_Pos1, wait=True, speed=speed, radius=50)
                    self.right.set_position(**right_Pos2, wait=False, speed=speed, radius=50)
                    self.left.set_position(**left_Pos2, wait=True, speed=speed, radius=50)

            # 上下交替
            right_Pos3 = {'x': 480, 'y': -200, 'z': 800, 'roll': 0, 'pitch': 60, 'yaw': 90}
            left_Pos3 = {'x': 480, 'y': 200, 'z': 800, 'roll': 0, 'pitch': 60, 'yaw': -90}

            def alter_up_down(speed):
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos3, wait=False, speed=speed, radius=50)
                    self.right.set_position(**right_init, wait=True, speed=speed, radius=50)
                    self.left.set_position(**left_Pos3, wait=False, speed=speed, radius=50)
                    self.left.set_position(**left_init, wait=True, speed=speed, radius=50)

            # 画圆
            def right_round(speed):
                #     right_pos_A = {'x': 700, 'y': -350, 'z': 500, 'roll': 0, 'pitch': 90, 'yaw': 0}
                #     right_pos_B = {'x': 700, 'y': -250, 'z': 400, 'roll': 0, 'pitch': 90, 'yaw': 0}
                #     right_pos_C = {'x': 700, 'y': -450, 'z': 400, 'roll': 0, 'pitch': 90, 'yaw': 0}
                right_pos_A = {'x': 700, 'y': -350, 'z': 500, 'roll': 0, 'pitch': 90, 'yaw': 0}
                right_pos_B = [700, -250, 400, 0, 90, 0]
                right_pos_C = [700, -450, 400, 0, 90, 0]
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_pos_A, speed=speed, wait=True)
                    self.right.move_circle(right_pos_B, right_pos_C, percent=200, speed=200, wait=True)

            def left_round(speed):
                left_pos_A = {'x': 700, 'y': 350, 'z': 500, 'roll': 0, 'pitch': 90, 'yaw': 0}
                left_pos_B = [700, 250, 400, 0, 90, 0]
                left_pos_C = [700, 450, 400, 0, 90, 0]
                if self.task_status == AdamTaskStatus.dancing:
                    self.left.set_position(**left_pos_A, speed=speed, wait=True)
                    self.left.move_circle(left_pos_B, left_pos_C, percent=200, speed=200, wait=True)

            # 加油上
            right_Pos4 = {'x': 30, 'y': -650, 'z': 1250, 'roll': 0, 'pitch': 0, 'yaw': 90}
            left_Pos4 = {'x': 30, 'y': 650, 'z': 1250, 'roll': 0, 'pitch': 0, 'yaw': -90}
            # 加油下
            right_Pos5 = {'x': 30, 'y': -650, 'z': 1100, 'roll': 0, 'pitch': 0, 'yaw': 90}
            left_Pos5 = {'x': 30, 'y': 650, 'z': 1100, 'roll': 0, 'pitch': 0, 'yaw': -90}

            def come_on_right(speed):
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos4, wait=False, speed=speed, radius=50)
                    self.right.set_position(**right_Pos5, wait=False, speed=speed, radius=50)

            def come_on_left(speed):
                if self.task_status == AdamTaskStatus.dancing:
                    self.left.set_position(**left_Pos4, wait=False, speed=speed, radius=50)
                    self.left.set_position(**left_Pos5, wait=False, speed=speed, radius=50)

            # 右上下加油
            right_Pos6 = {'x': 400, 'y': -400, 'z': 1000, 'roll': 0, 'pitch': -20, 'yaw': 90}
            left_Pos6 = {'x': 400, 'y': -200, 'z': 1000, 'roll': 0, 'pitch': 20, 'yaw': -90}

            right_Pos7 = {'x': 400, 'y': -260, 'z': 650, 'roll': 0, 'pitch': -20, 'yaw': 90}
            left_Pos7 = {'x': 400, 'y': -60, 'z': 650, 'roll': 0, 'pitch': 20, 'yaw': -90}

            def right_up_down(speed):
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos6, wait=False, speed=speed, radius=50)
                    self.left.set_position(**left_Pos6, wait=False, speed=speed, radius=50)
                    self.right.set_position(**right_Pos7, wait=False, speed=speed, radius=50)
                    self.left.set_position(**left_Pos7, wait=True, speed=speed, radius=50)

            # 左上下加油
            right_Pos8 = {'x': 400, 'y': 200, 'z': 1000, 'roll': 0, 'pitch': 20, 'yaw': 90}
            left_Pos8 = {'x': 400, 'y': 400, 'z': 1000, 'roll': 0, 'pitch': -20, 'yaw': -90}

            right_Pos9 = {'x': 400, 'y': 60, 'z': 650, 'roll': 0, 'pitch': 20, 'yaw': 90}
            left_Pos9 = {'x': 400, 'y': 260, 'z': 650, 'roll': 0, 'pitch': -20, 'yaw': -90}

            def left_up_down(speed):
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos8, wait=False, speed=speed, radius=50)
                    self.left.set_position(**left_Pos8, wait=False, speed=speed, radius=50)
                    self.right.set_position(**right_Pos9, wait=False, speed=speed, radius=50)
                    self.left.set_position(**left_Pos9, wait=True, speed=speed, radius=50)

            right_init1 = {'x': 400, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 0, 'yaw': 90}
            left_init1 = {'x': 400, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 0, 'yaw': -90}

            def parallel_init(speed):
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_init1, wait=False, speed=speed, radius=50)
                    self.left.set_position(**left_init1, wait=True, speed=speed, radius=50)

            # 削水果
            right_Pos10 = {'x': 580, 'y': -100, 'z': 400, 'roll': -35, 'pitch': 90, 'yaw': 40}
            left_Pos10 = {'x': 580, 'y': 100, 'z': 400, 'roll': 35, 'pitch': 90, 'yaw': -40}

            right_up_Pos1 = {'x': 580, 'y': 0, 'z': 500, 'roll': -35, 'pitch': 90, 'yaw': 40}
            right_down_Pos1 = {'x': 580, 'y': 0, 'z': 300, 'roll': -35, 'pitch': 90, 'yaw': 40}

            left_up_Pos1 = {'x': 580, 'y': 0, 'z': 500, 'roll': 35, 'pitch': 90, 'yaw': -40}
            left_down_Pos1 = {'x': 580, 'y': 0, 'z': 300, 'roll': 35, 'pitch': 90, 'yaw': -40}

            right_front_Pos1 = {'x': 700, 'y': -200, 'z': 500, 'roll': -35, 'pitch': 90, 'yaw': 60}

            left_front_Pos1 = {'x': 700, 'y': 200, 'z': 500, 'roll': 35, 'pitch': 90, 'yaw': -60}

            def peel_fruit(speed):
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos10, wait=False, speed=speed, radius=50)
                    self.left.set_position(**left_Pos10, wait=True, speed=speed, radius=50)

            def right_up_left_down(speed):
                if self.task_status == AdamTaskStatus.dancing:
                    self.left.set_position(**left_down_Pos1, wait=False, speed=speed, radius=50)
                    self.right.set_position(**right_up_Pos1, wait=True, speed=speed, radius=50)
                for _ in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.right.set_position(**right_front_Pos1, wait=True, speed=speed, radius=50)
                        self.right.set_position(**right_up_Pos1, wait=True, speed=speed, radius=50)

            def left_up_right_down(speed):
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_down_Pos1, wait=False, speed=speed, radius=50)
                    self.left.set_position(**left_up_Pos1, wait=True, speed=speed, radius=50)
                for _ in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.left.set_position(**left_front_Pos1, wait=True, speed=speed, radius=50)
                        self.left.set_position(**left_up_Pos1, wait=True, speed=speed, radius=50)

            # 拉小提琴
            left_Pos_violin1 = {'x': 230, 'y': 250, 'z': 900, 'roll': -30, 'pitch': 30, 'yaw': -150}
            right_Pos_violin1 = {'x': 360, 'y': 230, 'z': 670, 'roll': 30, 'pitch': 45, 'yaw': 150}
            right_Pos_violin2 = {'x': 400, 'y': 170, 'z': 600, 'roll': 30, 'pitch': 45, 'yaw': 150}

            def violin_prepare(speed):
                if self.task_status == AdamTaskStatus.dancing:
                    self.left.set_position(**left_Pos_violin1, wait=False, speed=speed, radius=50)
                    self.right.set_position(**right_Pos_violin1, wait=True, speed=speed, radius=50)

            def play_violin(speed):
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos_violin1, wait=False, speed=speed, radius=50)
                    self.right.set_position(**right_Pos_violin2, wait=False, speed=speed, radius=50)

            right_Pos11 = {'x': 420, 'y': -20, 'z': 600, 'roll': -70, 'pitch': 90, 'yaw': 20}
            left_Pos11 = {'x': 420, 'y': 20, 'z': 600, 'roll': 70, 'pitch': 90, 'yaw': -20}

            right_Pos12 = {'x': 500, 'y': -250, 'z': 300, 'roll': -90, 'pitch': 40, 'yaw': -40}
            left_Pos12 = {'x': 500, 'y': 250, 'z': 300, 'roll': 90, 'pitch': 40, 'yaw': 40}

            def alter_left_right(speed):
                if self.task_status == AdamTaskStatus.dancing:
                    self.left.set_position(**left_Pos11, wait=False, speed=speed, radius=50)
                    self.right.set_position(**right_Pos12, wait=True, speed=speed, radius=50)
                    self.right.set_position(**right_Pos11, wait=False, speed=speed, radius=50)
                    self.left.set_position(**left_Pos12, wait=True, speed=speed, radius=50)

            speed2 = 200
            speed3 = 300
            speed4 = 400
            speed5 = 500

            violin_prepare(speed2)
            time.sleep(1)
            AudioInterface.music('BLACKPINK_Shut_Down.mp3')

            for _ in range(15):
                play_violin(300)

            if self.task_status == AdamTaskStatus.dancing:
                self.right.set_position(**right_Pos_violin2, wait=True, speed=300, radius=50)
                self.left.set_position(**left_Pos_violin1, wait=True, speed=100, radius=50)
            init_adam(speed5)

            # 平举
            for _ in range(3):
                raise_down(speed5)
            init_adam(speed5)

            # 左上右上交替
            for _ in range(3):
                alter_up_down(speed5)
            init_adam(speed5)

            # 左右加油交替
            for _ in range(2):
                come_on_right(speed4)
            if self.task_status == AdamTaskStatus.dancing:
                self.right.set_position(**right_Pos4, wait=True, speed=speed4, radius=50)
                self.right.set_position(**right_init, wait=False, speed=speed5, radius=50)
            for _ in range(2):
                come_on_left(speed4)
            if self.task_status == AdamTaskStatus.dancing:
                self.left.set_position(**left_Pos4, wait=True, speed=speed4, radius=50)
                self.left.set_position(**left_init, wait=False, speed=speed5, radius=50)
            init_adam(speed5)

            # 画圆
            right_round(speed3)
            init_adam(speed5)
            left_round(speed3)
            init_adam(speed5)

            if self.task_status == AdamTaskStatus.dancing:
                self.left.set_position(**left_Pos11, wait=False, speed=250, radius=50)
                self.right.set_position(**right_Pos12, wait=True, speed=speed4, radius=50)

            for _ in range(2):
                alter_left_right(speed4)

            init_adam(speed5)

            # 左上下加油
            right_up_down(speed4)
            left_up_down(speed4)
            right_up_down(speed4)
            left_up_down(speed4)
            parallel_init(speed4)

            # init_adam(speed2)

            def reduce_sound():
                for i in range(100, -1, -1):
                    os.system(f"amixer set PCM {i}%")
                    time.sleep(0.08)

            def init_adam():
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_init, wait=False, speed=100, radius=50)
                    self.left.set_position(**left_init, wait=True, speed=100, radius=50)

            if self.task_status == AdamTaskStatus.dancing:
                step_thread = [threading.Thread(target=reduce_sound), threading.Thread(target=init_adam)]
                for t in step_thread:
                    t.start()
                for t in step_thread:
                    t.join()

            # # 削水果
            # peel_fruit(speed4)
            # right_up_left_down(speed4)
            # peel_fruit(speed4)
            # left_up_right_down(speed4)
            # init_adam(speed4)

        def dance9():
            logger.info('dance9!!!')
            AudioInterface.music('Dance_The_Night.mp3')

            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 500, 'wait': True},
                    right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 500, 'wait': True}
                )

            # if self.task_status == AdamTaskStatus.dancing:
            #     self.left.set_position(x=156.8, y=708, z=1256, roll=1.7, pitch=11.9, yaw=-9.7, speed=550, wait=True)
            #     for i in range(3):
            #         self.left.set_servo_angle(servo_id=4, angle=-50, speed=80, wait=False)
            #         self.left.set_servo_angle(servo_id=4, angle=-150, speed=80, wait=False)
            #     self.left.set_servo_angle(servo_id=4, angle=-115, speed=80, wait=True)
            #     # 抱胸
            #     # self.left.set_servo_angle(angle=[141.3, 17.2, -41.7, -58.5, 71.1, -24.1], speed=50, wait=True)
            #     self.env.adam.set_position(
            #         left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 500, 'wait': True},
            #         right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 500, 'wait': True}
            #     )

            # 波浪 wave
            left_Pos3_1 = {'x': 380, 'y': 330, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': -90}

            right_Pos3_1 = {'x': 380, 'y': 100, 'z': 700, 'roll': 0, 'pitch': 60, 'yaw': 90}

            right_Pos3_2 = {'x': 380, 'y': 100, 'z': 700, 'roll': 0, 'pitch': 45, 'yaw': 90}

            right_Pos3_3 = {'x': 380, 'y': -50, 'z': 700, 'roll': 0, 'pitch': 60, 'yaw': 90}

            right_Pos3_4 = {'x': 380, 'y': -50, 'z': 700, 'roll': 0, 'pitch': 45, 'yaw': 90}

            right_Pos3_5 = {'x': 380, 'y': -200, 'z': 700, 'roll': 0, 'pitch': 60, 'yaw': 90}

            right_Pos3_6 = {'x': 380, 'y': -200, 'z': 700, 'roll': 0, 'pitch': 45, 'yaw': 90}

            left_Pos4_1 = {'x': 380, 'y': -330, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 90}

            right_Pos4_1 = {'x': 380, 'y': -100, 'z': 700, 'roll': 0, 'pitch': 60, 'yaw': -90}

            right_Pos4_2 = {'x': 380, 'y': -100, 'z': 700, 'roll': 0, 'pitch': 45, 'yaw': -90}

            right_Pos4_3 = {'x': 380, 'y': 50, 'z': 700, 'roll': 0, 'pitch': 60, 'yaw': -90}

            right_Pos4_4 = {'x': 380, 'y': 50, 'z': 700, 'roll': 0, 'pitch': 45, 'yaw': -90}

            right_Pos4_5 = {'x': 380, 'y': 200, 'z': 700, 'roll': 0, 'pitch': 60, 'yaw': -90}

            right_Pos4_6 = {'x': 380, 'y': 200, 'z': 700, 'roll': 0, 'pitch': 45, 'yaw': -90}

            def new_pos1(speed):
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos3_1, wait=False, speed=speed, radius=50)
                    self.left.set_position(**left_Pos3_1, wait=True, speed=speed, radius=50)
                    self.right.set_position(**right_Pos3_2, wait=False, speed=speed, radius=50)
                    self.right.set_position(**right_Pos3_3, wait=False, speed=speed, radius=50)
                    self.right.set_position(**right_Pos3_4, wait=False, speed=speed, radius=50)
                    self.right.set_position(**right_Pos3_5, wait=False, speed=speed, radius=50)
                    self.right.set_position(**right_Pos3_6, wait=True, speed=speed, radius=50)

            def new_pos2(speed):
                if self.task_status == AdamTaskStatus.dancing:
                    self.left.set_position(**right_Pos4_1, wait=False, speed=speed, radius=50)
                    self.right.set_position(**left_Pos4_1, wait=True, speed=speed, radius=50)
                    self.left.set_position(**right_Pos4_2, wait=False, speed=speed, radius=50)
                    self.left.set_position(**right_Pos4_3, wait=False, speed=speed, radius=50)
                    self.left.set_position(**right_Pos4_4, wait=False, speed=speed, radius=50)
                    self.left.set_position(**right_Pos4_5, wait=False, speed=speed, radius=50)
                    self.left.set_position(**right_Pos4_6, wait=True, speed=speed, radius=50)

            for _ in range(2):
                new_pos1(200)

            if self.task_status == AdamTaskStatus.dancing:
                right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
                left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
                self.left.set_position(**left_init, wait=False, speed=300, radius=50)
                self.right.set_position(**right_init, wait=True, speed=300, radius=50)

            for _ in range(2):
                new_pos2(200)

            # run
            for i in range(6):
                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(
                        left={'x': 205, 'y': 550, 'z': 250, 'roll': -110, 'pitch': 0, 'yaw': -90, 'speed': 700},
                        right={'x': 405, 'y': -550, 'z': 350, 'roll': 70, 'pitch': 0, 'yaw': 90, 'speed': 700}
                    )
                    self.env.adam.set_position(
                        left={'x': 405, 'y': 550, 'z': 350, 'roll': -70, 'pitch': 0, 'yaw': -90, 'speed': 700},
                        right={'x': 205, 'y': -550, 'z': 250, 'roll': 110, 'pitch': 0, 'yaw': 90, 'speed': 700}
                    )

            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 305, 'y': 550, 'z': 250, 'roll': -90, 'pitch': 0, 'yaw': -90, 'speed': 500, 'wait': True},
                    right={'x': 305, 'y': -550, 'z': 250, 'roll': 90, 'pitch': 0, 'yaw': 90, 'speed': 500, 'wait': True}
                )

            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 500, 'y': 200, 'z': 700, 'roll': 0, 'pitch': 0, 'yaw': -90, 'speed': 500, 'wait': True},
                    right={'x': 500, 'y': -200, 'z': 700, 'roll': 0, 'pitch': 0, 'yaw': 90, 'speed': 500, 'wait': True}
                )

            # clap
            for i in range(3):
                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(
                        left={'x': 500, 'y': 50, 'z': 700, 'roll': 0, 'pitch': 0, 'yaw': -90, 'speed': 250},
                        right={'x': 500, 'y': -50, 'z': 700, 'roll': 0, 'pitch': 0, 'yaw': 90, 'speed': 250}
                    )
                    self.env.adam.set_position(
                        left={'x': 500, 'y': 200, 'z': 700, 'roll': 0, 'pitch': 0, 'yaw': -90, 'speed': 250},
                        right={'x': 500, 'y': -200, 'z': 700, 'roll': 0, 'pitch': 0, 'yaw': 90, 'speed': 250}
                    )

            # heart
            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 300, 'y': 200, 'z': 830, 'roll': 35, 'pitch': 25, 'yaw': -70, 'speed': 500, 'wait': False},
                    right={'x': 300, 'y': -200, 'z': 830, 'roll': -35, 'pitch': 25, 'yaw': 70, 'speed': 500, 'wait': False}
                )
            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 0, 'y': 60, 'z': 930, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 500, 'wait': True},
                    right={'x': 0, 'y': -60, 'z': 930, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 400, 'wait': True}
                )

            for i in range(6):
                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(
                        left={'x': 0, 'y': 160, 'z': 930, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 200, 'wait': False},
                        right={'x': 0, 'y': 40, 'z': 930, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 200, 'wait': False}
                    )
                    self.env.adam.set_position(
                        left={'x': 0, 'y': -40, 'z': 930, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 200, 'wait': False},
                        right={'x': 0, 'y': -160, 'z': 930, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 200, 'wait': False}
                    )

            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 0, 'y': 60, 'z': 930, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 250, 'wait': True},
                    right={'x': 0, 'y': -60, 'z': 930, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 250, 'wait': True}
                )

            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_servo_angle(
                    left={'angle': [148.5, 20, -46.3, -52.1, 74.7, -23.9], 'speed': 60, 'wait': True},
                    right={'angle': [-148.5, 20, -46.3, 52.1, 74.7, 23.9], 'speed': 70, 'wait': True},
                )

            # move circle
            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 580, 'y': 100, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 0, 'speed': 500, 'wait': True},
                    right={'x': 580, 'y': -100, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 180, 'speed': 500, 'wait': True}
                )
            # for i in range(3):
            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.move_circle(
                    left={'pose1': [580, 200, 900, 0, 0, 0], 'pose2': [580, 0, 900, 0, 0, 0], 'percent': 300,
                          'speed': 200, 'wait': False},
                    right={'pose1': [580, -0, 900, 0, 0, 180], 'pose2': [580, -200, 900, 0, 0, 180], 'percent': 300,
                           'speed': 200, 'wait': False}
                )

            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 500, 'wait': True},
                    right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 500, 'wait': True}
                )

            def init_round(speed):
                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(
                        left={'x': 520, 'y': 50, 'z': 530, 'roll': 40, 'pitch': 90, 'yaw': -50, 'speed': speed, 'wait': True},
                        right={'x': 520, 'y': -50, 'z': 530, 'roll': -40, 'pitch': 90, 'yaw': 50, 'speed': speed, 'wait': True}
                    )

            def right_round(speed, percent):
                if self.task_status == AdamTaskStatus.dancing:
                    # a = {'x': 520, 'y': -50, 'z': 450, 'roll': -40, 'pitch': 90, 'yaw': 50}
                    right_pos_A = {'x': 520, 'y': -50, 'z': 530, 'roll': -40, 'pitch': 90, 'yaw': 50}
                    right_pos_B = [600, -50, 450, -40, 90, 50]
                    right_pos_C = [440, -50, 450, -40, 90, 50]
                    self.right.set_position(**right_pos_A, speed=speed, wait=True)
                    self.right.move_circle(right_pos_B, right_pos_C, percent=percent, speed=300, wait=True)

            def left_round(speed, percent):
                if self.task_status == AdamTaskStatus.dancing:
                    left_pos_A = {'x': 520, 'y': 50, 'z': 530, 'roll': 40, 'pitch': 90, 'yaw': -50}
                    left_pos_B = [600, 50, 450, 40, 90, -50]
                    left_pos_C = [440, 50, 450, 40, 90, -50]
                    self.left.set_position(**left_pos_A, speed=speed, wait=True)
                    self.left.move_circle(left_pos_B, left_pos_C, percent=percent, speed=300, wait=True)

            def all_round(speed, percent):
                if self.task_status == AdamTaskStatus.dancing:
                    right_pos_A = {'x': 520, 'y': -50, 'z': 370, 'roll': -40, 'pitch': 90, 'yaw': 50}
                    right_pos_B = [600, -50, 450, -40, 90, 50]
                    right_pos_C = [440, -50, 450, -40, 90, 50]
                    self.right.set_position(**right_pos_A, speed=speed, wait=False)
                    self.right.move_circle(right_pos_C, right_pos_B, percent=percent, speed=300, wait=False)
                    left_pos_A = {'x': 520, 'y': 50, 'z': 530, 'roll': 40, 'pitch': 90, 'yaw': -50}
                    left_pos_B = [600, 50, 450, 40, 90, -50]
                    left_pos_C = [440, 50, 450, 40, 90, -50]
                    self.left.set_position(**left_pos_A, speed=speed, wait=False)
                    self.left.move_circle(left_pos_B, left_pos_C, percent=percent, speed=300, wait=False)

            init_round(500)
            for _ in range(2):
                right_round(200, 100)
                left_round(200, 100)
            right_round(200, 50)
            all_round(200, 600)
            init_round(500)

            def reduce_sound():
                for i in range(100, -1, -1):
                    os.system(f"amixer set PCM {i}%")
                    time.sleep(0.05)

            def init_adam():
                if self.task_status == AdamTaskStatus.dancing:
                    right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
                    left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
                    self.left.set_position(**left_init, wait=False, speed=100, radius=50)
                    self.right.set_position(**right_init, wait=True, speed=100, radius=50)

            if self.task_status == AdamTaskStatus.dancing:
                step_thread = [threading.Thread(target=reduce_sound), threading.Thread(target=init_adam)]
                for t in step_thread:
                    t.start()
                for t in step_thread:
                    t.join()

        def dance10():
            logger.info('dance10!!!')
            AudioInterface.music('Jingle_Bells.mp3')

            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 500, 'wait': True},
                    right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 500, 'wait': True}
                )

            # 拉小提琴
            for _ in range(1):
                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(
                        left={'x': 230, 'y': 250, 'z': 900, 'roll': -30, 'pitch': 30, 'yaw': -150, 'speed': 200, 'wait': True},
                        right={'x': 360, 'y': 230, 'z': 670, 'roll': 30, 'pitch': 45, 'yaw': 150, 'speed': 200, 'wait': True}
                    )

                for i in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.right.set_servo_angle(servo_id=6, angle=98, speed=80, wait=False)
                        self.right.set_servo_angle(servo_id=6, angle=38, speed=80, wait=False)

                for i in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.left.set_servo_angle(servo_id=6, angle=-141, speed=80, wait=False)
                        self.left.set_servo_angle(servo_id=6, angle=-81, speed=80, wait=False)

                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_servo_angle(servo_id=6, angle=98, speed=80, wait=False)
                    self.left.set_servo_angle(servo_id=6, angle=-141, speed=80, wait=True)

                if self.task_status == AdamTaskStatus.dancing:
                    left_Pos_violin1 = {'x': 360, 'y': -230, 'z': 670, 'roll': -30, 'pitch': 45, 'yaw': -150}
                    right_Pos_violin1 = {'x': 230, 'y': -250, 'z': 900, 'roll': 30, 'pitch': 30, 'yaw': 150}
                    self.right.set_position(**right_Pos_violin1, wait=False, speed=200, radius=50)
                    time.sleep(1)
                    self.left.set_position(**left_Pos_violin1, wait=True, speed=350, radius=50)

                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(
                        left={'x': 360, 'y': -230, 'z': 670, 'roll': -30, 'pitch': 45, 'yaw': -150, 'speed': 100, 'wait': True},
                        right={'x': 230, 'y': -250, 'z': 900, 'roll': 30, 'pitch': 30, 'yaw': 150, 'speed': 100, 'wait': True}
                    )

                for i in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.right.set_servo_angle(servo_id=6, angle=141, speed=80, wait=False)
                        self.right.set_servo_angle(servo_id=6, angle=81, speed=80, wait=False)

                for i in range(3):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.left.set_servo_angle(servo_id=6, angle=-98, speed=80, wait=False)
                        self.left.set_servo_angle(servo_id=6, angle=-38, speed=80, wait=False)

                # init
                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(
                        left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 200, 'wait': True},
                        right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 200, 'wait': True}
                    )

            # # 奔跑
            # right_Pos1 = {'x': 420, 'y': -20, 'z': 600, 'roll': -70, 'pitch': 90, 'yaw': 20}
            # left_Pos1 = {'x': 420, 'y': 20, 'z': 600, 'roll': 70, 'pitch': 90, 'yaw': -20}
            #
            # right_Pos2 = {'x': 500, 'y': -250, 'z': 300, 'roll': -90, 'pitch': 40, 'yaw': -40}
            # left_Pos2 = {'x': 500, 'y': 250, 'z': 300, 'roll': 90, 'pitch': 40, 'yaw': 40}
            #
            # def alter_left_right(speed):
            #     if self.task_status == AdamTaskStatus.dancing:
            #         self.left.set_position(**left_Pos1, wait=False, speed=speed, radius=50)
            #         self.right.set_position(**right_Pos2, wait=True, speed=speed, radius=50)
            #         self.right.set_position(**right_Pos1, wait=False, speed=speed, radius=50)
            #         self.left.set_position(**left_Pos2, wait=True, speed=speed, radius=50)
            #
            # if self.task_status == AdamTaskStatus.dancing:
            #     self.left.set_position(**left_Pos1, wait=False, speed=250, radius=50)
            #     self.right.set_position(**right_Pos2, wait=True, speed=400, radius=50)
            #
            # for _ in range(3):
            #     alter_left_right(400)

            right_Pos3_1 = {'x': 380, 'y': -330, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 90}
            left_Pos3_1 = {'x': 380, 'y': 330, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': -90}

            right_Pos3_2 = {'x': 380, 'y': -100, 'z': 500, 'roll': 90, 'pitch': 90, 'yaw': 180}
            left_Pos3_2 = {'x': 380, 'y': 100, 'z': 500, 'roll': -90, 'pitch': 90, 'yaw': -180}

            for _ in range(4):
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos3_2, wait=False, speed=300, radius=50)
                    self.left.set_position(**left_Pos3_1, wait=True, speed=300, radius=50)
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos3_1, wait=False, speed=300, radius=50)
                    self.left.set_position(**left_Pos3_2, wait=True, speed=300, radius=50)

            # init
            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 200, 'wait': True},
                    right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 200, 'wait': True}
                )

            # 切菜 tcp
            right_Pos12 = {'x': 724, 'y': -80, 'z': 514, 'roll': 90, 'pitch': 0, 'yaw': 90}
            left_Pos12 = {'x': 724, 'y': 80, 'z': 514, 'roll': -90, 'pitch': 0, 'yaw': -90}
            right_Pos12_left = {'x': 724, 'y': 0, 'z': 514, 'roll': 90, 'pitch': 0, 'yaw': 90}
            left_Pos12_left = {'x': 724, 'y': 160, 'z': 514, 'roll': -90, 'pitch': 0, 'yaw': -90}
            right_Pos12_right = {'x': 724, 'y': -160, 'z': 514, 'roll': 90, 'pitch': 0, 'yaw': 90}
            left_Pos12_right = {'x': 724, 'y': 0, 'z': 514, 'roll': -90, 'pitch': 0, 'yaw': -90}

            # 上下搓手
            right_Pos14 = {'x': 724, 'y': -80, 'z': 564, 'roll': 90, 'pitch': 0, 'yaw': 90}
            left_Pos14 = {'x': 724, 'y': 80, 'z': 464, 'roll': -90, 'pitch': 0, 'yaw': -90}
            right_Pos15 = {'x': 724, 'y': -80, 'z': 464, 'roll': 90, 'pitch': 0, 'yaw': 90}
            left_Pos15 = {'x': 724, 'y': 80, 'z': 564, 'roll': -90, 'pitch': 0, 'yaw': -90}

            right_Pos16 = {'x': 724, 'y': 0, 'z': 564, 'roll': 90, 'pitch': 0, 'yaw': 90}
            left_Pos16 = {'x': 724, 'y': 160, 'z': 464, 'roll': -90, 'pitch': 0, 'yaw': -90}
            right_Pos17 = {'x': 724, 'y': 0, 'z': 464, 'roll': 90, 'pitch': 0, 'yaw': 90}
            left_Pos17 = {'x': 724, 'y': 160, 'z': 564, 'roll': -90, 'pitch': 0, 'yaw': -90}

            right_Pos18 = {'x': 724, 'y': -160, 'z': 564, 'roll': 90, 'pitch': 0, 'yaw': 90}
            left_Pos18 = {'x': 724, 'y': 0, 'z': 464, 'roll': -90, 'pitch': 0, 'yaw': -90}
            right_Pos19 = {'x': 724, 'y': -160, 'z': 464, 'roll': 90, 'pitch': 0, 'yaw': 90}
            left_Pos19 = {'x': 724, 'y': 0, 'z': 564, 'roll': -90, 'pitch': 0, 'yaw': -90}

            if self.task_status == AdamTaskStatus.dancing:
                self.right.set_position(**right_Pos12, wait=False, speed=200, radius=50)
                self.left.set_position(**left_Pos12, wait=True, speed=200, radius=50)

            for _ in range(3):
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos14, wait=False, speed=200, radius=50)
                    self.left.set_position(**left_Pos14, wait=False, speed=200, radius=50)
                    self.right.set_position(**right_Pos15, wait=False, speed=200, radius=50)
                    self.left.set_position(**left_Pos15, wait=False, speed=200, radius=50)

            if self.task_status == AdamTaskStatus.dancing:
                self.right.set_position(**right_Pos12, wait=False, speed=200, radius=50)
                self.left.set_position(**left_Pos12, wait=True, speed=200, radius=50)

            if self.task_status == AdamTaskStatus.dancing:
                self.right.set_position(**right_Pos12_left, wait=False, speed=200, radius=50)
                self.left.set_position(**left_Pos12_left, wait=True, speed=200, radius=50)

            for _ in range(3):
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos16, wait=False, speed=200, radius=50)
                    self.left.set_position(**left_Pos16, wait=False, speed=200, radius=50)
                    self.right.set_position(**right_Pos17, wait=False, speed=200, radius=50)
                    self.left.set_position(**left_Pos17, wait=False, speed=200, radius=50)

            if self.task_status == AdamTaskStatus.dancing:
                self.right.set_position(**right_Pos12_left, wait=False, speed=200, radius=50)
                self.left.set_position(**left_Pos12_left, wait=True, speed=200, radius=50)

            if self.task_status == AdamTaskStatus.dancing:
                self.right.set_position(**right_Pos12_right, wait=False, speed=200, radius=50)
                self.left.set_position(**left_Pos12_right, wait=True, speed=200, radius=50)

            for _ in range(3):
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos18, wait=False, speed=200, radius=50)
                    self.left.set_position(**left_Pos18, wait=False, speed=200, radius=50)
                    self.right.set_position(**right_Pos19, wait=False, speed=200, radius=50)
                    self.left.set_position(**left_Pos19, wait=False, speed=200, radius=50)
            if self.task_status == AdamTaskStatus.dancing:
                self.right.set_position(**right_Pos12_right, wait=False, speed=200, radius=50)
                self.left.set_position(**left_Pos12_right, wait=True, speed=200, radius=50)

            if self.task_status == AdamTaskStatus.dancing:
                self.right.set_position(**right_Pos12, wait=False, speed=200, radius=50)
                self.left.set_position(**left_Pos12, wait=True, speed=200, radius=50)

            for _ in range(3):
                right_Pos11 = {'x': 724, 'y': -137, 'z': 514, 'roll': 90, 'pitch': 0, 'yaw': 90}
                left_Pos11 = {'x': 724, 'y': 137, 'z': 514, 'roll': -90, 'pitch': 0, 'yaw': -90}

                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos11, wait=False, speed=500, radius=50)
                    self.left.set_position(**left_Pos11, wait=True, speed=500, radius=50)
                    self.right.set_position(**right_Pos12, wait=False, speed=500, radius=50)
                    self.left.set_position(**left_Pos12, wait=True, speed=500, radius=50)

                right_Pos_round1 = {'x': 724, 'y': -337, 'z': 514, 'roll': 90, 'pitch': 0, 'yaw': 90}
                right_Pos_round2 = [724, -287, 464, 90, 0, 90]
                right_Pos_round3 = [724, -387, 464, 90, 0, 90]
                left_Pos_round1 = {'x': 724, 'y': 337, 'z': 514, 'roll': -90, 'pitch': 0, 'yaw': -90}
                left_Pos_round2 = [724, 387, 464, -90, 0, -90]
                left_Pos_round3 = [724, 287, 464, -90, 0, -90]

                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos_round1, speed=200, wait=False)
                    self.right.move_circle(right_Pos_round2, right_Pos_round3, percent=100, speed=100, wait=False)

                if self.task_status == AdamTaskStatus.dancing:
                    self.left.set_position(**left_Pos_round1, speed=200, wait=False)
                    self.left.move_circle(left_Pos_round3, left_Pos_round2, percent=100, speed=100, wait=False)

            # init
            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 200, 'wait': True},
                    right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 200, 'wait': True}
                )

            def reduce_sound():
                for i in range(100, -1, -1):
                    os.system(f"amixer set PCM {i}%")
                    time.sleep(0.05)

            def init_adam():
                if self.task_status == AdamTaskStatus.dancing:
                    right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
                    left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
                    self.left.set_position(**left_init, wait=False, speed=100, radius=50)
                    self.right.set_position(**right_init, wait=True, speed=100, radius=50)

            if self.task_status == AdamTaskStatus.dancing:
                step_thread = [threading.Thread(target=reduce_sound), threading.Thread(target=init_adam)]
                for t in step_thread:
                    t.start()
                for t in step_thread:
                    t.join()

        def dance11():
            logger.info('dance11!!!')
            # os.system("amixer set PCM 85%")
            AudioInterface.music('Break_The_Ice.mp3')
            # init
            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 500, 'wait': True, 'timeout': 0.5},
                    right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 500, 'wait': True, 'timeout': 0.5}
                )

            # one
            right_Pos1_0 = {'x': 310, 'y': -550, 'z': 300, 'roll': 0, 'pitch': 90, 'yaw': 0}
            left_Pos1_0 = {'x': 310, 'y': 550, 'z': 300, 'roll': 0, 'pitch': 90, 'yaw': 0}
            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 310, 'y': 550, 'z': 300, 'roll': 0, 'pitch': 90, 'yaw': 0, 'speed': 200, 'wait': True},
                    right={'x': 310, 'y': -550, 'z': 300, 'roll': 0, 'pitch': 90, 'yaw': 0, 'speed': 200, 'wait': True}
                )

            right_Pos1_1 = {'x': 310, 'y': -550, 'z': 230, 'roll': 0, 'pitch': 90, 'yaw': 0}
            left_Pos1_1 = {'x': 310, 'y': 550, 'z': 230, 'roll': 0, 'pitch': 90, 'yaw': 0}
            right_Pos1_2 = {'x': 310, 'y': -550, 'z': 370, 'roll': 0, 'pitch': 90, 'yaw': 0}
            left_Pos1_2 = {'x': 310, 'y': 550, 'z': 370, 'roll': 0, 'pitch': 90, 'yaw': 0}

            def one_pos(speed):
                if self.task_status == AdamTaskStatus.dancing:
                    self.left.set_position(**left_Pos1_1, wait=False, speed=speed, radius=50)
                    self.right.set_position(**right_Pos1_2, wait=True, speed=speed, radius=50, timeout=0.5)
                    self.left.set_position(**left_Pos1_2, wait=False, speed=speed, radius=50)
                    self.right.set_position(**right_Pos1_1, wait=True, speed=speed, radius=50, timeout=0.5)

            # two
            def left_round():
                if self.task_status == AdamTaskStatus.dancing:
                    left_Pos_round1 = {'x': 600, 'y': 400, 'z': 300, 'roll': 0, 'pitch': 90, 'yaw': 0}
                    left_Pos_round2 = [600, 300, 350, 0, 90, 0]
                    left_Pos_round3 = [600, 500, 350, 0, 90, 0]
                    self.left.set_position(**left_Pos_round1, speed=450, wait=True)
                    self.left.move_circle(left_Pos_round3, left_Pos_round2, percent=100, speed=200, wait=True)

            def right_round():
                if self.task_status == AdamTaskStatus.dancing:
                    right_Pos_round1 = {'x': 600, 'y': -400, 'z': 300, 'roll': 0, 'pitch': 90, 'yaw': 0}
                    right_Pos_round2 = [600, -500, 350, 0, 90, 0]
                    right_Pos_round3 = [600, -300, 350, 0, 90, 0]
                    self.right.set_position(**right_Pos_round1, speed=450, wait=True)
                    self.right.move_circle(right_Pos_round2, right_Pos_round3, percent=100, speed=200, wait=True)

            for _ in range(5):
                one_pos(300)

            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 310, 'y': 550, 'z': 300, 'roll': 0, 'pitch': 90, 'yaw': 0, 'speed': 200, 'wait': True, 'timeout': 0.5},
                    right={'x': 310, 'y': -550, 'z': 300, 'roll': 0, 'pitch': 90, 'yaw': 0, 'speed': 200, 'wait': True, 'timeout': 0.5}
                )

            for _ in range(1):
                if self.task_status == AdamTaskStatus.dancing:
                    right_round()
                    self.right.set_position(**right_Pos1_0, wait=False, speed=450, radius=50)
                    left_round()
                    self.left.set_position(**left_Pos1_0, wait=False, speed=450, radius=50)

            if self.task_status == AdamTaskStatus.dancing:
                self.left.set_position(**left_Pos1_0, wait=True, speed=450, radius=50)

            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 200, 'wait': True},
                    right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 200, 'wait': True}
                )

            # 3
            # 加油上
            right_Pos4 = {'x': 30, 'y': -650, 'z': 1250, 'roll': 0, 'pitch': 0, 'yaw': 90}
            left_Pos4 = {'x': 30, 'y': 650, 'z': 1250, 'roll': 0, 'pitch': 0, 'yaw': -90}
            # 加油下
            right_Pos5 = {'x': 30, 'y': -650, 'z': 1100, 'roll': 0, 'pitch': 0, 'yaw': 90}
            left_Pos5 = {'x': 30, 'y': 650, 'z': 1100, 'roll': 0, 'pitch': 0, 'yaw': -90}

            def come_on_right(speed):
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos4, wait=False, speed=speed, radius=50)
                    self.right.set_position(**right_Pos5, wait=False, speed=speed, radius=50)

            def come_on_left(speed):
                if self.task_status == AdamTaskStatus.dancing:
                    self.left.set_position(**left_Pos5, wait=False, speed=speed, radius=50)
                    self.left.set_position(**left_Pos4, wait=False, speed=speed, radius=50)

            if self.task_status == AdamTaskStatus.dancing:
                self.right.set_position(**right_Pos4, wait=False, speed=250, radius=50)
                self.left.set_position(**left_Pos5, wait=True, speed=250, radius=50)
            for _ in range(5):
                come_on_right(250)
                come_on_left(250)

            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 200, 'wait': True},
                    right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 200, 'wait': True}
                )

            # 4
            right_Pos3_1 = {'x': 380, 'y': -330, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 90}
            left_Pos3_1 = {'x': 380, 'y': 330, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': -90}

            right_Pos3_2 = {'x': 380, 'y': -100, 'z': 500, 'roll': 90, 'pitch': 90, 'yaw': 180}
            left_Pos3_2 = {'x': 380, 'y': 100, 'z': 500, 'roll': -90, 'pitch': 90, 'yaw': -180}

            for _ in range(1):
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos3_2, wait=False, speed=300, radius=50)
                    self.left.set_position(**left_Pos3_1, wait=True, speed=300, radius=50)
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos3_1, wait=False, speed=300, radius=50)
                    self.left.set_position(**left_Pos3_2, wait=True, speed=300, radius=50)

            # init
            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 200, 'wait': True},
                    right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 200, 'wait': True}
                )

            def reduce_sound():
                for i in range(100, -1, -1):
                    os.system(f"amixer set PCM {i}%")
                    time.sleep(0.05)

            def init_adam():
                if self.task_status == AdamTaskStatus.dancing:
                    right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
                    left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
                    self.left.set_position(**left_init, wait=False, speed=100, radius=50)
                    self.right.set_position(**right_init, wait=True, speed=100, radius=50)

            if self.task_status == AdamTaskStatus.dancing:
                step_thread = [threading.Thread(target=reduce_sound), threading.Thread(target=init_adam)]
                for t in step_thread:
                    t.start()
                for t in step_thread:
                    t.join()

        def dance12():
            logger.info('dance12!!!')
            os.system("amixer set PCM 100%")
            AudioInterface.music('Sugar.mp3')
            # init
            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 500, 'wait': True, 'timeout': 0.5},
                    right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 500, 'wait': True, 'timeout': 0.5}
                )

            # one
            right_Pos1_0 = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
            left_Pos1_0 = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}

            right_Pos1_1 = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 30, 'yaw': 90}
            left_Pos1_1 = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 30, 'yaw': -90}

            for _ in range(4):
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos1_1, wait=False, speed=180, radius=50)
                    self.left.set_position(**left_Pos1_1, wait=False, speed=180, radius=50)
                    self.right.set_position(**right_Pos1_0, wait=False, speed=180, radius=50)
                    self.left.set_position(**left_Pos1_0, wait=False, speed=180, radius=50)

            for _ in range(10):
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos1_1, wait=False, speed=300, radius=50)
                    self.left.set_position(**left_Pos1_1, wait=False, speed=300, radius=50)
                    self.right.set_position(**right_Pos1_0, wait=False, speed=300, radius=50)
                    self.left.set_position(**left_Pos1_0, wait=False, speed=300, radius=50)

            for _ in range(2):
                # init
                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(
                        left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 200, 'wait': True},
                        right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 200, 'wait': True}
                    )

                # move circle
                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(
                        left={'x': 450, 'y': 200, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 0, 'speed': 500, 'wait': True},
                        right={'x': 450, 'y': 0, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 180, 'speed': 500, 'wait': True}
                    )
                for i in range(5):
                    if self.task_status == AdamTaskStatus.dancing:
                        self.env.adam.move_circle(
                            left={'pose1': [450, 100, 900, 0, 0, 0], 'pose2': [450, 100, 700, 0, 0, 0], 'percent': 50,
                                  'speed': 300, 'wait': False},
                            right={'pose1': [450, -100, 900, 0, 0, 180], 'pose2': [450, -100, 700, 0, 0, 180], 'percent': 50,
                                   'speed': 300, 'wait': False}
                        )

                    if self.task_status == AdamTaskStatus.dancing:
                        self.env.adam.move_circle(
                            left={'pose1': [450, 100, 900, 0, 0, 0], 'pose2': [450, 100, 700, 0, 0, 0], 'percent': 50,
                                  'speed': 300, 'wait': False},
                            right={'pose1': [450, -100, 900, 0, 0, 180], 'pose2': [450, -100, 700, 0, 0, 180], 'percent': 50,
                                   'speed': 300, 'wait': False}
                        )

                for _ in range(2):
                    # 3 open the window
                    if self.task_status == AdamTaskStatus.dancing:
                        self.env.adam.set_position(
                            left={'x': 450, 'y': 100, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 0, 'speed': 250, 'wait': False},
                            right={'x': 450, 'y': -100, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 180, 'speed': 250, 'wait': False}
                        )

                    if self.task_status == AdamTaskStatus.dancing:
                        self.env.adam.set_position(
                            left={'x': 600, 'y': 180, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 0, 'speed': 250, 'wait': False},
                            right={'x': 600, 'y': -180, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 180, 'speed': 250, 'wait': False}
                        )

                    if self.task_status == AdamTaskStatus.dancing:
                        self.env.adam.set_position(
                            left={'x': 450, 'y': 180, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 0, 'speed': 250, 'wait': False},
                            right={'x': 450, 'y': -180, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 180, 'speed': 250, 'wait': False}
                        )

                    if self.task_status == AdamTaskStatus.dancing:
                        self.env.adam.set_position(
                            left={'x': 600, 'y': 400, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 0, 'speed': 250, 'wait': False},
                            right={'x': 600, 'y': -400, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 180, 'speed': 250, 'wait': False}
                        )

                    if self.task_status == AdamTaskStatus.dancing:
                        self.env.adam.set_position(
                            left={'x': 450, 'y': 400, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 0, 'speed': 250, 'wait': False},
                            right={'x': 450, 'y': -400, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 180, 'speed': 250, 'wait': False}
                        )

                    # close the window
                    if self.task_status == AdamTaskStatus.dancing:
                        self.env.adam.set_position(
                            left={'x': 600, 'y': 100, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 0, 'speed': 250, 'wait': False},
                            right={'x': 600, 'y': -100, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 180, 'speed': 250, 'wait': False}
                        )

                    if self.task_status == AdamTaskStatus.dancing:
                        self.env.adam.set_position(
                            left={'x': 450, 'y': 100, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 0, 'speed': 250, 'wait': False},
                            right={'x': 450, 'y': -100, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 180, 'speed': 250, 'wait': False}
                        )

                right_Pos4_0 = {'x': 300, 'y': -240, 'z': 850, 'roll': 0, 'pitch': 60, 'yaw': 90}
                right_Pos4_1 = {'x': 300, 'y': -240, 'z': 850, 'roll': 0, 'pitch': 30, 'yaw': 90}
                left_Pos4_0 = {'x': 300, 'y': 240, 'z': 850, 'roll': 0, 'pitch': 60, 'yaw': -90}
                left_Pos4_1 = {'x': 300, 'y': 240, 'z': 850, 'roll': 0, 'pitch': 30, 'yaw': -90}

                def right_salute_shake():
                    if self.task_status == AdamTaskStatus.dancing:
                        self.right.set_position(**right_Pos4_0, wait=False, speed=300, radius=50)
                        self.right.set_position(**right_Pos4_1, wait=True, speed=300, radius=50)

                def left_salute_shake():
                    if self.task_status == AdamTaskStatus.dancing:
                        self.left.set_position(**left_Pos4_0, wait=False, speed=300, radius=50)
                        self.left.set_position(**left_Pos4_1, wait=True, speed=300, radius=50)

                # init
                if self.task_status == AdamTaskStatus.dancing:
                    self.env.adam.set_position(
                        left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 300, 'wait': True},
                        right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 300, 'wait': True}
                    )

                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos4_1, wait=False, speed=300, radius=50)
                    self.left.set_position(**left_Pos4_1, wait=False, speed=300, radius=50)
                for _ in range(4):
                    right_salute_shake()
                    left_salute_shake()

            def reduce_sound():
                for i in range(100, -1, -1):
                    os.system(f"amixer set PCM {i}%")
                    time.sleep(0.05)

            def init_adam():
                if self.task_status == AdamTaskStatus.dancing:
                    right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
                    left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
                    self.left.set_position(**left_init, wait=False, speed=100, radius=50)
                    self.right.set_position(**right_init, wait=True, speed=100, radius=50)

            if self.task_status == AdamTaskStatus.dancing:
                step_thread = [threading.Thread(target=reduce_sound), threading.Thread(target=init_adam)]
                for t in step_thread:
                    t.start()
                for t in step_thread:
                    t.join()

        def dance13():
            logger.info('dance13!!!')
            os.system("amixer set PCM 100%")
            # AudioInterface.music('Worth_It.mp3')
            # init
            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 500, 'wait': True, 'timeout': 0.5},
                    right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 500, 'wait': True, 'timeout': 0.5}
                )

            # one
            right_Pos1 = {'x': 320, 'y': 0, 'z': 800, 'roll': 50, 'pitch': 15, 'yaw': 170}
            left_Pos1 = {'x': 490, 'y': 0, 'z': 830, 'roll': -50, 'pitch': 15, 'yaw': -170}

            right_Pos2 = {'x': 320, 'y': 0, 'z': 800, 'roll': 60, 'pitch': 15, 'yaw': 170}
            left_Pos2 = {'x': 490, 'y': 0, 'z': 830, 'roll': -60, 'pitch': 15, 'yaw': -170}

            if self.task_status == AdamTaskStatus.dancing:
                self.right.set_position(**right_Pos2, wait=False, speed=200, radius=50)
                self.left.set_position(**left_Pos2, wait=True, speed=200, radius=50)

            AudioInterface.music('Worth_It.mp3')
            time.sleep(1)

            for _ in range(9):
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos2, wait=False, speed=120, radius=50)
                    self.left.set_position(**left_Pos2, wait=False, speed=120, radius=50)
                    self.right.set_position(**right_Pos1, wait=False, speed=120, radius=50)
                    self.left.set_position(**left_Pos1, wait=False, speed=120, radius=50)

            if self.task_status == AdamTaskStatus.dancing:
                right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
                left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
                self.left.set_position(**left_init, wait=False, speed=400, radius=50)
                self.right.set_position(**right_init, wait=True, speed=400, radius=50)

            def right_round(speed, percent):
                if self.task_status == AdamTaskStatus.dancing:
                    # a = {'x': 520, 'y': -50, 'z': 450, 'roll': -40, 'pitch': 90, 'yaw': 50}
                    right_pos_A = {'x': 520, 'y': -50, 'z': 530, 'roll': -40, 'pitch': 90, 'yaw': 50}
                    right_pos_B = [600, -50, 450, -40, 90, 50]
                    right_pos_C = [440, -50, 450, -40, 90, 50]
                    self.right.set_position(**right_pos_A, speed=speed, wait=True)
                    self.right.move_circle(right_pos_B, right_pos_C, percent=percent, speed=300, wait=True)

            def left_round(speed, percent):
                if self.task_status == AdamTaskStatus.dancing:
                    left_pos_A = {'x': 520, 'y': 50, 'z': 530, 'roll': 40, 'pitch': 90, 'yaw': -50}
                    left_pos_B = [600, 50, 450, 40, 90, -50]
                    left_pos_C = [440, 50, 450, 40, 90, -50]
                    self.left.set_position(**left_pos_A, speed=speed, wait=True)
                    self.left.move_circle(left_pos_B, left_pos_C, percent=percent, speed=300, wait=True)

            def all_round(speed, percent):
                if self.task_status == AdamTaskStatus.dancing:
                    right_pos_A = {'x': 520, 'y': -50, 'z': 370, 'roll': -40, 'pitch': 90, 'yaw': 50}
                    right_pos_B = [600, -50, 450, -40, 90, 50]
                    right_pos_C = [440, -50, 450, -40, 90, 50]
                    self.right.set_position(**right_pos_A, speed=speed, wait=False)
                    self.right.move_circle(right_pos_C, right_pos_B, percent=percent, speed=300, wait=False)
                    left_pos_A = {'x': 520, 'y': 50, 'z': 530, 'roll': 40, 'pitch': 90, 'yaw': -50}
                    left_pos_B = [600, 50, 450, 40, 90, -50]
                    left_pos_C = [440, 50, 450, 40, 90, -50]
                    self.left.set_position(**left_pos_A, speed=speed, wait=False)
                    self.left.move_circle(left_pos_B, left_pos_C, percent=percent, speed=300, wait=False)

            left_pos_A = {'x': 520, 'y': 50, 'z': 530, 'roll': 40, 'pitch': 90, 'yaw': -50}
            if self.task_status == AdamTaskStatus.dancing:
                self.left.set_position(**left_pos_A, speed=200, wait=False)
            right_round(200, 50)
            all_round(200, 800)

            # if self.task_status == AdamTaskStatus.dancing:
            #     right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
            #     left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
            #     self.left.set_position(**left_init, wait=False, speed=300, radius=50)
            #     self.right.set_position(**right_init, wait=True, speed=300, radius=50)

            if self.task_status == AdamTaskStatus.dancing:
                self.env.adam.set_position(
                    left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 500, 'wait': True, 'timeout': 0.5},
                    right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 500, 'wait': True, 'timeout': 0.5}
                )

            right_Pos_zhong1 = {'x': 370, 'y': -270, 'z': 850, 'roll': -10, 'pitch': -30, 'yaw': 100}
            left_Pos_zhong1 = {'x': 370, 'y': 270, 'z': 850, 'roll': 10, 'pitch': -30, 'yaw': -100}

            right_Pos_zhong2 = {'x': 370, 'y': -150, 'z': 1000, 'roll': -10, 'pitch': -30, 'yaw': 100}
            left_Pos_zhong2 = {'x': 370, 'y': 390, 'z': 1000, 'roll': 10, 'pitch': -30, 'yaw': -100}

            right_Pos_zhong3 = {'x': 370, 'y': -390, 'z': 1000, 'roll': -10, 'pitch': -30, 'yaw': 100}
            left_Pos_zhong3 = {'x': 370, 'y': 150, 'z': 1000, 'roll': 10, 'pitch': -30, 'yaw': -100}

            def zhong():
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos_zhong1, wait=False, speed=300, radius=50)
                    self.left.set_position(**left_Pos_zhong1, wait=True, speed=300, radius=50)

            def zhong_right():
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos_zhong2, wait=False, speed=300, radius=50)
                    self.left.set_position(**left_Pos_zhong2, wait=False, speed=300, radius=50)

            def zhong_left():
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos_zhong3, wait=False, speed=300, radius=50)
                    self.left.set_position(**left_Pos_zhong3, wait=False, speed=300, radius=50)

            for _ in range(4):
                zhong()
                zhong_right()
                zhong()
                zhong_left()
                zhong()

            right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
            left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
            if self.task_status == AdamTaskStatus.dancing:
                self.left.set_position(**left_init, wait=False, speed=300, radius=50)
                self.right.set_position(**right_init, wait=True, speed=300, radius=50)

            left_Pos3_1 = {'x': 380, 'y': 330, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': -90}

            right_Pos3_1 = {'x': 380, 'y': 100, 'z': 700, 'roll': 0, 'pitch': 60, 'yaw': 90}

            right_Pos3_2 = {'x': 380, 'y': 100, 'z': 700, 'roll': 0, 'pitch': 45, 'yaw': 90}

            right_Pos3_3 = {'x': 380, 'y': -50, 'z': 700, 'roll': 0, 'pitch': 60, 'yaw': 90}

            right_Pos3_4 = {'x': 380, 'y': -50, 'z': 700, 'roll': 0, 'pitch': 45, 'yaw': 90}

            right_Pos3_5 = {'x': 380, 'y': -200, 'z': 700, 'roll': 0, 'pitch': 60, 'yaw': 90}

            right_Pos3_6 = {'x': 380, 'y': -200, 'z': 700, 'roll': 0, 'pitch': 45, 'yaw': 90}

            left_Pos4_1 = {'x': 380, 'y': -330, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 90}

            right_Pos4_1 = {'x': 380, 'y': -100, 'z': 700, 'roll': 0, 'pitch': 60, 'yaw': -90}

            right_Pos4_2 = {'x': 380, 'y': -100, 'z': 700, 'roll': 0, 'pitch': 45, 'yaw': -90}

            right_Pos4_3 = {'x': 380, 'y': 50, 'z': 700, 'roll': 0, 'pitch': 60, 'yaw': -90}

            right_Pos4_4 = {'x': 380, 'y': 50, 'z': 700, 'roll': 0, 'pitch': 45, 'yaw': -90}

            right_Pos4_5 = {'x': 380, 'y': 200, 'z': 700, 'roll': 0, 'pitch': 60, 'yaw': -90}

            right_Pos4_6 = {'x': 380, 'y': 200, 'z': 700, 'roll': 0, 'pitch': 45, 'yaw': -90}

            def new_pos1(speed):
                if self.task_status == AdamTaskStatus.dancing:
                    self.right.set_position(**right_Pos3_1, wait=False, speed=speed, radius=50)
                    self.left.set_position(**left_Pos3_1, wait=True, speed=speed, radius=50)
                    self.right.set_position(**right_Pos3_2, wait=False, speed=speed, radius=50)
                    self.right.set_position(**right_Pos3_3, wait=False, speed=speed, radius=50)
                    self.right.set_position(**right_Pos3_4, wait=False, speed=speed, radius=50)
                    self.right.set_position(**right_Pos3_5, wait=False, speed=speed, radius=50)
                    self.right.set_position(**right_Pos3_6, wait=True, speed=speed, radius=50)

            def new_pos2(speed):
                if self.task_status == AdamTaskStatus.dancing:
                    self.left.set_position(**right_Pos4_1, wait=False, speed=speed, radius=50)
                    self.right.set_position(**left_Pos4_1, wait=True, speed=speed, radius=50)
                    self.left.set_position(**right_Pos4_2, wait=False, speed=speed, radius=50)
                    self.left.set_position(**right_Pos4_3, wait=False, speed=speed, radius=50)
                    self.left.set_position(**right_Pos4_4, wait=False, speed=speed, radius=50)
                    self.left.set_position(**right_Pos4_5, wait=False, speed=speed, radius=50)
                    self.left.set_position(**right_Pos4_6, wait=True, speed=speed, radius=50)

            for _ in range(2):
                new_pos1(200)

            if self.task_status == AdamTaskStatus.dancing:
                right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
                left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
                self.left.set_position(**left_init, wait=False, speed=300, radius=50)
                self.right.set_position(**right_init, wait=True, speed=300, radius=50)

            for _ in range(2):
                new_pos2(200)

            # right_Pos1 = {'x': 360, 'y': -180, 'z': 900, 'roll': -50, 'pitch': 40, 'yaw': 40}
            # left_Pos1 = {'x': 360, 'y': 180, 'z': 900, 'roll': 50, 'pitch': 40, 'yaw': -40}
            #
            # right_Pos2 = {'x': 500, 'y': -110, 'z': 320, 'roll': 80, 'pitch': 70, 'yaw': 145}
            # left_Pos2 = {'x': 500, 'y': 110, 'z': 320, 'roll': -80, 'pitch': 70, 'yaw': -145}
            #
            # def up_down_swing(speed):
            #     self.right.set_position(**right_Pos1, wait=False, speed=speed, radius=50)
            #     self.left.set_position(**left_Pos2, wait=True, speed=speed, radius=50)
            #     self.right.set_position(**right_Pos2, wait=False, speed=speed, radius=50)
            #     self.left.set_position(**left_Pos1, wait=True, speed=speed, radius=50)
            #
            # for _ in range(3):
            #     up_down_swing(400)

            def reduce_sound():
                for i in range(100, -1, -1):
                    os.system(f"amixer set PCM {i}%")
                    time.sleep(0.05)

            def init_adam():
                if self.task_status == AdamTaskStatus.dancing:
                    right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
                    left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
                    self.left.set_position(**left_init, wait=False, speed=100, radius=50)
                    self.right.set_position(**right_init, wait=True, speed=100, radius=50)

            if self.task_status == AdamTaskStatus.dancing:
                step_thread = [threading.Thread(target=reduce_sound), threading.Thread(target=init_adam)]
                for t in step_thread:
                    t.start()
                for t in step_thread:
                    t.join()

        def run_dance(choice):
            try:
                self.goto_gripper_position(Arm.left, 0, wait=False)
                self.goto_gripper_position(Arm.right, 0, wait=False)
                if choice != 5:
                    left_angles, right_angles = self.get_initial_position()
                    logger.info('left_angles={}, right_angles={}'.format(left_angles, right_angles))
                    self.env.adam.set_servo_angle(dict(angle=left_angles, speed=20, wait=True),
                                                  dict(angle=right_angles, speed=20, wait=True))
                AudioInterface.stop()
                choice = choice
                with MySuperContextManager() as db:
                    adam_crud.update_single_dance(db, choice, 1)
                if choice == 1:
                    logger.info('run dance1 hi.mp3')
                    dance1()
                elif choice == 2:
                    logger.info('run dance2 whistle.mp3')
                    dance2()
                elif choice == 3:
                    logger.info('run dance3 wa.mp3')
                    dance3()
                elif choice == 4:
                    logger.info('run dance4 YouNeverCanTell.mp3')
                    dance4()
                elif choice == 5:
                    logger.info('run dance5 dance.mp3')
                    dance5()
                elif choice == 6:
                    logger.info('run dance6 Saturday_night_fever_dance.mp3')
                    dance6()
                elif choice == 7:
                    logger.info('run dance7 Because_of_You.mp3')
                    dance7()
                elif choice == 8:
                    logger.info('run dance8 BLACKPINK_Shut_Down.mp3')
                    dance8()
                elif choice == 9:
                    logger.info('run dance9 Dance_The_Night.mp3')
                    dance9()
                elif choice == 10:
                    logger.info('run dance10 Jingle_Bells.mp3')
                    dance10()
                elif choice == 11:
                    logger.info('run dance11 Break_The_Ice.mp3')
                    dance11()
                elif choice == 12:
                    logger.info('run dance12 Sugar.mp3')
                    dance12()
                elif choice == 13:
                    logger.info('run dance13 Worth_It.mp3')
                    dance13()
                self.goto_standby_pose()
            except Exception as e:
                logger.error('random dance have a error is {}'.format(str(e)))
                logger.error(traceback.format_exc())
            finally:
                AudioInterface.stop()
                with MySuperContextManager() as db:
                    adam_crud.update_single_dance(db, choice, 0)
                os.system("amixer set PCM 100%")
                self.env.init_adam()

        # self.stop_and_goto_zero(is_sleep=True)
        if self.task_status != AdamTaskStatus.idle:
            return self.task_status
        self.task_status = AdamTaskStatus.dancing
        t = threading.Thread(target=run_dance, args=(choice,))
        t.setDaemon(True)
        t.start()
        t.join()
        if self.task_status != AdamTaskStatus.making:
            self.task_status = AdamTaskStatus.idle
        return self.task_status


class QueryCoffeeThread(threading.Thread):
    def __init__(self, coffee_driver: Coffee_Driver):
        super().__init__()
        self.coffee_driver = coffee_driver
        self.coffee_status = dict(status_code=self.coffee_driver.last_status.get('status_code', ''),
                                  status=self.coffee_driver.last_status.get('status', ''),
                                  error_code=self.coffee_driver.last_status.get('error_code', ''),
                                  error=self.coffee_driver.last_status.get('error', ''),)
        self.run_flag = True
        self.bean_out_flag = False

    def pause(self):
        self.run_flag = False

    def proceed(self):
        self.coffee_status = dict(status_code=self.coffee_driver.last_status.get('status_code', ''),
                                  status=self.coffee_driver.last_status.get('status', ''),
                                  error_code=self.coffee_driver.last_status.get('error_code', ''),
                                  error=self.coffee_driver.last_status.get('error', ''), )
        self.run_flag = True

    def run(self):
        while True:
            if self.run_flag:
                try:
                    logger.debug('query in coffee thread')
                    query_status = self.coffee_driver.query_status()
                    logger.info(f"query_status:{query_status}")
                    self.coffee_status = dict(status_code=self.coffee_driver.last_status.get('status_code', ''),
                                              status=self.coffee_driver.last_status.get('status', ''),
                                              error_code=self.coffee_driver.last_status.get('error_code', ''),
                                              error=self.coffee_driver.last_status.get('error', ''), )
                except Exception as e:
                    AudioInterface.gtts(str(e))
                    query_status = {"status_code": "", "status": ""}
                error_code = query_status.get('error_code', '')
                error = query_status.get('error', '')
                if error_code in [27, 28]:
                    CoffeeInterface.bean_out()
                    self.bean_out_flag = True
                else:
                    CoffeeInterface.bean_reset()
                    self.bean_out_flag = False
                if error != '':
                    AudioInterface.gtts(error)
            time.sleep(60)  # 每分钟查询一次咖啡机状态
