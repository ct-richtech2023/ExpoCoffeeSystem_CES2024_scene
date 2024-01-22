import time
import os
from copy import deepcopy

from loguru import logger

from xarm.wrapper import XArmAPI

from dual import AdamRobot
from common.schemas import total as total_schema
from common.schemas import adam as adam_schema
from common import conf, utils
from common.api import ExceptionInterface
from common.define import ExceptionType, Arm


class EnvConfig:
    """
    用来初始化机械臂，获取机械臂相关配置的类
    """

    def __init__(self, machine_config: total_schema.MachineConfig, adam_config: adam_schema.AdamConfig):
        # adam所处环境的配置
        self.machine_config = machine_config
        # adam机器人本身的配置
        self.adam_config = adam_config
        self._left, self._right = None, None
        # 校验adam本身的系统配置
        self.check_adam_init()
        self.adam = AdamRobot(self.left, self.right)
        self.record_dir = '../record'
        if not os.path.exists(self.record_dir):
            os.makedirs('../record')

    @property
    def adam_left_ip(self):
        return str(self.machine_config.adam.ip.left)

    @property
    def default_arm_speed(self):
        return self.machine_config.adam.default_speed.arm

    @property
    def default_gripper_speed(self):
        return self.machine_config.adam.default_speed.gripper

    @property
    def adam_right_ip(self):
        return str(self.machine_config.adam.ip.right)

    @property
    def gripper_open_pos(self):
        return self.machine_config.adam.gripper.open

    @property
    def limiter_high(self):
        return self.machine_config.share_position.limiter.high

    @property
    def left(self) -> XArmAPI:
        if not self._left:
            self._left = XArmAPI(self.adam_left_ip)
            logger.info('implement {} robot'.format(self.adam_left_ip))
        return self._left

    @property
    def right(self) -> XArmAPI:
        if not self._right:
            self._right = XArmAPI(self.adam_right_ip)
            logger.info('implement {} robot'.format(self.adam_right_ip))
        return self._right

    @staticmethod
    def left_or_right(y):
        return Arm.left if y > 0 else Arm.right

    def get_tcp_offset(self, which) -> adam_schema.Pose:
        return self.adam_config.gripper_config[getattr(self.adam_config.different_config, which).gripper].tcp_offset

    def get_tcp_load(self, which) -> adam_schema.TcpLoad:
        return self.adam_config.gripper_config[getattr(self.adam_config.different_config, which).gripper].tcp_load

    def get_world_offset(self, which) -> adam_schema.Pose:
        return getattr(self.adam_config.different_config, which).world_offset

    def get_record_path(self, which):
        if which == 'left':
            return os.path.join(self.record_dir, 'left.csv')
        if which == 'right':
            return os.path.join(self.record_dir, 'right.csv')

    def check_adam_init(self):
        """
        adam机器人初始化是落地settings/adam.yml中的配置，如果配置下发失败会直接导致异常退出
        """
        try:
            logger.info('adam init config before work')
            self.init_adam()
        except Exception as e:
            logger.error('{}, err={}'.format(ExceptionType.adam_initial_position_failed, str(e)))
            time.sleep(3)
            # 配置落地失败，直接异常退出
            exit(-1)

    def set_robot_config(self, attr, value, which=None):
        def get_attr_value(_robot):
            if attr == 'tcp_maxacc':
                return getattr(_robot, 'tcp_acc_limit')[-1]
            elif attr == 'joint_maxacc':
                return getattr(_robot, 'joint_acc_limit')[-1]
            elif attr == 'mount_direction':
                _gravity_direction = getattr(_robot, 'gravity_direction')
                left_value = [-0.8660253882408142, -0.5, -6.123234262925839e-17]
                right_value = [-0.8660253882408142, 0.5, -6.123234262925839e-17]
                if utils.compare_value(_gravity_direction, left_value):
                    return [90, 150]
                elif utils.compare_value(_gravity_direction, right_value):
                    return [90, -150]
                else:
                    logger.warning("can't check gravity_direction is correct")
            elif hasattr(_robot, attr):
                return getattr(_robot, attr)
            elif hasattr(_robot, "get_{}".format(attr)):
                result = getattr(_robot, "get_{}".format(attr))()
                return result[-1] if isinstance(result, tuple) else result
            else:
                logger.warning('robot not have {} attr'.format(attr))

        which = [which] if which in [Arm.left, Arm.right] else [Arm.left, Arm.right]

        for arm in which:
            robot = getattr(self, arm)
            origin = get_attr_value(robot)
            compare_value = list(value.values()) if isinstance(value, dict) else value
            if utils.compare_value(origin, compare_value, 0.05):
                logger.debug('{} arm {} already is {}'.format(arm, attr, compare_value))
            else:
                set_func = getattr(robot, "set_{}".format(attr))
                if isinstance(value, dict):
                    set_func(**value)
                else:
                    set_func(value)
                getattr(robot, "set_state")()
                logger.info('{} arm set {} to {}'.format(arm, attr, value))
                time.sleep(1)
                if after_set := get_attr_value(robot):
                    if not utils.compare_value(after_set, compare_value, 0.05):
                        err_msg = "{} arm origin {}={}, change to {} failed!".format(arm, attr, origin, compare_value)
                        raise Exception(err_msg)

    def one_arm(self, which) -> XArmAPI:
        return getattr(self, which)

    def set_one_arm_tcp_load(self, which, weight=0, center=None):
        """
        单个手臂的负载=夹爪本身的负载+受力负载
        """
        center = center or [0, 0, 0]
        arm = self.one_arm(which)
        tcp_load = self.get_tcp_load(which)
        weight = tcp_load.weight + weight
        origin_center_of_gravity = list(dict(tcp_load.center_of_gravity).values())
        center = [center[i] + value for i, value in enumerate(origin_center_of_gravity)]
        arm.set_tcp_load(weight, center)

    def init_adam(self):
        self.left.set_state(0)
        self.left.set_mode(0)
        self.left.motion_enable()
        self.left.clean_error()
        self.left.clean_warn()
        self.left.set_state()
        self.right.set_state(0)
        self.right.set_mode(0)
        self.right.motion_enable()
        self.right.clean_error()
        self.right.clean_warn()
        self.right.set_state()
        same_config = self.adam_config.same_config
        for name, value in dict(same_config).items():
            self.set_robot_config(name, value)
        different_config = dict(self.adam_config.different_config)
        for arm, arm_config in different_config.items():
            for name, value in dict(arm_config).items():
                if name == 'gripper':
                    gripper_config = self.adam_config.gripper_config[value]
                    tcp_offset = list(dict(gripper_config.tcp_offset).values())
                    self.set_robot_config('tcp_offset', tcp_offset, arm)  # noqa
                    center_of_gravity = list(dict(gripper_config.tcp_load.center_of_gravity).values())
                    tcp_load = dict(gripper_config.tcp_load)
                    tcp_load['center_of_gravity'] = center_of_gravity
                    self.set_robot_config('tcp_load', tcp_load, arm)
                elif name == 'world_offset':
                    world_offset = list(dict(value).values())
                    self.set_robot_config('world_offset', world_offset, arm)  # noqa
                elif name == 'mount_direction':
                    self.set_robot_config('mount_direction', dict(value), arm)
        if self.adam_config.save_conf:
            self.left.save_conf()
            self.right.save_conf()
            logger.debug("save robot config")
