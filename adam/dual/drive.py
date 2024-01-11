import typing
from concurrent.futures import ThreadPoolExecutor

from common import utils

from xarm import XArmAPI

from .model import *
from .wrapper import *


class AdamRobot(object):
    """
    The API wrapper of Adam Robot

    :param left: XArmAPI obj
    :param right: XArmAPI obj
        Reserved
    """

    def __init__(self, left: XArmAPI, right: XArmAPI):
        self.left = left
        self.right = right

    @property
    def core(self):
        """
        Core layer API, set only for advanced developers, please do not use
        Ex:
            self.core.move_line(...)
            self.core.move_lineb(...)
            self.core.move_joint(...)
            ...
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def count(self):
        """
        Counter val
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def realtime_tcp_speed(self):
        """
        The real time speed of tcp motion, only available if version > 1.2.11

        :return: real time speed (mm/s)
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def realtime_joint_speeds(self):
        """
        The real time speed of joint motion, only available if version > 1.2.11

        :return: [joint-1-speed(°/s or rad/s), ...., joint-7-speed(°/s or rad/s)]
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def gpio_reset_config(self):
        """
        The gpio reset enable config
        :return: [cgpio_reset_enable, tgpio_reset_enable]
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def version_number(self):
        """
        Frimware version number

        :return: (major_version_number, minor_version_number, revision_version_number)
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def connected(self):
        """
        Connection status
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def default_is_radian(self):
        """
        The default unit is radians or not
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def version(self):
        """
        xArm version
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def sn(self):
        """
        xArm sn
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def control_box_sn(self):
        """
        Control box sn
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def position(self):
        """
        Core layer API, set only for advanced developers, please do not use
        Ex:
            self.core.move_line(...)
            self.core.move_lineb(...)
            self.core.move_joint(...)
            ...
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def position_aa(self):
        """
        The pose represented by the axis angle pose
        Note:
            1. If self.default_is_radian is True, the returned value (only roll/pitch/yaw) is in radians

        :return: [x(mm), y(mm), z(mm), rx(° or rad), ry(° or rad), rz(° or rad)]
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def last_used_position(self):
        """
        The last used cartesion position, default value of parameter x/y/z/roll/pitch/yaw of interface set_position
        Note:
            1. If self.default_is_radian is True, the returned value (only roll/pitch/yaw) is in radians
            2. self.set_position(x=300) <==> self.set_position(x=300, *last_used_position[1:])
            2. self.set_position(roll=-180) <==> self.set_position(x=self.last_used_position[:3], roll=-180, *self.last_used_position[4:])

        :return: [x(mm), y(mm), z(mm), roll(° or rad), pitch(° or rad), yaw(° or rad)]
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def tcp_jerk(self):
        """
        Tcp jerk

        :return: jerk (mm/s^3)
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def tcp_speed_limit(self):
        """
        Tcp speed limit, only available in socket way and enable_report is True and report_type is 'rich'

        :return: [min_tcp_speed(mm/s), max_tcp_speed(mm/s)]
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def tcp_acc_limit(self):
        """
        Tcp acceleration limit, only available in socket way and enable_report is True and report_type is 'rich'

        :return: [min_tcp_acc(mm/s^2), max_tcp_acc(mm/s^2)]
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def last_used_tcp_speed(self):
        """
        The last used cartesion speed, default value of parameter speed of interface set_position/move_circle

        :return: speed (mm/s)
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def last_used_tcp_acc(self):
        """
        The last used cartesion acceleration, default value of parameter mvacc of interface set_position/move_circle

        :return: acceleration (mm/s^2)
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def angles(self):
        """
        Servo angles
        Note:
            1. If self.default_is_radian is True, the returned value is in radians

        :return: [angle1(° or rad), angle2(° or rad), ..., anglen7(° or rad)]
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def joint_jerk(self):
        """
        Joint jerk
        Note:
            1. If self.default_is_radian is True, the returned value is in radians

        :return: jerk (°/s^3 or rad/s^3)
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def joint_speed_limit(self):
        """
        Joint speed limit,  only available in socket way and enable_report is True and report_type is 'rich'
        Note:
            1. If self.default_is_radian is True, the returned value is in radians

        :return: [min_joint_speed(°/s or rad/s), max_joint_speed(°/s or rad/s)]
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def joint_acc_limit(self):
        """
        Joint acceleration limit, only available in socket way and enable_report is True and report_type is 'rich'
        Note:
            1. If self.default_is_radian is True, the returned value is in radians

        :return: [min_joint_acc(°/s^2 or rad/s^2), max_joint_acc(°/s^2 or rad/s^2)]
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def last_used_angles(self):
        """
        The last used servo angles, default value of parameter angle of interface set_servo_angle
        Note:
            1. If self.default_is_radian is True, the returned value is in radians
            2. self.set_servo_angle(servo_id=1, angle=75) <==> self.set_servo_angle(angle=[75] + self.last_used_angles[1:])
            3. self.set_servo_angle(servo_id=5, angle=30) <==> self.set_servo_angle(angle=self.last_used_angles[:4] + [30] + self.last_used_angles[5:])

        :return: [angle1(° or rad), angle2(° or rad), ..., angle7(° or rad)]
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def last_used_joint_speed(self):
        """
        The last used joint speed, default value of parameter speed of interface set_servo_angle
        Note:
            1. If self.default_is_radian is True, the returned value is in radians

        :return: speed (°/s or rad/s)
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def last_used_joint_acc(self):
        """
        The last used joint acceleration, default value of parameter mvacc of interface set_servo_angle
        Note:
            1. If self.default_is_radian is True, the returned value is in radians

        :return: acceleration (°/s^2 or rad/s^2)
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def tcp_offset(self):
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def world_offset(self):
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def state(self):
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def mode(self):
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def is_simulation_robot(self):
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def joints_torque(self):
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def tcp_load(self):
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def collision_sensitivity(self):
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def teach_sensitivity(self):
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def motor_brake_states(self):
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def motor_enable_states(self):
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def temperatures(self):
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def has_err_warn(self):
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def gpio_reset_config(self):
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def has_error(self):
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def has_warn(self):
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def error_code(self):
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def warn_code(self):
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def cmd_num(self):
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def device_type(self):
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def axis(self):
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def master_id(self):
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def slave_id(self):
        """
        Slave id, only available in socket way and enable_report is True and report_type is 'rich'
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def gravity_direction(self):
        """
        gravity direction, only available in socket way and enable_report is True and report_type is 'rich'
        :return:
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def servo_codes(self):
        """
        Servos status and error_code
        :return: [
            [servo-1-status, servo-1-code],
            ...,
            [servo-7-status, servo-7-code],
            [tool-gpio-status, tool-gpio-code]
        ]
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def voltages(self):
        """
        Servos voltage

        :return: [servo-1-voltage, ..., servo-7-voltage]
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def currents(self):
        """
        Servos electric current

        :return: [servo-1-current, ..., servo-7-current]
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def cgpio_states(self):
        """
        Controller gpio state

        :return: states
            states[0]: contorller gpio module state
                states[0] == 0: normal
                states[0] == 1：wrong
                states[0] == 6：communication failure
            states[1]: controller gpio module error code
                states[1] == 0: normal
                states[1] != 0：error code
            states[2]: digital input functional gpio state
                Note: digital-i-input functional gpio state = states[2] >> i & 0x01
            states[3]: digital input configuring gpio state
                Note: digital-i-input configuring gpio state = states[3] >> i & 0x01
            states[4]: digital output functional gpio state
                Note: digital-i-output functional gpio state = states[4] >> i & 0x01
            states[5]: digital output configuring gpio state
                Note: digital-i-output configuring gpio state = states[5] >> i & 0x01
            states[6]: analog-0 input value
            states[7]: analog-1 input value
            states[8]: analog-0 output value
            states[9]: analog-1 output value
            states[10]: digital input functional info, [digital-0-input-functional-mode, ... digital-7-input-functional-mode]
            states[11]: digital output functional info, [digital-0-output-functional-mode, ... digital-7-output-functional-mode]
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def self_collision_params(self):
        """
        Self collision params

        :return: params
            params[0]: self collision detection or not
            params[1]: self collision tool type
            params[2]: self collision model params
        """
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def ft_ext_force(self):
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    @property
    def ft_raw_force(self):
        func_name = utils.get_current_func_name()
        return self._get_adam_attr_value(func_name)

    def disconnect(self):
        """
        Disconnect
        """
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool(func_name)
        return result

    def _register_callback(self, register_func_name, callback: typing.Tuple):
        """
        Register the error code or warn code changed callback, only available if enable_report is True
        Note: this func for dynamic setattr, not for user

        :param register_func_name: must a api in XArmAPI
        :param callback: callable function
        :return: dict {'1.1.1.1': True/False, '1.1.1.2': True/False}
        """

        if callable(callback):
            left_callback = right_callback = callback
        elif isinstance(callback, tuple):
            if len(callback) != 2:
                raise Exception('if callback is tuple, length must be 2, callback={}'.format(callback))
            left_callback = callback[0]
            right_callback = callback[1]
        else:
            raise Exception('register callback must be callable or tuple')
        left_func = getattr(self.left, register_func_name)
        left_result = left_func(left_callback)
        right_func = getattr(self.right, register_func_name)
        right_result = right_func(right_callback)
        return left_result, right_result

    @analyze_error_code
    @check_adam_sdk_left_and_right_param(SetPosition)
    def set_position(self, left: dict, right: dict):
        """
        set adam robot position

        :param left: dict model is SetPosition
        :param right: dict model is SetPosition
        :return: code, code
        """
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool_with_param(func_name, left, right)
        return result

    @analyze_error_code
    @check_adam_sdk_left_and_right_param(MotionEnable)
    def motion_enable(self, left: dict, right: dict):
        """
        Adam Motion enable
        :param left: dict model is MotionEnable
        :param right: dict model is MotionEnable
        :return: code, code
        """
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool_with_param(func_name, left, right)
        return result

    @analyze_error_code
    @check_adam_sdk_left_and_right_param(SetMode)
    def set_mode(self, left: dict, right: dict):
        """
        Set the Adam mode

        :param left: model is SetMode
        :param right: model is SetMode
        :return: code, code
        """
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool_with_param(func_name, left, right)
        return result

    def _get_adam_attr_value(self, attr_name: str) -> tuple:
        left_result = getattr(self.left, attr_name) if self.left else None
        right_result = getattr(self.right, attr_name) if self.right else None
        return left_result, right_result

    def run_in_thread_pool_with_param(self, func_name, left_p: dict, right_p: dict):
        with ThreadPoolExecutor(max_workers=2) as pool:
            def get_result(future):
                pass

            if self.left and left_p:
                func1 = getattr(self.left, func_name)
                future1 = pool.submit(func1, **left_p)
                future1.add_done_callback(get_result)
            if self.right and right_p:
                func2 = getattr(self.right, func_name)
                future2 = pool.submit(func2, **right_p)
                future2.add_done_callback(get_result)
            result1 = future1.result() if self.left and left_p else None
            result2 = future2.result() if self.right and right_p else None
            return result1, result2

    def run_in_thread_pool(self, func_name):
        with ThreadPoolExecutor(max_workers=2) as pool:
            def get_result(future):
                pass

            if self.left:
                func1 = getattr(self.left, func_name)
                future1 = pool.submit(func1)
                future1.add_done_callback(get_result)
            if self.right:
                func2 = getattr(self.right, func_name)
                future2 = pool.submit(func2)
                future2.add_done_callback(get_result)

            result1 = future1.result() if self.left else None
            result2 = future2.result() if self.right else None
            return result1, result2

    def get_adam_state(self):
        left = {
            'state': self.left.state,
            'mode': self.left.mode,
            'enable': self.left.motor_enable_states,
            'world_offset': self.left.world_offset,
            'warn_code': self.left.warn_code,
            'error_code': self.left.error_code,
            'tcp_offset': self.left.tcp_offset,
            'version': self.left.version,
            'position': self.left.position,
            'angles': self.left.angles,
            'sn': self.left.sn,
        } if self.left else None
        right = {
            'state': self.right.state,
            'mode': self.right.mode,
            'enable': self.right.motor_enable_states,
            'world_offset': self.right.world_offset,
            'warn_code': self.right.warn_code,
            'error_code': self.right.error_code,
            'tcp_offset': self.right.tcp_offset,
            'version': self.right.version,
            'position': self.right.position,
            'angles': self.right.angles,
            'sn': self.right.sn,
        } if self.right else None
        return left, right

    @analyze_error_code
    @check_adam_sdk_left_and_right_param(SetState)
    def set_state(self, left: dict, right: dict):
        """
        Set the Adam state

        :param left: model is SetState
        :param right: model is SetState
        :return: code, code
        """
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool_with_param(func_name, left, right)
        return result

    @print_result
    @check_adam_sdk_left_and_right_param(Reset)
    def reset(self, left: dict, right: dict):
        """
        Reset the Adam
        Warning: without limit detection

        :param left: model is Reset
        :param right: model is Reset
        """
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool_with_param(func_name, left, right)
        return result

    @analyze_error_code
    @check_adam_sdk_left_and_right_param(SetServoAngle)
    def set_servo_angle(self, left: dict, right: dict):
        """

        :param left: model is SetServoAngle
        :param right: model is SetServoAngle
        :return:
        """
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool_with_param(func_name, left, right)
        return result

    @analyze_error_code
    def clean_warn(self):
        """

        :return:
        """
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool(func_name)
        return result

    @analyze_error_code
    def clean_error(self):
        """

        :return:
        """
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool(func_name)
        return result

    def move_circle(self, left: dict, right: dict):
        """
        set adam robot position

        :param left: dict model is SetPosition
        :param right: dict model is SetPosition
        :return: code, code
        """
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool_with_param(func_name, left, right)
        return result

    @check_adam_sdk_left_and_right_param(RegisterReportLocationCallbackModel)
    def register_report_location_callback(self, left: dict, right: dict):
        """

        :param left:
        :param right:
        :return: :return: True/False, True/False
        """
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool_with_param(func_name, left, right)
        return result

    def release_report_location_callback(self):
        """

        :return:
        """

        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool(func_name)
        return result

    def emergency_stop(self):
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool(func_name)
        return result

    @analyze_error_code
    @check_adam_sdk_left_and_right_param(SetWorldOffset)
    def set_world_offset(self, left: dict, right: dict):
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool_with_param(func_name, left, right)
        return result

    @analyze_error_code
    @check_adam_sdk_left_and_right_param(SetTcpOffset)
    def set_tcp_offset(self, left: dict, right: dict):
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool_with_param(func_name, left, right)
        return result

    @analyze_error_code
    @check_adam_sdk_left_and_right_param(SetTcpLoad)
    def set_tcp_load(self, left: dict, right: dict):
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool_with_param(func_name, left, right)
        return result

    @analyze_error_code
    @check_adam_sdk_left_and_right_param(SetGripperEnable)
    def set_gripper_enable(self, left: dict, right: dict):
        """
        Set the gripper enable

        :param enable: enable or not
         Note： such as code = arm.set_gripper_enable(True)  #turn on the Gripper
        :return: code
            code: See the Gripper code documentation for details.
        """
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool_with_param(func_name, left, right)
        return result

    @analyze_error_code
    @check_adam_sdk_left_and_right_param(SetGripperMode)
    def set_gripper_mode(self, left: dict, right: dict):
        """
        Set the gripper mode mode: 0: location mode

        :return: code
            code: See the Gripper code documentation for details.
        """
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool_with_param(func_name, left, right)
        return result

    def get_gripper_position(self):
        """
        Get the gripper position

        :return: tuple((code, pos)), only when code is 0, the returned result is correct.
            code: See the Gripper code documentation for details.
        """
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool(func_name)
        return result

    @analyze_error_code
    @check_adam_sdk_left_and_right_param(SetGripperPosition)
    def set_gripper_position(self, left: dict, right: dict):
        """
        Set the gripper position

        :param left: pos
        :param right: pos
        :return: code
            code: See the Gripper code documentation for details.
        """
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool_with_param(func_name, left, right)
        return result

    @analyze_error_code
    @check_adam_sdk_left_and_right_param(SetGripperSpeed)
    def set_gripper_speed(self, left: dict, right: dict):
        """
        Set the gripper speed

        :param speed:
        :return: code
            code: See the Gripper code documentation for details.
        """
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool_with_param(func_name, left, right)
        return result

    def get_gripper_err_code(self):
        """
        Get the gripper error code

        :return: tuple((code, err_code)), only when code is 0, the returned result is correct.
            code: See the API code documentation for details.
            err_code: See the Gripper code documentation for details.
        """
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool(func_name)
        return result

    @analyze_error_code
    def clean_gripper_error(self):
        """
        Clean the gripper error

        :return: code
            code: See the Gripper code documentation for details.
        """
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool(func_name)
        return result

    @analyze_error_code
    def clean_conf(self):
        """
        Clean current config and restore system default settings
        Note:
            1. This interface will clear the current settings and restore to the original settings (system default settings)

        :return: code
            code: See the API code documentation for details.
        """
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool(func_name)
        return result

    @analyze_error_code
    def save_conf(self):
        """
        Save config
        Note:
            1. This interface can record the current settings and will not be lost after the restart.
            2. The clean_conf interface can restore system default settings

        :return: code
            code: See the API code documentation for details.
        """
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool(func_name)
        return result

    @analyze_error_code
    @check_adam_sdk_left_and_right_param(SetGravityDirection)
    def set_gravity_direction(self, left, right):
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool_with_param(func_name, left, right)
        return result

    @analyze_error_code
    @check_adam_sdk_left_and_right_param(SetMountDirection)
    def set_mount_direction(self, left, right):
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool_with_param(func_name, left, right)
        return result

    @analyze_error_code
    @check_adam_sdk_left_and_right_param(SetCollisionSensitivity)
    def set_collision_sensitivity(self, left, right):
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool_with_param(func_name, left, right)
        return result

    @analyze_error_code
    @check_adam_sdk_left_and_right_param(SetCollisionSensitivity)
    def set_teach_sensitivity(self, left, right):
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool_with_param(func_name, left, right)
        return result

    @analyze_error_code
    @check_adam_sdk_left_and_right_param(SetTcpJerk)
    def set_tcp_jerk(self, left, right):
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool_with_param(func_name, left, right)
        return result

    @analyze_error_code
    @check_adam_sdk_left_and_right_param(SetTcpMaxacc)
    def set_tcp_maxacc(self, left, right):
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool_with_param(func_name, left, right)
        return result

    @analyze_error_code
    @check_adam_sdk_left_and_right_param(SetJointMaxacc)
    def set_joint_maxacc(self, left, right):
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool_with_param(func_name, left, right)
        return result

    @analyze_error_code
    @check_adam_sdk_left_and_right_param(SetJointJerk)
    def set_joint_jerk(self, left, right):
        func_name = utils.get_current_func_name()
        result = self.run_in_thread_pool_with_param(func_name, left, right)
        return result
