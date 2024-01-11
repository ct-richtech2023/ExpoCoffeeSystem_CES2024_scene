from typing import Literal, Dict, List

from pydantic import BaseModel, Field
from pydantic.schema import IPv4Address

from common.define import SUPPORT_ARM_TYPE
from common import define
from common.schemas.common import Pose, XYZ


class AdamIpConfig(BaseModel):
    left: IPv4Address
    right: IPv4Address


class AdamDefaultSpeed(BaseModel):
    arm: int = Field(500, ge=50, le=2000)
    gripper: int = Field(1000, ge=500, le=20000)


class Angles(BaseModel):
    j1: float = Field(..., ge=-360, le=360)
    j2: float = Field(..., ge=-118, le=120)
    j3: float = Field(..., ge=-225, le=11)
    j4: float = Field(..., ge=-360, le=360)
    j5: float = Field(..., ge=-97, le=180)
    j6: float = Field(..., ge=-360, le=360)

    @classmethod
    def list_to_obj(cls, angle_list: list):
        angle_dict = dict(zip(define.ANGLE_PARAM, angle_list))
        return cls(**angle_dict)


class GripperPosition(BaseModel):
    open: int = Field(..., le=850)
    # close: int = Field(..., ge=0)


class GPIOConfig(BaseModel):
    which: SUPPORT_ARM_TYPE
    delay: List[float] = Field(max_items=8, min_items=8)


class MountDirection(BaseModel):
    base_tilt_deg: float = Field(..., ge=-180, le=180)
    rotation_deg: float = Field(..., ge=-180, le=180)


class _DifferentConfig(BaseModel):
    gripper: str
    gripper_enable: bool = True
    mount_direction: MountDirection
    world_offset: Pose


class DifferentConfig(BaseModel):
    left: _DifferentConfig
    right: _DifferentConfig


class SameConfig(BaseModel):
    teach_sensitivity: Literal[1, 2, 3, 4, 5]
    collision_sensitivity: Literal[0, 1, 2, 3, 4, 5]
    safe_level: Literal[4]
    tcp_jerk: float
    tcp_maxacc: float
    joint_jerk: float
    joint_maxacc: float = Field(..., le=1146)


class TcpLoad(BaseModel):
    weight: float
    center_of_gravity: XYZ


class GripperConfig(BaseModel):
    tcp_offset: Pose
    tcp_load: TcpLoad


class AdamConfig(BaseModel):
    save_conf: bool = False
    different_config: DifferentConfig
    same_config: SameConfig
    gripper_config: Dict[str, GripperConfig]


class SetGPIO(BaseModel):
    gpio: Literal[0, 1, 2, 3, 4, 5, 6, 7]
    value: Literal[0, 1]


class ArduinoConfig(BaseModel):
    no1: str
    no2: str


class AdamMachineConfig(BaseModel):
    sn: str
    ip: AdamIpConfig
    default_speed: AdamDefaultSpeed
    gripper: GripperPosition
    arduino: ArduinoConfig
    coffee_device: str
    tap_device: str


if __name__ == '__main__':
    pass
