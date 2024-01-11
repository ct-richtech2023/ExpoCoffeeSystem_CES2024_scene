from datetime import datetime, timedelta

import jwt
import requests
from fastapi import HTTPException, Header, status
from loguru import logger
from passlib.context import CryptContext

from common import conf
from common.db.crud import center as center_crud
from common.db.database import MySuperContextManager
from common.define import UserMsg


class Auth:
    hasher = CryptContext(schemes=["sha512_crypt"])
    secret = "richtech"
    algorithm = 'HS256'



    def get_password_hash(self, password):
        """
        哈希来自用户的密码
        :param password: 原密码
        :return: 哈希后的密码
        """
        return self.hasher.hash(password)

    def verify_password(self, password, hashed_password):
        """
        校验接收的密码是否与存储的哈希值匹配
        :param password: 原密码
        :param hashed_password: 哈希后的密码
        :return: 返回值为bool类型，校验成功返回True,反之False
        """
        return self.hasher.verify(password, hashed_password)

    def create_access_token(self, sn):
        payload = {
            'exp': datetime.utcnow() + timedelta(minutes=UserMsg.ACCESS_TOKEN_EXPIRE_MINUTES),
            'scope': 'access_token',
            'sub': sn
        }
        encoded_jwt = jwt.encode(payload, self.secret, algorithm=self.algorithm)
        return encoded_jwt

    def check_jwt_token(self, token: str = Header(...)):
        if token == conf.get_x_token():
            return 'richtech'
        try:
            payload = jwt.decode(token, self.secret, algorithms=self.algorithm)
            sn: str = payload.get("sub")
            with MySuperContextManager() as db:
                return center_crud.get_user_by_sn(db, sn)
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Token expired'
            )
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail='Invalid token')

    @classmethod
    def check_token_from_asw(cls, token: str = Header(...)):
        if token == conf.get_x_token():
            return 'richtech'
        try:
            payload = {'token': token}
            url = 'https://adam.richtechrobotics.com:5001/customer/verify_token'
            headers = {}
            response = requests.request("POST", url, headers=headers, data=payload)
            response_date = response.json()
            if response.status_code == 200:
                return response_date
            else:
                raise HTTPException(status_code=response.status_code, detail=response_date.get('err_msg'))
        except ConnectionError as err:
            raise HTTPException(status_code=400, detail='connect asw error, please wait')

    def check_user(self, db, sn, password):
        user = center_crud.get_user_by_sn(db, sn)
        if not user:
            return False
        if not self.verify_password(password, user.password):
            return False
        return user.to_dict()

    def check_login(self, name, password):
        param = {'name': name, 'password': password}
        url = "https://adam.richtechrobotics.com:5001/customer/login"
        headers = {}
        response = requests.request("POST", url, headers=headers, data=param)
        login_msg = response.json()
        if response.status_code == 200:
            return login_msg
        else:
            logger.error('sth error when get login from asw: {}'.format(login_msg.get('err_msg')))
            raise Exception(login_msg.get('err_msg'))


def get_square_msg(user_id):
    param = {'user_id': user_id}
    url = "https://adam.richtechrobotics.com:5001/user/message"
    headers = {}
    response = requests.request("GET", url, headers=headers, params=param)
    response_date = response.json()
    if response_date.get('code') == 'success':
        user_msg = response_date.get('data', {})
        logger.debug('get user msg success, data={}'.format(user_msg))
        return user_msg
    else:
        logger.error('sth error when get user msg from asw: {}'.format(response_date.get('data')))
        raise Exception(response_date.get('data'))


