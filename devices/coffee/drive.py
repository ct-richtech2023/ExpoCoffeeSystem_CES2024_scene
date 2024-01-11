import time

from loguru import logger
import serial.tools.list_ports
# from serial import Serial


class Communication:

    def __init__(self, com_name, baudrate=9600, bytesize=8, stopbits=1, timeout=1):
        self.com_name = com_name
        self.busy_flag = False
        try:
            self.main_engine = serial.Serial(port=self.com_name, baudrate=baudrate,
                                             bytesize=bytesize, stopbits=stopbits, timeout=timeout)
        except Exception as e:
            raise Exception('open {} failed, err={}'.format(self.com_name, str(e)))
        self.print_serial_msg()

    def print_serial_msg(self):
        s = self.main_engine
        logger.info("name={}, port={}, baudrate={}, bytesize={}, parity={}, stopbits={}, timeout={}".format(
            s.name, s.port, s.baudrate, s.bytesize, s.parity, s.stopbits, s.timeout))
        logger.info("writeTimeout={}, xonxoff={}, rtscts={}, dsrdtr={}, interCharTimeout={}".format(
            s.writeTimeout, s.xonxoff, s.rtscts, s.dsrdtr, s.interCharTimeout))

    def open_engine(self):
        self.main_engine.open()

    def close_engine(self):
        # if self.main_engine.is_open:
        #     logger.info('close {}'.format(self.com_name))
        #     self.main_engine.close()
        logger.info('close {}'.format(self.com_name))
        self.main_engine.close()

    @staticmethod
    def available_serial_port():
        return list(serial.tools.list_ports.comports())

    def read_line(self):
        self.wait_busy()
        try:
            self.busy_flag = True
            return self.main_engine.readline()
        finally:
            self.busy_flag = False

    def send_data(self, data):
        self.wait_busy()
        try:
            self.busy_flag = True
            self.main_engine.write(data)
        finally:
            self.busy_flag = False

    def wait_busy(self, timeout=5):
        start_time = time.perf_counter()
        time.sleep(0.1)
        while True:
            current_time = time.perf_counter()
            if self.busy_flag:
                logger.debug('{} now busy, current_time={}'.format(self.com_name, current_time))
                time.sleep(0.5)
            else:
                break
            if current_time - start_time > timeout:
                raise Exception('{} wait busy timeout={}'.format(self.com_name, timeout))


if __name__ == '__main__':
    # test tap
    serial = Communication("/dev/ttyS0", 9600, 8, 1, 1)
    serial.send_data('L'.encode())
    time.sleep(5)
    serial.send_data('l'.encode())

    """
    # Creamer instructions(奶油机指令)
    # RS485    
    # 波特率 38400
    # 开：01 06 00 34 00 01 09 C4 
    # 关：01 06 00 34 00 00 C8 04 
    # b'\x01\x03\x10\x00\x00\x01\x80\xCA'
    """
    # serial = Communication("/dev/ttyUSB0", 38400, 8, 1, 1)
    # serial.send_data(b'\x01\x06\x00\x34\x00\x01\x09\xC4')
    # time.sleep(5)
    # serial.send_data(b'\x01\x06\x00\x34\x00\x00\xC8\x04')

