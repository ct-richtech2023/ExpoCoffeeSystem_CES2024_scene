from uuid import UUID
from typing import Literal, Optional, List, Dict

from pydantic import BaseModel, validator

from common import define

class MilkTeaRecord(BaseModel):
    task_uuid: UUID
    formula: str
    cup: str
    sweetness: int
    ice: str
    milk: str
    boba: int
    milk_cap: int
    failed_msg: Optional[str] = ''
    status: Literal[tuple([i for i in dir(define.TaskStatus) if '__' not in i])]  # noqa

    # @validator("formula")
    # def check_formula(cls, formula: str):
    #     name, cup_name, sugar_type, milk_type = formula.split('-')
    #     assert name in define.SUPPORT_FORMULA, "formula='{}' name must in {}".format(formula, define.SUPPORT_FORMULA)
    #     assert cup_name in define.SUPPORT_CUP_NAME_TYPE, "formula='{}' cup_name must in {}".format(formula, define.SUPPORT_CUP_NAME_TYPE)
    #     assert sugar_type in define.SUPPORT_SUGAR_TYPE, "formula='{}' sugar_type must in {}".format(formula, define.SUPPORT_SUGAR_TYPE)
    #     assert milk_type in define.SUPPORT_MILK_TYPE, "formula='{}' milk_type must in {}".format(formula, define.SUPPORT_MILK_TYPE)
    #     return formula

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True


class _ComposotionConfig(BaseModel):
    cup: define.SUPPORT_CUP_NAME_TYPE
    composition: List[str]

    @validator("composition")
    def check_composition(cls, composition: list):
        support_milktea_ingredients = define.Material.base_milktea + define.Material.ingredients + define.Material.treacle
        for value in composition:
            assert ',' in value, "composition='{}' must have ','".format(value)
            values = [i.strip() for i in value.split(',')]
            assert len(values) == 2, "composition='{}' must have 2 elements".format(value)
            assert values[0] in support_milktea_ingredients, \
                "composition='{}' first element must in {}".format(value, support_milktea_ingredients)
            try:
                float(values[1])
            except:
                "composition='{}' second element must be float".format(value)
        return composition


class _FormulaConfig(BaseModel):
    name: define.SUPPORT_FORMULA
    size: List[_ComposotionConfig]
    ice_cube: Literal[0, 1]  # 制作是否要冰块
    ice_cube_cup: Literal[0, 1]  # 是否先将冰块倒入出品杯中


class MaterialConfig(BaseModel):
    milktea: List[_FormulaConfig]


class MaterialCurrentRecord(BaseModel):
    name: define.SUPPORT_ALL_MILKTEA_INGREDIENTS
    capacity: int
    count: int
    left: int

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True


class NewMaterialCurrent(BaseModel):
    name: str
    capacity: int
    alarm: int
    count: int
    left: float
    unit: int
    type: Literal[define.SUPPORT_MATERIAL_TYPE]
    machine: Literal[define.SUPPORT_MACHINE_TYPE]
    extra: Optional[str]
    in_use: int = 1

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True


class UpdateMaterialCurrent(BaseModel):
    capacity: Optional[int]
    alarm: Optional[int]
    unit: Optional[int]
    type: Optional[define.SUPPORT_MATERIAL_TYPE]
    machine: Optional[define.SUPPORT_MACHINE_TYPE]
    extra: Optional[str]

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True


class NewFormula(BaseModel):
    name: str
    cup: str
    with_ice: Literal[0, 1] = 0
    type: define.SUPPORT_FORMULA_TYPE
    in_use: Literal[0, 1] = 1
    composition: Dict[str, float]

    # @validator("composition")
    # def check_composition(cls, composition: dict):
    #     support_material_name = define.Constant.support_material_name
    #     for material in composition.keys():
    #         assert material in support_material_name, "key='{}'  must in {}".format(material, support_material_name)
    #     return composition

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True


class NewMachineConfig(BaseModel):
    name: str
    machine: Literal[define.SUPPORT_MACHINE_TYPE]
    num: int
    gpio: str
    speed: Optional[int]
    delay_time: Optional[int]
    type: Optional[str]  # 1: material, figure by speed, 2: action, use_delay_time

    @validator("gpio")
    def check_composition(cls, gpio: str):
        support_which = ['left', 'right']
        assert ',' in gpio, "gpio='{}' must have ','".format(gpio)
        values = [i.strip() for i in gpio.split(',')]
        assert len(values) == 2, "gpio='{}' must have 2 elements".format(gpio)
        assert values[0] in support_which, "composition='{}' first element must in {}".format(gpio, support_which)
        assert values[1].isdigit(), "gpio='{}' second element must be digit".format(gpio)
        return gpio

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True


class UpdateGpioConfig(BaseModel):
    arm: Optional[Literal['left', 'right']]
    num: Optional[int]
    speed: Optional[int]
    delay_time: Optional[int]
    type: Optional[str]  # 1: material, figure by speed, 2: action, use_delay_time

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True