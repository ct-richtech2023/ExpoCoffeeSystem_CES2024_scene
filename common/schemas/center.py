from typing import List, Literal, Dict, Optional

from pydantic import BaseModel, Field, validator, root_validator
from pydantic.schema import UUID

from common import define
from common.schemas.common import Drink
from .adam import Pose
from .common import Account
from .wake import PicovoiceConfig


# base model

class Customer(BaseModel):
    name: str = Field(default='')
    mail: str = Field(default='')
    phone: str = Field(default='')
    debit_card: str = Field(default='')
    credit_card: str = Field(default='')


# model

class Order(Customer):
    order_number: str
    payment_id: str
    table: Optional[str]
    order_status: define.SUPPORT_ORDER_STATUS = define.OrderStatus.unpaid
    drinks: List[Drink] = Field(..., min_items=1, max_items=2)

    # @validator('order_number')
    # def validator_order_number(cls, v):
    #     assert len(v) == 8 + 1 + 4, 'len error'
    #     assert v[8] == '_', '_ not in'
    #     datetime.strptime('{}-{}-{}'.format(v[:4], v[4:6], v[6:8]), "%Y-%m-%d")
    #     assert str.isdigit(v[9:]), 'error: The last four bits are not integers'
    #     return v


class PadDrink(BaseModel):
    reference_id: Optional[str] = ''
    receipt_number: str
    name: str
    milk: Optional[str] = ''
    choose_beans: Optional[str] = ''
    discount: define.SUPPORT_DISCOUNT_STATUS = define.DiscountStatus.no
    refund: define.SUPPORT_REFUND_STATUS = define.RefundStatus.no
    option: dict


class PadOrder(BaseModel):
    order_number: str
    reference_id: Optional[str] = ''
    status: define.SUPPORT_ORDER_STATUS = define.OrderStatus.paid
    refund: define.SUPPORT_REFUND_STATUS = define.RefundStatus.no
    drinks: List[PadDrink] = Field(..., min_items=1)


class CancelOrder(BaseModel):
    order_number: str


class CancelTask(BaseModel):
    # task_uuid: UUID
    task_uuid: str


class Task(BaseModel):
    order_number: str
    task_uuid: UUID
    formula: str

    class Config:
        orm_mode = True


class OrderStatus(BaseModel):
    order_number: str
    speak_name: str
    processing: Dict[UUID, str]
    complete: Dict[UUID, str]


class TaskStatus(BaseModel):
    task_uuid: UUID
    order_number: str
    receipt_number: str
    formula: str
    cup: str
    sweetness: int
    milk: Optional[str]
    ice: str
    status: str

    class Config:
        orm_mode = True


class InnerDrink(BaseModel):
    reference_id: Optional[str] = ''
    receipt_number: Optional[str] = ''
    formula: str
    discount: define.SUPPORT_DISCOUNT_STATUS
    refund: define.SUPPORT_REFUND_STATUS
    option: dict


class InnerOrder(BaseModel):
    order_number: str
    reference_id: Optional[str] = ''
    status: define.SUPPORT_ORDER_STATUS = define.OrderStatus.paid
    refund: define.SUPPORT_REFUND_STATUS
    drinks: List[InnerDrink] = Field(..., min_items=1)


class InnerUpdateTask(BaseModel):
    task_uuid: str
    refund: Optional[define.SUPPORT_REFUND_STATUS]
    discount: Optional[define.SUPPORT_DISCOUNT_STATUS]
    status: Optional[define.SUPPORT_TASK_STATUS]


class InnerUpdateOrder(BaseModel):
    order_number: str
    refund: define.SUPPORT_REFUND_STATUS
    drinks: List[InnerUpdateTask] = Field(..., min_items=0)


class PointConfig(BaseModel):
    number: int = Field(..., lt=10, ge=0)
    name: str


class PutConfig(Pose):
    y: int = 0
    z: int = Field(..., ge=100)
    roll: int
    pitch: int = 90
    yaw: int = 0

    @validator("roll")
    def check_x_y_security(cls, v):
        v = abs(v)
        return v


class DrinkPosition(Pose):
    roll: int = 0
    pitch: int = 0
    yaw: int = 0

    @root_validator
    def check_x_y_security(cls, values):
        values['yaw'] = 0
        values['pitch'] = 90
        values['roll'] = -90 if values['y'] > 0 else 90
        return values


class DrinkConfig(BaseModel):
    name: Literal[tuple(define.support_take_drinks)]
    pose: DrinkPosition


class RobotConfig(BaseModel):
    enable: bool = False
    account: Account
    uuid: str
    here: str
    timeout: int
    point: List[PointConfig]


class WakeDemoConfig(BaseModel):
    drink: List[DrinkConfig]
    put: PutConfig
    robot: RobotConfig
    picovoice: PicovoiceConfig


class UserBase(BaseModel):
    sn: str = None

    class Config:
        orm_mode = True


class RegisterRequest(UserBase):
    password: str


class RegisterResponse(UserBase):
    id: str
    msg: str


class LoginRequest(BaseModel):
    name: str = None
    password: str = None


class LocalLoginRequest(BaseModel):
    sn: str = None
    password: str = None


class LoginResponse(UserBase):
    token: str = None
    square_token: str
    location: str
