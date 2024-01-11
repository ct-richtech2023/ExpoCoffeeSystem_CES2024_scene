from uuid import UUID
from typing import Literal, Optional, List

from pydantic import BaseModel, validator

from common import define


class WineRecord(BaseModel):
    task_uuid: UUID
    formula: define.SUPPORT_FORMULA
    failed_msg: Optional[str] = ''
    status: Literal[tuple([i for i in dir(define.TaskStatus) if '__' not in i])]  # noqa

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True


class CupConfig(BaseModel):
    gripper: int
    high: float
    clamp: int
    capacity: float


class _FormulaConfig(BaseModel):
    name: define.SUPPORT_FORMULA
    composition: List[str]
    ice_cube: Literal[0, 1]
    ice_cube_cup: Literal[0, 1]
    cup: define.SUPPORT_CUP_NAME_TYPE

    @validator("composition")
    def check_composition(cls, composition: list):
        support_wine_ingredients = define.Material.red_wine + define.Material.ingredients + define.Material.base_wine \
                                   + define.Material.gas_water + define.Material.ingredient_wine
        for value in composition:
            assert ',' in value, "composition='{}' must have ','".format(value)
            values = [i.strip() for i in value.split(',')]
            assert len(values) == 2, "composition='{}' must have 2 elements".format(value)
            assert values[0] in support_wine_ingredients, \
                "composition='{}' first element must in {}".format(value, support_wine_ingredients)
            try:
                float(values[1])
            except:
                "composition='{}' second element must be float".format(value)
        return composition


class MaterialConfig(BaseModel):
    milktea: List[_FormulaConfig]


class MaterialCurrentRecord(BaseModel):
    name: define.SUPPORT_ALL_WINE_INGREDIENTS
    capacity: int
    count: int
    left: int

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True
