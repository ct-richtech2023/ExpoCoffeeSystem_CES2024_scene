import threading
import os
import time
import traceback
import requests

from loguru import logger
from pydantic import BaseModel
from typing import Optional, Literal

from devices.coffee.drive import Communication


def get_devs():
    devs = set()
    for root, dirs, files in os.walk('/dev'):
        if root == '/dev' or root == '/dev/usb':
            logger.debug('{}:{}'.format(root, files))
            for f in files:
                devs.add(os.path.join(root, f))
    return devs


milkshake_Serial_dict = {"J": "H", "K": "G", "L": "F", "M": "E", "N": "D", "O": "C", "P": "B", "Q": "A"}
# Dates（枣）Mango（芒果）Pineapple（菠萝）Strawberry（草莓）Banana（香蕉）Orange（橙子）Apple（苹果）Blueberry（蓝莓）
milkshake_material_list = ["Dates", "Mango", "Pineapple", "Strawberry", "Banana", "Orange", "Apple", "Blueberry"]
# Water Milk Sugar Yogurt Soymilk Almond_milk
milkshake_tap_list = ["Water", "Milk", "Sugar", "Yogurt", "Soymilk", "Almond_milk"]

SUPPORT_ARDUINO_MATERIAL = ['sea_salt_foam', 'coconut_water', 'coconut_milk', 'vanilla_cream', 'fresh_dairy',
                                   'chocolate_syrup', 'cold_coffee', 'vanilla_syrup', 'green_tea_syrup']


class MachineConfig(BaseModel):
    machine: str
    num: int
    arduino_write: Optional[str]  # 向arduino发送什么字符
    arduino_read: Optional[str]  # 从arduino流量列表读取第几个示数
    speed: Optional[float]  # 龙头流速
    delay_time: Optional[int]  # 通过时间控制开关的话，打开时间
    type: Optional[str]  # 类型，根据时间开关为time， 根据流量计开关为volume



class Serial_Pump:

    def open_port_one_by_time(self, open_dict, dev_name):
        """
        一次操作一个龙头
        open_dict: {'material_name': quantity}

        """
        lock = threading.Lock()
        lock.acquire()
        logger.info('open_port_one_by_time get lock')
        logger.info('open_dict is {}'.format(open_dict))

        try:
            machine_config = self.refresh_config()  # 每次使用前，重新读取数据库内容进行刷新
            logger.info('refresh_config get machine_config is {}'.format(machine_config))

            for material, quantity in open_dict.items():
                config = machine_config.get(material)
                if material in SUPPORT_ARDUINO_MATERIAL and quantity > 0:
                    self.send_one_msg(config.arduino_write, dev_name)  # 打开龙头泵
                    time.sleep(quantity)  # 5.2
                    self.send_one_msg(config.arduino_write.lower(), dev_name)
        except Exception as e:
            logger.error(traceback.format_exc())
            get_devs()
            raise e
        finally:
            lock.release()
            self.send_one_msg('i', dev_name)  # 关闭所有龙头
            logger.info('open_port_one_by_time release lock')

    def open_port_together_by_speed(self, open_dict):
        """
        一次性打开所有龙头
        open_dict: {'material_name': quantity}

        """
        lock = threading.Lock()
        lock.acquire()
        logger.info('open_port_together_by_speed get lock')
        logger.info('open_dict is {}'.format(open_dict))
        take_flag = True
        dev_name = "/dev/ttyS0"

        try:
            machine_config = self.refresh_config()  # 每次使用前，重新读取数据库内容进行刷新
            logger.info('refresh_config get machine_config is {}'.format(machine_config))

            opened = []  # 已经打开的龙头列表
            closed = []  # 已经关闭的龙头列表

            for material, quantity in open_dict.items():
                config = machine_config.get(material)
                if quantity > 0:
                    self.send_one_msg(config.arduino_write, dev_name)  # 依次打开龙头
                    opened.append(material)
                    volume = quantity
                    logger.debug('open material {} for {} ml'.format(material, quantity))

            start_time = time.time()  # 打开龙头时间，通过时间控制龙头开关的时候用到

            while len(closed) < len(opened) and take_flag:
                for material, quantity in open_dict.items():
                    config = machine_config.get(material)
                    close_char = chr(ord(str(config.arduino_write)) + 32)  # 大写字符转小写字符
                    if material not in closed:
                        # 只对没有关闭的进行判断
                        if time.time() - start_time >= quantity:
                            # 根据时间判断开关
                            self.send_one_msg(close_char, dev_name)  # 发送英文字符进行关闭
                            closed.append(material)
                            logger.debug('closed {} after {} s'.format(material, config.delay_time))

            # while len(closed) < len(opened) and take_flag:
            #     for material, quantity in open_dict.items():
            #         config = machine_config.get(material)
            #         close_char = chr(ord(str(config.arduino_write)) + 32)  # 大写字符转小写字符
            #         if material not in closed:
            #             # 只对没有关闭的进行判断
            #             if config.type == 'time' and time.time() - start_time >= config.delay_time:
            #                 # 根据时间判断开关
            #                 self.send_one_msg(close_char, dev_name)  # 发送英文字符进行关闭
            #                 closed.append(material)
            #                 logger.debug('closed {} after {} s'.format(material, config.delay_time))
            #             elif config.type == 'speed' and time.time() - start_time >= round(quantity / config.speed, 1):
            #                 # 根据流量计读数判断开关
            #                 self.send_one_msg(close_char, dev_name)  # 发送英文字符进行关闭
            #                 closed.append(material)
            #                 logger.debug('close {} after {} s'.format(material, round(quantity / config.speed), 1))
        except Exception as e:
            logger.error(traceback.format_exc())
            get_devs()
            raise e
        finally:
            lock.release()
            self.send_one_msg('i', dev_name)  # 关闭所有龙头
            take_flag = True
            logger.info('open_port_together_by_speed release lock')

    def send_one_msg(self, char, dev_name):
        fail_count = 0
        for i in range(5):
            try:
                logger.debug('{}th connect in send_one_msg'.format(i + 1))
                ser = Communication(dev_name)
                ser.send_data(char.encode())
                logger.info('send char {}'.format(char))
                # if ser.open_engine():
                #     break
                # time.sleep(1)
            except Exception as e:
                fail_count += 1
                if fail_count >= 5:
                    raise
                time.sleep(1)
            # finally:
            #     if ser.open_engine():
            #         time.sleep(0.5)
            #         ser.close_engine()

        # time.sleep(0.1)
        # if not ser.open_engine():  # Turn on serial port.
        #     ser.open_engine()
        #     logger.info('opened again==========================================================')
        #     time.sleep(1)
        #
        # ser.send_data(char.encode())
        # time.sleep(0.1)
        # logger.info('send char {}'.format(char))

        # if ser.open_engine():
        #     time.sleep(0.5)
        #     ser.close_engine()

    def refresh_config(self):
        # 获取所有machine_config表tap和cup的数据
        url = "http://127.0.0.1:9001/coffee/machine/get"
        res = requests.get(url)
        machine_configs = {}
        if res.status_code == 200:
            machine_configs = res.json()
        machine_dict = {}
        for config in machine_configs:
            if config.get('machine') in ['tap', 'cup']:
                machine_dict[config.get('name')] = MachineConfig(**config)
        return machine_dict

# if __name__ == '__main__':
# Serial_Pump()
# serial = Communication("/dev/ttyUSB1", 57600, 8, 1, 1)
# serial.send_data("B")
# serial.send_data("b")

# serial = Communication("/dev/ttyS0", 57600, 8, 1, 1)
# serial.send_data("K")
# time.sleep(5)
# serial.send_data("k")
# serial.send_data("a")
