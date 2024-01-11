import os
import sys

from starlette.staticfiles import StaticFiles

sys.path.append('..')

import uvicorn
from fastapi import FastAPI, Request
from starlette.responses import RedirectResponse
from loguru import logger

from common import conf, utils
from api import router
from common.define import ServicePort, ServiceHost, CLOUFFEE_DESCRIPTION

MODULE = utils.get_file_dir_name(__file__)

app = FastAPI(
    title="{} api".format(MODULE),
    # dependencies=[Depends(get_query_token)],
    description=CLOUFFEE_DESCRIPTION
)
app.mount('/static', StaticFiles(directory=os.path.join('../static/swagger-ui')), name='static')

app.include_router(router)


@app.get("/", include_in_schema=False)
def root(request: Request):
    docs_url = "{}docs".format(request.url)
    return RedirectResponse(url=docs_url)


if __name__ == '__main__':
    LOG_PATH = conf.get_log_path(MODULE)
    logger.add(LOG_PATH, rotation="1024KB")
    host, port = ServiceHost.host, getattr(ServicePort, MODULE).value
    logger.info('{} is starting, bind on {}:{}, log_path is {}'.format(MODULE, host, port, LOG_PATH))
    uvicorn.run(app="exception:app", host=host, port=port)
