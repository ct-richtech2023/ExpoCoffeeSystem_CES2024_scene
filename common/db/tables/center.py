import datetime

from sqlalchemy import Column, Integer, String, DateTime, func, SMALLINT, JSON, Float
from sqlalchemy.dialects.postgresql import UUID

from common.db.database import Base


class Order(Base):
    __tablename__ = "order"  # noqa
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    order_number = Column(String, primary_key=True, unique=True, comment='order number')
    payment_id = Column(String, unique=True, comment='payment_id from square')
    table = Column(String, default='', comment='table number')
    reference_id = Column(String, default='', comment='reference_id from online order')
    status = Column(String, default='unpaid', comment='order status')
    name = Column(String, default='', comment='customer name')
    phone = Column(String, default='', comment='customer phone')
    mail = Column(String, default='', comment='customer mail')
    is_vip = Column(Integer, default=0, comment='is vip; 0:normal 1:vip')
    refund = Column(SMALLINT, default=0, comment='0:no refund;1:part refund; 2:all refund')
    debit_card = Column(String, default='', comment='customer debit card number')
    credit_card = Column(String, default='', comment='customer credit card number')
    currency = Column(String, default='USD', comment='currency')
    total_discount_money = Column(Float, comment='total_discount_money')
    total_tax_money = Column(Float, comment='total_tax_money')
    total_tip_money = Column(Float, comment='total_tip_money')
    total_money = Column(Float, comment='total_money')
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data

    @classmethod
    def implement(cls, value: dict):
        data = {c.name: getattr(cls, c.name, None) for c in cls.__table__.columns}
        filter_value = {key: value for key, value in value.items() if key in data}
        return cls(**filter_value)


class Task(Base):
    __tablename__ = "task"  # noqa
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    order_number = Column(String, comment='order number')
    receipt_number = Column(String, comment='order number')
    reference_id = Column(String, default='', comment='reference_id from online order')
    task_uuid = Column(UUID(as_uuid=True), primary_key=True, unique=True, comment='calc unique task uuid')
    formula = Column(String, comment='formula')
    cup = Column(String, comment='cup name')
    sweetness = Column(Integer, comment='sweetness percent like 80, 100')
    ice = Column(String, comment='no_ice/light/more')
    milk = Column(String, comment='fresh_dairy or plant_milk')
    beans = Column(String, comment='Light roast coffee beans or High roast coffee beans')
    status = Column(String, default='unpaid', comment='make status')
    refund = Column(SMALLINT, default=0, comment='0:no refund;1:refunded')
    discount = Column(Float, default=0, comment='0:no discount;1:resell; 2:normal')
    unit_money = Column(Float, comment='unit money')
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data

class User(Base):
    __tablename__ = "user"  # noqa
    id = Column(String, index=True, unique=True, primary_key=True)
    sn = Column(String, unique=True, comment='sn of adam')
    password = Column(String, comment='hashed password')
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data

    @classmethod
    def implement(cls, value: dict):
        data = {c.name: getattr(cls, c.name, None) for c in cls.__table__.columns}
        filter_value = {key: value for key, value in value.items() if key in data}
        return cls(**filter_value)


class ConstantSetting(Base):
    __tablename__ = "constant_setting"  # noqa
    name = Column(String, unique=True, comment='constant name', primary_key=True)
    param = Column(JSON, comment='json dict')
    type = Column(String, comment='constant name')
    extra = Column(JSON, comment='json dict')
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data

    @classmethod
    def implement(cls, value: dict):
        data = {c.name: getattr(cls, c.name, None) for c in cls.__table__.columns}
        filter_value = {key: value for key, value in value.items() if key in data}
        return cls(**filter_value)