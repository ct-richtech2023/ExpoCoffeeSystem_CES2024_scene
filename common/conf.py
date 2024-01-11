import os
import platform
import tempfile
import configparser

from common import utils

HERE = os.path.dirname(__file__)


class MyParser(configparser.ConfigParser):
    def as_dict(self):
        d = dict(self._sections)
        for k in d:
            d[k] = dict(d[k])
        return d


def read_ini(path):
    conf = MyParser()
    conf.read(path, encoding="utf-8")
    return conf.as_dict()


def get_log_path(module):
    path = get_module_config(module).get('log')
    log_path = os.path.join(log_dir(), path)
    return os.path.abspath(log_path)


def get_module_config(module) -> dict:
    config = read_ini(os.path.join(HERE, '../settings/project.ini'))
    return config.get(module, {})


def get_machine_config() -> dict:
    config = utils.read_yaml(os.path.join(HERE, '../settings/coffee_machine.yml'))
    return config


def get_idle_Interaction() -> dict:
    config = utils.read_yaml(os.path.join(HERE, '../settings/idle_Interaction.yml'))
    return config


def set_idle_Interaction(data) -> dict:
    config = utils.write_yaml(os.path.join(HERE, '../settings/idle_Interaction.yml'), data)
    return config


def get_adam_config() -> dict:
    config = utils.read_yaml(os.path.join(HERE, '../settings/adam.yml'))
    return config


def get_wake_demo_config() -> dict:
    config = utils.read_yaml(os.path.join(HERE, '../settings/wake-demo.yml'))
    return config


def get_x_token():
    # if check_is_production():
    config = get_module_config('global')
    return config.get('x-token')


def log_dir():
    if platform.system() == 'Windows':
        return tempfile.gettempdir()
    else:
        return '/var/log'


def log_file(file_name, dir_name=None):
    path = log_dir()
    if dir_name:
        path = os.path.join(path, dir_name)
    path = os.path.join(path, file_name)
    return os.path.abspath(path)


def check_is_production():
    # 检查是否是容器环境
    if platform.system() == 'Windows':
        return False
    proc_name = utils.get_proc_head_1_name()
    if 'supervisord' == proc_name:
        return True
    else:
        return False
