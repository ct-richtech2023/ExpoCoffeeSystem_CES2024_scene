import sys
sys.path.append('..')

import os
import uvicorn
from fastapi import FastAPI, Request
from starlette.responses import RedirectResponse
from starlette.staticfiles import StaticFiles
from loguru import logger

from common import conf, utils
from common.define import ServicePort, ServiceHost, CLOUFFEE_DESCRIPTION
from api import router
from kinematics import kinematics_router
from matradee import matradee_router

MODULE = utils.get_file_dir_name(__file__)

app = FastAPI(
    title="{} api".format(MODULE),
    # dependencies=[Depends(get_query_token)],
    description=CLOUFFEE_DESCRIPTION
)
app.mount('/static', StaticFiles(directory=os.path.join('../static/swagger-ui')), name='static')

app.include_router(router)
app.include_router(kinematics_router)
app.include_router(matradee_router)


@app.get("/", include_in_schema=False)
async def root(request: Request):
    docs_url = "{}docs".format(request.url)
    return RedirectResponse(url=docs_url)


if __name__ == '__main__':
    LOG_PATH = conf.get_log_path(MODULE)
    logger.add(LOG_PATH, rotation="08:00")
    STEP_PATH = LOG_PATH.split('.')[0] + '_steps.log'
    logger.add(STEP_PATH, filter=lambda record: record["extra"].get('threads'), rotation="08:00")
    host, port = ServiceHost.host, getattr(ServicePort, MODULE).value
    logger.info('{} is starting, bind on {}:{}, log_path is {}'.format(MODULE, host, port, LOG_PATH))
    uvicorn.run(app="adam:app", host=host, port=port)
