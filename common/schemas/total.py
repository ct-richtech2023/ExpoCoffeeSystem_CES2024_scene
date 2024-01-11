from typing import List, Optional

from pydantic import BaseModel, Field, validator
from pydantic.schema import IPv4Address

from common.schemas.adam import AdamMachineConfig, Angles
from common.schemas.common import DefaultEulerPose, LeftArmDefaultEulerPose
from common import define

"""
    主要用来读取settings/machine.yml中的配置，将配置文件改为可以用“.”来索引的对象，方便管理和调用
"""


class LimiterConfig(BaseModel):
    high: float


class PoseWithDeviceAndDelay(BaseModel):
    device: Optional[str] = ''
    delay: Optional[float] = 0
    gripper: Optional[float] = 0
    speed: Optional[float] = 1.0
    clamp: Optional[int] = 0
    capacity: Optional[float] = 0
    collision_sensitivity: Optional[int] = 3
    pose: DefaultEulerPose


class BucketConfig(BaseModel):
    name: str
    pose: DefaultEulerPose

class GetCupConfig(BaseModel):
    name: define.SUPPORT_CUP_NAME_TYPE
    gripper: int = Field(..., le=850, ge=0)
    high: int = Field(..., le=300, ge=0)
    collision_sensitivity: int = Field(0, le=5, ge=0)
    clamp: int = Field(..., le=850, ge=0)
    capacity: int = Field(..., gt=0)
    percent: float
    pose: DefaultEulerPose


class ShakerPoseConfig(BaseModel):
    take: DefaultEulerPose
    clean: DefaultEulerPose


class PositionConfig(BaseModel):
    left: int
    right: int
    top: int
    bottom: int


class ShakerConfig(BaseModel):
    gripper: int = Field(..., le=850, ge=0)
    high: int = Field(..., le=300, ge=0)
    collision_sensitivity: int = Field(0, le=5, ge=0)
    clamp: int = Field(..., le=850, ge=0)
    capacity: int = Field(..., gt=0)
    pose: ShakerPoseConfig
    position: PositionConfig


class _ScoopConfig(BaseModel):
    num: int
    pose: DefaultEulerPose


# class OneMechanicalSwitchConfig(BaseModel):
#     name: define.SUPPORT_ALL_WINE_INGREDIENTS
#     speed: float = Field(1, ge=0, le=100)
#     capacity: int
#     one_bottom: int


class _GpioBaseMilkTeaConfig(BaseModel):
    start: DefaultEulerPose
    spacing: int = Field(50, ge=-300, le=300)
    difference: int


class _GpioTreacleConfig(BaseModel):
    pose: DefaultEulerPose


# class _GpioNoGasConfig(BaseModel):
#     start: DefaultEulerPose
#     spacing: int = Field(50, ge=-300, le=0)
#     outlet: OutletConfig

# class _GpioGasConfig(BaseModel):
#     start: DefaultEulerPose
#     difference: int
#     spacing: int = Field(50, ge=-300, le=0
#
#
#
#     )
#     outlet: List[
#     ]


class GpioConfig(BaseModel):
    tap: _GpioTreacleConfig


class DanceConfig(BaseModel):
    count: int = Field(3, ge=1, le=10)


class SoundConfig(BaseModel):
    AUDIODEV: str = '0,0'


class IceTypeConfig(BaseModel):
    no_ice: float
    light: float
    more: float


class SugarTypeConfig(BaseModel):
    extra: float


class TaskOptionConfig(BaseModel):
    ice_type: IceTypeConfig
    sweetness_type: SugarTypeConfig


class CenterConfig(BaseModel):
    printer: str
    scanner: str
    time_offset: int


class DetectConfig(BaseModel):
    name: Optional[str] = ""
    table: Optional[str] = ""
    pose: DefaultEulerPose
    position: PositionConfig


class MachineConfig(BaseModel):
    adam: AdamMachineConfig
    put: List[BucketConfig]
    put_position: List[DetectConfig]
    get: List[GetCupConfig]
    gpio: GpioConfig
    foam_machine: DetectConfig
    americano: PoseWithDeviceAndDelay
    coffee_machine: PoseWithDeviceAndDelay
    bucket: List[BucketConfig]
    dance: DanceConfig
    sound: SoundConfig
    shaker: ShakerConfig
    ice_maker: List[PoseWithDeviceAndDelay]
    cup_env: define.SUPPORT_PRODUCT_ENV_TYPE
    task_option: TaskOptionConfig
    espresso: ShakerConfig
    jetson_ip: IPv4Address
