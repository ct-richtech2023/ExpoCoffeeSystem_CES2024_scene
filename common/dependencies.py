from fastapi import Header, HTTPException

from common import conf

X_Token = conf.get_x_token()


async def get_admin_token(x_token: str = Header(...)):
    if x_token != X_Token:
        raise HTTPException(status_code=400, detail="X-Token header invalid")


async def get_query_token(token: str = 'adam'):
    if token != "adam":
        raise HTTPException(status_code=400, detail="No adam token provided")
