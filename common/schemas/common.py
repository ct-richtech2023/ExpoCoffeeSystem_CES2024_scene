from typing import Literal

from pydantic import BaseModel, validator, Field, root_validator

from common import define
from common.db.crud.db_const import DB_Constant

class AdamArm:
    initial_y = 550
    x_y_radius = 250
    min_z = 50
    line6 = 100

    @classmethod
    def check_x_y_security(cls, x, y):
        err_msg = "x={} y={} must outside adam radius={} security perimeter".format(x, y, cls.x_y_radius)
        assert x ** 2 + y ** 2 > cls.x_y_radius ** 2, err_msg


class XY(BaseModel):
    # adam work env x(-2000,2000) y(-2000,2000)
    x: float = Field(..., ge=-2000, le=2000)
    y: float = Field(..., ge=-2000, le=2000)


class XYZ(XY):
    # adam work env z(0,2000)
    z: float = Field(..., ge=0, le=2000)


class Pose(XYZ):
    roll: float = Field(..., ge=-180, le=180)
    pitch: float = Field(..., ge=-180, le=180)
    yaw: float = Field(..., ge=-180, le=180)

    @validator("roll", 'pitch', 'yaw', pre=True)
    def check_x_y_security(cls, v):
        return round(v, 2)

    @classmethod
    def list_to_obj(cls, pose_list: list):
        pose_dict = dict(zip(define.POSITION_PARAM, pose_list))
        return cls(**pose_dict)


class DefaultEulerPose(Pose):
    roll: float = 0
    pitch: float = 90
    yaw: Literal[0] = 0

    @root_validator
    def set_default_euler(cls, values: dict):
        default_config = {'roll': values['roll'], 'pitch': 90, 'yaw': 0}
        values.update(default_config)
        x, y = values.get('x'), values.get('y')
        AdamArm.check_x_y_security(x, y)
        return values


class Account(BaseModel):
    username: str
    password: str


class RightArmDefaultEulerPose(DefaultEulerPose):

    @validator("y")
    def set_positive_y(cls, y: int):
        assert y < 0, "right arm position must y<0"
        return y


class LeftArmDefaultEulerPose(DefaultEulerPose):

    @validator("y")
    def set_positive_y(cls, y: int):
        assert y > 0, "left arm position must y>0"
        return y


class Drink(BaseModel):
    name: str
    cup: define.SUPPORT_CUP_NAME_TYPE
    sweetness: int = 100
    ice: define.SUPPORT_ICE_TYPE
    milk: define.SUPPORT_MILK_TYPE = define.MilkType.milk
    boba: int = 0
    milk_cap: int = 0

    _formula = None
    _instance = None

    # @validator("name")
    # def set_positive_y(cls, name: str):
    #     support_formula_name = DB_Constant.support_formula_name()
    #     assert name in support_formula_name, "name='{}' must in {}".format(name, support_formula_name)
    #     return name

    @classmethod
    def create(cls, formula):
        if formula == cls._formula:
            return cls._instance
        else:
            name, cup_name, sugar_type, milk_type = formula.split('-')
            option_dict = {
                'name': name,
                'cup_name': cup_name,
                'sugar_type': sugar_type,
                'milk_type': milk_type,
            }
            cls._formula = formula
            obj = cls(**option_dict)
            cls._instance = obj
            return obj
