import os

import requests
import threading
import time
from loguru import logger
from requests import ConnectionError

from common.api import CenterInterface
from common.define import RefundStatus, TaskStatus, OrderStatus


def get_list(ll, index, default):
    try:
        return ll[index]
    except IndexError as e:
        return default


def get_location(sn, url):
    param = {'sn': sn}
    headers = {}
    location_file = 'location.txt'
    try:
        response = requests.request("GET", url, headers=headers, params=param, timeout=5)
        adam_msg = response.json()
        location = adam_msg.get('location_id')
        if location:
            with open(location_file, 'w') as f:
                logger.info('location_id is {}, saved to {}'.format(location, location_file))
                f.write(location)
            return location
        else:
            raise Exception(adam_msg.get('err_msg'))
    except Exception as e:
        logger.warning('cannot get location from asw server')
        if os.path.exists(location_file):
            with open(location_file, 'r') as f:
                location = f.read().strip()
                logger.info('get location_id = {} from {}'.format(location, location_file))
                return location
        raise e


class GetOrderThread(threading.Thread):
    def __init__(self, sn):
        super().__init__()
        self.sn = sn  # adam sn
        self.adam_msg_url = 'https://adam.richtechrobotics.com:5001/customer/get_adam'
        self.location = get_location(self.sn, self.adam_msg_url)

        self.url = "https://adam.richtechrobotics.com:5001/drink/new_order"
        self.update_url = "https://adam.richtechrobotics.com:5001/drink/adam_update"
        self.run_flag = True
        self.network = True

    def stop(self):
        self.run_flag = False

    @staticmethod
    def format_option(option_dict: dict):
        formatted_dict = {}
        for key, value in option_dict.items():
            if key == 'sugar':
                key = 'sweetness'
            elif key == 'milk':
                value = 'fresh_dairy' if value == 'Dairy milk' else 'plant_milk'
            elif key == 'ice':
                value = 'no_ice' if value == 'no' else value
            formatted_dict[key] = value

        return formatted_dict

    def update_square(self, update_dict):
        """
        update_dict: {'order_id': order_id, 'drinks':[{name:name, option:{cup:Med, ice:no, sweetness:80, milk:Fresh Dairy}}] }
        """
        try:
            res = requests.post(self.update_url, json=update_dict)
            logger.info('update square data={}, drinks to square, res={}'.format(update_dict, res.content))
        except Exception as e:
            logger.error('update square data fail, error={}, data={}'.format(e, update_dict))

    def parse_order(self, order):
        # order: {'order_id': 'sfdsdfsd', 'drinks':[{'discount':0, 'refund':0, 'status':0, 'name':'stout'}]
        order_number_from_square = 'S_{}'.format(order.get('order_id'))
        order_number_from_pad = 'P_{}'.format(order.get('order_id'))
        refunded = sum(d.get('refund', 0) for d in order.get('drinks', []))
        refund = RefundStatus.no
        if refunded == len(order.get('drinks', [])):
            refund = RefundStatus.all
        elif refunded > 0 and refunded < len(order.get('drinks', [])):
            refund = RefundStatus.part
        logger.debug('1refunded={}, refund={}'.format(refunded, refund))

        old_order_from_square = CenterInterface.get_one_order(order_number_from_square)
        old_order_from_pad = CenterInterface.get_one_order(order_number_from_pad)
        if old_order_from_square:
            logger.debug('order exist, update, old_order_from_square={}'.format(old_order_from_square))
            tasks = old_order_from_square.get('drinks', [])[::-1]
            refunded += sum(i.get('refund', 0) for i in tasks)
            if refunded == len(old_order_from_square.get('drinks', [])):
                refund = RefundStatus.all
            elif refunded > 0 and refunded < len(old_order_from_square.get('drinks', [])):
                refund = RefundStatus.part
            logger.debug('2refunded={}, refund={}'.format(refunded, refund))
            update_order = {'order_number': order_number_from_square, 'refund': refund}
            update_tasks = []
            # order already exists
            for drink in order.get('drinks', []):
                status = drink.get('status', -1)
                if status == 2:  # refunded, update task
                    for task in tasks:
                        if task.get('formula') == drink.get('name') and task.get('refund') != RefundStatus.refunded:
                            # 根据名字从后往前更新task的退款状态
                            update_task = {'task_uuid': task.get('task_id'), 'discount': drink.get('discount'),
                                           'refund': drink.get('refund'), 'status': TaskStatus.canceled}
                            task['refund'] = RefundStatus.refunded  # 及时更新查询到的task字段，防止多个退款项只对应一个taskuuid
                            update_tasks.append(update_task)
                            break  # 及时退出，防止同名都被更新为退款
            update_order['drinks'] = update_tasks
            logger.debug('update_order = {}'.format(update_order))
            CenterInterface.inner_update_order(update_order)
        elif old_order_from_pad:
            if old_order_from_pad.get('status') == OrderStatus.unpaid:
                receipt_number = order.get('drinks', [])[0].get('receipt_number', '')
                logger.debug('order [{}] has paid'.format(order_number_from_pad))
                drinks = CenterInterface.inner_paid_order(order_number_from_pad, receipt_number)
                update_dict = dict(order_id=order.get('order_id'), drinks=drinks)
                self.update_square(update_dict)
        else:
            # need to add new order
            logger.debug('order not exist, add')
            new_drinks = []
            reference_id = ''
            for drink in order.get('drinks', []):
                reference_id = drink.get('reference_id', '')
                format_option = self.format_option(drink.get('option'))
                new_drink = {'formula': drink.get('name'), 'reference_id': reference_id, 'option': format_option,
                             'discount': drink.get('discount'), 'refund': drink.get('refund'),
                             'receipt_number': drink.get('receipt_number', '')}
                new_drinks.append(new_drink)

            new_order = {'order_number': order_number_from_square, 'refund': refund, 'drinks': new_drinks,
                         'reference_id': reference_id}
            logger.debug('new_order = {}'.format(new_order))
            CenterInterface.inner_new_order(new_order)

    def get_order(self):
        try:
            param = {'location': self.location}
            headers = {}
            with requests.session() as s:
                response = s.request("GET", self.url, headers=headers, params=param, timeout=2)
                self.network = True
                response_date = response.json()
                if response_date.get('code') == 'success':
                    orders = response_date.get('data', [])
                    logger.debug('get new order success, data={}'.format(orders))
                    for order in orders:
                        self.parse_order(order)
                else:
                    logger.error('sth error when get new order from square: {}'.format(response_date.get('data')))
        except ConnectionError as err:
            self.network = False
            logger.error('sth error in get_order, err = {}'.format(err))
            time.sleep(5)
        except Exception as e:
            self.network = False
            logger.error('sth error in get_order, err = {}'.format(e))
            time.sleep(5)

    def run(self):
        while self.run_flag:
            self.get_order()
            time.sleep(0.5)

