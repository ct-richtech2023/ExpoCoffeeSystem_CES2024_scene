import datetime

from sqlalchemy import Column, Integer, String, DateTime, Boolean, func, Float, UniqueConstraint, SMALLINT
from sqlalchemy.dialects.postgresql import UUID

from common.db.database import Base


class Coffee(Base):
    __tablename__ = "coffee"  # noqa
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    task_uuid = Column(UUID(as_uuid=True), primary_key=True, unique=True, comment='task uuid')
    receipt_number = Column(String, default='', comment='receipt number')
    formula = Column(String, comment='formula name')
    cup = Column(String, comment='cup name')
    sweetness = Column(Integer, comment='sweetness percent like 80, 100')
    ice = Column(String, comment='no_ice/light/more')
    milk = Column(String, comment='fresh_dairy or plant_milk')
    beans = Column(String, comment='Light roast coffee beans or High roast coffee beans')
    status = Column(String, default='waiting', comment='make status')
    refund = Column(SMALLINT, default=0, comment='0:no refund;1:refunded')
    discount = Column(Float, default=0, comment='discount  0:no discount;1:resell; 2:normal')
    unit_money = Column(Float, comment='unit money')
    failed_msg = Column(String, default='', comment='failed msg')
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data


class Detect(Base):
    __tablename__ = "detect"  # noqa
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    name = Column(String, unique=True, comment='name')
    status = Column(String, default='0', comment='0:no exist 1:exist')
    detail = Column(String, comment='detail')
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data



class Espresso(Base):
    __tablename__ = "espresso"  # noqa
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    formula = Column(String, unique=True, comment='formula name')
    drink_type = Column(Integer, comment='drink type')
    coffee = Column(Integer, comment='how much coffee')
    coffee_temp = Column(Integer, comment='level of coffee temperature, 0/1/2')
    coffee_concentration = Column(Integer, comment='concentration level of coffee, 0/1/2')
    water = Column(Integer, comment='how much hot water')
    water_temp = Column(Integer, comment='level of how water temperature, 0/1/2')
    milk_time = Column(Integer, comment='time of making milk')
    foam_time = Column(Integer, comment='time of making foam')
    precook = Column(Integer, comment='precook or not,true=1/false=0')
    enhance = Column(Integer, comment='enhance or not,true=1/false=0')
    together = Column(Integer, comment='coffee and milk out together or not, true=1/false=0')
    order = Column(Integer, comment='0：milk first then coffee; 1: coffee first then milk')
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data

    def to_coffee_dict(self):
        """
            drinkType: 饮品类型,1-8
            volume: 咖啡量: 15-240 / 0
            coffeeTemperature: 咖啡温度 0/1/2 低/中/高
            concentration: 咖啡浓度 0/1/2 清淡/适中/浓郁
            hotWater: 热水量
            waterTemperature: 热水温度 0/1/2 低/中/高
            hotMilk: 牛奶时间 5-120 / 0
            foamTime: 奶沫时间  5-120 / 0
            precook: 预煮 1/0 是/否
            moreEspresso: 咖啡增强 1/0 是/否
            coffeeMilkTogether: 咖啡牛奶同时出 1/0 是/否
            adjustOrder: 出品顺序 1/0 0：先奶后咖啡/1：先咖啡后奶
        """
        coffee_dict = dict(
            drinkType=self.drink_type, volume=self.coffee, coffeeTemperature=self.coffee_temp,
            concentration=self.coffee_concentration, hotWater=self.water, waterTemperature=self.water_temp,
            hotMilk=self.milk_time, foamTime=self.foam_time, precook=self.precook, moreEspresso=self.enhance,
            coffeeMilkTogether=self.together, adjustOrder=self.order
        )
        return coffee_dict


class MaterialCurrent(Base):
    __tablename__ = "material_current"  # noqa
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    name = Column(String, unique=True, comment='material name')
    img = Column(String, comment='formula img path')
    display = Column(String, comment='material name displayed on pad')
    display_type = Column(String, comment='bucket/bottle/cup/tap/fruit')
    sort = Column(Integer, comment='sort')
    capacity = Column(Integer, comment='capacity')
    alarm = Column(Integer, comment='when to alarm')
    left = Column(Float, comment='left')
    count = Column(Integer, comment='use times')
    unit = Column(String, comment='unit of measurement')
    batch = Column(Integer, comment='minimum use in one time')
    type = Column(String, comment='type of material, choose in material_type table')
    in_use = Column(Integer, comment='formula in use? 1:in use; 0:not in use')
    machine = Column(String, comment='formula in use? 1:gpio; 2:scoop; 3: ice_maker')
    extra = Column(String, comment='extra param for future extend')
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data


class AddMaterialHistory(Base):
    __tablename__ = "material_history"  # noqa
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    name = Column(String, comment='material name')
    before_add = Column(Float, comment='how much left before add')
    count = Column(Integer, comment='use times')
    add = Column(Float, comment='how much added')
    add_time = Column(DateTime, server_default=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data


class AddCleaningHistory(Base):
    __tablename__ = "cleaning_history"  # noqa
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    name = Column(String, comment='tap name')
    cleaning_method = Column(Integer, comment='Cleaning method Automatic or Manual? 1:Automatic; 2:Manual')
    timelength = Column(Integer, comment='time length')
    flag = Column(Integer, default=0, comment='flag')
    cleaning_time = Column(DateTime, server_default=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data


class Formula(Base):
    __tablename__ = "formula"  # noqa
    __table_args__ = (UniqueConstraint('name', 'cup'),)
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    name = Column(String, comment='formula name')
    img = Column(String, comment='formula img path')
    cup = Column(String, comment='cup name')
    with_ice = Column(String, comment='ice in cup: 0: not in cup, 1: in cup')
    with_foam = Column(String, comment='with foam: 0: no need, 1: coffee_machine, 2: foam_machine')
    with_milk = Column(String, comment='milk in cup: 0: not in cup, 1: in cup')
    choose_beans = Column(String, comment='choose beans: 0: not choose, 1: choose')
    type = Column(String, comment='type of drink; 1:milktea; 2:milk, 3:coffee')
    in_use = Column(Integer, comment='formula in use? 1:in use; 0:not in use')
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data


class Composition(Base):
    __tablename__ = "composition"  # noqa
    __table_args__ = (UniqueConstraint('formula', 'cup', 'material'),)
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    formula = Column(String, comment='formula name')
    cup = Column(String, comment='cup_name')
    material = Column(String, comment='material name')
    count = Column(Float, comment='the quantity required')
    extra = Column(String, default='', comment='prepare for extra param')
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data


class MachineConfig(Base):
    __tablename__ = "machine_config"  # noqa
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    name = Column(String, unique=True, comment='material name or action name')
    machine = Column(String, comment='gpio/scoop/ice_maker')
    num = Column(Integer, comment='which num')
    gpio = Column(String, comment='arm,num')
    arduino_write = Column(String, comment='which:char, send char to which arduino')
    arduino_read = Column(String, comment='which:index, read index from which arduino')
    speed = Column(Integer, comment='flow rate')
    delay_time = Column(Float, comment='seconds')
    type = Column(String, comment='1: speed, figure by speed, 2: time, use_delay_time')
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data


class SpeechText(Base):
    __tablename__ = "speech_text"  # noqa
    __table_args__ = (UniqueConstraint('code', 'text'),)
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    code = Column(String, comment='type of text such as get_order/making/take_wine')
    text = Column(String, comment='content')
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        data = {'id': self.id, 'code': self.code, 'text': self.text}
        return data


class IdleInteraction(Base):
    __tablename__ = "idle_interaction"  # noqa
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    type = Column(String, comment='type of content; 1:riddle 2:joke 3:riddle_transition 4:joke_transition')
    content = Column(String, comment='content')
    answer = Column(String, comment='content')
    sentiment = Column(String, comment='sentiment: 1:positive 2:negative 3:mild')
    action = Column(String, comment='content')
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data

class MachineStates(Base):
    __tablename__ = "machine_states"  # noqa
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    return_id = Column(String, unique=True, comment='coffee machine return id')
    category = Column(String, comment='coffee machine category')
    chinese_content = Column(String, comment='coffee machine chinese_content')
    content = Column(String, comment='coffee machine content')
    remark = Column(String, comment='coffee machine remark')

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data


class Report(Base):
    __tablename__ = "report"  # noqa
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    task_uuid = Column(UUID(as_uuid=True), comment='task uuid')
    report = Column(Integer, comment='0: need report; 1: reported')


class FormulaDuration(Base):
    __tablename__ = "formula_duration"  # noqa
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    formula = Column(String, unique=True, comment='formula name')
    duration = Column(Float, comment='make coffee duration')
    left_status = Column(Integer, comment='0:free 1:make')
    right_status = Column(Integer, comment='0:free 1:make')
    type = Column(String, default='coffee', comment='type of drink; 1:milktea; 2:milk, 3:coffee')
    introduction = Column(String, comment='coffee introduction')
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data
