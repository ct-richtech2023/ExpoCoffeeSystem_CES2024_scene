from loguru import logger

from sqlalchemy.orm import Session
from common.schemas import exception as exception_schema
from common.db.tables import exception as exception_table

error_table = exception_table.Error
error_table_name = error_table.__tablename__


def add_new_error(db: Session, error: exception_schema.Error):
    filter_dict = {'name': error.name}
    if error_record := db.query(error_table).filter_by(**filter_dict).first():
        origin_name = error_record.msg
        error_record.msg = error.msg
        db.add(error_record)
        db.commit()
        logger.info("update table={} name={} '{}' -> '{}'".format(error_table_name, error.name, origin_name, error.msg))
    else:
        db.add(error_table(**error.dict()))
        db.commit()
        logger.info("add table={} name={} msg='{}'".format(error_table_name, error.name, error.msg))


def clear_error(db: Session, name):
    filter_dict = {'name': name}
    if records := db.query(error_table).filter_by(**filter_dict).all():
        for record in records:
            db.delete(record)
            logger.info("clear table={} name={} err='{}'".format(error_table_name, name, record.msg))
        db.commit()


def get_all_error(db: Session) -> dict:
    records = db.query(error_table).order_by(error_table.id.asc()).all()
    records = [exception_schema.Error.from_orm(record) for record in records]
    records = {record.name: record.msg for record in records}
    return records


def get_all_base_error(db: Session) -> dict:
    records = db.query(exception_table.BaseError).all()
    records = [exception_schema.BaseError.from_orm(record) for record in records]
    logger.info("get_all_base_error records={}".format(records))
    return records


def add_new_base_error(db: Session, value: dict):
    record = exception_table.BaseError(**value)
    db.add(record)
    db.commit()
    logger.info('add_new_base_error base_error={}'.format(value))
