import json
import sys
import time

sys.path.append('..')
import threading
import requests
import urllib
from loguru import logger

from common import define
from common.conf import get_machine_config
from common.schemas import adam as adam_schema
from common.myerror import AdamError
from requests.exceptions import ConnectionError


def module_base_url(module):
    host, port = define.ServiceHost.localhost, getattr(define.ServicePort, module).value
    return "http://{}:{}".format(host, port)


class VisualDetectInterface:
    base_url = 'http://192.168.2.55:5002'

    # base_url = 'http://192.168.0.55:5002'  # scene url

    @classmethod
    def start_following(cls):
        try:
            url = "{}/start".format(cls.base_url)
            res = requests.post(url)
            logger.info('url={} result={}'.format(url, res.content))
        except Exception as e:
            pass

    @classmethod
    def stop_following(cls):
        try:
            url = "{}/stop".format(cls.base_url)
            res = requests.post(url)
            logger.info('url={} result={}'.format(url, res.content))
        except Exception as e:
            pass


class ASWServerInterface:
    base_url = 'https://adam.richtechrobotics.com:5001'

    @classmethod
    def making_report(cls, task_uuid, drink: dict):
        drink['task_uuid'] = str(task_uuid)
        drink['sn'] = get_machine_config().get('adam', {}).get('sn', '')
        sweetness = drink.pop('sweetness', 100)
        ice = drink.pop('ice', 'light')
        milk = drink.pop('milk', 'Fresh Dairy')
        beans = drink.pop('beans', '')
        extra = []
        if drink.pop('boba', 0):
            extra.append('boba')
        if drink.pop('milk_cap', 0):
            extra.append('milk_cap')
        drink['option'] = {
            'ice': ice,
            'milk': milk,
            'sweetness': sweetness,
            'beans': beans,
            'extra': ' + '.join(extra)
        }
        url = "{}/drink/report".format(cls.base_url)
        res = requests.post(url, json=drink)
        logger.info('url={} drink={}, result={}'.format(url, drink.get('task_uuid'), res.content))
        if res.status_code == 200:
            return True
        return False

    @classmethod
    def add_cleaning_history(cls, cleaning_history: dict):
        payload = json.dumps({
            "sn": get_machine_config().get('adam', {}).get('sn', ''),
            "name": cleaning_history['name'],
            "cleaning_method": cleaning_history['cleaning_method'],
            "timelength": cleaning_history['timelength'],
            "flag": cleaning_history['flag'],
            "cleaning_time": cleaning_history['cleaning_time']
        })
        headers = {
            'Content-Type': 'application/json'
        }
        url = "{}/action/clean".format(cls.base_url)
        res = requests.post(url, headers=headers, data=payload)
        logger.info('url={} params={}, result={}'.format(url, payload, res.content))
        if res.status_code == 200:
            return True
        return False


class CenterInterface:
    base_url = module_base_url('center')

    # @classmethod
    # def new_order(cls, order: dict, token: str = 'richtech'):
    #     header = {'x-token': token}
    #     url = "{}/center/order".format(cls.base_url)
    #     res = requests.post(url, json=order, headers=header)
    #     logger.info('url={} data={}, result={}'.format(url, order, res.content))

    @classmethod
    def inner_new_order(cls, order: dict, token: str = 'richtech'):
        header = {'token': token}
        url = "{}/center/inner_new_order".format(cls.base_url)
        res = requests.post(url, json=order, headers=header)
        logger.info('url={} data={}, result={}'.format(url, order, res.content))

    @classmethod
    def get_one_order(cls, order_number, token: str = 'richtech'):
        header = {'token': token}
        param = {'inner': 1}
        url = "{}/center/order/{}".format(cls.base_url, order_number)
        res = requests.get(url, params=param, headers=header)
        logger.info('url={} order_number={}, result={}'.format(url, order_number, res.content))
        return res.json()

    @classmethod
    def update_task_status(cls, task_uuid, status, token: str = 'richtech'):
        params = {'task_uuid': task_uuid, 'status': status}
        header = {'token': token}
        url = "{}/center/order/task/status".format(cls.base_url)
        res = requests.post(url, params=params, headers=header)
        logger.info('url={} task_uuid={}, result={}'.format(url, task_uuid, res.content))
        return res.json()

    @classmethod
    def restart_service(cls, service_name, token: str = 'richtech'):
        params = {'service': service_name}
        header = {'token': token}
        url = "{}/center/service/restart".format(cls.base_url)
        logger.info('url={} service_name={}'.format(url, service_name))
        res = requests.post(url, params=params, headers=header)
        logger.info('url={} service_name={}, result={}'.format(url, service_name, res.content))
        return res.content

    @classmethod
    def update_last_milk_time(cls, material_names: list, token: str = 'richtech'):
        params = {'material_names': material_names}
        payload = json.dumps(material_names)
        headers = {
            'token': token,
            'accept': 'application/json',
            'Content-Type': 'application/json'
        }
        url = "{}/center/setting/milk/last_time".format(cls.base_url)
        res = requests.post(url, data=payload, headers=headers)
        logger.info('url={}, result={}'.format(url, res.content))
        return res.json()

    @classmethod
    def get_order_by_task_uuid(cls, task_uuid, token: str = 'richtech'):
        header = {'token': token}
        param = {'task_uuid': task_uuid}
        url = "{}/center/order/get_order_by_task_uuid".format(cls.base_url)
        res = requests.post(url, params=param, headers=header)
        # logger.info('url={} task_uuid={}, result={}'.format(url, task_uuid, res.content))
        return res.json()


class AudioInterface:
    base_url = module_base_url('audio')

    @classmethod
    def tts(cls, text, sync: bool = True):
        params = {'text': text, 'sync': sync}
        url = "{}/audio/tts".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={} params={}, result={}'.format(url, params, res.content))

    @classmethod
    def gtts(cls, text, sync: bool = False):
        params = {'text': text, 'sync': sync}
        url = "{}/audio/gtts".format(cls.base_url)
        try:
            res = requests.post(url, params=params, timeout=3)
            logger.info('url={} params={}, result={}'.format(url, params, res.content))
        except Exception as e:
            pass

    @classmethod
    def weather(cls, lat=None, lon=None, units=None):
        params = {}
        if lat:
            params['lat'] = lat
        if lon:
            params['lon'] = lon
        if units:
            params['units'] = units
        url = "{}/audio/weather".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={} params={}, result={}'.format(url, params, res.content))

    @classmethod
    def music(cls, name, delay=None):
        params = {'name': name, 'delay': delay}
        url = "{}/audio/music".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={} params={}, result={}'.format(url, params, res.content))

    @classmethod
    def stop(cls):
        url = "{}/audio/stop".format(cls.base_url)
        try:
            res = requests.post(url)
            logger.info('url={}, result={}'.format(url, res.content))
        except Exception as e:
            pass

    @classmethod
    def sound(cls, name):
        params = {'name': name}
        url = "{}/audio/sound".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={} params={}, result={}'.format(url, params, res.content))


class CoffeeInterface:
    base_url = module_base_url('coffee')

    @classmethod
    def make(cls, formula, cup, sweetness, ice, milk, beans, discount, unit_money, task_uuid=None, receipt_number='', create_time=None):
        params = {'formula': formula, 'cup': cup, 'sweetness': sweetness, 'ice': ice, 'milk': milk, 'beans': beans,
                  'discount': discount, 'unit_money': unit_money, 'receipt_number': receipt_number}
        if create_time:
            params['create_time'] = create_time
        if task_uuid:
            params['task_uuid'] = task_uuid
        url = "{}/coffee/make".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={} params={}, code={}, result={}'.format(url, params, res.status_code, res.content))
        if res.status_code == 200:
            return True
        return False

    @classmethod
    def add_cleaning_history(cls, cleaning_dict, cleaning_method):
        url = "{}/coffee/clean_history?cleaning_method={}".format(cls.base_url, cleaning_method)
        res = requests.post(url, json=cleaning_dict)
        if res.status_code == 400:
            logger.warning('url={} result={}'.format(url, res.content))
        else:
            logger.info('url={} result={}'.format(url, res.content))

    @classmethod
    def get_machine_config(cls, name=None, machine=None):
        """
        get machine config by material name or machine
        :param name: material name or machine
        :return: dict, {}
        """
        params = {}
        if name:
            params['name'] = name
        if machine:
            params['machine'] = machine
        url = "{}/coffee/machine/get".format(cls.base_url)
        res = requests.get(url, params=params)
        if res.status_code == 400:
            logger.warning('url={} result={}'.format(url, res.content))
            return None
        else:
            logger.info('url={}'.format(url))
            return res.json()

    @classmethod
    def post_use(cls, name: str, quantity: int):
        try:
            params = {'name': name, 'quantity': quantity}
            url = "{}/coffee/material/use".format(cls.base_url)
            res = requests.post(url, params=params, timeout=1)
            if res.status_code == 400:
                logger.warning('url={} result={}'.format(url, res.content))
            else:
                logger.info('url={} result={}'.format(url, res.content))
        except Exception as e:
            logger.error(e)

    @classmethod
    def get_formula_composition(cls, formula, cup, formula_in_use=None):
        params = {'formula': formula, 'cup': cup, 'formula_in_use': formula_in_use}
        url = "{}/coffee/composition/get".format(cls.base_url)
        res = requests.get(url, params=params)
        if res.status_code == 400:
            logger.warning('url={} params={} result={}'.format(url, params, res.content))
        else:
            logger.info('url={} params={} result={}'.format(url, params, res.content))
            return res.json()

    @classmethod
    def choose_one_speech_text(cls, code):
        params = {'code': code}
        url = "{}/coffee/speech/random".format(cls.base_url)
        try:
            res = requests.get(url, params=params)
            logger.info('url={} params={}, result={}'.format(url, params, res.content))
            return res.content
        except ConnectionError:
            pass

    @classmethod
    def pause_making(cls):
        url = "{}/coffee/pause_making".format(cls.base_url)
        try:
            res = requests.post(url)
            logger.info('url={}, result={}'.format(url, res.content))
        except ConnectionError:
            pass

    @classmethod
    def proceed_making(cls):
        url = "{}/coffee/proceed_making".format(cls.base_url)
        try:
            res = requests.post(url)
            logger.info('url={}, result={}'.format(url, res.content))
        except ConnectionError:
            pass

    @classmethod
    def cancel_drink(cls, task_uuid):
        params = {'task_uuid': task_uuid}
        url = "{}/coffee/drink/cancel".format(cls.base_url)
        res = requests.post(url, params=params, timeout=1)
        if res.status_code == 400:
            logger.warning('url={} result={}'.format(url, res.content))
        else:
            logger.info('url={} result={}'.format(url, res.content))

    @classmethod
    def update_detect_by_name(cls, name=None, status=None, task_uuid=None):
        update_detect_thread = threading.Thread(target=cls._update_detect_by_name, args=(name, status, task_uuid))
        update_detect_thread.start()

    @classmethod
    def _update_detect_by_name(cls, name=None, status=None, task_uuid=None):
        """
        get machine config by material name or machine
        :param name: material name or machine
        :return: dict, {}
        """
        params = {}
        if name:
            params['name'] = name
        if status:
            params['status'] = status
        if task_uuid:  # Fixed the if condition here
            params['task_uuid'] = task_uuid
            logger.info(f'task_uuid{task_uuid}')
        url = "{}/coffee/update_detect_by_name".format(cls.base_url)
        # Define the time interval and total duration
        interval = 5  # seconds
        total_duration = 60  # seconds
        start_time = time.time()
        while time.time() - start_time < total_duration:
            res = requests.post(url, params=params)
            if res.status_code == 400:
                logger.warning('url={} result={}'.format(url, res.content))
            else:
                logger.info('url={}'.format(url))
                return "ok"
            time.sleep(interval)  # Wait for the specified interval before the next request
        return None  # Return None if the 60-second duration elapses without a successful request

    @classmethod
    def get_detect_all_data(cls, name=None):
        """
        get machine config by material name or machine
        :param name: material name or machine
        :return: dict, {}
        """
        params = {}
        if name:
            params['name'] = name
        url = "{}/coffee/get_detect_all_data".format(cls.base_url)
        res = requests.get(url, params=params)
        if res.status_code == 400:
            logger.warning('url={} result={}'.format(url, res.content))
            return None
        else:
            logger.info('url={}'.format(url))
            return res.json()


class ExceptionInterface:
    base_url = module_base_url('exception')

    @classmethod
    def add_error(cls, name, msg):
        try:
            params = {'name': name, 'msg': msg}
            url = "{}/exception/error".format(cls.base_url)
            res = requests.post(url, params=params)
            logger.info('url={} params={}, msg={}, result={}'.format(url, params, msg, res.json()))
        except Exception as e:
            logger.error(str(e))

    @classmethod
    def status(cls):
        url = "{}/exception/status".format(cls.base_url)
        res = requests.get(url)
        logger.info('url={}, result={}'.format(url, res.json()))

    @classmethod
    def clear_error(cls, name):
        try:
            params = {'name': name}
            url = "{}/exception/error/clear".format(cls.base_url)
            res = requests.post(url, params=params)
            logger.info('url={}, params={}, result={}'.format(url, params, res.json()))
        except Exception as e:
            logger.error(str(e))

    @classmethod
    def add_base_error(cls, arm, code, desc, by, error_status='unsolved'):
        try:
            params = {'arm': arm, 'code': code, 'desc': desc, 'by': by, 'error_status': error_status}
            url = "{}/exception/base_error".format(cls.base_url)
            res = requests.post(url, params=params)
            logger.info('url={} params={}, result={}'.format(url, params, res.json()))
        except Exception as e:
            logger.error(str(e))


class AdamInterface:
    base_url = module_base_url('adam')

    @classmethod
    def get_status(cls):
        url = "{}/adam/status".format(cls.base_url)
        res = requests.get(url)
        logger.info('url={}, result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            return {}
        else:
            return res.json()

    @classmethod
    def make_cold_drink(cls, coffee_record):
        params = {"coffee_record": coffee_record}
        url = "{}/adam/make_cold_drink".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={}, result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            msg = res.content if res.content else ''
            raise AdamError(msg)

    @classmethod
    def make_hot_drink(cls, coffee_record):
        params = {"coffee_record": coffee_record}
        url = "{}/adam/make_hot_drink".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={}, result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            msg = res.content if res.content else ''
            raise AdamError(msg)

    @classmethod
    def standby_pose(cls):
        url = "{}/adam/standby_pose".format(cls.base_url)
        res = requests.post(url)
        logger.info('url={}, result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()

    @classmethod
    def stop_move(cls):
        url = "{}/adam/stop_move".format(cls.base_url)
        res = requests.post(url)
        logger.info('url={}, result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()

    @classmethod
    def change_adam_status(cls, status, timeout=None):
        params = {'status': status}
        url = "{}/adam/change_adam_status".format(cls.base_url)
        res = requests.post(url, params=params, timeout=timeout)
        logger.info('url={}, result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()

    @classmethod
    def change_adam_status_idle(cls, status):
        params = {'status': status}
        url = "{}/adam/change_adam_status_idle".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={}, result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()

    @classmethod
    def clean_milk_pipe(cls, materials: list):
        payload = json.dumps(materials)
        headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json'
        }
        url = "{}/adam/clean_milk_pipe".format(cls.base_url)
        res = requests.post(url, headers=headers, data=payload)
        logger.info('url={}, result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()

    @classmethod
    def inverse(cls, which: define.SUPPORT_ARM_TYPE, pose: adam_schema.Pose, q_pre: dict):
        params = {'which': which}
        json = {'pose': pose, 'q_pre': q_pre}
        url = "{}/kinematics/inverse".format(cls.base_url)
        res = requests.post(url, params=params, json=json)
        logger.info('url={} params={}, json={}, result={}'.format(url, params, json, res.json()))
        return res.content

    @classmethod
    def random_dance(cls, choice, timeout):
        params = {'choice': choice}
        url = "{}/adam/random_dance".format(cls.base_url)
        res = requests.post(url, params=params, timeout=timeout)
        logger.info('url={} result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()
        return res.json()

    @classmethod
    def pause_dance(cls):
        url = "{}/adam/pause_dance".format(cls.base_url)
        res = requests.post(url)
        logger.info('url={} result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()
        return res.json()

    @classmethod
    def zero(cls, idle):
        params = {'idle': idle}
        url = "{}/adam/zero".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={} result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()
        return res.json()

    @classmethod
    def stop(cls):
        url = "{}/adam/stop".format(cls.base_url)
        res = requests.post(url)
        logger.info('url={} result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()
        return res.json()

    @classmethod
    def resume(cls):
        url = "{}/adam/resume".format(cls.base_url)
        res = requests.post(url)
        logger.info('url={} result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()
        return res.json()


class MathadeeInterface:
    base_url = module_base_url('adam')

    @classmethod
    def robot_info(cls, uuid):
        params = {'uuid': uuid}
        url = "{}/matradee/robot/info".format(cls.base_url)
        res = requests.get(url, params=params)
        logger.info('url={} params={}, result={}'.format(url, params, res.json()))

    @classmethod
    def robot_task(cls, uuid, position_name):
        params = {'uuid': uuid, 'position_name': position_name}
        url = "{}/matradee/robot/task".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={} params={}, result={}'.format(url, params, res.json()))
        return res.json()

    @classmethod
    def robot_pos(cls, uuid):
        params = {'uuid': uuid}
        url = "{}/matradee/robot/pos".format(cls.base_url)
        res = requests.get(url, params=params)
        logger.info('url={} params={}, text={}'.format(url, params, res.json()))
        return res.json()


if __name__ == '__main__':
    AudioInterface().gtts('123')
