from loguru import logger
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy_utils import database_exists, create_database
from sqlalchemy.orm import sessionmaker

from common import conf

DB_NAME = 'coffee'
DB_PASSWORD = 'richtech'
DB_HOST = 'db_ces' if conf.check_is_production() else '127.0.0.1'

#DB_HOST = '127.0.0.1'
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:{}@{}:5432/{}".format(DB_PASSWORD, DB_HOST, DB_NAME)
engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_size=80,  pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

if database_exists(engine.url):
    logger.info("db={} is already exist, no need create".format(DB_NAME))
else:
    create_database(engine.url)
    logger.info("create db={}, now exist flag={}".format(DB_NAME, database_exists(engine.url)))


class MySuperContextManager:
    def __init__(self):
        self.db = SessionLocal()

    def __enter__(self):
        return self.db

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            # logger.warning('try commit db={}'.format(self.db))
            self.db.commit()
        except Exception as e:
            logger.debug('try error, rollback, db={}'.format(self.db))
            self.db.rollback()
        # logger.debug('close db={}'.format(self.db))
        self.db.close()


def get_db():
    with MySuperContextManager() as db:
        yield db
