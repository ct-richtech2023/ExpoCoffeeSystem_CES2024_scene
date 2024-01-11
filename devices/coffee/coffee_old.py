from copy import deepcopy
import time

from loguru import logger
import requests

from .constant import SERIAL_CONFIG, COFFEE_STATUS, MachineStatus
from .drive import Communication

FORMULA = {
    #     drinkType: 饮品类型,1-8
    #     volume: 咖啡量: 15-240 / 0
    #     coffeeTemperature: 咖啡温度 0/1/2 低/中/高
    #     concentration: 咖啡浓度 0/1/2 清淡/适中/浓郁
    #     hotWater: 热水量
    #     waterTemperature: 热水温度 0/1/2 低/中/高
    #     hotMilk: 牛奶时间 5-120 / 0
    #     foamTime: 奶沫时间  5-120 / 0
    #     precook: 预煮 1/0 是/否
    #     moreEspresso: 咖啡增强 1/0 是/否
    #     coffeeMilkTogether: 咖啡牛奶同时出 1/0 是/否
    #     adjustOrder: 出品顺序 1/0 0：先奶后咖啡/1：先咖啡后奶
    "hot water": {
        "drinkType": 3, "volume": 0, "coffeeTemperature": 0, "concentration": 0, "hotWater": 1.00,
        "waterTemperature": 2, "hotMilk": 0, "foamTime": 0, "precook": 0, "moreEspresso": 0,
        "coffeeMilkTogether": 0, "adjustOrder": 0},
    "espresso": {
        "drinkType": 1, "volume": 0.35, "coffeeTemperature": 2, "concentration": 0, "hotWater": 0,
        "waterTemperature": 0, "hotMilk": 0, "foamTime": 0, "precook": 1, "moreEspresso": 0,
        "coffeeMilkTogether": 0, "adjustOrder": 0},
    "americano": {
        "drinkType": 2, "volume": 0.3478, "coffeeTemperature": 2, "concentration": 1, "hotWater": 0.6522,
        "waterTemperature": 2, "hotMilk": 0, "foamTime": 0, "precook": 1, "moreEspresso": 0,
        "coffeeMilkTogether": 0, "adjustOrder": 0},
    "cappuccino": {
        "drinkType": 4, "volume": 0.1739, "coffeeTemperature": 2, "concentration": 0, "hotWater": 0,
        "waterTemperature": 0, "hotMilk": 0.0304, "foamTime": 0.1087, "precook": 1, "moreEspresso": 0,
        "coffeeMilkTogether": 1, "adjustOrder": 0},
    "latte": {
        "drinkType": 6, "volume": 0.35, "coffeeTemperature": 2, "concentration": 1, "hotWater": 0,
        "waterTemperature": 0, "hotMilk": 0.034, "foamTime": 0.0870, "precook": 1, "moreEspresso": 0,
        "coffeeMilkTogether": 1, "adjustOrder": 0},
    "flat white": {
        "drinkType": 5, "volume": 0.3043, "coffeeTemperature": 2, "concentration": 0, "hotWater": 0,
        "waterTemperature": 0, "hotMilk": 0.0652, "foamTime": 0.0435, "precook": 1, "moreEspresso": 0,
        "coffeeMilkTogether": 1, "adjustOrder": 0},
    "hot milk": {
        "drinkType": 7, "volume": 0, "coffeeTemperature": 0, "concentration": 0, "hotWater": 0,
        "waterTemperature": 0, "hotMilk": 0.1740, "foamTime": 0, "precook": 0, "moreEspresso": 0,
        "coffeeMilkTogether": 0, "adjustOrder": 0},
    "italian espresso": {
        "drinkType": 1, "volume": 0.5217, "coffeeTemperature": 2, "concentration": 2, "hotWater": 0,
        "waterTemperature": 0, "hotMilk": 0, "foamTime": 0, "precook": 0, "moreEspresso": 0,
        "coffeeMilkTogether": 0, "adjustOrder": 0},
    "italian-style macchiato": {
        "drinkType": 1, "volume": 0.1957, "coffeeTemperature": 2, "concentration": 0, "hotWater": 0,
        "waterTemperature": 0, "hotMilk": 0.2173, "foamTime": 0.0435, "precook": 0, "moreEspresso": 0,
        "coffeeMilkTogether": 0, "adjustOrder": 0},
}


class AnalyzeStatus:
    def __init__(self, coffee_status):
        self.coffee_status = coffee_status
        self.useful_value = self.get_useful_value()

    def get_useful_value(self):
        if isinstance(self.coffee_status, bytes):
            self.coffee_status = bytes.decode(self.coffee_status)
        if ':0105' != self.coffee_status[:5]:
            raise Exception("'{}' is not coffee status, must start with ':0105'".format(self.coffee_status))
        if r'\r\n' != self.coffee_status[-4:]:
            raise Exception(r'coffee status not have \r\n, status={}'.format(self.coffee_status))
        return self.coffee_status[5:5 + 21]

    @property
    def system_status(self):
        value = self.useful_value[0]
        return COFFEE_STATUS['system_status'].get(value, 'unknown system status')

    @property
    def make_status(self):
        value = self.useful_value[4:7 + 1]
        which = COFFEE_STATUS['make_status']['type'].get(value[0], 'undefined')
        status = COFFEE_STATUS['make_status']['status'].get(value[1], 'undefined')
        progress = COFFEE_STATUS['make_status']['progress'].get(value[2], 'undefined')
        return {'type': which, 'status': status, 'progress': progress}

    @property
    def current_progress(self):
        value = self.useful_value[8:11 + 1]
        return int(value, 16)

    @property
    def expect_progress(self):
        value = self.useful_value[12:15 + 1]
        return int(value, 16)

    @property
    def error_msg(self):
        value = self.useful_value[16:19 + 1]
        bin_str = bin(int(value, 16)).replace('0b', '')
        bin_str = bin_str.zfill(16)
        bin_str = bin_str[::-1]
        error_list = []
        for i, value in enumerate(bin_str):
            if value == '1':
                error_list.append(COFFEE_STATUS['error_msg'][str(i)])
        return error_list

    @property
    def error_code(self):
        value = self.useful_value[16:19 + 1]
        bin_str = bin(int(value, 16)).replace('0b', '')
        bin_str = bin_str.zfill(16)
        bin_str = bin_str[::-1]
        error_list = []
        for i, value in enumerate(bin_str):
            if value == '1':
                error_list.append(str(i))
        return error_list

    @property
    def assure_msg(self):
        value = self.useful_value[20]
        bin_str = bin(int(value, 16)).replace('0b', '')
        bin_str = bin_str.zfill(4)
        assure_list = []
        for i, value in enumerate(bin_str):
            if value == '1':
                assure_list.append(COFFEE_STATUS['assure_msg'][str(i)])
        return assure_list

    @property
    def status(self):
        coffee_status = {'system_status': self.system_status}
        if self.useful_value[0] == '8':
            coffee_status['make_status'] = self.make_status
            coffee_status['progress'] = "{}/{}".format(self.current_progress, self.expect_progress)
        error_msg = self.error_msg
        error_code = self.error_code
        assure_msg = self.assure_msg
        if error_msg:
            coffee_status['error_msg'] = error_msg
        if error_code:
            coffee_status['error_code'] = error_code
        if assure_msg:
            coffee_status['assure_msg'] = assure_msg
        return coffee_status


class CoffeeError(Exception):
    pass


class CoffeeDriver:
    def __init__(self, device=None):
        self.last_status = {'system_status': 'UNKNOWN'}
        if device:
            self.serial = self.connect_device_name(device)
        else:
            self.serial = self.check_coffee_port()

    def check_coffee_port(self):
        port_list = Communication.available_serial_port()
        port_name_list = [port_info.device for port_info in port_list]
        for name in port_name_list:
            result = self.connect_device_name(name, raise_flag=False)
            if result:
                return result
        else:
            err_msg = 'already check all devices={}, but no one is coffee device'.format(port_name_list)
            logger.error(err_msg)
            raise Exception(err_msg)

    def connect_device_name(self, name, raise_flag=True):
        try:
            self.serial = Communication(name, **SERIAL_CONFIG)
            logger.info('open {} success'.format(name))
            value = self.query_status()
            if not value:
                raise Exception("Although open {} success, but can't query coffee status, check next!".format(name))
        except Exception as e:
            if raise_flag:
                raise Exception(str(e))
            else:
                logger.warning(str(e))
        else:
            logger.info('open coffee COM success, it is {}!'.format(name))
            return self.serial

    @staticmethod
    def get_lrc_code(input_str: str) -> int:
        def char_2_hex(value: str):
            value = value.upper()
            num = ord(value)
            if num < ord('A'):
                return num & 0x0f
            else:
                return num - 0x37

        def two_char2_hex(str1):
            num = char_2_hex(str1[0]) << 4
            num += char_2_hex(str1[1])
            return num & 0xff

        lrc = 0
        if len(input_str) % 2 != 0:
            input_str = input_str + '0'
        length = len(input_str)
        for i in range(length // 2):
            m = two_char2_hex(input_str[2 * i:2 * (i + 1)])
            lrc += m
            lrc = lrc & 0xff
        lrc = 0xff - lrc + 1
        return lrc

    def _base_command(self, str1):
        str1 = '01' + str1
        lrc = self.get_lrc_code(str1)
        lrc_hex = '{:02x}'.format(lrc)
        # lrc_hex = hex(lrc).replace('0x', '')
        content = (str1 + lrc_hex).upper()
        return r":{}\r\n".format(content)

    def function_message(self):
        pass

    def send_control_message(self, control_command, control_content):
        control = control_command + control_content
        msg = self._base_command(control)
        logger.debug('send kalerm control message, length={}, content={}'.format(len(msg), msg))
        self.serial.send_data(msg.encode())
        return_value = self.serial.read_line()
        logger.debug('{} return value：{}'.format(self.serial.com_name, return_value))
        return return_value

    @staticmethod
    def format_hex(num, length):
        content = '{:#x}'.format(int(num)).replace('0x', '')
        content = content.zfill(length)
        return content

    def clean_the_brewer(self):
        logger.debug('clean the brewer')
        self.send_control_message('04', '0001010A')

    def clean_the_milk_froth(self):
        logger.debug('clean the milk froth')
        self.send_control_message('04', '0001040A')

    def query_status(self, pass_null=False):
        logger.debug('query coffee status')
        value = self.send_control_message('05', '0000000D')
        logger.info("value is {}".format(value))
        try:
            temp_value = bytes.decode(value)
        except Exception as e:
            return self.last_status
        if temp_value == '' and not pass_null:
            # 咖啡机连接失败，通信为空
            # return self.last_status
            raise Exception('cannot get msg from coffee machine, please check it')
        # 对状态值进行校验
        lrc = self.get_lrc_code(temp_value[1:-6])
        lrc_hex = '{:02x}'.format(lrc)
        check = lrc_hex.upper()
        if check != temp_value[-6:-4] or len(temp_value) > 35:
            # 校验失败，状态值有误，丢弃
            logger.warning(
                'check fail, pass. value={}, value[1:-6]={}, check={}'.format(temp_value, temp_value[1:-6], check))
            return self.last_status
        else:
            try:
                analyze_status = AnalyzeStatus(value).status
                logger.debug('current coffee status is {}'.format(analyze_status))
                self.last_status = analyze_status
                return analyze_status
            except Exception as e:
                return self.last_status

    def cancel_make(self):
        logger.warning('cancel make coffee')
        self.send_control_message('03', '0001000C')

    def confirm_put_the_cup(self):
        logger.debug('confirm put the cup')
        self.send_control_message('06', '0001')

    def make_k95_coffee(self):
        logger.warning('make k95 coffee')
        raise Exception('not support k95 coffee, please modify coffee make wat in machine!')

    # def make_coffee(self, formula_name: str):
    #     formula_number = [number for number, name in FORMULA.items() if name == formula_name]
    #     if not formula_number:
    #         raise Exception('not support formula={}, support is {}'.format(formula_name, list(FORMULA.values())))
    #     content = self.format_hex(formula_number[0], 4)
    #     self.send_control_message('01', content)

    def get_control_content(self, value_dict):
        if 1 <= value_dict['drinkType'] <= 8:
            drink_type_hex = self.format_hex(value_dict['drinkType'], 2)
        else:
            raise Exception('drink type should be 1~8, now is {}'.format(value_dict['drinkType']))

        if 15 <= value_dict['volume'] <= 240 or value_dict['volume'] == 0:
            pass
        else:
            raise Exception('coffee volume should be 15~240 or 0, now is {}'.format(value_dict['volume']))

        if value_dict['coffeeTemperature'] not in range(3):
            raise Exception('coffee temperature level should be 0~2, now is {}'.format(value_dict['coffeeTemperature']))

        if value_dict['concentration'] not in range(3):
            raise Exception('coffee concentration level should be 0~2, now is {}'.format(value_dict['concentration']))

        if 25 <= value_dict['hotWater'] <= 450 or value_dict['hotWater'] == 0:
            pass
        else:
            raise Exception('hotWater volume should be 25~450 or 0, now is {}'.format(value_dict['hotWater']))

        if value_dict['waterTemperature'] not in range(3):
            raise Exception('water temperature level should be 0~2, now is {}'.format(value_dict['waterTemperature']))

        if 5 <= value_dict['hotMilk'] <= 120 or (value_dict['hotMilk'] == 0 and value_dict['drinkType'] not in [6, 7]):
            pass
        else:
            raise Exception('hot Milk time should be 5~120 or 0, now is {}'.format(value_dict['hotMilk']))

        if 5 <= value_dict['foamTime'] <= 120 or value_dict['foamTime'] == 0:
            pass
        else:
            raise Exception('foam time should be 5~120 or 0, now is {}'.format(value_dict['foamTime']))

        if value_dict['precook'] not in range(2):
            raise Exception('precook should be 0~1, now is {}'.format(value_dict['precook']))

        if value_dict['moreEspresso'] not in range(2):
            raise Exception('moreEspresso should be 0~1, now is {}'.format(value_dict['moreEspresso']))

        if value_dict['coffeeMilkTogether'] not in range(2):
            raise Exception('coffeeMilkTogether should be 0~1, now is {}'.format(value_dict['coffeeMilkTogether']))

        if value_dict['adjustOrder'] not in range(2):
            raise Exception('adjustOrder should be 0~1, now is {}'.format(value_dict['adjustOrder']))

        volume_hex = self.format_hex(value_dict['volume'], 4)
        hot_water_hex = self.format_hex(value_dict['hotWater'], 4)
        water_temperature_hex = self.format_hex(value_dict['waterTemperature'], 2)
        hot_mike_hex = self.format_hex(value_dict['hotMilk'], 2)
        foam_time_hex = self.format_hex(value_dict['foamTime'], 2)

        coffee_temperature_hex = self.format_hex(value_dict['coffeeTemperature'], 2)
        concentration_hex = self.format_hex(value_dict['concentration'], 2)
        precook_hex = self.format_hex(value_dict['precook'], 2)
        moreespresso_hex = self.format_hex(value_dict['moreEspresso'], 2)
        coffee_milk_together_hex = self.format_hex(value_dict['coffeeMilkTogether'], 2)
        adjustorder_hex = self.format_hex(value_dict['adjustOrder'], 2)
        content = drink_type_hex + volume_hex + coffee_temperature_hex + concentration_hex \
                  + hot_water_hex + water_temperature_hex + hot_mike_hex + foam_time_hex + precook_hex \
                  + moreespresso_hex + coffee_milk_together_hex + adjustorder_hex
        return content

    def make_coffee(self, formula_name: str, cup_capacity: int):
        formula = deepcopy(FORMULA[formula_name])
        formula['volume'] = int(round(cup_capacity * formula['volume']))
        formula['hotWater'] = int(round(cup_capacity * formula['hotWater']))
        formula['hotMilk'] = int(round(cup_capacity * formula['hotMilk']))
        formula['foamTime'] = int(round(cup_capacity * formula['foamTime']))
        logger.info('name={}, formula={}'.format(formula_name, formula))
        content = self.get_control_content(formula)
        logger.info('send to coffee content={}, cup_capacity={}'.format(content, cup_capacity))
        return_value = self.send_control_message('02', content)
        return True if b':010200' in return_value else False


    def make_coffee_from_dict(self, make_dict):
        """
        发送制作指令
        """
        wait_time = 0
        logger.info("make_dict is {}".format(make_dict))
        while check_status := self.query_status():
            if err := check_status.get('error_msg', []):
                # 制作前系统有错误信息，直接抛出异常
                if len(err) == 1 and COFFEE_STATUS.get('error_msg', {}).get('11') in err:
                    call_gtts(err[0])
                    return False
                raise Exception('Sorry, {}'.format(','.join(err)))
            if check_status.get('system_status') != MachineStatus.idle:
                # 制作前检查咖啡机状态,必须为idle
                logger.error('coffee machine is {} now, waiting idle status'.format(check_status.get('system_status')))
                time.sleep(1)
                wait_time += 1
                if wait_time > 600:
                    raise Exception('has wait 10 minutes before make coffee, please check first')
            else:
                logger.info("It broke!")
                break

        content = self.get_control_content(make_dict)
        logger.info('send to coffee content={}, dict={}'.format(content, make_dict))
        # 发送制作指令
        return_value = self.send_control_message('02', content)
        if return_value == b'':
            return True
        if b':010200' not in return_value:
            raise CoffeeError('send command error, please check! cmd={}, return_value={}'.format(content, return_value))
            # pass

        return True

    def wait_until_completed(self):
        """
        等待制作完成
        """
        try:
            while status_msg := self.query_status(pass_null=True):
                status = status_msg.get('system_status')
                error_msg = status_msg.get('error_msg', [])
                # 制作过程中，如果不是making状态就退出循环，否则一直等待
                if status != MachineStatus.making:
                    break
                if error_msg:
                    # 制作过程中有报错信息，立刻抛出异常
                    # raise Exception('make error! status_msg={}'.format(status_msg))
                    make_error = error_msg
                    logger.warning(error_msg)
                time.sleep(1)
            after_status = self.query_status()
            if after_status.get('system_status') != MachineStatus.idle:
                # 制作完成后，咖啡机必须为idle状态
                raise CoffeeError('Sorry, making failed, status is {}'.format(after_status))
            err = after_status.get('error_msg', [])
            if len(err) == 1 and COFFEE_STATUS.get('error_msg', {}).get('11') in err:
                call_gtts(err[0])
        except CoffeeError as e:
            raise e
        except Exception as e:
            logger.error(str(e))

        return True

def call_gtts(text):
    params = {'text': text, 'sync': False}
    url = "http://127.0.0.1:9004/audio/gtts"
    try:
        res = requests.post(url, params=params, timeout=1)
        logger.info('url={} params={}, result={}'.format(url, params, res.content))
    except Exception as e:
        pass

# if __name__ == '__main__':
#     # print(FORMULA.keys())
#     coffee_driver = CoffeeDriver('/dev/ttyUSB0')
#     print(coffee_driver.last_status)
#     # print(coffee_driver.query_status())
#     # coffee_driver.clean_the_brewer()
#     # coffee_driver.clean_the_milk_froth()
#     # coffee_driver.confirm_put_the_cup()
#     make_coffee = {
#         "drinkType": 1, "volume": 60, "coffeeTemperature": 2, "concentration": 1, "hotWater": 0,
#         "waterTemperature": 0, "hotMilk": 0, "foamTime": 0, "precook": 0, "moreEspresso": 0,
#         "coffeeMilkTogether": 0, "adjustOrder": 1}
#     hot_water = {
#         "drinkType": 3, "volume": 0, "coffeeTemperature": 0, "concentration": 0, "hotWater": 50,
#         "waterTemperature": 2, "hotMilk": 0, "foamTime": 0, "precook": 0, "moreEspresso": 0,
#         "coffeeMilkTogether": 0, "adjustOrder": 0}
#     coffee_driver.make_coffee_from_dict(make_coffee)
#     # while True:
#     #     # 制作过程中，如果是making状态就一直等待
#     #     status_msg = coffee_driver.query_status()
#     #     status = status_msg.get('system_status')
#     #     error_msg = status_msg.get('error_msg', [])
#     #     if status != MachineStatus.making:
#     #         break
#     #     if error_msg:
#     #         raise Exception('make error! status={}'.format(status))
#     #     time.sleep(1)
#     # for i in range(20):
#     #     coffee_driver.query_status()
#     #     time.sleep(1)
#     # if coffee_driver.query_status().get('system_status') != MachineStatus.idle:
#     #     # 制作完成后，咖啡机必须为idle状态
#     #     raise Exception('Sorry coffee making failed, status is {}'.format(
#     #         coffee_driver.query_status()))
#     # for i in range(3):
#         # if i == 2:
#         #     coffee_driver.cancel_make()
#         # print(coffee_driver.query_status())
#         # time.sleep(1)
