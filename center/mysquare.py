import os
import threading
import time
import queue
import requests
from datetime import datetime
from loguru import logger
from square.client import Client
from requests import ConnectionError
from common.api import CenterInterface


class DiscontStatus:
    NO = 0
    RESELL = 1
    NORMAL = 2


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


class GetNewOrderThread(threading.Thread):

    def __init__(self, access_token, adam_sn,  queue, environment='production'):
        super().__init__()
        self.last_request_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        # self.last_request_time = '2023-09-10T16:55:28.602Z'
        adam_msg_url = 'https://adam.richtechrobotics.com:5001/customer/get_adam'
        self.location_id = get_location(adam_sn, adam_msg_url)

        self.queue = queue
        self.square_client = Client(access_token=access_token, environment=environment)
        self.order_api = self.square_client.orders
        self.payment_api = self.square_client.payments
        self.new_orders = []
        self.network = True

    def get_modify_list_name_by_modify_id(self, modify_catalog_id):
        result = self.square_client.catalog.retrieve_catalog_object(modify_catalog_id)
        if result.is_success():
            modify = result.body.get('object')
            modify_list_id = modify.get('modifier_data', {}).get('modifier_list_id')
            result = self.square_client.catalog.retrieve_catalog_object(modify_list_id)
            if result.is_success():
                modify_list = result.body.get('object')
                modify_list_name = modify_list.get('modifier_list_data', {}).get('name')
                return modify_list_name
            elif result.is_error():
                logger.error('sth error when retrieve_modify_list_object, error = {}'.format(result.errors))
                # raise Exception('sth error when retrieve_modify_list_object, error = {}'.format(result.errors))
        elif result.is_error():
            logger.error('sth error when retrieve_modify_object, error = {}'.format(result.errors))
            # raise Exception('sth error when retrieve_modify_object, error = {}'.format(result.errors))

    @staticmethod
    def format_option(option_dict: dict):
        formatted_dict = {}
        for key, value in option_dict.items():
            lower_key = key.lower()
            if lower_key == 'sugar':
                key = 'sweetness'
            elif lower_key == 'milk':
                key = 'milk'
                value = 'fresh_dairy' if value.lower() == 'milk' else 'plant_milk'
            elif lower_key == 'ice':
                key = 'ice'
                value = 'no_ice' if value == 'no' else value
            elif lower_key == 'beans':
                key = 'beans'
                value = 'medium_roast' if value.lower().replace(' ', '') == 'mediumroastcoffeebeans' else 'high_roast'
            formatted_dict[key] = value
        return formatted_dict

    @staticmethod
    def next_time(create_time):
        new_time = datetime.strptime(create_time, '%Y-%m-%dT%H:%M:%S.%fZ').timestamp() + 1/1000
        new_dt = datetime.fromtimestamp(new_time)
        return new_dt.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

    def get_order_detail(self, order_id, receipt_number, reference_id):
        new_drinks = []
        order_response = self.order_api.retrieve_order(order_id)
        if order_response.status_code == 200:
            order_data = order_response.body.get('order', {})
            line_items = order_data.get('line_items', [])

            for line_item in line_items:
                name = line_item.get('name')
                quantity = int(line_item.get('quantity'))

                modifiers = line_item.get('modifiers', [])
                option = {'extra': []}
                for modify in modifiers:
                    # total_money = modify.get('base_price_money').get('amount')
                    # modify_quantity = modify.get('quantity')
                    option_name = modify.get('name')
                    modify_catalog_id = modify.get('catalog_object_id')

                    param = self.get_modify_list_name_by_modify_id(modify_catalog_id)

                    if param == 'extra':
                        # option[param].append(
                        #     {'total_money': total_money, 'quantity': modify_quantity, 'name': option_name})
                        option[param].append(option_name)
                    else:
                        option[param] = option_name

                for i in range(quantity):
                    new_drink = {
                        'reference_id': reference_id,
                        'receipt_number': receipt_number,
                        'formula': name,
                        'discount': 0,  # 未考虑折扣情况
                        'refund': 0,  # 未考虑退款情况
                        'option': self.format_option(option)
                    }
                    new_drinks.append(new_drink)
            new_order = {'order_number': 'S_{}'.format(order_id), 'refund': 0, 'drinks': new_drinks,
                         'reference_id': reference_id}
            logger.debug('get new order: {}'.format(new_order))
            self.queue.put(new_order)

    def check_for_new_orders(self):
        # logger.debug('Scanning ... {}'.format(time.time(), self.last_request_time))
        payment_response = self.payment_api.list_payments(begin_time=self.last_request_time, location_id=self.location_id, sort_order='ASC', limit=1)
        if payment_response.status_code == 200:
            payments = payment_response.body.get('payments', {})
            for payment in payments:
                payment_id = payment.get('id')
                order_id = payment.get('order_id')
                receipt_number = payment.get('receipt_number')
                reference_id = payment.get('reference_id', '')
                refund_ids = payment.get('refund_ids', None)
                create_time = payment.get('created_at')
                self.get_order_detail(order_id, receipt_number, reference_id)
                self.last_request_time = self.next_time(create_time)
                logger.debug('change last time to {}'.format(self.last_request_time))

    def run(self):
        while True:
            try:
                self.check_for_new_orders()
            except Exception as e:
                self.network = False
                logger.error('sth error in check_for_new_orders, err = {}'.format(e))
            time.sleep(0.5)


class ProcessOrderThread(threading.Thread):

    def __init__(self, queue: queue.Queue):
        super(ProcessOrderThread, self).__init__()
        self.queue = queue

    def run(self) -> None:
        while new_order := self.queue.get():
            # pass
            CenterInterface.inner_new_order(new_order)



# token = 'EAAAEeADGuJrbl2y80hYMxJKOrla181hLmf5SBYY2CyfcVZyNtDJ-eOVbZk2XPQt'
# location_id = 'L5BTESE51XM1J'
# wait_queue = queue.Queue()
# report_queue = queue.Queue()
# producer = GetNewOrderThread(access_token=token, adam_sn='abcde', queue=wait_queue)
# producer.setDaemon(True)
# producer.start()
#
# customer = ProcessOrderThread(wait_queue)
# customer.setDaemon(True)
# customer.start()
#
#
# # repoter = ReportThread(report_queue)
# # repoter.setDaemon(True)
# # repoter.start()
#
# # producer.join()