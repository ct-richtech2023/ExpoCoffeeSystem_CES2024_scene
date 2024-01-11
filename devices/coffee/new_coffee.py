import serial
import time
import logging
#from common.db.crud import coffee as coffee_crud
from loguru import logger



# 串口设置
# port = 'COM8'
port = "/dev/ttyS3"
baudrate = 57600

# 咖啡机从机地址
slave_address = 0x01

# 功能码
read_registers_func_code = 0x03
write_register_func_code = 0x06

# 寄存器地址 制作饮品
coffee_control_register = 0x2000
# 关机，重启
coffee_control_register_B = 0x200B
# 冲洗
coffee_control_register_C = 0x200C
# 取消
coffee_control_register_E = 0x200E

# 寄存器值：制作第一个咖啡
# coffee_ui_position = 0x0000
# coffee_ui_position = 0x0011
# 意式、美式、卡布奇洛、拿铁、热牛奶、热水
coffee_ui_position_list = [0x0001, 0x0004, 0x0005, 0x0006, 0x0011, 0x0015]
coffee_ui_position_all_list = [0x0001, 0x0002, 0x0003, 0x0004, 0x0005, 0x0006, 0x0007, 0x0008, 0x0009, 0x000a, 0x000b,
                               0x000c, 0x000d, 0x000e, 0x000f, 0x0010, 0x0011, 0x0012, 0x0013, 0x0014, 0x0015]

# 0xFF 对应十进制数值 255  空闲状态
# 第一个0，就是状态码
# [0, 0, 0, 0, 0, 0, 0, 0]


error_dict = {'1': '主板故障', '2': '锅炉温度过高', '3': '电热盘温度过高', '4': '锅炉温度过低', '5': '电热盘温度过低',
              '6': '锅炉加热过快', '7': '电热盘加热过快', '8': '锅炉加热过慢', '9': '电热盘加热过慢',
              '10': '锅炉不继续加热', '11': '加热盘不继续加热', '12': '水源温度检测组件异', '13': '混水阀异常',
              '25': '左磨豆组异常', '26': '右磨豆组异常', '63': '异常开机', '78': '锅炉不继续加热',
              '307': '推粉电机异常', '400': '咖啡水路异常', '401': '蒸汽水路异常', '402': '冲泡器异常',
              '403': '咖啡分向阀异常', '404': '蒸汽分向阀异常', '405': '搅拌器异常', '406': '左推粉电机异常',
              '407': '右推粉电机异常', '14': '屏幕未关闭', '15': '水箱丢失', '16': '蓄水盘丢失', '17': '渣盒丢失',
              '18': '左豆仓丢失', '19': '右豆仓丢失', '20': '左粉仓丢失', '21': '右粉仓丢失', '22': '牛奶组件不在位',
              '23': '水箱低水位', '24': '清空蓄水盘', '27': '左豆仓无豆', '28': '右豆仓无豆', '29': '左粉仓无粉',
              '30': '右粉仓无粉', '31': '使用牛奶温度高', '32': '使用牛奶温度低', '33': '请安装冲泡器',
              '70': '请连接牛奶', '75': '清空渣盒', '76': '水桶组件通讯异常', '79': '水箱低水位\n', '80': '冰箱不在位',
              '81': '冰箱左侧奶盒缺奶', '82': '冰箱右侧奶盒缺奶', '85': '糖浆机不在位', '600': '咖啡系统温度低',
              '601': '蒸汽系统温度低', '200': '咖啡系统水路警告', '201': '蒸汽系统水路警告', '202': '冲泡器行程警告',
              '203': '冲泡器内粉量警告', '204': '咖啡分向阀警告', '205': '蒸汽分向阀警告', '56': '搅拌器警告',
              '57': '左粉仓推粉警告', '58': '右粉仓推粉警告', '64': '软件警告', '67': '冲泡器未复位',
              '69': '咖啡渣是否已清空', '77': '水桶组件水路警告', '83': '冰箱#1', '84': '冰箱#2', '86': '糖浆机#1',
              '87': '糖浆机#2', '88': '糖浆机#3', '89': '糖浆机#4', '306': '粉仓推粉警告'}


# CRC16校验函数
def calculate_crc16(data):
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
def read_registers(serial_port, address, count):
    request = bytearray([slave_address, read_registers_func_code])
    request.extend(address.to_bytes(2, 'big'))
    request.extend(count.to_bytes(2, 'big'))
    request.extend(calculate_crc16(request))
    serial_port.write(request)
    time.sleep(0.1)  # 等待响应数据返回
    response = serial_port.read_all()
    return response


# 写单个寄存器数据
def write_register(serial_port, address, value):
    request = bytearray([slave_address, write_register_func_code])
    #print(f'request0 {request}')
    request.extend(address.to_bytes(2, 'big'))
    #print(f'request1 {request}')
    request.extend(value.to_bytes(2, 'big'))
    #print(f'request2 {request}')
    request.extend(calculate_crc16(request))
    #print('\x01\x03\x10\x00\x00\x01\x80\xca\\') #(b'\x01\x06 \x00\x00\x01C\xca')
    #print(f'request3 {request}')
    serial_port.write(request)
    #serial_port.write(b'\x01\x06\x20\x00\x00\x06\x02\08')
    # serial_port.write(bytes.fromhex("0106200000060208"))
    #serial_port.write(bytes.fromhex("01031000000180CA"))
    #serial_port.flush()
    time.sleep(0.1)  # 等待响应数据返回
    response = serial_port.read_all()
    #response = serial_port.readline()
    return response




#----------------------------------------------------------------------------
# 打开串口
#ser = serial.Serial(port, baudrate)

#a = b'\x01\x03\x10\x00\x00\x01\x80\xCA'
#ser.write(a)
#time.sleep(0.1)  # 等待响应数据返回
#response1 = ser.read_all()
#print(f'send {a}')
#print(f'status_response : {response1}')

#b = b'\x01\x03\x10\x01\x00\x08\x11\x0C'
#ser.write(b)
#time.sleep(0.1)  # 等待响应数据返回
#response2 = ser.read_all()
#print(f'send {b}')
#print(f'error_response : {response2}')
# 关闭串口
#ser.close()

#ser = serial.Serial(port, baudrate)

#a = b'\x01\x03\x10\x00\x00\x01\x80\xCA'
#ser.write(a)
#time.sleep(0.1) # 等待响应数据返回
#response1 = ser.read_all()
#print(f'send {a}')
#print(f'status_response : {response1}')

#b = b'\x01\x03\x10\x01\x00\x08\x11\x0C'
#ser.write(b)
#time.sleep(0.1) # 等待响应数据返回
#response2 = ser.read_all()
#print(f'send {b}')
#print(f'error_response : {response2}')
#----------------------------------------------------------------------------


# 打开串口
#ser = serial.Serial(port, baudrate)

# #检查咖啡机状态和故障
#status_response = read_registers(ser, 0x1000, 1)
#error_response = read_registers(ser, 0x1001, 8)

#status = int.from_bytes(status_response[3:5], 'big')
#errors = [int.from_bytes(error_response[i+3:i+5], 'big') for i in range(8)]

#print(f'status_response: {status_response}')
#print(f'error_response: {error_response}')

#print(f'status: {status}')
#print(f'errors: {errors}')

# # print(hex(status))

# # if status == 0x1:
# #    print("init status ")

# # result_list = coffee_crud.get_machine_states_by_id()
# # print(result_list)
# if status == 0xFF and all(error == 0 for error in errors):
#     # 咖啡机处于空闲状态且无故障，开始制作咖啡
#     coffee_ui_position = 0x0000
#     start_coffee = 0x2000
#write_register(ser, coffee_control_register_B, start_coffee)
#     print("制作第一个咖啡")

# # 关闭串口
# ser.close()











# 打开串口
ser = serial.Serial(port, baudrate)
#ser.close()
#ser.open()
retuun = write_register(ser, coffee_control_register, 0x0000)

print(f'write return: {retuun}')
#logger = get_logger()

#while True:
#    num = 1
#    for coffee_ui_position in coffee_ui_position_list:
#        is_error = True
#        while is_error:
#            # 检查咖啡机状态和故障
#            status_response = read_registers(ser, 0x1000, 1)
#            error_response = read_registers(ser, 0x1001, 8)

#            status = int.from_bytes(status_response[3:5], 'big')
#            errors = [int.from_bytes(error_response[i + 3:i + 5], 'big') for i in range(8)]
#            print(status_response)
#            print(status)
#            print(errors)
#             logger.info(f"获取机器状态码：{status}")
#             logger.info(f"获取机器状态：{errors[0]}")

#            for error_id, errors_name in error_dict.items():
#                if int(errors[0]) == int(error_id):
#                     logger.info(f"机器故障：{errors_name}")
#                    time.sleep(5)

#                if status == 0xFF and all(error == 0 for error in errors):
#                 # 咖啡机处于空闲状态且无故障，开始制作咖啡
#                 logger.info("咖啡机故障已解决")
#                 logger.info("咖啡机处于空闲状态且无故障，开始制作咖啡")
#                    is_error = False
#                    write_register(ser, coffee_control_register, coffee_ui_position)
#         logger.info(f"正在制作第{num}杯")

# 关闭串口
ser.close()
