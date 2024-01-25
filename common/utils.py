import datetime
import queue
import threading
import traceback

import pytz
import inspect
import json
import math
import os
import shlex
import subprocess
import time

import yaml
from loguru import logger

# from common.define import STEPNAME_MAP

PROC_1_NAME = None
PCM_NUMBER = None

STEPNAME_MAP = {  # 如果重新添加了关键步骤，这边的字典需要及时维护 | If a key step is re-added, the dictionary here needs to be maintained in a timely manner
    'START': 'Start Making',  # 制作开始
    'error': 'Error',  # 出错
    'END': 'End Making',  # 制作结束
    'get_composition_by_option': 'Parse Recipe',  # 解析配方
    'put_hot_cup': 'Put Hot Cup',  # 出热杯
    'take_coffee_machine': 'Take Cup for Coffee',  # 抓杯接咖啡
    'take_foam_cup': 'Take Foam Cup',  # 抓奶泡杯
    'pour_foam_cup': 'Pour Foam',  # 倒奶泡
    'take_foam_cup_judge': 'Grab Foam Cup',  # 抓奶泡杯
    'put_foam_cup': 'Put Foam Cup',  # 放奶泡杯
    'take_ingredients': 'Take Ingredients',  # 接龙头
    'take_cold_cup': 'Take Cold Cup',  # 抓冷杯
    'take_ice': 'Take Ice',  # 接冰
    'idle_interaction': 'Interaction',  # 互动
    'put_cold_cup': 'Put Cold Cup',  # 放冷杯
    'clean_and_put_espresso_cup': 'Clean and Place Espresso Cup',  # 清洗不锈钢杯
    'clean_foamer': 'Clean Foamer',  # 清洗奶泡杯
    'make_foam': 'Make Foam',  # 打奶泡
    'stainless_cup_pour_foam': 'Pour Coffee into Foam Cup', # stainless_cup_pour_foam
}


def reduce_sound():
    for i in range(100, -1, -1):
        os.system(f"amixer set PCM {i}%")
        time.sleep(0.05)

def recover_sound():
    os.system(f"amixer set PCM 80%")  # 100%


def get_current_func_name():
    return inspect.stack()[1][3]


def get_file_dir_name(abs_path):
    abs_path = os.path.abspath(abs_path)
    dir_path = os.path.dirname(abs_path)
    return os.path.basename(dir_path)


def read_yaml(path):
    with open(path, encoding="utf-8") as f:
        result = f.read()
        result = yaml.load(result, Loader=yaml.FullLoader)
        return result


def read_resource_json(path) -> dict:
    path = '/richtech/resource' + path
    assert os.path.isfile(path), '{} is not exist'.format(path)
    with open(path, encoding="utf-8") as f:
        result = f.read()
        return json.loads(result)


def write_yaml(path, data):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, Dumper=yaml.SafeDumper)


def get_execute_cmd_result(cmd: str, shell=False, **kwargs):
    cmd_err = "execute cmd='{}' failed".format(cmd)
    args = cmd if shell else shlex.split(cmd)
    logger.info("cmd={}, shell={}, args={}".format(cmd, shell, args))
    try:
        res = subprocess.check_output(args, stderr=subprocess.STDOUT, universal_newlines=True,
                                      shell=shell, encoding="utf-8", **kwargs)
    except subprocess.TimeoutExpired:
        err = "{}, timeout={} seconds".format(cmd_err, kwargs.get('timeout'))
        logger.error(err)
        raise Exception(err)
    except subprocess.CalledProcessError as e:
        err = "{}, code={}, err={}".format(cmd_err, e.returncode, e.output.strip())
        logger.error(err)
        raise Exception(err)
    except Exception as e:
        err = "{}, err={}".format(cmd_err, str(e))
        logger.error(err)
        raise Exception(err)
    else:
        msg = "cmd={}, return_code=0".format(cmd)
        logger.debug(msg)
        # return bytes.decode(p).strip()
        return res


def get_now_day():
    return datetime.datetime.now().strftime("%Y-%m-%d")


def get_now_day_now_time():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_proc_head_1_name():
    """
    output like: "systemd" or "supervisord"
    """
    global PROC_1_NAME
    if PROC_1_NAME is None:
        cmd = "cat /proc/1/status | head -1"
        result = get_execute_cmd_result(cmd, shell=True)
        proc_name = result.strip().split(':')[-1]
        PROC_1_NAME = proc_name.strip()
        logger.info("current system No.1 proc is '{}'".format(PROC_1_NAME))
    return PROC_1_NAME


def compare_value(a, b, abs_tol=1e-5):
    # 比较两个对象中的值是否相似
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return False
        for i in range(len(a)):
            flag = compare_value(a[i], b[i], abs_tol=abs_tol)
            if not flag:
                return False
        else:
            return True
    elif isinstance(a, list) and not isinstance(b, list):
        return False
    elif not isinstance(a, list) and isinstance(b, list):
        return False
    else:
        if type(a) not in [int, float] or type(b) not in [int, float]:
            return False
        return math.isclose(a, b, abs_tol=abs_tol)


# def utc_to_local(local_tz: str, utc_time: str, fmt='%Y-%m-%d %H:%M:%S'):
#     utc_time = datetime.datetime.strptime(utc_time, fmt)
#     utc_tz = pytz.timezone('UTC')
#     utc_time = utc_tz.localize(utc_time)
#
#     local_tz = pytz.timezone(local_tz)
#     format_time = utc_time.astimezone(local_tz)
#     return format_time.strftime(fmt)
#
#
# def local_to_utc(local_tz: str, origin_time: str, fmt='%Y-%m-%d %H:%M:%S'):
#     origin_time = datetime.datetime.strptime(origin_time, fmt)
#     origin_tz = pytz.timezone(local_tz)
#     origin_time = origin_tz.localize(origin_time)
#     # print(origin_time.strftime(fmt))
#
#     utc_tz = pytz.timezone('UTC')
#     format_time = origin_time.astimezone(utc_tz)
#     return format_time.strftime(fmt)


def utc_to_local(local_offset: int, utc_time: str, fmt='%Y-%m-%d %H:%M:%S'):
    utc_time = datetime.datetime.strptime(utc_time, fmt)
    format_time = utc_time + datetime.timedelta(hours=local_offset)
    return format_time.strftime(fmt)


def local_to_utc(local_offset: int, origin_time: str, fmt='%Y-%m-%d %H:%M:%S'):
    origin_time = datetime.datetime.strptime(origin_time, fmt)
    format_time = origin_time + datetime.timedelta(hours=0 - local_offset)
    return format_time.strftime(fmt)


def format_option(ori_name):
    if ori_name == 'no':
        return 'no_ice'
    if ori_name == 'Med':
        return 'Medium Cup'
    if ori_name == 'Lrg':
        return 'Large Cup'
    return ori_name


def update_threads_step(status_queue: queue.Queue, thread=threading.current_thread(), step='create'):
    """
    thread name formatted as {name}-{step}
    """
    thread_name, current_step = thread.name, ''
    try:
        thread_name, current_step = thread.name.split('-')  # 防止在初始化时不进行格式化命名 | Prevent naming without formatting at initialization
    except Exception:
        thread.name = f'{thread_name}-{current_step}'

    if current_step != step:
        # 防止多次设置同一状态导致时间被覆盖 | Prevent time from being overwritten if you set the same status multiple times
        msg = dict(time=datetime.datetime.utcnow(), thread=thread_name, step=step)
        logger.bind(threads=True).info(msg)
        # logger.bind(threads=True).info(traceback.print_stack(limit=3))
        thread.name = f'{thread_name}-{step}'
        if status_queue.full():
            status_queue.get()
        status_queue.put(msg)


def format_step_name(step_detail:dict, offset):
    """
    step: dict(time=datetime.datetime.utcnow(), thread=thread_name, step=step)
    """
    result = {}
    step_time = step_detail.get('time', datetime.datetime.utcnow())
    thread_name = step_detail.get('thread', '')
    step = step_detail.get('step', '')

    result['time'] = (step_time + datetime.timedelta(hours=int(offset))).strftime('%Y-%m-%d %H:%M:%S')
    show_step = STEPNAME_MAP.get(step, '')
    if not show_step:  # 没有对应step的显示值，则不显示在pad上，忽略
        return None

    if thread_name.startswith('making.left'):
        step_name = 'Left Arm ' + show_step
    elif thread_name.startswith('making.right'):
        step_name = 'Right Arm ' + show_step
    elif thread_name == 'making':
        step_name = show_step
    else:
        return None

    result['step'] = step_name
    return result


