import sys
sys.path.append('..')

import os
import uvicorn
from fastapi import FastAPI, Request
from starlette.staticfiles import StaticFiles
from starlette.responses import RedirectResponse
from loguru import logger  # noqa

from common import conf, utils  # noqa
from common.define import ServiceHost, ServicePort, CLOUFFEE_DESCRIPTION

from api import router
from user import router as user_router

MODULE = utils.get_file_dir_name(__file__)

app = FastAPI(
    title="{} api".format(MODULE),
    # dependencies=[Depends(get_query_token)],
    description=CLOUFFEE_DESCRIPTION
)
app.mount('/static', StaticFiles(directory=os.path.join('../static/swagger-ui')), name='static')

app.include_router(router)
app.include_router(user_router)


@app.get("/", include_in_schema=False)
async def root(request: Request):
    docs_url = "{}docs".format(request.url)
    return RedirectResponse(url=docs_url)


if __name__ == '__main__':
    LOG_PATH = conf.get_log_path(MODULE)
    logger.add(LOG_PATH, rotation="1024KB")
    host, port = ServiceHost.host, getattr(ServicePort, MODULE).value
    logger.info('{} is starting, bind on {}:{}, log_path is {}'.format(MODULE, host, port, LOG_PATH))
    uvicorn.run(app="center:app", host=host, port=port)
