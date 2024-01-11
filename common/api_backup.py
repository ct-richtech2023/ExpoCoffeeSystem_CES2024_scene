import json
import sys
import time
sys.path.append('..')

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
    base_url = 'http://192.168.0.55:5002'

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
    def _making_report(cls, drink):
        url = "{}/drink/report".format(cls.base_url)
        res = requests.post(url, json=drink)
        logger.info('url={} drink={}, result={}'.format(url, drink.get('task_uuid'), res.content))

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
        ASWServerInterface._making_report(drink)

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



class CenterInterface:
    base_url = module_base_url('center')

    @classmethod
    def new_order(cls, order: dict, token: str = 'richtech'):
        header = {'x-token': token}
        url = "{}/center/order".format(cls.base_url)
        res = requests.post(url, json=order, headers=header)
        logger.info('url={} data={}, result={}'.format(url, order, res.content))

    @classmethod
    def inner_new_order(cls, order: dict, token: str = 'richtech'):
        header = {'token': token}
        url = "{}/center/inner_order".format(cls.base_url)
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
    def inner_update_order(cls, update_dict, token: str = 'richtech'):
        header = {'token': token}
        url = "{}/center/order/inner_update".format(cls.base_url)
        res = requests.post(url, json=update_dict, headers=header)
        logger.info('url={} data={}, result={}'.format(url, update_dict, res.content))
        return res.json()

    @classmethod
    def inner_paid_order(cls, order_number, receipt_number, token: str = 'richtech'):
        params = {'order_number': order_number, 'receipt_number': receipt_number}
        header = {'token': token}
        url = "{}/center/order/inner_paid".format(cls.base_url)
        res = requests.post(url, params=params, headers=header)
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
            if str(text).startswith("/"):
                res = requests.post(url, params=params, timeout=3)
                logger.info('url={} params={}, result={}'.format(url, params, res.content))
            else:
                pass
        except Exception as e:
            pass

    @classmethod
    def gtts2(cls, text, sync: bool = False):
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
    def exist_next(cls):
        url = "{}/coffee/task/next".format(cls.base_url)
        res = requests.get(url)
        if res.status_code == 200:
            logger.info('check if exist_next, result={}'.format(res.content))
            if res.text != '""':
                logger.info('exist waiting record with task_uuid={}'.format(res.content))
                return True
            else:
                return False
        else:
            return False

    @classmethod
    def get_material(cls, name):
        params = {'name': name}
        params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        url = "{}/coffee/material/get".format(cls.base_url)
        res = requests.get(url, params=params)
        if res.status_code == 400:
            logger.warning('url={} result={}'.format(url, res.content))
            return None
        else:
            logger.info('url={} result={}'.format(url, res.content))
            return res.json()[0]

    @classmethod
    def add_cleaning_history(cls, cleaning_dict, cleaning_method):
        url = "{}/coffee/clean_history?cleaning_method={}".format(cls.base_url, cleaning_method)
        res = requests.post(url, json=cleaning_dict)
        if res.status_code == 400:
            logger.warning('url={} result={}'.format(url, res.content))
        else:
            logger.info('url={} result={}'.format(url, res.content))

    @classmethod
    def get_last_one_clean_history(cls):
        url = "{}/coffee/clean_history/get_last_one".format(cls.base_url)
        res = requests.get(url)
        if res.status_code == 400:
            logger.warning('url={} result={}'.format(url, res.content))
            return None
        else:
            logger.info('url={} result={}'.format(url, res.content))
            return res.json()

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
        params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
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
        params = {'name': name, 'quantity': quantity}
        url = "{}/coffee/material/use".format(cls.base_url)
        res = requests.post(url, params=params, timeout=1)
        if res.status_code == 400:
            logger.warning('url={} result={}'.format(url, res.content))
        else:
            logger.info('url={} result={}'.format(url, res.content))

    @classmethod
    def get_formula_composition(cls, formula, cup, formula_in_use=None):
        params = {'formula': formula, 'cup': cup, 'formula_in_use': formula_in_use}
        # params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        url = "{}/coffee/composition/get".format(cls.base_url)
        res = requests.get(url, params=params)
        logger.info('url={} params={}, result={}'.format(url, params, res.json()))
        return res.json()

    @classmethod
    def get_espresso_by_formula(cls, formula):
        params = {'formula': formula}
        # params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        url = "{}/coffee/espresso/get".format(cls.base_url)
        res = requests.get(url, params=params)
        logger.info('url={} params={}, result={}'.format(url, params, res.json()))
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
    def bean_out(cls):
        url = "{}/coffee/material/bean_out".format(cls.base_url)
        try:
            res = requests.post(url)
            logger.info('url={}, result={}'.format(url, res.content))
        except ConnectionError:
            pass

    @classmethod
    def bean_reset(cls):
        url = "{}/coffee/material/bean_reset".format(cls.base_url)
        try:
            res = requests.post(url)
            logger.info('url={}, result={}'.format(url, res.content))
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
    def get_all_machine_states(cls):
        url = "{}/machine/get_all_machine_states".format(cls.base_url)
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

    # @classmethod
    # def update_detect_by_name(cls, name=None, status=None, task_uuid=None):
    #     """
    #     get machine config by material name or machine
    #     :param name: material name or machine
    #     :return: dict, {}
    #     """
    #     params = {}
    #     if name:
    #         params['name'] = name
    #     if status:
    #         params['status'] = status
    #     if status:
    #         params['task_uuid'] = task_uuid
    #     params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    #     url = "{}/coffee/update_detect_by_name".format(cls.base_url)
    #     res = requests.get(url, params=params)
    #     if res.status_code == 400:
    #         logger.warning('url={} result={}'.format(url, res.content))
    #         return None
    #     else:
    #         logger.info('url={}'.format(url))
    #         # return res.json()

    @classmethod
    def update_detect_by_name(cls, name=None, status=None, task_uuid=None):
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

        params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        url = "{}/coffee/update_detect_by_name".format(cls.base_url)

        # Define the time interval and total duration
        interval = 5  # seconds
        total_duration = 60  # seconds
        start_time = time.time()

        while time.time() - start_time < total_duration:
            res = requests.get(url, params=params)
            if res.status_code == 400:
                logger.warning('url={} result={}'.format(url, res.content))
            else:
                logger.info('url={}'.format(url))
                # Return "ok" upon successful request
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
        params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        url = "{}/coffee/get_detect_all_data".format(cls.base_url)
        res = requests.get(url, params=params)
        if res.status_code == 400:
            logger.warning('url={} result={}'.format(url, res.content))
            return None
        else:
            logger.info('url={}'.format(url))
            return res.json()

    @classmethod
    def add_formula_duration(cls, formula, duration, left_status, right_status):
        params = {'formula': formula, 'duration': duration, 'left_status': left_status, 'right_status': right_status}
        url = "{}/coffee/add_formula_duration".format(cls.base_url)
        res = requests.post(url, params=params)
        if res.status_code == 400:
            logger.warning('url={} result={}'.format(url, res.content))
        else:
            logger.info('url={} result={}'.format(url, res.content))

    @classmethod
    def get_formula_duration(cls, formula=None):
        if formula:
            params = {'formula': formula}
        else:
            params = {'formula': ''}
        url = "{}/coffee/get_formula_duration".format(cls.base_url)
        res = requests.get(url, params=params)
        if res.status_code == 400:
            logger.warning('url={} result={}'.format(url, res.content))
        else:
            # logger.info('url={} result={}'.format(url, res.content))
            return res.json()

    @classmethod
    def get_idle_interaction(cls):
        url = "{}/coffee/get_idle_interaction".format(cls.base_url)
        res = requests.get(url)
        if res.status_code == 400:
            logger.warning('url={} result={}'.format(url, res.content))
        else:
            # logger.info('url={} result={}'.format(url, res.content))
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
    def prepare_for(cls, formula):
        params = {'formula': formula}
        url = "{}/adam/prepare_for".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={}, params={}, result={}'.format(url, params, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()

    @classmethod
    def main_make(cls, formula, cup, sweetness, ice, milk):
        params = {'formula': formula, 'cup': cup, 'sweetness': sweetness, 'ice': ice, 'milk': milk}
        url = "{}/adam/main_make".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={}, params={}, result={}'.format(url, params, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()

    @classmethod
    def make_cold_drink(cls, formula, sweetness, ice, milk, beans, receipt_number, task_uuid):
        params = {'formula': formula, 'sweetness': sweetness, 'ice': ice, 'milk': milk, 'beans': beans,
                  'receipt_number': receipt_number, 'task_uuid': task_uuid}
        url = "{}/adam/make_cold_drink".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={}, result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            msg = res.content if res.content else ''
            raise AdamError(msg)

    @classmethod
    def make_hot_drink(cls, formula, sweetness, ice, milk, beans, receipt_number, task_uuid):
        params = {'formula': formula, 'sweetness': sweetness, 'ice': ice, 'milk': milk, 'beans': beans,
                  'receipt_number': receipt_number, 'task_uuid': task_uuid}
        url = "{}/adam/make_hot_drink".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={}, result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            msg = res.content if res.content else ''
            raise AdamError(msg)

    @classmethod
    def pour(cls, action):
        params = {'action': action}
        url = "{}/adam/pour".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={}, params={}, result={}'.format(url, params, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()

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
    def change_adam_status_idle(cls, status):
        params = {'status': status}
        url = "{}/adam/change_adam_status_idle".format(cls.base_url)
        res = requests.post(url, params=params)
        logger.info('url={}, result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()

    @classmethod
    def release_ice(cls):
        url = "{}/adam/release_ice".format(cls.base_url)
        res = requests.post(url)
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
    def dance(cls):
        url = "{}/adam/dance".format(cls.base_url)
        res = requests.post(url)
        logger.info('url={} result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()
        return res.json()

    @classmethod
    def random_dance(cls, choice):
        params = {'choice': choice}
        url = "{}/adam/random_dance".format(cls.base_url)
        res = requests.post(url, params=params)
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
    def zero(cls):
        url = "{}/adam/zero".format(cls.base_url)
        res = requests.post(url)
        logger.info('url={} result={}'.format(url, res.json()))
        if res.status_code and res.status_code != 200:
            raise AdamError()
        return res.json()

    @classmethod
    def stop_CountdownTime(cls):
        url = "{}/adam/stop_CountdownTime".format(cls.base_url)
        res = requests.post(url)
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
