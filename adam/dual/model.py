from typing import Callable

from pydantic import BaseModel, Field, conlist


class ParamDesc:
    x = 'cartesian position x, (unit= mm), default is self.last_used_position[0]'
    y = 'cartesian position y, (unit: mm), default is self.last_used_position[1]'
    z = 'cartesian position z, (unit: mm), default is self.last_used_position[2]'
    roll = 'rotate around the X axis, (unit: rad if is_radian is True else °), default is self.last_used_position[3]'
    pitch = 'rotate around the Y axis, (unit: rad if is_radian is True else °), default is self.last_used_position[4]'
    yaw = 'rotate around the Z axis, (unit: rad if is_radian is True else °), default is self.last_used_position[5]'
    tcp_speed = 'move speed (mm/s, rad/s), default is self.last_used_tcp_speed'
    tcp_mvacc = 'move acceleration (mm/s^2, rad/s^2), default is self.last_used_tcp_acc'
    is_radian = 'the roll/pitch/yaw in radians or not, default is self.default_is_radian'
    wait = 'whether to wait for the arm to complete, default is False'
    timeout = 'maximum waiting time(unit: second), default is None(no timeout), only valid if wait is True'
    servo_id = "1. 1-(Number of axes) indicates the corresponding joint, " \
               "the parameter angle should be a numeric value; " \
               "2. None(8) means all joints, default is None, " \
               "the parameter angle should be a list of values whose length is the number of joints"
    angle = "1. If servo_id is 1-(Number of axes), angle should be a numeric value" \
            "2. If servo_id is None or 8, angle should be a list of values whose length is the number of joints"
    relative = 'relative move or not'

    state = 'arm state, default is 0, sport state'
    mode = 'arm mode, default is 0, position control mode'
    tcp_jerk = 'jerk of Cartesian space (mm/s^3)'
    tcp_acc = 'acceleration of Cartesian space (mm/s^2)'

    teach_sensitivity = 'the sensitivity of drag and teach, sensitivity value, 1~5'
    collision_sensitivity = 'the sensitivity of collision, sensitivity value, 0~5'

    base_tilt_deg = 'mount direction, tilt degree'
    rotation_deg = 'mount direction, rotation degree'

    gravity_direction = 'direction of gravity, such as [x(mm), y(mm), z(mm)]'

    weight = 'load weight (unit: kg)'
    center_of_gravity = 'load center of gravity, such as [x(mm), y(mm), z(mm)]'

    offset = '[x, y, z, roll, pitch, yaw]'


class XYZ(BaseModel):
    """cartesian position"""
    x: float = Field(None, title=ParamDesc.x)
    y: float = Field(None, description=ParamDesc.y)
    z: float = Field(None, description=ParamDesc.z)


class RPY(BaseModel):
    roll: float = Field(None, title=ParamDesc.roll)
    pitch: float = Field(None, title=ParamDesc.pitch)
    yaw: float = Field(None, title=ParamDesc.yaw)


class SetPosition(RPY, XYZ):
    """Set the cartesian position, the API will modify self.last_used_position value"""
    speed: int = Field(None, title=ParamDesc.tcp_speed)
    mvacc: int = Field(None, title=ParamDesc.tcp_mvacc)
    is_radian: int = Field(None, title=ParamDesc.is_radian)
    wait: bool = Field(False, title=ParamDesc.wait)
    timeout: int = Field(None, title=ParamDesc.timeout)


class ArmMode(BaseModel):
    enable: bool = True
    mode: int = Field(0, title=ParamDesc.mode)
    state: int = Field(0, title=ParamDesc.state)


class MotionEnable(BaseModel):
    """
    enable:True/False
    servo_id: 1-(Number of axes), None(8)
    """
    enable: bool = True
    servo_id: int = None


class SetMode(BaseModel):
    """Set the xArm mode"""
    mode: int = Field(0, title=ParamDesc.state)


class SetState(BaseModel):
    """Set the xArm state,default is 0, sport state"""
    state: int = Field(0, title=ParamDesc.state)


class Reset(BaseModel):
    """Reset the xArm without limit detection"""
    speed: int = None
    mvacc: int = None
    is_radian: int = None
    wait: bool = False
    timeout: int = None


class SetServoAngle(BaseModel):
    """Set the servo angle, the API will modify self.last_used_angles value"""
    servo_id: int = None
    angle: conlist(float, min_items=6, max_items=6)
    speed: int = None
    mvacc: float = None
    # mvtime: float = None
    relative: bool = False
    is_radian: bool = None
    wait: bool = False
    timeout: int = None
    radius: float = None


class RegisterReportLocationCallbackModel(BaseModel):
    callback: Callable = None
    report_cartesian: bool = True
    report_joints: bool = True


class SetWorldOffset(BaseModel):
    offset: conlist(float, min_items=6, max_items=6)
    is_radian: bool = None


class SetTcpOffset(BaseModel):
    """Set the tool coordinate system offset at the end"""
    offset: conlist(float, min_items=6, max_items=6)
    is_radian: bool = None


class SetTcpLoad(BaseModel):
    """Set the end load of xArm"""
    weight: float
    center_of_gravity: conlist(float, min_items=3, max_items=3)


class SetGripperEnable(BaseModel):
    enable: bool = True


class SetGripperMode(BaseModel):
    mode: int = 0


class SetGripperPosition(BaseModel):
    pos: int
    wait: bool = False
    speed: int = None
    auto_enable: bool = False
    timeout: int = None


class SetGripperSpeed(BaseModel):
    speed: int


class SetGravityDirection(BaseModel):
    """Set the direction of gravity"""
    direction: conlist(float, min_items=3, max_items=3)


class SetMountDirection(BaseModel):
    """Set the mount direction"""
    base_tilt_deg: float
    rotation_deg: float
    is_radian: None


class SetCollisionSensitivity(BaseModel):
    """Set the sensitivity of collision"""
    value: int


class SetTeachSensitivity(BaseModel):
    """Set the sensitivity of drag and teach"""
    value: int


class SetTcpJerk(BaseModel):
    """Set the translational jerk of Cartesian space"""
    jerk: int


class SetTcpMaxacc(BaseModel):
    """Set the max translational acceleration of Cartesian space"""
    acc: int


class SetJointMaxacc(BaseModel):
    acc: int


class SetJointJerk(BaseModel):
    jerk: int
