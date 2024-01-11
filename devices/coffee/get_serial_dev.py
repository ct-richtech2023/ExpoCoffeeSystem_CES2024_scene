import serial.tools.list_ports

# 获取系统中的串口设备列表
ports = serial.tools.list_ports.comports()

# 遍历串口设备列表并打印设备名称
for port in ports:
    print(port.device)