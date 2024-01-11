from typing import Literal

from pydantic import BaseModel

from common.define import SUPPORT_ERROR_TYPE, SUPPORT_BASE_ERROR_STATUS, SUPPORT_ARM_TYPE


class Error(BaseModel):
    name: SUPPORT_ERROR_TYPE  # noqa
    msg: str

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True


class BaseError(BaseModel):
    arm: SUPPORT_ARM_TYPE
    code: str
    desc: str
    by: str
    status: SUPPORT_BASE_ERROR_STATUS

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True

