from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from business import get_exception_obj, DealWithException
from common.db.database import get_db
from common.define import Channel, SUPPORT_ERROR_TYPE, SUPPORT_BASE_ERROR_STATUS, SUPPORT_ARM_TYPE
from common.db.crud import exception as exception_curd
from common.schemas import exception as exception_schema
from common.api import AudioInterface

router = APIRouter(
    prefix="/{}".format(Channel.exception),
    tags=[Channel.exception],
    # dependencies=[Depends(get_admin_token)],
    responses={404: {"description": "Not found"}},
    on_startup=[get_exception_obj]
)


# db = next(get_db())


# @router.get("/status", description='get critical error in adam container')
def status(db: Session = Depends(get_db)):
    """
    获取所有的已知异常
    """
    return exception_curd.get_all_error(db) or {}


# @router.post("/error", description='create a error')
def add_error(name: SUPPORT_ERROR_TYPE, msg: str, db: Session = Depends(get_db)):
    """
    添加异常
    """
    error = exception_schema.Error(**dict(name=name, msg=msg))
    exception_curd.add_new_error(db, error)
    AudioInterface.gtts(name)


# @router.post("/error/clear", description='clear a error')
def clear_error(name: SUPPORT_ERROR_TYPE, db: Session = Depends(get_db)):
    """
    清楚异常
    """
    exception_curd.clear_error(db, name)
    return exception_curd.get_all_error(db) or {}


# @router.get("/failed/task", description='get failed task')
# def get_fail_task(obj: DealWithException = Depends(get_exception_obj)):
#     return obj.get_failed_task()


@router.get("/base_error", description='get all base_error')
def get_all_base_error(db: Session = Depends(get_db)):
    """
    获取所有异常
    """
    return exception_curd.get_all_base_error(db)


@router.post("/base_error", description='create a error')
def add_base_error(arm: SUPPORT_ARM_TYPE, code: str, desc: str, by: str, error_status: SUPPORT_BASE_ERROR_STATUS, db: Session = Depends(get_db)):
    """
    添加异常
    """
    value = {'arm': arm, 'code': code, 'desc': desc, 'by': by, 'status': error_status}
    exception_curd.add_new_base_error(db, value)

