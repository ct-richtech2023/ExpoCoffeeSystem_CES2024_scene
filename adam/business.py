import math
import os
import random
import threading
import time
import csv
import traceback
import datetime
from copy import deepcopy
from loguru import logger
from queue import Queue

from common import define, utils, conf
from common.api import AudioInterface, CoffeeInterface, CenterInterface
from common.define import Arm, AdamTaskStatus, ThreadName
from common.schemas import adam as adam_schema
from common.schemas import coffee as coffee_schema
from common.schemas import common as common_schema
from common.schemas import total as total_schema
from common.db.crud import adam as adam_crud
from common.myerror import MoveError, FormulaError, MaterialError, StopError
from common.utils import update_threads_step
from init import EnvConfig

from coffee_device import Coffee_Driver
from devices.coffee.serial_device import Serial_Pump

from back import RecordThread
from check import CheckThread
from dance_thread import DanceThread, FollowThread
from detect_cup import DetectCupStandThread
from detect_person import DetectPersonThread  # 英伟达

from mutagen.mp3 import MP3


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
        # adam所处环境的配置 | Configuration of adam’s environment
        self.machine_config = total_schema.MachineConfig(**conf.get_machine_config())
        # adam机器人本身的配置 | The configuration of the adam robot itself
        self.adam_config = adam_schema.AdamConfig(**conf.get_adam_config())
        self.env = EnvConfig(self.machine_config, self.adam_config)
        self.left, self.right = self.env.left, self.env.right

        # 泵相关 | Pump related
        self.tap_device_name = self.env.machine_config.adam.tap_device
        self.ser = Serial_Pump(self.tap_device_name)
        self.ser.close_all()
        adam_crud.init_tap()

        # 一些线程初始化及状态标志
        self.thread_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.steps_queue = Queue(maxsize=200)
        self.step_cache = []  # 状态记录缓存，接口调用需要 | The state record is cached, which is required for API calls
        self.all_threads = {}  # {name: thread}

        # 咖啡机相关 | Coffee machine related
        self.coffee_device_name = self.env.machine_config.adam.coffee_device
        self.coffee_driver = None  # remove later
        connect_coffee_fail_count = 0
        # Comment back in to allow the coffee machine to work
        for i in range(5):
            try:
                logger.info('in {}th connect coffee machine'.format(i + 1))
                self.coffee_driver = Coffee_Driver(self.stop_event, self.coffee_device_name)
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

        # 制作过程中的一些状态标志
        self.task_status = None
        self.put_hot_cup_index = 0  # 放哪一个热杯拖
        self.put_cold_cup_index = 0  # 放哪一个冷杯拖
        self.put_foam_flag = False  # put foam cup sign 放奶泡杯标志
        self.is_coffee_finished = False  # coffee completed sign 咖啡完成标志

        self.error_msg = []

        # 其他功能的一些状态标志
        self.enable_visual_recognition = False  # visual identity open sign 视觉识别开启标识

        # 记录机械臂位置线程
        self.left_record = RecordThread(self.left, self.env.get_record_path('left'), 'left arm', self.steps_queue)
        self.left_record.name = ThreadName.left_pos_record
        self.left_record.update_step('create')
        self.left_record.setDaemon(True)
        self.all_threads[ThreadName.left_pos_record] = self.left_record
        self.right_record = RecordThread(self.right, self.env.get_record_path('right'), 'right arm', self.steps_queue)
        self.right_record.name = ThreadName.right_pos_record
        self.right_record.update_step('create')
        self.right_record.setDaemon(True)
        self.all_threads[ThreadName.right_pos_record] = self.right_record
        self.init_record()
        self.left_roll_end = True  # 左臂是否回退完标志
        self.right_roll_end = True  # 右臂是否回退完标志

        # Comment back in to allow the coffee machine to work
        # 咖啡机状态线程
        self.coffee_thread = QueryCoffeeThread(self.coffee_driver, self.steps_queue)
        self.coffee_thread.name = ThreadName.coffee_thread
        self.coffee_thread.update_step('create')
        self.coffee_thread.setDaemon(True)
        self.all_threads[ThreadName.coffee_thread] = self.coffee_thread
        self.coffee_thread.start()

        # dance threading 跳舞线程
        self.dance_thread = DanceThread(self.steps_queue)
        self.dance_thread.name = ThreadName.dance_thread
        self.dance_thread.update_step('create')
        self.dance_thread.setDaemon(True)
        self.all_threads[ThreadName.dance_thread] = self.dance_thread
        self.dance_time = 20 * 60  # Countdown time 倒计时时间  Unit: s

        self.follow_thread = FollowThread(0, self.steps_queue)
        self.follow_thread.name = ThreadName.follow_thread
        self.follow_thread.update_step('create')
        self.follow_thread.setDaemon(True)
        self.all_threads[ThreadName.follow_thread] = self.follow_thread

        # # detect cup 视觉识别杯子识别
        # self.detect_cup_thread = DetectCupStandThread(steps_queue=self.steps_queue)
        # self.detect_cup_thread.name = ThreadName.cup_detect
        # self.detect_cup_thread.update_step('create')
        # self.detect_cup_thread.setDaemon(True)
        # self.all_threads[ThreadName.cup_detect] = self.detect_cup_thread
        # self.detect_cup_thread.start()
        #
        # # detect person 视觉识别人物识别
        # self.detect_person_thread = DetectPersonThread(steps_queue=self.steps_queue)
        # self.detect_person_thread.name = ThreadName.person_detect
        # self.detect_person_thread.update_step('create')
        # self.detect_person_thread.setDaemon(True)
        # self.all_threads[ThreadName.person_detect] = self.detect_person_thread
        # self.detect_person_thread.start()

        # 程序上电就会强制回零点
        self.check_adam_goto_initial_position()
        self.task_status = AdamTaskStatus.idle

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

    def update_step(self, name, step):
        msg = dict(time=datetime.datetime.utcnow(), thread=name, step=step)
        logger.bind(threads=True).info(msg)
        if self.steps_queue.full():
            self.steps_queue.get()
        self.steps_queue.put(msg)

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

    def dead_before_manual(self):
        AudioInterface.gtts('/richtech/resource/audio/voices/init_manual_on.mp3', True)
        self.manual(Arm.left)
        self.manual(Arm.right)
        time.sleep(15)
        AudioInterface.gtts('/richtech/resource/audio/voices/init_manual_off.mp3', True)
        time.sleep(3)
        self.manual(Arm.left, 0)
        self.manual(Arm.right, 0)

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
        except Exception as e:
            logger.error(traceback.format_exc())
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

    def get_initial_position(self):
        # 回到作揖状态下
        left_pre_angles = [148.5, 20, -46.3, -52.1, 74.7, -23.9]
        right_pre_angles = [-148.5, 20, -46.3, 52.1, 74.7, 23.9]
        left_position = [355, 100, 630, 0, 60, -90]
        right_position = [355, -100, 630, 0, 60, 90]
        left_angles = self.inverse(define.Arm.left, left_position, left_pre_angles)
        right_angles = self.inverse(define.Arm.right, right_position, right_pre_angles)
        return left_angles, right_angles

    def initial_position(self, which) -> adam_schema.Pose:
        # 计算工作零点的位姿
        center_position = self.initial_center_point(which)
        center_position['x'] = self.center_to_tcp_length(which)
        center_position.update(dict(roll=0, pitch=90, yaw=0))
        return adam_schema.Pose(**center_position)

    def initial_center_point(self, which):
        y = common_schema.AdamArm.initial_y
        y = abs(y) if which == Arm.left else -abs(y)
        z = 250
        return {'x': 0, 'y': y, 'z': z}

    def center_to_tcp_length(self, which):
        # 工作零点的x坐标如何计算
        gripper_name = getattr(self.env.adam_config.different_config, which).gripper
        return self.env.adam_config.gripper_config[gripper_name].tcp_offset.z + common_schema.AdamArm.line6

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
            if lcode != 0 or rcode != 0:
                # self.stop()logger.info(f'into make_coffee')
                #         make_content = int(f'0x{make_content:04X}', 16)
                raise MoveError('adam goto angle_left={} angle_right={} fail, code={},{}'.
                                format(left_angles, right_angles, lcode, rcode))
            self.check_adam_angles(Arm.left, left_angles, "goto_work_zero left_angles check_adam_angles")
            self.check_adam_angles(Arm.right, right_angles, "goto_work_zero right_angles check_adam_angles")

    def check_adam_pos(self, which, pos, desc):
        arm = self.env.one_arm(which)
        real_pos = arm.position
        passed = utils.compare_value(real_pos[:3], pos[:3], 1)
        logger.info('{} arm check_adam_pos {}, pos={}, actual={}, passed={}'.format(which, desc, pos, real_pos, passed))
        if not passed:
            raise MoveError('move error in {} position compare not passed'.format(desc))
        else:
            return True

    def check_adam_xyz(self, which, desc, x=None, y=None, z=None):
        arm = self.env.one_arm(which)
        real_pos = []
        pos = []
        if x:
            pos.append(x)
            real_pos.append(arm.position[0])
        if y:
            pos.append(y)
            real_pos.append(arm.position[1])
        if z:
            pos.append(z)
            real_pos.append(arm.position[2])
        passed = utils.compare_value(real_pos, pos, 1)
        logger.info('{} arm check_adam_pos {}, pos={}, actual={}, passed={}'.format(which, desc, pos, real_pos, passed))
        if not passed:
            raise MoveError('move error in {} position compare not passed'.format(desc))
        else:
            return True

    def check_adam_angles(self, which, angles_list, desc):
        arm = self.env.one_arm(which)
        real_angles = arm.angles
        passed = utils.compare_value(real_angles[:6], angles_list[:6], 1)
        logger.info('{} arm check_adam_angles {}, angles={}, actual={}, passed={}'.format(which, desc, angles_list, real_angles, passed))
        if not passed:
            raise MoveError('move error in {} angles compare not passed'.format(desc))
        else:
            return True

    def check_adam_status(self, desc, status=AdamTaskStatus.making):
        logger.info('check after {}, status is {}'.format(desc, self.task_status))
        if self.task_status != status:
            raise MoveError('move error in {}'.format(desc))
        if self.env.one_arm(Arm.left).state == 4 or self.left.has_error:
            raise MoveError('left move error in {}'.format(desc))
        if self.env.one_arm(Arm.right).state == 4 or self.right.has_error:
            raise MoveError('right move error in {}'.format(desc))

    def get_xy_initial_angle(self, which, x, y) -> float:
        src = self.initial_center_point(which)
        x0, y0 = src['x'], src['y']
        return math.atan2(y0 - y, x - x0) / math.pi * 180

    def goto_point(self, which, pose: adam_schema.Pose, wait=True, speed=None, radius=50, timeout=None, roll_flag=False):
        """
        运动到点，可以指定速度比例，否则以machine.yml中的默认速度来运动
        """
        if speed:
            speed = speed
        else:
            speed = self.env.default_arm_speed
        arm = self.env.one_arm(which)
        if arm.has_error:
            raise MoveError(f'arm {which} has error')
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead] or roll_flag:
            logger.debug('{} arm goto pose={} at {} speed, wait={}'.format(which, pose.dict(), speed, wait))
            code = arm.set_position(**pose.dict(), speed=speed, wait=wait, radius=radius, timeout=timeout)
            if code not in [0, 100]:
                logger.error('{} arm goto pose={} fail, code={}'.format(which, pose.dict(), code))
                self.stop('{} arm goto pose={} fail, code={}'.format(which, pose.dict(), code))
                raise MoveError('{} arm goto pose={} fail, code={}'.format(which, pose.dict(), code))
            if wait:
                self.check_adam_pos(which, [pose.x, pose.y, pose.z], "goto_point check_adam_pos")
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
        if arm.has_error:
            raise MoveError(f'arm {which} has error')
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead] or roll_flag:
            logger.debug('{} arm goto_XYZ_point pose={} at {} speed, wait={}'.format(which, pose_dict, speed, wait))
            code = arm.set_position(**pose_dict, speed=speed, wait=wait, radius=50)
            if code != 0:
                logger.error('{} arm goto_XYZ_point pose={} fail, code={}'.format(which, pose_dict, code))
                self.stop('{} arm goto_XYZ_point pose={} fail, code={}'.format(which, pose_dict, code))
                raise MoveError('{} arm goto_XYZ_point pose={} fail, code={}'.format(which, pose_dict, code))
            if wait:
                self.check_adam_pos(which, [pose.x, pose.y, pose.z], "goto_point check_adam_pos")
        return [round(i, 2) for i in arm.angles[:6]]

    def goto_temp_point(self, which, x=None, y=None, z=None, roll=None, pitch=None, yaw=None, wait=True, speed=None, mvacc=None, roll_flag=False):
        """
        一些中间位置，可以只传一个位置参数，而不需要传全部
        """
        if speed:
            speed = speed
        else:
            speed = self.env.default_arm_speed
        arm = self.env.one_arm(which)
        pose_dict = {'x': x, 'y': y, 'z': z, 'roll': roll, 'pitch': pitch, 'yaw': yaw}
        if arm.has_error:
            raise MoveError(f'arm {which} has error')
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead] or roll_flag:
            logger.debug('{} arm goto_temp_point pose={} at {} speed, wait={}'.format(which, pose_dict, speed, wait))
            code = arm.set_position(**pose_dict, speed=speed, wait=wait, radius=50, mvacc=mvacc)
            if code != 0:
                logger.error('{} arm goto_temp_point pose={} fail, code={}'.format(which, pose_dict, code))
                self.stop('{} arm goto_temp_point pose={} fail, code={}'.format(which, pose_dict, code))
                raise MoveError('{} arm goto_temp_point pose={} fail, code={}'.format(which, pose_dict, code))
            if wait:
                self.check_adam_xyz(which, "goto_temp_point check_adam_xyz", x=x, y=y, z=z)
        return [round(i, 2) for i in arm.angles[:6]]

    def goto_gripper_position(self, which, pos, wait=False, roll_flag=False):
        # 控制机械臂的夹爪开关
        arm = self.env.one_arm(which)
        if arm.has_error:
            raise MoveError(f'arm {which} has error')
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead] or roll_flag:
            arm.set_gripper_enable(True)
            arm.set_gripper_mode(0)
            code = arm.set_gripper_position(pos, wait=wait, speed=self.env.default_gripper_speed)
            if code != 0:
                logger.error('{} arm goto_gripper_position pose={} fail, code={}'.format(which, pos, code))
                self.stop('{} arm goto_gripper_position pose={} fail, code={}'.format(which, pos, code))
                raise MoveError('{} arm goto_gripper_position pose={} fail, code={}'.format(which, pos, code))

    def goto_tool_position(self, which, x=0, y=0, z=0, roll=0, pitch=0, yaw=0, speed=None, wait=False, roll_flag=False):
        # 控制机械臂的夹爪开关
        arm = self.env.one_arm(which)
        if arm.has_error:
            raise MoveError(f'arm {which} has error')
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead] or roll_flag:
            code = arm.set_tool_position(x=x, y=y, z=z, roll=roll, pitch=pitch, yaw=yaw, speed=speed, wait=wait)
            if code != 0:
                logger.error('{} arm goto_tool_position fail, code={}'.format(which, code))
                self.stop('{} arm goto_tool_position fail, code={}'.format(which, code))
                raise MoveError('{} arm goto_tool_position fail, code={}'.format(which, code))

    def goto_angles(self, which, angles: adam_schema.Angles, wait=True, speed=50, roll_flag=False, relative=False):
        angle_list = list(dict(angles).values())
        arm = self.env.one_arm(which)
        if arm.has_error:
            raise MoveError(f'arm {which} has error')
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead] or roll_flag:
            logger.info('{} arm set_servo_angle from {} to {}'.format(which, arm.angles[:6], angle_list))
            return_code = arm.set_servo_angle(angle=angle_list, speed=speed, wait=wait, relative=relative)
            now_angles = arm.angles
            if return_code != 0:
                self.stop('{} arm goto angle={} fail, code={}'.format(which, angle_list, return_code))
                raise MoveError('{} arm goto angle={} fail, code={}'.format(which, angle_list, return_code))
            if wait:
                self.check_adam_angles(which, angle_list, "goto_angles check_adam_angles")
            return now_angles

    def goto_relative_angles(self, which, angles: list, wait=True, speed=50):
        # 相对运动，一般情况下请勿调用
        arm = self.env.one_arm(which)
        if arm.has_error:
            raise MoveError(f'arm {which} has error')
        if self.task_status not in [AdamTaskStatus.stopped, AdamTaskStatus.rolling, AdamTaskStatus.dead]:
            logger.info('{} arm goto relative angles {}'.format(which, angles))
            return_code = arm.set_servo_angle(angle=angles, speed=speed, wait=wait, relative=True)
            now_angles = arm.angles
            if return_code != 0:
                self.stop('{} arm goto angle={} fail, code={}'.format(which, angles, return_code))
                raise MoveError('{} arm goto angle={} fail, code={}'.format(which, angles, return_code))
            return now_angles

    def change_adam_status(self, status):
        if self.task_status not in [AdamTaskStatus.rolling, AdamTaskStatus.restart, AdamTaskStatus.dead]:
            self.task_status = status

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
            self.check_adam_angles(Arm.left, left_angles, "goto_standby_pose left_angles check_adam_angles")
            self.check_adam_angles(Arm.right, right_angles, "goto_standby_pose right_angles check_adam_angles")

    # 异常处理 | Exception handling
    def stop_and_goto_zero(self, is_sleep=True, idle=True):
        """
        Adam软件急停并回工作状态的零点
        """
        if is_sleep:
            time.sleep(1)
        if self.task_status in [AdamTaskStatus.making, AdamTaskStatus.stopped, AdamTaskStatus.rolling,
                                AdamTaskStatus.dead, AdamTaskStatus.warm, AdamTaskStatus.restart]:
            return {'msg': 'not ok', 'status': self.task_status}
        elif self.task_status == AdamTaskStatus.idle:
            self.change_adam_status(AdamTaskStatus.making)
            self.goto_work_zero(speed=30, open_gripper=False)
            if idle:
                self.change_adam_status(AdamTaskStatus.idle)
            logger.debug('adam is idle now, return in stop_and_goto_zero')
            return {'msg': 'ok', 'status': self.task_status}
        else:
            logger.debug('adam is dancing now, stop and goto zero')
            self.env.adam.set_state(dict(state=4), dict(state=4))
            self.change_adam_status(AdamTaskStatus.making)
            if self.follow_thread.is_alive():
                self.follow_thread.stop_thread(idle=False)
            if self.dance_thread.is_alive() and self.dance_thread.need_zero:
                self.dance_thread.need_zero = False
                self.dance_thread.stop_thread()
            # 停止播放音乐
            AudioInterface.stop()
            logger.warning("adam stop and wait 5 seconds")
            time.sleep(5)
            self.env.init_adam()
            self.goto_work_zero(speed=30)
            logger.warning("adam stop and goto zero finish")
            print(f"self.task_status: {self.task_status}")
            if idle:
                self.change_adam_status(AdamTaskStatus.idle)
                self.goto_standby_pose()
            return {'msg': 'ok', 'status': self.task_status}

    def stop(self, err='something error'):
        """
        Adam软件急停
        """
        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='stop')
        self.stop_event.set()
        self.is_coffee_finished = True
        self.change_adam_status(AdamTaskStatus.stopped)
        self.error_msg.append({'time': time.strftime("%Y-%m-%d %H:%M:%S"), 'err': str(err)})
        if self.task_status != AdamTaskStatus.rolling:
            self.env.adam.set_state(dict(state=4), dict(state=4))
        self.coffee_driver.cancel_make()
        self.ser.close_all()
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

    # 自动清洗奶管 | Automatic milk tube cleaning
    def clean_milk_pipe(self, materials: list):
        self.change_adam_status(AdamTaskStatus.making)

        self.stop_event.clear()
        self.left_record.clear()  # start a new task, delete the previous log file
        self.right_record.clear()
        self.right_record.proceed()  # 记录关节位置线程开启
        self.left_record.proceed()
        try:
            self.check_adam_status("start clean_milk_pipe", AdamTaskStatus.making)

            angle_speed = 20
            logger.info('clean_milk_tap with task status={}'.format(self.task_status))
            logger.info('clean_milk_tap with materials={}'.format(materials))

            self.take_foam_cup_judge(Arm.left)
            for i, (name, seconds) in enumerate(materials):
                which = Arm.left
                self.take_ingredients(which, {name: seconds})
                self.goto_angles(which, adam_schema.Angles.list_to_obj([164.1, 54.2, -92.2, -5.2, 35.4, -42.2]), wait=True, speed=angle_speed + 40)
                self.goto_angles(which, adam_schema.Angles.list_to_obj([161.9, 85.4, -143, -29.6, 34.4, -210.4]), wait=True, speed=angle_speed)
                if i == len(materials) - 1:
                    self.check_adam_status("clean_milk_pipe", AdamTaskStatus.making)
                    com = self.ser.new_communication()
                    self.ser.send_one_msg(com, 'L')
                    time.sleep(2)
                    self.ser.send_one_msg(com, 'l')
                    time.sleep(2)
                    com.close_engine()
                self.goto_temp_point(which, z=135, wait=True, speed=200)
                self.goto_angles(which, adam_schema.Angles.list_to_obj([158.0, 73.4, -120.8, -37.4, 24.2, -22.2]), wait=True, speed=angle_speed + 20)
                # add cleaning_history
                CoffeeInterface.add_cleaning_history({name: seconds}, 1)

            self.put_foam_cup(Arm.left)
            self.goto_initial_position_direction(Arm.left, 0, wait=True, speed=500)
            self.goto_standby_pose()
            self.change_adam_status(AdamTaskStatus.idle)
        except Exception as e:
            self.stop(str(e))
        finally:
            self.right_record.pause()
            self.left_record.pause()

    def get_composition_by_option(self, coffee_record: coffee_schema.CoffeeRecord) -> dict:
        """
        根据饮品名称查询配方表，返回不同机器处需要的物料名称和数量
        return:{
                'coffee_machine': {'coffee': {'count':60, 'coffee_make':{...}}}, # 用咖啡机的
                'foam_machine': {"foam": {"foam_composition": {"fresh_dairy":450 }, "foam_time":45} },# 奶泡
                'tap': {sugar':10, 'white_chocolate_syrup': 20, 'cold_coffee': 150}, # 用龙头的
                'ice_machine': {'ice': 0}, # 用制冰机的
                'cup': {'hot_cup': 1}
                }
        """
        composition = CoffeeInterface.get_formula_composition(coffee_record.formula, coffee_record.cup, define.Constant.InUse.in_use)
        milk_dict = composition.pop("milk_dict")
        real_milk_name = ""
        real_milk_left = 0
        if coffee_record.milk:
            if milk := milk_dict.get(coffee_record.milk, ""):
                real_milk_name = milk.get("name", "")
                real_milk_left = milk.get("left", 0)
            else:
                msg = f'milk type {coffee_record.milk} does not exist, please check again'
                AudioInterface.gtts(msg)
                logger.error(msg)
                raise MaterialError(msg)
        if not composition:
            # 校验方案是否支持
            msg = 'there are no formula named {} in use, please check again'.format(coffee_record.formula)
            AudioInterface.gtts(msg)
            logger.error(msg)
            raise FormulaError(msg)
        result = {}
        lack = ''

        milk_all_count = 0
        for name, material in composition.items():
            if material.get('in_use') == define.Constant.InUse.not_in_use:
                # 校验材料是否支持
                msg = 'material {} is not in use, please check again'.format(name)
                AudioInterface.gtts(msg)
                logger.error(msg)
                raise MaterialError(msg)
            if material.get('left') < material.get('count') and material.get('type') not in ["Plant-based milk", "Milk"]:
                # 校验材料是否充足
                lack += ' ' + name

            machine_name = material.get('machine')
            material_type = material.get('type')

            # 根据选项更新数量
            if machine_name == define.Constant.MachineType.ice_maker:
                result.setdefault(machine_name, {})[name] = material.get('count')
            elif machine_name == define.Constant.MachineType.tap:
                if material_type in ["Plant-based milk", "Milk"]:
                    result.setdefault(machine_name, {})[real_milk_name] = material.get('count')
                    milk_all_count += material.get('count')
                else:
                    result.setdefault(machine_name, {})[name] = material.get('count')
            elif machine_name == define.Constant.MachineType.coffee_machine:
                if extra := material.get('extra'):
                    if len(extra) > 1:
                        coffee_make = {}
                        for key, value in extra.items():
                            if key == coffee_record.beans:
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
                    for milk_type, milk_material in milk_dict.items():
                        if tap_name == milk_material.get("name", ""):
                            foam_data["foam_composition"][real_milk_name] = foam_data["foam_composition"].pop(tap_name)
                            milk_all_count += foam_data["foam_composition"][real_milk_name]
                result.setdefault(machine_name, {})[name] = foam_data
            else:
                result.setdefault(machine_name, {})[name] = material.get('count')
        logger.debug('composition is {}'.format(result))

        if milk_all_count > real_milk_left:
            # 校验milk是否充足
            lack += ' ' + real_milk_name

        if lack:
            AudioInterface.gtts('material {} not enough please add them first'.format(lack))
            raise MaterialError('material {} not enough please add them first'.format(lack))
        return result

    # 制作方法 | make Method
    def make_cold_drink(self, coffee_record: coffee_schema.CoffeeRecord):
        """
        make_cold_drink
        """
        self.update_step(ThreadName.make, 'START')

        start_time = int(time.time())
        # AudioInterface.gtts2("Got it, I'm making your drink now!")
        AudioInterface.gtts('/richtech/resource/audio/voices/start_making4.mp3')
        logger.debug('start in make_cold_drink')

        try:
            self.update_step(ThreadName.make, 'get_composition_by_option')
            composition = self.get_composition_by_option(coffee_record)
            logger.info(f"into make_cold_drink  :{composition}")
        except Exception as e:
            # 防止只改变订单状态，并未改变adam状态 | Prevent only changing the order status without changing the adam status
            self.change_adam_status(AdamTaskStatus.idle)
            self.update_step(ThreadName.make, 'error')
            self.update_step(ThreadName.make, 'END')
            raise e

        with_foam = True if composition.get(define.Constant.MachineType.foam_machine, {}) else False
        with_foam_coffee = True if composition.get(define.Constant.MachineType.foam_machine, {}).get('foam', {}).get('foam_composition', {}).get(
            'foam_coffee', {}) else False
        with_coffee = True if composition.get(define.Constant.MachineType.coffee_machine, {}) else False

        self.is_coffee_finished = False
        self.put_foam_flag = False

        self.stop_event.clear()
        self.left_record.clear()  # start a new task, delete the previous log file
        self.right_record.clear()
        self.right_record.proceed()  # 记录关节位置线程开启
        self.left_record.proceed()

        try:
            # step 1 : 两个线程：左手（需要咖啡味奶泡就去那奶泡杯接配料），右手（需要咖啡机原液就去接）
            def left_step1():
                try:
                    if with_foam_coffee:
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='take_foam_cup_judge')
                        self.take_foam_cup_judge(Arm.left)
                        self.check_adam_status('make_cold_drink take_foam_cup', status=AdamTaskStatus.making)
                        foam_composition = deepcopy(
                            composition.get(define.Constant.MachineType.foam_machine, {}).get('foam', {}).get('foam_composition', {}))
                        foam_composition.pop('foam_coffee')
                        # if self.enable_visual_recognition:
                        #     self.detect_cup_thread.pause()  # close detect_cup_thread
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='take_ingredients')
                        self.take_ingredients(Arm.left, foam_composition)
                        self.check_adam_status('make_cold_drink take_ingredients_foam', status=AdamTaskStatus.making)
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='put_foam_cup')
                        self.put_foam_cup(Arm.left)
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='put_foam_cup_end')
                        self.check_adam_status('make_cold_drink put_foam_cup', status=AdamTaskStatus.making)
                        self.put_foam_flag = True
                        self.goto_temp_point(Arm.left, y=20, wait=False)
                        self.goto_angles(Arm.left, adam_schema.Angles.list_to_obj([209.1, -41.9, -24.7, -90.4, 89.2, 23.3]), wait=True)
                        # self.back_to_initial(Arm.left)
                        self.check_adam_status('make_cold_drink back_to_initial', status=AdamTaskStatus.making)
                        # if self.enable_visual_recognition:
                        #     self.detect_cup_thread.proceed()  # open detect_cup_thread

                    update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='take_cold_cup')
                    self.take_cold_cup()
                    self.check_adam_status('make_cold_drink take_cold_cup', status=AdamTaskStatus.making)
                    if delay_time := composition.get(define.Constant.MachineType.ice_maker, {}).get("ice", 0):
                        if delay_time > 0:
                            update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='take_ice')
                            self.take_ice(delay_time)
                            self.check_adam_status('make_cold_drink take_ice', status=AdamTaskStatus.making)

                    if not with_foam:
                        # if self.enable_visual_recognition:
                        #     self.detect_cup_thread.pause()  # close detect_cup_thread
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='take_ingredients')
                        self.take_ingredients(Arm.left, composition.get(define.Constant.MachineType.tap, {}))
                        self.check_adam_status('make_cold_drink take_ingredients', status=AdamTaskStatus.making)
                        self.goto_initial_position_direction(Arm.left, 0, wait=True, speed=800)
                        self.check_adam_status('make_cold_drink goto_initial_position_direction', status=AdamTaskStatus.making)
                        if not with_coffee:
                            self.is_coffee_finished = True
                        # if self.enable_visual_recognition:
                        #     self.detect_cup_thread.proceed()  # open detect_cup_thread

                    # 冷咖在等待咖啡机制作时空闲互动 idle interaction
                    if conf.get_idle_Interaction()['state'] and not self.is_coffee_finished:
                        if with_coffee:
                            update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='idle_interaction')
                            self.idle_interaction(coffee_record.formula, "cold")
                        # else:
                        #     self.is_coffee_finished = True
                        #     AudioInterface.stop()
                except Exception as e:
                    logger.error(traceback.format_exc())
                    update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='error')
                    self.stop(f"make_cold_drink left_step1 error is {e}")
                finally:
                    update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='end')

            def right_step1():
                try:
                    if with_foam:
                        foam_machine = composition.get(define.Constant.MachineType.foam_machine, {})
                        if with_foam_coffee:
                            # self.take_espresso_cup()
                            foam_coffee = foam_machine.get('foam', {}).get('foam_composition', {}).get('foam_coffee', {})
                            espresso_composition = {"foam_coffee": {"coffee_make": {"drinkType": foam_coffee - 1}}}
                            update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='take_coffee_machine')
                            self.take_coffee_machine(espresso_composition, parent_thread_name=threading.current_thread().name, formula=coffee_record.formula, is_take_espresso_cup=True)
                            self.check_adam_status('make_cold_drink take_coffee_machine', status=AdamTaskStatus.making)
                            while not self.put_foam_flag and not self.stop_event.is_set():
                                logger.info(f"waiting put_foam_cup success")
                                time.sleep(1)
                            if not self.stop_event.is_set():
                                update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='stainless_cup_pour_foam')
                                self.stainless_cup_pour_foam()
                            self.check_adam_status('make_cold_drink stainless_cup_pour_foam', status=AdamTaskStatus.making)
                        else:
                            update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='take_foam_cup_judge')
                            self.take_foam_cup_judge(Arm.right)
                            self.check_adam_status('make_cold_drink take_foam_cup', status=AdamTaskStatus.making)
                            # if self.enable_visual_recognition:
                            #     self.detect_cup_thread.pause()  # close detect_cup_thread
                            update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='take_ingredients')
                            self.take_ingredients(Arm.right, foam_machine.get('foam', {}).get('foam_composition', {}))
                            self.check_adam_status('make_cold_drink take_ingredients_foam', status=AdamTaskStatus.making)
                            update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='put_foam_cup')
                            self.put_foam_cup(Arm.right, wait=True)
                            self.check_adam_status('make_cold_drink put_foam_cup', status=AdamTaskStatus.making)
                            # if self.enable_visual_recognition:
                            #     self.detect_cup_thread.proceed()  # open detect_cup_thread
                    elif with_coffee:
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='take_coffee_machine')
                        self.take_coffee_machine(composition.get(define.Constant.MachineType.coffee_machine, {}), parent_thread_name=threading.current_thread().name, formula=coffee_record.formula,
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
                                update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='right_random_action')
                                self.right_random_action(coffee_record.formula)
                except Exception as e:
                    logger.error(traceback.format_exc())
                    update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='error')
                    self.stop(f"make_cold_drink right_step1 error is {e}")
                finally:
                    update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='end')

            self.check_adam_status("make_cold_drink step1 thread", AdamTaskStatus.making)
            step1_thread = [threading.Thread(target=left_step1, name='making.left1', daemon=True),
                            threading.Thread(target=right_step1, name='making.right1', daemon=True)]
            for t in step1_thread:
                update_threads_step(status_queue=self.steps_queue, thread=t, step='start')
                t.start()
            for t in step1_thread:
                t.join()

            # step 2 : 三个线程：左手(有配料去接配料)，右手(不锈钢杯需要清洗就去清洗)，有奶泡就开始制作奶泡
            def make_foam_step():
                try:
                    if with_foam:
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='make_foam')
                        self.make_foam(composition.get(define.Constant.MachineType.foam_machine, {}))
                        self.check_adam_status('make_cold_drink make_foam', status=AdamTaskStatus.making)
                except Exception as e:
                    logger.error(traceback.format_exc())
                    update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='error')
                    self.stop(f"make_cold_drink make_foam_step error is {e}")
                finally:
                    update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='end')

            def right_step2():
                try:
                    if with_foam_coffee:
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='clean_and_put_espresso_cup')
                        self.clean_and_put_espresso_cup()
                        self.check_adam_status('make_cold_drink clean_and_put_espresso_cup', status=AdamTaskStatus.making)
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='take_foam_cup')
                        self.take_foam_cup(Arm.right, move=True, waiting=True)
                        self.check_adam_status('make_cold_drink take_foam_cup', status=AdamTaskStatus.making)
                except Exception as e:
                    logger.error(traceback.format_exc())
                    update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='error')
                    self.stop(f"make_cold_drink make_foam_step error is {e}")
                finally:
                    update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='end')

            def left_step2():
                try:
                    time.sleep(1)  # Prevent taking tap first and then cleaning the stainless steel cup
                    # self.thread_lock.acquire()
                    if with_foam and not self.stop_event.is_set():
                        # if self.enable_visual_recognition:
                        #     self.detect_cup_thread.pause()  # close detect_cup_thread
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='take_ingredients')
                        self.take_ingredients(Arm.left, composition.get(define.Constant.MachineType.tap, {}))
                        self.check_adam_status('make_cold_drink take_ingredients', status=AdamTaskStatus.making)
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='goto_initial')
                        self.goto_initial_position_direction(Arm.left, 0, wait=True, speed=800)
                        self.check_adam_status('make_cold_drink goto_initial_position_direction', status=AdamTaskStatus.making)
                        # if self.enable_visual_recognition:
                        #     self.detect_cup_thread.proceed()  # open detect_cup_thread
                except Exception as e:
                    logger.error(traceback.format_exc())
                    update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='error')
                    self.stop(f"make_cold_drink make_foam_step error is {e}")
                finally:
                    # self.thread_lock.release()
                    update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='end')

            self.check_adam_status("make_cold_drink before step2 thread", AdamTaskStatus.making)
            step2_thread = [threading.Thread(target=make_foam_step, name='making.make_foam', daemon=True),
                            threading.Thread(target=right_step2, name='making.right2', daemon=True),
                            threading.Thread(target=left_step2, name='making.left2', daemon=True)]
            for t in step2_thread:
                update_threads_step(status_queue=self.steps_queue, thread=t, step='start')
                t.start()
            for t in step2_thread:
                t.join()
            self.check_adam_status('make_cold_drink after step2 thread', status=AdamTaskStatus.making)

            # step 3 : 如果判断需要咖啡原液，则将其导入左手冷杯中
            if not with_foam:
                if with_coffee:
                    self.update_step(ThreadName.make, 'pour_foam_cup')
                    self.pour_foam_cup('right')
                    self.check_adam_status('make_cold_drink pour_foam_cup', status=AdamTaskStatus.making)

                # AudioInterface.gtts(receipt {}, your {} is ready.".format('-'.join(list(receipt_number)), formula))
                AudioInterface.gtts(f'/richtech/resource/audio/voices/ready_{coffee_record.formula}.mp3')

                def left_step3():
                    try:
                        self.goto_initial_position_direction(Arm.left, 0, wait=False, speed=250)
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='put_cold_cup')
                        self.put_cold_cup(task_uuid=coffee_record.task_uuid)
                        self.check_adam_status('make_cold_drink put_cold_cup', status=AdamTaskStatus.making)
                    except Exception as e:
                        logger.error(traceback.format_exc())
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='error')
                        # self.stop(f"make_cold_drink make_foam_step error is {e}")  # 出杯失败不认为制作失败 | A failure to come out of the cup is not considered a failure of production
                    finally:
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='end')

                def right_step3():
                    try:
                        if with_coffee:
                            update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='clean_and_put_espresso_cup')
                            self.clean_and_put_espresso_cup()
                            self.check_adam_status('make_cold_drink clean_and_put_espresso_cup', status=AdamTaskStatus.making)
                    except Exception as e:
                        logger.error(traceback.format_exc())
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='error')
                        # self.stop(f"make_cold_drink make_foam_step error is {e}")  # 出杯失败不认为制作失败 | A failure to come out of the cup is not considered a failure of production
                    finally:
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='end')

                self.check_adam_status("make_cold_drink before step3 thread", AdamTaskStatus.making)
                step3_thread = [threading.Thread(target=left_step3, name='making.left3', daemon=True),
                                threading.Thread(target=right_step3, name='making.right3', daemon=True)]
                for t in step3_thread:
                    update_threads_step(status_queue=self.steps_queue, thread=t, step='start')
                    t.start()
                for t in step3_thread:
                    t.join()
                self.check_adam_status("make_cold_drink after step3 thread", AdamTaskStatus.making)

            # step 4 :
            else:
                self.update_step(ThreadName.make, 'take_foam_cup')
                self.take_foam_cup(Arm.right, move=False, waiting=False)
                self.check_adam_status('make_cold_drink take_foam_cup', status=AdamTaskStatus.making)
                self.update_step(ThreadName.make, 'pour_foam_cup')
                self.pour_foam_cup("right")
                self.check_adam_status('make_cold_drink pour_foam_cup', status=AdamTaskStatus.making)

                # AudioInterface.gtts(receipt {}, your {} is ready.".format('-'.join(list(receipt_number)), formula))
                AudioInterface.gtts(f'/richtech/resource/audio/voices/ready_{coffee_record.formula}.mp3')

                def left_step4():
                    try:
                        self.goto_initial_position_direction(Arm.left, 0, wait=False, speed=250)
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='put_cold_cup')
                        self.put_cold_cup(task_uuid=coffee_record.task_uuid)
                        self.check_adam_status('make_cold_drink put_cold_cup', status=AdamTaskStatus.making)
                    except Exception as e:
                        logger.error(traceback.format_exc())
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='error')
                        self.stop(f"make_cold_drink make_foam_step error is {e}")
                    finally:
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='end')


                def right_step4():
                    try:
                        time.sleep(1)
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='clean_foamer')
                        self.clean_foamer()
                        self.check_adam_status('make_cold_drink clean_foamer', status=AdamTaskStatus.making)
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='put_foam_cup')
                        self.put_foam_cup(Arm.right)
                        self.check_adam_status('make_cold_drink put_foam_cup', status=AdamTaskStatus.making)
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='back_to_initial')
                        self.back_to_initial(Arm.right)
                        self.check_adam_status('make_cold_drink back_to_initial', status=AdamTaskStatus.making)
                    except Exception as e:
                        logger.error(traceback.format_exc())
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='error')
                        self.stop(f"make_cold_drink make_foam_step error is {e}")
                    finally:
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='end')

                self.check_adam_status("make_cold_drink before step4 thread", AdamTaskStatus.making)
                step4_thread = [threading.Thread(target=left_step4, name='making.left4', daemon=True),
                                threading.Thread(target=right_step4, name='making.right4', daemon=True)]
                for t in step4_thread:
                    update_threads_step(status_queue=self.steps_queue, thread=t, step='start')
                    t.start()
                for t in step4_thread:
                    t.join()
                self.check_adam_status("make_cold_drink after step4 thread", AdamTaskStatus.making)

            self.check_adam_status('make_cold_drink done')  # 判断机械臂在子线程中是否有动作失败，有错误及时抛出异常
            self.left_record.pause()
            self.right_record.pause()
            self.change_adam_status(AdamTaskStatus.idle)

        except Exception as e:
            self.update_step(ThreadName.make, 'error')
            self.stop(str(e))
        finally:
            self.is_coffee_finished = True
            self.update_step(ThreadName.make, 'END')
            get_make_time = int(time.time()) - start_time
            logger.info(f"{coffee_record.formula} making use time is : {get_make_time}")

    def make_hot_drink(self, coffee_record: coffee_schema.CoffeeRecord):
        """
        {'coffee_machine':
        {'double_espresso':
        {'count': 45, 'coffee_make':
        {'drinkType': 21, 'volume': 32, 'coffeeTemperature': 2,
        'concentration': 2, 'hotWater': 0, 'waterTemperature': 0,
        'hotMilk': 0, 'foamTime': 0, 'precook': 0, 'moreEspresso': 0,
        'coffeeMilkTogether': 0, 'adjustOrder': 1}
        }}, 'cup': {'hot_cup': 1}}
        """

        self.update_step(ThreadName.make, 'START')

        start_time = int(time.time())
        AudioInterface.gtts('/richtech/resource/audio/voices/start_making4.mp3')
        logger.debug('start in make_hot_drink')

        try:
            self.update_step(ThreadName.make, 'get_composition_by_option')
            composition = self.get_composition_by_option(coffee_record)
            logger.info(f"into make_hot_drink  :{composition}")
        except Exception as e:
            # 防止只改变订单状态，并未改变adam状态 | Prevent only changing the order status without changing the adam status
            self.change_adam_status(AdamTaskStatus.idle)
            self.update_step(ThreadName.make, 'error')
            self.update_step(ThreadName.make, 'END')
            raise e

        self.is_coffee_finished = False

        self.stop_event.clear()
        self.left_record.clear()  # start a new task, delete the previous log file
        self.right_record.clear()
        self.right_record.proceed()  # 记录关节位置线程开启
        self.left_record.proceed()

        try:
            self.check_adam_status('make_hot_drink take_hot_cup', status=AdamTaskStatus.making)
            self.update_step(ThreadName.make, 'take_coffee_machine')
            self.take_coffee_machine(composition.get("coffee_machine", {}), parent_thread_name='making', formula=coffee_record.formula, type="hot", is_take_hot_cup=True)
            self.check_adam_status('make_hot_drink take_coffee_machine', status=AdamTaskStatus.making)
            # AudioInterface.gtts("receipt {}, your {} is ready.".format('-'.join(list(receipt_number)), formula))
            AudioInterface.gtts(f'/richtech/resource/audio/voices/ready_{coffee_record.formula}.mp3')
            self.update_step(ThreadName.make, 'put_hot_cup')
            self.put_hot_cup(task_uuid=coffee_record.task_uuid)
            self.check_adam_status('make_hot_drink put_hot_cup', status=AdamTaskStatus.making)
            self.change_adam_status(AdamTaskStatus.idle)
        except Exception as e:
            self.update_step(ThreadName.make, 'error')
            self.stop(str(e))
        finally:
            self.right_record.pause()
            self.left_record.pause()
            self.update_step(ThreadName.make, 'END')
            get_make_time = int(time.time()) - start_time
            logger.info(f"{coffee_record.formula} making use time is : {get_make_time}")

    # 抓杯 | take cup
    def take_cold_cup(self):
        """
        左手取冷咖杯子，一旦取杯子就认为开始做咖啡了
        """
        logger.info('into take_cold_cup')
        pose_speed = 500
        angle_speed = 200

        cup_config = self.get_cup_config(define.CupName.cold_cup)
        logger.info('now take {} cup'.format(cup_config.name))
        cup_pose = deepcopy(cup_config.pose)
        which = Arm.left

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

        while is_gripper_flag and not self.stop_event.is_set():
            gripper_pose, gripper_pose1 = take_cup()
            if gripper_pose1 < cup_config.clamp + 3:
                logger.warning('take cup fail，gripper_pose = {}'.format(gripper_pose1))
                take_cup_num += 1
                cup_config.clamp -= 3  # 每次没有抓起来都会将夹爪张合度-3
                if take_cup_num > 5 or cup_config.clamp < 78:
                    AudioInterface.gtts(f'{which} arm take cup fail')
                    self.stop_event.set()
                    raise MoveError(f'after {take_cup_num},{which} arm take cup fail')
                is_gripper_flag = False  # test use
            else:
                logger.info('take cup success，gripper_pose = {}'.format(gripper_pose1))
                is_gripper_flag = False

        self.goto_angles(which, adam_schema.Angles.list_to_obj([209.4, -22.7, -39, -90.3, 89.5, 28.3]), wait=False, speed=angle_speed)

        CoffeeInterface.post_use(define.CupName.cold_cup, 1)  # 冷咖杯子数量-1

    def take_hot_cup(self, take_cup_success):
        """
        右手取热咖杯子，一旦取杯子就认为开始做咖啡了
        """
        logger.info('take_hot_cup')
        pose_speed = 500
        angle_speed = 200

        cup_config = self.get_cup_config(define.CupName.hot_cup)
        logger.info('now take {} cup'.format(cup_config.name))
        cup_pose = deepcopy(cup_config.pose)
        which = Arm.right

        def take_cup():
            # 计算旋转手臂到落杯器的角度
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
            self.env.one_arm(which).set_collision_sensitivity(self.env.adam_config.same_config.collision_sensitivity)  # 恢复灵敏度，与上方设置灵敏度一起注释或一起放开
            self.safe_set_state(Arm.right, 0)
            time.sleep(0.5)
            return gripper_pose, gripper_pose1

        is_gripper_flag = True  # CT gripper or not
        take_cup_num = 0

        while is_gripper_flag and not self.stop_event.is_set():
            gripper_pose, gripper_pose1 = take_cup()
            if gripper_pose1 < cup_config.clamp + 4:
                logger.warning('take cup fail，gripper_pose = {}'.format(gripper_pose1))
                take_cup_num += 1
                cup_config.clamp -= 3  # 每次没有抓起来都会将夹爪张合度-3
                if take_cup_num > 5 or cup_config.clamp < 78:
                    AudioInterface.gtts(f'{which} arm take cup fail')
                    self.stop_event.set()
                    raise MoveError(f'after {take_cup_num},{which} arm take cup fail')
                is_gripper_flag = False  # test use
                take_cup_success.set()  # test use
            else:
                logger.info('take cup success，gripper_pose = {}'.format(gripper_pose1))
                is_gripper_flag = False
                take_cup_success.set()

        self.goto_angles(which, adam_schema.Angles.list_to_obj([-209.4, -22.6, -39.0, 90.3, 89.5, -28.3]), wait=False, speed=angle_speed)

        CoffeeInterface.post_use(define.CupName.hot_cup, 1)  # 热咖杯子数量-1

    def take_espresso_cup(self, take_cup_success):
        logger.info('take_espresso_cup')
        pose_speed = 500  # 800
        angle_speed = 200  # 200
        which = Arm.right
        espresso_config = deepcopy(self.env.machine_config.espresso)
        take_pose = deepcopy(espresso_config.pose.take)

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

        while is_gripper_flag and not self.stop_event.is_set():
            gripper_pose, gripper_pose1 = take_cup()
            if gripper_pose1 < 123:
                logger.info('++++++++++++++++++++++++++++++++++++++++++++++++++++++')
                logger.info('take espresso cup fail，gripper_pose = {}'.format(gripper_pose))
                # AudioInterface.gtts(f'{which} arm take espresso cup fail,waiting 5s again')
                # time.sleep(5)
                take_cup_num += 3
                if take_cup_num > 3:
                    AudioInterface.gtts(f'{which} arm take espresso cup fail')
                    self.stop_event.set()
                    raise MoveError(f'after {take_cup_num},{which} arm take espresso cup fail')
                is_gripper_flag = False  # test use
                take_cup_success.set()  # test use
            else:
                logger.info('++++++++++++++++++++++++++++++++++++++++++++++++++++++')
                logger.info('take espresso cup success，gripper_pose = {}'.format(gripper_pose))
                is_gripper_flag = False
                take_cup_success.set()
        self.goto_angles(which, adam_schema.Angles.list_to_obj([-163.0, 32.9, -99.3, 115.9, 51.0, -34.1]), wait=False, speed=angle_speed)

    def clean_and_put_espresso_cup(self):
        self.thread_lock.acquire()
        logger.info('into clean_espresso_cup')
        pose_speed = 200  # 400
        angle_speed = 100  # 100
        which = Arm.right
        time.sleep(2)
        self.goto_temp_point(which, x=500, y=10.5, z=400, wait=False, speed=pose_speed)
        self.goto_angles(which, adam_schema.Angles.list_to_obj([-159.6, 72, -116.9, 49.6, 29.6, -173.9]), wait=True, speed=angle_speed)
        self.check_adam_angles(which, [-159.6, 72, -116.9, 49.6, 29.6, -173.9], "goto clean espresso_cup")
        current_thread_name = threading.current_thread().name.replace('-', '.')
        check_thread = CheckThread(self.env.one_arm(which), self.stop, thread_name=f'{current_thread_name}.check', steps_queue=self.steps_queue)
        try:
            check_thread.start()
            self.check_adam_status("clean_and_put_espresso_cup", AdamTaskStatus.making)
            com = self.ser.new_communication()
            self.ser.send_one_msg(com, 'L')
            time.sleep(2)
            self.ser.send_one_msg(com, 'l')
            time.sleep(2)
            com.close_engine()
        finally:
            self.thread_lock.release()
            check_thread.stop()
        self.goto_angles(which, adam_schema.Angles.list_to_obj([-155.9, 9.9, -55.1, 101.3, 31.3, -218]), wait=False, speed=80)
        self.goto_point(which, adam_schema.Pose.list_to_obj([778.6, -538.1, 302.8, 23.1, -87.8, 157.5]), wait=False, speed=pose_speed)
        self.goto_temp_point(which, z=157.4, wait=True, speed=pose_speed)
        self.goto_gripper_position(which, 850, wait=True)
        self.goto_temp_point(which, x=626.3, z=262.5, wait=False, speed=pose_speed)
        self.goto_angles(which, adam_schema.Angles.list_to_obj([-209.4, -22.6, -39.0, 90.3, 89.5, -28.3]), wait=False, speed=angle_speed)
        # self.goto_initial_position_direction(which, 0, wait=True, speed=pose_speed)

    def stainless_cup_pour_foam(self):
        pose_speed = 300
        angle_speed = 50
        which = Arm.right
        self.goto_point(which, adam_schema.Pose.list_to_obj([539.7, -79.8, 254.3, -60.0, 90.0, 0.0]), wait=True, speed=pose_speed)
        time.sleep(0.1)
        self.goto_angles(which, adam_schema.Angles.list_to_obj([-150.5, 34.4, -58.0, 61.4, 19.2, -129.8]), wait=True, speed=angle_speed)

    def take_foam_cup_judge(self, arm):
        logger.info('into take_foam_cup_judge')
        cup_config = self.get_cup_config(define.CupName.cold_cup)
        foam_cup_config = deepcopy(self.env.machine_config.shaker)
        take_pose = deepcopy(foam_cup_config.pose.take)
        pose_speed = 500  # 800
        which = arm

        self.goto_initial_position_direction(which, 0, wait=False, speed=pose_speed)  # 转向奶泡杯方向

        # judge foam cup does it exist
        # 视觉识别判断奶泡杯是否存在 | Visual recognition to determine whether the milk foam cup exists
        # *****************************
        if self.enable_visual_recognition:
            check_cup = True
            start_time = time.time()
            play_num = 1
            while check_cup and not self.stop_event.is_set():
                foam_cup_list = CoffeeInterface.get_detect_all_data("foam_cup")
                logger.info(f"foam_cup_list {foam_cup_list}")
                if foam_cup_list[0]["status"] == "1":
                    check_cup = False
                    # break
                if check_cup:
                    time.sleep(5)
                    if time.time() - start_time > 10 * play_num:
                        play_num += 1
                        AudioInterface.gtts('foam cup is not there, please check')

        # *****************************

        def take_cup():
            # 抓杯，获取夹住杯子的张合度，以及向上运动后夹住杯子的张合度
            # Grasp the cup to obtain the opening and closing degree of clamping the cup, and the opening and closing degree of clamping the cup after upward movement.
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
            # first 获取夹爪的张合度 | first obtains the opening and closing degree of the clamping jaw
            code, gripper_pose = self.env.one_arm(which).get_gripper_position()
            logger.info(f'first take foam cup with clamp = {gripper_pose}')
            self.goto_temp_point(which, z=take_pose.z + 50, speed=pose_speed, wait=True)  # 向上运动5cm | Move upward 5cm
            time.sleep(0.5)
            # second 获取夹爪的张合度 | second gets the opening and closing degree of the clamping jaw
            code1, gripper_pose1 = self.env.one_arm(which).get_gripper_position()
            logger.info(f'second take foam cup with clamp = {gripper_pose1}')
            self.env.one_arm(which).set_collision_sensitivity(self.env.adam_config.same_config.collision_sensitivity)  # 恢复灵敏度，与上方设置灵敏度一起注释或一起放开
            self.safe_set_state(which, 0)
            time.sleep(0.5)
            return gripper_pose, gripper_pose1

        # 夹住杯子标识符 | clamp cup identifier
        is_gripper_flag = True  # CT gripper or not
        take_cup_num = 0
        while is_gripper_flag and not self.stop_event.is_set():
            # 获取两次夹住杯子的张合度 | Get the opening and closing degree of clamping the cup twice
            gripper_pose, gripper_pose1 = take_cup()
            # 两次获取的夹住杯子的张合度与杯子本来需要的张合度相比
            # The opening and closing of the clamped cup obtained twice is compared with the original opening and closing of the cup.
            if gripper_pose < 123 and gripper_pose1 < 123:  # 123是给夹爪设置的张合度 | 123 is the opening and closing degree set for the clamping jaw
                logger.warning('take foam cup fail，gripper_pose = {}'.format(gripper_pose))
                AudioInterface.gtts(f'{which} arm take foam cup fail,waiting 5s again')
                take_cup_num += 1
                if take_cup_num > 3:
                    AudioInterface.gtts(f'{which} arm take foam cup fail')
                    self.stop_event.set()
                    raise Exception(f'{which} arm take foam cup fail')  # 抛出异常，返回false
                time.sleep(5)
                is_gripper_flag = False  # test use
            else:
                logger.info('take foam cup success，gripper_pose = {}'.format(gripper_pose))
                is_gripper_flag = False

    def take_foam_cup(self, arm, move=True, waiting=True):
        logger.info('take_foam_cup')
        foam_cup_config = deepcopy(self.env.machine_config.shaker)
        take_pose = deepcopy(foam_cup_config.pose.take)
        pose_speed = 500  # 300
        which = arm

        if move:
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
        if not waiting:
            self.goto_gripper_position(which, 0, wait=True)  # 闭合夹爪
            self.goto_temp_point(which, z=take_pose.z + 50, speed=pose_speed, wait=False)  # 向上运动5cm

    def clean_foamer(self):
        """清洗奶泡杯 | Clean the milk froth cup"""
        logger.info('into clean_foamer')
        pose_speed = 300  # 300
        which = Arm.right
        self.goto_point(which, adam_schema.Pose.list_to_obj([632.6, 3.2, 158.0, -75.4, -86.9, -53.8]), wait=True, speed=pose_speed)
        self.check_adam_pos(which, [632.6, 3.2, 158.0, -75.4, -86.9, -53.8], "goto clean foamer")
        current_thread_name = threading.current_thread().name.replace('-', '.')
        check_thread = CheckThread(self.env.one_arm(which), self.stop, thread_name=f'{current_thread_name}.check', steps_queue=self.steps_queue)
        try:
            check_thread.start()
            self.check_adam_status("clean_foamer", AdamTaskStatus.making)
            com = self.ser.new_communication()
            self.ser.send_one_msg(com, 'L')
            time.sleep(2)
            self.ser.send_one_msg(com, 'l')
            time.sleep(3)
            com.close_engine()
        finally:
            check_thread.stop()

        self.goto_point(which, adam_schema.Pose.list_to_obj([622.5, -10.2, 245.4, -56.5, -89.4, -45.8]), wait=False, speed=pose_speed)
        self.goto_point(which, adam_schema.Pose.list_to_obj([587.3, -13.6, 238.2, -82.6, 52.2, 5.1]), wait=True, speed=pose_speed)
        self.goto_point(which, adam_schema.Pose.list_to_obj([413.5, 2.4, 300.1, -11.8, 90.0, 78.2]), wait=True, speed=pose_speed)

    def back_to_initial(self, arm):
        which = arm
        pose_speed = 400  # 600
        if which == Arm.left:
            self.goto_temp_point(which, y=200, wait=False, speed=pose_speed)
        else:
            self.goto_temp_point(which, y=-200, wait=False, speed=pose_speed)
        self.goto_initial_position_direction(which, 0, wait=True, speed=pose_speed)

    def put_foam_cup(self, which, wait=False):
        logger.info('into put_foam_cup')
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
        if not wait:
            self.goto_gripper_position(which, self.env.gripper_open_pos, wait=True)

    def make_foam(self, composition: dict):
        """
        右手先到龙头处接奶，再到奶泡机打发
        composition: {'foam': {'foam_composition': {'tap01': 3.5, 'foam_coffee': 4}, 'foam_time': 7}}
        """
        logger.info('make_foam with composition = {}'.format(composition))

        if composition:
            foam_time = composition.get('foam', {}).get('foam_time', 15)  # 从字典获取奶泡的制作时间
            com = self.ser.new_communication()
            self.ser.send_one_msg(com, 'M')
            time.sleep(foam_time)  # 30  # 等待制作奶泡，前一步wait必为True   #此时需要去抓冷杯，准备制作咖啡，无需等待
            self.ser.send_one_msg(com, 'm')
            time.sleep(0.1)
            com.close_engine()

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

                self.check_adam_status("")

                # Move both arms into a position ready to pour and receive the pour
                def left_action():
                    self.goto_point(Arm.left, adam_schema.Pose.list_to_obj([478.7, 15.3, 310, 90.0, 90.0, 0.0]), wait=True, speed=pose_speed + 25)

                def right_action():
                    self.goto_point(Arm.right, adam_schema.Pose.list_to_obj([652.1, -9.9, 460.0, -90.0, 90.0, 0.0]), speed=pose_speed,
                                    wait=True)  # 右手位置 x = 465, y = -70, z=420

                self.check_adam_status("ready pour_foam_cup", AdamTaskStatus.making)
                thread_list = [threading.Thread(target=right_action, name=f'{ThreadName.make}.pour_foam_cup.right', daemon=True),
                               threading.Thread(target=left_action, name=f'{ThreadName.make}.pour_foam_cup.left', daemon=True)]
                for t in thread_list:
                    update_threads_step(status_queue=self.steps_queue, thread=t, step='start')
                    t.start()
                for t in thread_list:
                    t.join()
                for t in thread_list:
                    update_threads_step(status_queue=self.steps_queue, thread=t, step='end')

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
        finally:
            logger.info('set back tcp_offset to default')
            default_tcp_offset = list(self.adam_config.gripper_config['default'].tcp_offset.dict().values())
            default_weight = self.adam_config.gripper_config['default'].tcp_load.weight
            default_tool_gravity = list(self.adam_config.gripper_config['default'].tcp_load.center_of_gravity.dict().values())
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

    def put_cold_cup(self, task_uuid=None):
        logger.info('into put_cold_cup')
        pose_speed = 125
        put_pose = None
        which = None
        table = None
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
            check_cup = True
            start_time = time.time()
            play_num = 0
            while check_cup and not self.stop_event.is_set():
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
                    if not check_cup:
                        break
                if check_cup:
                    time.sleep(3)
                    if time.time() - start_time > 10 * play_num:
                        play_num += 1
                        AudioInterface.gtts('/richtech/resource/audio/voices/no_place.mp3')
            if self.stop_event.is_set():
                raise Exception("put_cold_cup stop_event.is_set()")
        # **********************************************
        if put_pose and which and table:
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
        else:
            raise Exception("put_cold_cup put_pose or which or table is None")

    def put_hot_cup(self, task_uuid=None):
        logger.info('into put_hot_cup')
        pose_speed = 125
        put_pose = None
        which = None
        table = None
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
            check_cup = True
            start_time = time.time()
            play_num = 0
            while check_cup and not self.stop_event.is_set():
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
                    if not check_cup:
                        break
                if check_cup:
                    time.sleep(3)
                    if time.time() - start_time > 10 * play_num:
                        play_num += 1
                        AudioInterface.gtts('/richtech/resource/audio/voices/no_place.mp3')
            if self.stop_event.is_set():
                raise Exception("put_hot_cup stop_event.is_set()")
        # **********************************************

        # put_pose.roll = self.get_xy_initial_angle(which, put_pose.x, put_pose.y)
        if put_pose and which and table:
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
        else:
            raise Exception("put_hot_cup put_pose or which or table is None")

    def take_ingredients(self, arm, composition: dict):
        """
        从龙头接糖浆等配料，根据arm参数决定左手接还是右手接
        arm: left or right 左手或右手
        composition: {'material_name': quantity, 'chocolate_syrup': 100}
        """
        logger.info('{} arm take_ingredients {}'.format(arm, composition))

        if composition:
            self.thread_lock.acquire()
            try:
                pose_speed = 300  # 500
                tap_pose = deepcopy(self.env.machine_config.gpio.tap.pose)
                which = arm
                tap_pose.roll = self.get_xy_initial_angle(which, tap_pose.x, tap_pose.y)
                take_pose = deepcopy(tap_pose)
                if composition:
                    self.goto_initial_position_direction(which, tap_pose.roll, wait=False, speed=pose_speed)
                    self.goto_point(which, take_pose, wait=True, speed=pose_speed)  # 运动到龙头下方位置
                    self.check_adam_pos(which, [take_pose.x, take_pose.y, take_pose.z, take_pose.roll, take_pose.pitch, take_pose.yaw],
                                        'take_ingredients open port')
                for name, quantity in composition.items():
                    CoffeeInterface.post_use(name, quantity)
                logger.debug('open_dict = {}'.format(composition))
                current_thread_name = threading.current_thread().name.replace('-', '.')
                check_thread = CheckThread(self.env.one_arm(which), self.stop, thread_name=f'{current_thread_name}.check', steps_queue=self.steps_queue)
                try:
                    check_thread.start()
                    self.ser.open_port_together_by_type(composition, self.stop_event)
                    CenterInterface.update_last_milk_time(list(composition.keys()))
                finally:
                    check_thread.stop()

            except Exception as e:
                raise e
            finally:
                self.thread_lock.release()

    def take_ice(self, delay_time):
        """
        delay_time 接冰停顿时间
        see coffee_machine.yaml -> task_option for more detail
        """
        logger.info('into take_ice, delay_time = {}'.format(delay_time))

        pose_speed = 350  # 500
        which = Arm.left
        before_dispense_pose = deepcopy(self.env.machine_config.ice_maker[1].pose)
        dispense_pose = deepcopy(self.env.machine_config.ice_maker[2].pose)

        self.goto_point(which, before_dispense_pose, wait=False, speed=pose_speed)

        self.goto_point(which, dispense_pose, wait=True, speed=100)

        current_thread_name = threading.current_thread().name.replace('-', '.')
        check_thread = CheckThread(self.env.one_arm(which), self.stop, thread_name=f'{current_thread_name}.check', steps_queue=self.steps_queue)
        check_thread.start()
        time.sleep(delay_time)  # 等待接冰
        check_thread.stop()

        self.goto_point(which, before_dispense_pose, wait=False, speed=pose_speed)
        # 设置成True后，防止直接进入下一步After setting to True, prevent directly entering the next step.
        self.goto_initial_position_direction(which, 0, wait=True, speed=pose_speed)  # 返回工作零点

    def take_coffee_machine(self, composition: dict, parent_thread_name, formula=None, type=None, is_take_espresso_cup=False, is_take_hot_cup=False):
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
        coffee_pose = deepcopy(self.env.machine_config.coffee_machine.pose)
        before_coffee_pose = deepcopy(coffee_pose)
        before_coffee_pose.x = 663.7
        before_coffee_pose.y = -567.7
        before_coffee_pose.z = 181.1
        before_coffee_pose.roll = 0
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
                    while check_cup and self.stop_event.is_set():
                        espresso_cup_list = CoffeeInterface.get_detect_all_data("espresso_cup")
                        logger.info(f"espresso_cup_list {espresso_cup_list}")
                        if espresso_cup_list[0]["status"] == "1":
                            check_cup = False
                            # break
                        if check_cup == True:
                            time.sleep(1)
                            if time.time() - start_time > 10 * play_num:
                                play_num += 1
                                AudioInterface.gtts('espresso cup is not there, please check')
                # ********************************

            def goto_coffee_pose(coffee_pose, take_cup_success):
                try:
                    logger.info("There is coffee_pose: {}".format(coffee_pose))
                    if is_take_hot_cup:
                        logger.info("Now grabbing the hot cup")
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='take_hot_cup')
                        self.take_hot_cup(take_cup_success)
                    if is_take_espresso_cup:
                        logger.info("Now grabbing the espresso cup")
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='take_espresso_cup')
                        self.take_espresso_cup(take_cup_success)
                    # If a hot drink was ordered this motion will move very slow if the last wait in take_hot_cup is False.
                    self.goto_point(which, before_coffee_pose, speed=pose_speed, wait=False)
                    self.goto_point(which, coffee_pose, wait=True, speed=pose_speed)
                    if conf.get_idle_Interaction()['state'] and type and not self.is_coffee_finished and not self.stop_event.is_set():
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='idle_interaction')
                        self.idle_interaction(formula, type)
                except Exception as e:
                    logger.error(traceback.format_exc())
                    update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='error')
                    self.stop(f"goto_coffee_pose error={e}")
                finally:
                    update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='end')

            def make_coffee(composition, take_cup_success):
                for name, config in composition.items():
                    current_thread_name = threading.current_thread().name.replace('-', '.')
                    check_thread = CheckThread(self.env.one_arm(which), self.stop, thread_name=f'{current_thread_name}.check', steps_queue=self.steps_queue)
                    self.coffee_thread.pause()
                    try:
                        check_thread.start()
                        coffee_dict = config.get('coffee_make')
                        self.coffee_thread.pause()
                        while not take_cup_success.is_set() and not self.stop_event.is_set():
                            time.sleep(0.5)
                        self.coffee_driver.wait_until_idle(check=True)
                        if not self.stop_event.is_set():
                            update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='make_coffee')
                            self.coffee_driver.make_coffee(coffee_dict["drinkType"])
                    except Exception as e:
                        logger.error(traceback.format_exc())
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='error')
                        self.stop(f"make_coffee error={e}")
                    finally:
                        self.coffee_thread.proceed()
                        self.is_coffee_finished = True
                        check_thread.stop()
                        update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='end')

            take_cup_success = threading.Event()
            parent_thread_name = parent_thread_name.replace('-', '.')
            step1_thread = [threading.Thread(target=goto_coffee_pose, args=(coffee_pose, take_cup_success), name=f'{parent_thread_name}.goto_coffee_pose', daemon=True),
                            threading.Thread(target=make_coffee, args=(composition, take_cup_success), name=f'{parent_thread_name}.make_coffee', daemon=True)]
            logger.info("Begin the thread")
            for t in step1_thread:
                update_threads_step(status_queue=self.steps_queue, thread=t, step='start')
                t.start()
            for t in step1_thread:
                t.join()
            logger.info("The threads are done")

            self.check_adam_status('take_coffee_machine', status=AdamTaskStatus.making)  # 判断机械臂在子线程中是否有动作失败，有错误及时抛出异常
            logger.info("No issues with the status")
            self.goto_point(which, before_coffee_pose, speed=150, wait=True)
            logger.info("Take_coffee_machine is done")

    def get_cup_config(self, cup_name) -> total_schema.GetCupConfig:
        cup_config = deepcopy([i for i in self.env.machine_config.get if i.name == cup_name][0])
        return cup_config

    def safe_set_state(self, which, state=0):
        arm = self.env.one_arm(which)
        if arm.state != 4:
            self.env.one_arm(which).set_state(state)

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
        self.goto_point(which, pose, wait=wait, speed=speed)

    # 空闲互动 | idle interaction
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
                        self.left_interaction_dance()
                    elif num == 1:
                        self.left_random_action(formula)
                elif type == 'cold':
                    num = random.randint(0, 0)
                    if num == 0:
                        self.left_round(formula)

    def choose_speech(self, type, formula=None):
        if type == 'coffee_knowledge':
            AudioInterface.gtts(f'/richtech/resource/audio/voices/coffee_knowledge_transition1.mp3')
            for i in range(5):
                self.check_adam_status('make coffee waiting', status=AdamTaskStatus.making)
                time.sleep(1)
            num = random.randint(1, 48)
            file_path = f'/richtech/resource/audio/voices/coffee_knowledge{num}.mp3'
            AudioInterface.gtts(file_path)
            return MP3(file_path).info.length
        elif type == 'mood':
            num_t = random.randint(1, 2)
            AudioInterface.gtts(f'/richtech/resource/audio/voices/mood_transition{num_t}.mp3')
            for i in range(5):
                self.check_adam_status('make coffee waiting', status=AdamTaskStatus.making)
                time.sleep(1)
            num = random.randint(1, 34)
            file_path = f'/richtech/resource/audio/voices/mood{num}.mp3'
            AudioInterface.gtts(file_path)
            return MP3(file_path).info.length
        elif type == 'dance_transition':
            AudioInterface.gtts(f'/richtech/resource/audio/voices/dance_transition1.mp3')
        elif type == 'coffee_introduction':
            AudioInterface.gtts(f'/richtech/resource/audio/voices/coffee_introduction_transition1.mp3')
            time.sleep(1)
            file_path = f'/richtech/resource/audio/voices/coffee_introduction_{formula}.mp3'
            AudioInterface.gtts(file_path)
            return MP3(file_path).info.length

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

        speed = 150
        self.choose_speech("dance_transition")
        self.goto_gripper_position(Arm.left, 0, wait=False)
        self.left.set_position(**left_init, wait=True, speed=speed, radius=50)
        AudioInterface.music('She.mp3')
        self.left.set_position(**left1, wait=False, speed=200, radius=50)
        for i in range(4):
            self.left.set_position(**left1, wait=False, speed=speed, radius=50)
            self.left.set_position(**left2, wait=False, speed=speed, radius=50)

        for i in range(7):
            self.check_adam_status('left_interaction_dance', status=AdamTaskStatus.making)
            if self.is_coffee_finished and self.stop_event.is_set():
                utils.reduce_sound()
                AudioInterface.stop()
                utils.recover_sound()
                break
            self.left.set_position(**left3, wait=False, speed=speed + 100, radius=50)
            self.left.set_position(**left4, wait=False, speed=speed, radius=50)
            self.left.set_position(**left5, wait=False, speed=speed, radius=50)
            self.left.set_position(**left6, wait=False, speed=speed, radius=50)
            self.left.set_position(**left7, wait=False, speed=speed, radius=50)
            self.left.set_position(**left8, wait=True, speed=speed, radius=50)

        self.left.set_position(**left1, wait=False, speed=200, radius=50)

    def left_random_action(self, formula):

        num = random.randint(0, 2)
        duration_in_seconds = 0
        if num == 0:
            duration_in_seconds = self.choose_speech("coffee_introduction", formula)
        elif num == 1:
            duration_in_seconds = self.choose_speech("coffee_knowledge", formula)
        elif num == 2:
            duration_in_seconds = self.choose_speech("mood", formula)

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

        self.goto_gripper_position(Arm.left, 0, wait=False)
        start_time = time.time()
        while True:
            logger.debug(f"self.is_coffee_finished : {self.is_coffee_finished}")
            self.check_adam_status('left_random_action', status=AdamTaskStatus.making)
            if self.is_coffee_finished or time.time() - start_time > duration_in_seconds or self.stop_event.is_set():
                utils.reduce_sound()
                AudioInterface.stop()
                utils.recover_sound()
                break
            left_left_up(90)
            left_front(90)
            left_up(90)

        if not self.stop_event.is_set():
            self.left.set_position(**left_init, wait=False, speed=200, radius=50)

    def left_round(self, formula):
        """left arm draw a circle"""
        speech_list = ['coffee_introduction', 'mood', 'coffee_knowledge']
        speech_num = random.randint(0, 2)
        duration_in_seconds = self.choose_speech(speech_list[speech_num], formula)

        start_time = time.time()
        left_pos_A = {'x': 310, 'y': 550, 'z': 250, 'roll': 0, 'pitch': 90, 'yaw': 0}
        left_pos_B = [360, 600, 250, 0, 90, 0]
        left_pos_C = [360, 500, 250, 0, 90, 0]
        self.left.set_position(**left_pos_A, speed=100, wait=True)
        while time.time() - start_time < duration_in_seconds and not self.stop_event.is_set():
            self.check_adam_status('left_round', status=AdamTaskStatus.making)
            if self.is_coffee_finished:
                return
            self.left.move_circle(left_pos_B, left_pos_C, percent=100, speed=100, wait=True)

    def right_random_action(self, formula):

        duration_in_seconds = self.choose_speech("coffee_introduction", formula)

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

        start_time = time.time()
        while True:
            self.check_adam_status('right_random_action', status=AdamTaskStatus.making)
            if self.is_coffee_finished or time.time() - start_time > duration_in_seconds or self.stop_event.is_set():
                utils.reduce_sound()
                AudioInterface.stop()
                utils.recover_sound()
                break
            right_right_up(90)
            right_front(90)
            right_up(90)

        if not self.stop_event.is_set():
            self.right.set_position(**right_init, wait=False, speed=200, radius=50)

    # 安全返回 | safe return
    def back(self, which, file_path):
        """
        rollback according to the records in file
        """
        logger.info('before {} record thread rollback'.format(which))
        arm = self.env.one_arm(which)
        arm.set_state(0)
        arm.set_mode(0)
        arm.motion_enable()
        arm.clean_error()
        arm.clean_warn()
        arm.set_state()
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

    def dead(self, which):
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

    def roll(self):
        logger.warning('adam prepare to roll back')
        AudioInterface.gtts('/richtech/resource/audio/voices/start_roll.mp3', True)
        if self.task_status not in [AdamTaskStatus.stopped]:
            return 'don\'t need to roll back'
        self.change_adam_status(AdamTaskStatus.rolling)
        self.update_step(name=ThreadName.roll, step='start')
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

        def left_roll():
            lflag, msg = self.back(Arm.left, self.env.get_record_path(Arm.left))
            logger.debug('left back flag = {}, {}'.format(lflag, msg))
            if lflag in [0, 1]:
                self.left_roll_end = True
                roll_end()
            else:
                logger.warning('left roll back failed')
                self.env.adam.set_state(dict(state=4), dict(state=4))
                self.dead(Arm.left)
            logger.warning('adam left arm roll back end')
            update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='end')

        def right_roll():
            rflag, msg = self.back(Arm.right, self.env.get_record_path(Arm.right))
            logger.debug('right back flag = {}, {}'.format(rflag, msg))
            if rflag in [0, 1]:
                self.right_roll_end = True
                roll_end()
            else:
                logger.warning('right roll back failed')
                self.env.adam.set_state(dict(state=4), dict(state=4))
                self.dead(Arm.right)
            logger.warning('adam right arm roll back end')
            update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step='end')

        thread_list = [
            threading.Thread(target=left_roll, name=f'{ThreadName.roll}.left', daemon=True),
            threading.Thread(target=right_roll, name=f'{ThreadName.roll}.right', daemon=True)
        ]
        for t in thread_list:
            update_threads_step(self.steps_queue, thread=t, step='start')
            t.start()
        for t in thread_list:
            t.join()
        self.update_step(name=ThreadName.roll, step='end')
        return 'ok'


class QueryCoffeeThread(threading.Thread):
    def __init__(self, coffee_driver: Coffee_Driver, steps_queue=None):
        super().__init__()
        self.coffee_driver = coffee_driver
        self.coffee_status = dict(status_code=self.coffee_driver.last_status.get('status_code', ''),
                                  status=self.coffee_driver.last_status.get('status', ''),
                                  error_code=self.coffee_driver.last_status.get('error_code', []),
                                  error=self.coffee_driver.last_status.get('error', []))
        self.run_flag = True
        self.steps_queue = steps_queue

    def update_step(self, step):
        if self.steps_queue is not None:
            utils.update_threads_step(status_queue=self.steps_queue, thread=self, step=step)

    def pause(self):
        self.run_flag = False
        self.update_step('pause')

    def proceed(self):
        self.coffee_status = dict(status_code=self.coffee_driver.last_status.get('status_code', ''),
                                  status=self.coffee_driver.last_status.get('status', ''),
                                  error_code=self.coffee_driver.last_status.get('error_code', []),
                                  error=self.coffee_driver.last_status.get('error', []))
        self.run_flag = True
        self.update_step('proceed')

    def run(self):
        self.update_step('start')
        while True:
            if self.run_flag:
                try:
                    logger.debug('query in coffee thread')
                    query_status = self.coffee_driver.query_status()
                    logger.info(f"query_status:{query_status}")
                    self.coffee_status = dict(status_code=self.coffee_driver.last_status.get('status_code', ''),
                                              status=self.coffee_driver.last_status.get('status', ''),
                                              error_code=self.coffee_driver.last_status.get('error_code', []),
                                              error=self.coffee_driver.last_status.get('error', []))
                except Exception as e:
                    AudioInterface.gtts(str(e))
                    query_status = {"status_code": "", "status": ""}
                error_code = query_status.get('error_code', [])
                error = query_status.get('error', [])
                if error != '':
                    for i in error:
                        AudioInterface.gtts(i)
            time.sleep(20)  # 每分钟查询一次咖啡机状态
        # self.update_step('end') # 永远不会进入这一行代码 | Never get into this line of code
