import datetime

from sqlalchemy import Column, Integer, String, DateTime, Boolean, func

from common.db.database import Base


class Error(Base):
    __tablename__ = "error"  # noqa
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    name = Column(String, comment='drink name')
    msg = Column(String, default='', comment='failed msg')
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data


class BaseError(Base):
    __tablename__ = "base_error"  # noqa
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    arm = Column(String, comment='left or right')
    code = Column(String, comment='exception code')
    desc = Column(String, comment='desc to exception code')
    by = Column(String, comment='exception called by which function')
    status = Column(String, comment='exception solved or not')
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data
