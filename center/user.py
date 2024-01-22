from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from starlette.responses import PlainTextResponse

from auth import Auth, get_square_msg
from business import get_center_obj
from common.db.crud import center as center_crud
from common.db.database import get_db
from common.define import Channel
from common.define import UserMsg
from common.schemas import center as center_schemas
from sqlalchemy.orm import Session

user_handler = Auth()

router = APIRouter(
    prefix="/{}".format(Channel.center),
    tags=[Channel.center],
    # dependencies=[Depends(user_handler.check_jwt_token)],
    responses={404: {"description": "Not found"}, 401: {"description": "token valid fail"}},
    on_startup=[get_center_obj]
)


# @router.post("/verify/account ", description="verify account")
# async def verify_account(user: str, password: str):
#     try:
#         if user == 'rich' and password == '123456':
#             return user
#         elif user == 'admin' and password == '123456':
#             return user
#         else:
#             raise Exception('invalid user or password')
#     except Exception as e:
#         logger.warning("get order status failed, error={}".format(str(e)))
#         return PlainTextResponse(status_code=400, content=str(e))


@router.post("/register", summary="本地注册", dependencies=[])
def signup(user_msg: center_schemas.RegisterRequest, db: Session = Depends(get_db)):
    try:
        hashed_password = user_handler.get_password_hash(user_msg.password)
        user_msg.password = hashed_password
        new_new_id = center_crud.add_user(db, user_msg)
        return new_new_id
    except Exception as e:
        logger.warning("signup failed, error={}".format(str(e)))
        raise HTTPException(
            status_code=401,
            detail=UserMsg.register_error
        )


@router.post("/local/login", summary="本地登录", dependencies=[])
def local_login(user_msg: center_schemas.LocalLoginRequest, db: Session = Depends(get_db)):
    try:
        login_msg = user_handler.check_user(db, user_msg.sn, user_msg.password)
        if not login_msg:
            raise HTTPException(
                status_code=401,
                detail=UserMsg.login_error
            )
        else:
            resullt = {}
            resullt['token'] = user_handler.create_access_token(user_msg.sn)
            resullt['name'] = user_msg.sn
            resullt['id'] = login_msg.get('id')
            return resullt
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=str(e)
        )

# @router.post("/login", response_model=center_schemas.LoginResponse, dependencies=[])
# def login_for_access_token(user_msg: center_schemas.LoginRequest):
#     try:
#         login_msg = user_handler.check_login(user_msg.name, user_msg.password)
#         return login_msg
#     except Exception as e:
#         raise HTTPException(
#             status_code=401,
#             detail=str(e)
#         )

# user_msg = get_square_msg(login_msg.get('customer_id'))
# if not user_msg:
#     raise HTTPException(
#         status_code=401,
#         detail=UserMsg.lack_square_msg.format(login_msg.get('id'))
#     )
# login_msg.update(user_msg)
# return login_msg
