import serial
import time
from loguru import logger
from copy import deepcopy
import requests
import serial.tools.list_ports
from common.api import AudioInterface


class CoffeeError(Exception):
    pass


class Coffee_Driver:
    def __init__(self, device=None):
        self.last_status = {'system_status': 'UNKNOWN'}
        self.baudrate = 57600
        # 咖啡机从机地址
        self.slave_address = 0x01
        # 功能码
        self.read_registers_func_code = 0x03
        self.write_register_func_code = 0x06
        # 意式、美式、卡布奇洛、拿铁、热牛奶、热水
        self.coffee_ui_position_list = [0x0001, 0x0004, 0x0005, 0x0006, 0x0011, 0x0015]
        self.coffee_ui_position_all_list = [0x0000, 0x0001, 0x0002, 0x0003, 0x0004, 0x0005, 0x0006, 0x0007, 0x0008,
                                            0x0009,
                                            0x000a, 0x000b, 0x000c, 0x000d, 0x000e, 0x000f, 0x0010, 0x0011, 0x0012,
                                            0x0013, 0x0014, 0x0015, 0x0016, 0x0017, 0x0018, 0x0019, 0x001A, 0x001B,
                                            0x001C, 0x001D, 0x001E, 0x001F, 0x0020, 0x0021, 0x0022, 0x0023, 0x0024,
                                            0x0025, 0x0026, 0x0027, 0x0028, 0x0029, 0x002A, 0x002B, 0x002C, 0x002D,
                                            0x002E, 0x002F, 0x0030, 0x0031, 0x0032, 0x0033, 0x0034, 0x0035, 0x0036,
                                            0x0037, 0x0038, 0x0039, 0x003A]
        self.machine_states_state_dict = {}
        self.machine_states_error_dict = {}
        self.refresh_config()
        self.serial = None
        if device:
            self.serial = self.connect_device_name(device)
        else:
            self.serial = self.check_coffee_port()

    def connect_device_name(self, name, raise_flag=True):
        fail_count = 0
        for i in range(5):
            try:
                logger.info('{}th connect in connect_device_name'.format(i + 1))
                self.serial = serial.Serial(name, self.baudrate)
                logger.info('open {} success'.format(name))
                value = self.query_status()
                if not value:
                    raise Exception("Although open {} success, but can't query coffee status, check next!".format(name))
            except Exception as e:
                fail_count += 1
                if raise_flag:
                    raise Exception(str(e))
                else:
                    logger.warning(str(e))
            else:
                logger.info('open coffee COM success, it is {}!'.format(name))
                return self.serial

    def check_coffee_port(self):
        port_list = list(serial.tools.list_ports.comports())
        port_name_list = [port_info.device for port_info in port_list]
        for name in port_name_list:
            result = self.connect_device_name(name, raise_flag=False)
            if result:
                return result
        else:
            err_msg = 'already check all devices={}, but no one is coffee device'.format(port_name_list)
            logger.error(err_msg)
            raise Exception(err_msg)

    def get_register_adress(self, code):
        coffee_control_register = None
        if code == "A":
            # 寄存器地址 制作饮品
            coffee_control_register = 0x2000
        elif code == "B":
            # 关机，重启
            coffee_control_register = 0x200B
        elif code == "C":
            # 冲洗
            coffee_control_register = 0x200C
        elif code == "E":
            # 取消
            coffee_control_register = 0x200E
        return coffee_control_register if coffee_control_register else None

    # CRC16校验函数
    def calculate_crc16(self, data):
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return crc.to_bytes(2, 'little')

    # 读取多个寄存器数据
    def read_registers(self, serial_port, address, count):
        request = bytearray([self.slave_address, self.read_registers_func_code])
        request.extend(address.to_bytes(2, 'big'))
        request.extend(count.to_bytes(2, 'big'))
        request.extend(self.calculate_crc16(request))
        serial_port.write(request)
        time.sleep(0.1)  # 等待响应数据返回
        response = serial_port.read_all()
        return response

    # 写单个寄存器数据
    def write_register(self, serial_port, address, value):
        request = bytearray([self.slave_address, self.write_register_func_code])
        request.extend(address.to_bytes(2, 'big'))
        request.extend(value.to_bytes(2, 'big'))
        request.extend(self.calculate_crc16(request))
        serial_port.write(request)
        time.sleep(0.1)  # 等待响应数据返回
        response = serial_port.read_all()
        return response

    def query_status(self):
        logger.info("into query_status")
        status_response = self.read_registers(self.serial, 0x1000, 1)
        error_response = self.read_registers(self.serial, 0x1001, 8)

        if status_response == '' and error_response == '':
            # 咖啡机连接失败，通信为空
            return self.last_status
            # raise Exception('cannot get msg from coffee machine, please check it')

        status = int.from_bytes(status_response[3:5], 'big')
        errors = [int.from_bytes(error_response[i + 3:i + 5], 'big') for i in range(8)]
        logger.debug(f"status: {status}, errors: {errors}")
        status_dict = {}
        if status in self.machine_states_state_dict:
            status_dict["status_code"] = status
            status_dict["status"] = self.machine_states_state_dict.get(status, "")
        else:
            if 4096 <= status <= 8191:
                status_dict["status_code"] = status
                status_dict["status"] = "Beverage preparation in progress"
            elif 8192 <= status <= 12287:
                status_dict["status_code"] = status
                status_dict["status"] = "Clearing fault reset"
        if errors[0] in self.machine_states_error_dict:
            status_dict["error_code"] = errors[0]
            status_dict["error"] = self.machine_states_error_dict.get(errors[0], "")
        # logger.debug(f"status_dict: {status_dict}")
        return status_dict

    def refresh_config(self):
        url = "http://127.0.0.1:9001/coffee/machine/get_all_machine_states"
        start_time = time.time()
        machine_states_list = []

        while time.time() - start_time < 100:  # Try for up to 2 minutes
            try:
                res = requests.get(url)
                if res.status_code == 200:
                    machine_configs = res.json()
                    machine_states_list = machine_configs.get("data",[])
                    if machine_states_list:
                        break  # Break the loop if data is received
            except requests.RequestException as e:
                logger.error("Request failed:", e)
            time.sleep(5)  # Wait for 5 seconds before retrying

        for machine_states in machine_states_list:
            if machine_states["category"] == "State":
                if machine_states["return_id"] not in ["0x1000~0x1FFF", "0x2000~0x2FFF"]:
                    return_id = int(machine_states["return_id"], 16)
                    self.machine_states_state_dict[return_id] = machine_states["content"]
            elif machine_states["category"] in ["ERROR", "Sensor warning", "Alarm requires confirmation"]:
                return_id = int(machine_states["return_id"])
                self.machine_states_error_dict[return_id] = machine_states["content"]

    def send_control_message(self, code, control_content):
        logger.info("into send_control_message")
        coffee_control_register = self.get_register_adress(code)
        if coffee_control_register is None:
            return "Unable to obtain the register address"
        self.write_register(self.serial, coffee_control_register, control_content)
        time.sleep(2)
        status_dict = self.query_status()
        logger.info(f"already send control_content:{control_content}, status:{status_dict}")
        return status_dict

    def make_coffee(self, make_content):
        # make_content = self.coffee_ui_position_all_list[int(make_content)]
        logger.info(f'into make_coffee')
        make_content = int(f'0x{make_content:04X}', 16)
        logger.info(f'start make coffee,make_content:{make_content}')
        self.send_control_message('A', make_content)
        time.sleep(5)
        result = self.wait_until_completed(make_content)
        return result

    def cancel_make(self):
        logger.warning('cancel make coffee')
        self.send_control_message('E', 0x0000)

    def select_clean(self, code):
        """
        0x0001：冲泡器冲洗
        0x0002：奶沫器冲洗
        0x0003：粉料混合器冲洗
        0x0004：内部奶管冲洗
        0x0005：智能冲洗（只冲洗需要的部件）
        0x0006：外部奶管冲洗
        """
        logger.debug('select clean')
        clean_code = None
        if code == 1:
            clean_code = 0x0001
        elif code == 2:
            clean_code = 0x0002
        elif code == 3:
            clean_code = 0x0003
        elif code == 4:
            clean_code = 0x0004
        elif code == 5:
            clean_code = 0x0005
        elif code == 6:
            clean_code = 0x0006
        if clean_code:
            self.send_control_message('C', clean_code)

    def wait_until_completed(self, make_content):
        """
        等待制作完成
        """
        start_time = time.time()
        logger.info("into wait_until_completed")
        while True:
            status_dict = self.query_status()
            status_code = status_dict.get('status_code')
            status = status_dict.get('status')
            error_code = status_dict.get('error_code', '')
            error = status_dict.get('error', '')
            if error:
                # 制作过程中有报错信息，立刻抛出异常
                logger.error(error)
                if error_code in [15, 16, 17, 18, 19, 20, 21, 23, 24, 25, 26, 29, 30, 75]:
                    AudioInterface.gtts(f"error is {error},Wait 5 minutes")
                    start_time = time.time()
                    wait_num = 0
                    while True:
                        if wait_num > 30:
                            raise CoffeeError(
                                f'Failed to make coffee. The coffee machine error is {error}')
                        time.sleep(10)
                        wait_num += 1
                        logger.info(f"waiting process error ,time:{wait_num * 10}")
                        status_dict = self.query_status()
                        logger.info(f"status_dict:{status_dict}")
                        status_code = status_dict.get('status_code')
                        status = status_dict.get('status')
                        error_code = status_dict.get('error_code', '')
                        error = status_dict.get('error', '')
                        if status_code == 255 and error_code == '':
                            logger.debug('Preparing to remake coffee')
                            # self.make_coffee(make_content)
                            # self.send_control_message('A', make_content)
                            start_time = time.time()
                            break
                    continue

            # 制作过程中，如果状态是255 且无error就退出循环，否则一直等待
            if status_code == 255 and error_code in ['', 27, 28]:
                logger.debug('no making status in {}'.format(status))
                break
            if time.time() - start_time > 5 * 60:
                raise CoffeeError(f'Failed to make coffee. The coffee machine error is {error}')
            time.sleep(1)
        return True

