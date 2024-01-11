import time
from binascii import *

import crcmod
from loguru import logger
from serial import Serial


# from common.myerror import DeviceError


def crc16Add(read):
    crc16 = crcmod.mkCrcFun(0x18005, rev=True, initCrc=0xFFFF, xorOut=0x0000)
    data = read.replace(" ", "")  # 消除空格
    readcrcout = hex(crc16(unhexlify(data))).upper()
    str_list = list(readcrcout)
    # print(str_list)
    if len(str_list) == 5:
        str_list.insert(2, '0')  # 位数不足补0，因为一般最少是5个
    crc_data = "".join(str_list)  # 用""把数组的每一位结合起来  组成新的字符串
    # print(crc_data)
    read = read.strip() + ' ' + crc_data[4:] + ' ' + crc_data[2:4]  # 把源代码和crc校验码连接起来
    # print('CRC16校验:', crc_data[4:] + ' ' + crc_data[2:4])
    # print(read)
    return read


class Conveyer:
    def __init__(self, dev_name):
        self.belt = Serial(dev_name, 19200, timeout=0.1)

    @property
    def speed(self):
        if not self.belt.isOpen():
            self.belt.open()
        self.belt.flushOutput()
        result = self.send_command('01 03 30 06 00 01 6B 0B')  # 读取传送带当前的速度
        # print('in speed, result={}'.format(result))
        try:
            speed = int(result[6:10], 16)
        except Exception as e:
            speed = -1
            logger.error('get speed error, result = {}'.format(result))
        return speed

    def send_command(self, cmd):
        if not self.belt.isOpen():
            self.belt.open()
        logger.info('conveyer send cmd {}'.format(cmd))
        cmd = bytes.fromhex(cmd)
        self.belt.write(cmd)  # 发送指令
        time.sleep(0.1)
        read = self.belt.readall().hex()
        self.belt.close()
        return read

    def start(self, speed=500):
        speed_16 = ('0000' + hex(speed).upper()[2:])[-4:]
        cmd = '01 06 20 01 ' + speed_16[0:2] + ' ' + speed_16[2:4]
        start_cmd = crc16Add(cmd)
        result = self.send_command(start_cmd)
        if result != start_cmd.replace(' ', '').lower():
            print('conveyer start error, result = {}'.format(result))
            # raise Exception('conveyer start error, result = {}'.format(result))

    def stop(self):
        stop_command = '01 06 20 01 00 00 D3 CA'
        result = self.send_command(stop_command)  # 设置速度为0
        if result != stop_command.replace(' ', '').lower():
            print('conveyer stop error, result = {}'.format(result))
            # raise Exception('conveyer stop error, result = {}'.format(result))


class USLSensor:
    """
    超声波传感器
    """

    def __init__(self, dev_name):
        self.sensor = Serial(dev_name, 115200, timeout=0.5)
        if self.read_distance(1) == -1:
            raise Exception('cannot start USLS, please check again')

    def read_distance(self, count=1):
        if not self.sensor.isOpen():
            self.sensor.open()
        distances = []
        try:
            for i in range(count):
                self.sensor.write(bytes.fromhex('01 03 01 01 00 01 D4 36'))  # 发送指令
                read = self.sensor.readall().hex()
                logger.debug('read={}'.format(read))
                logger.debug('read[6:10]={}'.format(read[6:10]))
                distance = int(read[6:10], 16)
                # print('read{}: distance={}'.format(i, distance))
                distances.append(distance)
        except Exception as e:
            logger.error('read distance has error:{}'.format(str(e)))
            return -1
        return round(sum(distances) / count)


class TakeConveyer(Conveyer):

    def __init__(self, belt_dev, sensor_dev):
        super().__init__(belt_dev)
        # self.sensor = Serial(sensor_dev, 115200, timeout=0.5)
        self.sensor = USLSensor(sensor_dev)

    @property
    def distance(self):
        return self.sensor.read_distance()
        # return 180 - self.sensor.read_distance()

# if __name__ == '__main__':
    # take_transer = TakeConveyer('/dev/ttyCV1', '/dev/ttyCV0')
    #put_transer = Conveyer('/dev/ttyUSB0')

    # logger.info('step 1, start with speed=100')
    # take_transer.start(500)
    # for i in range(3):
    #     if take_transer.speed != 0:
    #         logger.error('where\'s my cup!')
    #         time.sleep(2)
    #     else:
    #         break
    # take_transer.stop()
    # print('distance = {}'.format(take_transer.distance))
    # time.sleep(0.1)
    # logger.info('step 1, after 0.1s, real speed is {}'.format(take_transer.speed))
    # time.sleep(1)
    # logger.info('step 1, after 1.1s, real speed is {}'.format(take_transer.speed))


    # time.sleep(3)
    # print(put_transer.speed)
    # logger.info('step 1, start with speed=500')
    # put_transer.start(500)
    # time.sleep(5)
    # put_transer.stop()
    # time.sleep(0.1)
    # logger.info('step 1, after 0.1s, real speed is {}'.format(put_transer.speed))
    # time.sleep(1)
    # logger.info('step 1, after 1.1s, real speed is {}'.format(put_transer.speed))
    #
    # usls = USLSensor('/dev/ttyCV0')
    # start = time.time()
    # print(usls.read_distance(2))
    # end = time.time()
    # print(end - start)
    
