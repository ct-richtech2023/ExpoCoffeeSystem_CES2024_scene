import json
import uuid

from loguru import logger

from common import utils


def parse_requests_response_code_and_dict(func):
    def wrapper(self, *args, **kwargs):
        res = func(self, *args, **kwargs)
        logger.info("url={}, status_code={}, func_name={}".format(
            res.url, res.status_code, func.__name__))
        if res.status_code // 100 != 2:
            logger.warning("res.text={}".format(res.text))
        json_response = res.content.decode()
        dict_json = json.loads(json_response)
        return res.status_code, dict_json

    return wrapper


def catch_exception(func):
    def wrapper(*args, **kwargs):
        try:
            res = func(*args, **kwargs)
        except Exception as e:
            return str(e)
        else:
            return res

    return wrapper


def while_break_when_keyboard_interrupt(func):
    def wrapper(self, *args, **kwargs):
        id_value = str(uuid.uuid4())
        start_time = utils.get_now_day_now_time()
        logger.info('{} start while loop, id is {}'.format(start_time, id_value))
        while True:
            try:
                func(self, *args, **kwargs)
            except KeyboardInterrupt:
                logger.error('Catch user Ctrl+C, break while loop!')
                break
            except Exception as e:
                logger.warning('{} have exception, err={}'.format(id_value, str(e)))
                raise
        end_time = utils.get_now_day_now_time()
        logger.info('{} end while loop, id is {}'.format(end_time, id_value))

    return wrapper
