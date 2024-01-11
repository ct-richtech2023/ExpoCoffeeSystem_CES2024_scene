from loguru import logger
from functools import wraps
import traceback

from . import error
from common.api import ExceptionInterface


def print_result(func):
    def wrapper(self, *args, **kwargs):
        result = func(self, *args, **kwargs)
        print("func_name={}, result={}".format(func.__name__, result))
        return result

    return wrapper


def analyze_error_code(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        result = func(self, *args, **kwargs)
        func_name = func.__name__
        logger.info("func_name={}, result={}".format(func.__name__, result))
        left_return_code, right_return_code = result
        stack = traceback.extract_stack()
        by = str([i[-2] for i in stack])
        if left_return_code != 0 and left_return_code is not None:
            desc = error.get_return_code_desc(left_return_code)
            ExceptionInterface.add_base_error('left', left_return_code, desc, by)
            logger.error("left func_name={} called_by={} return_code={}, desc={}".format(func_name, by, left_return_code, desc))
        if right_return_code != 0 and right_return_code is not None:
            desc = error.get_return_code_desc(right_return_code)
            ExceptionInterface.add_base_error('right', right_return_code, desc, by)
            logger.error("right func_name={} called_by={} return_code={}, desc={}".format(func_name, by, right_return_code, desc))
        return result

    return wrapper


def check_adam_sdk_left_and_right_param(model):
    def check_model(func):
        func_name = func.__name__
        model_name = model.__name__
        msg = "param in func={} can't pass class={} check".format(func_name, model_name)

        def wrapper(self, left: dict = None, right: dict = None):
            if left is not None:
                try:
                    left = model(**left).dict()
                except Exception as e:
                    err_msg = "left {}, err={}".format(msg, str(e))
                    logger.error(err_msg)
            if right is not None:
                try:
                    right = model(**right).dict()
                except Exception as e:
                    err_msg = "right {}, err={}".format(msg, str(e))
                    logger.error(err_msg)
            print("{} left={}, right={}".format(func_name, left, right))
            return func(self, left, right)

        return wrapper

    return check_model
