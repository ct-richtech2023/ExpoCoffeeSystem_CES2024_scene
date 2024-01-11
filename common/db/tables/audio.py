import datetime

from sqlalchemy import Column, Integer, String, DateTime, func

from common.db.database import Base


class Speak(Base):
    __tablename__ = "speak"  # noqa
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    text = Column(String, comment='content or file path of mp3')
    level = Column(Integer, comment='bigger numbers come first')
    status = Column(Integer, comment='0: waiting; 1: said')
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data
