import os
import threading
import time
import traceback
from copy import deepcopy

from loguru import logger

from common import utils
from common.define import AdamTaskStatus, Arm
from common.api import AudioInterface
from common.db.crud import adam as adam_crud
from common.db.database import MySuperContextManager
from business import Adam


def dance_random(adam: Adam, choice):
    default_speed = 600

    def dance1():
        # hi
        AudioInterface.music('hi.mp3')
        adam.right.set_position(x=156.8, y=-708, z=1256, roll=-1.7, pitch=-11.9, yaw=175, speed=800, wait=True)
        adam.check_adam_status("dance1", AdamTaskStatus.dancing)
        for i in range(4):
            adam.right.set_position(x=149, y=-402, z=1185, roll=27.7, pitch=-11.2, yaw=175, speed=800,
                                    wait=False)
            adam.right.set_position(x=156.8, y=-708, z=1256, roll=-1.7, pitch=-11.9, yaw=175, speed=800,
                                    wait=False)
        adam.right.set_servo_angle(angle=[-132.32, 8.69, -34.49, 45.93, 42.84, 38.71], speed=40, wait=True)
        adam.check_adam_status("dance1", AdamTaskStatus.dancing)

    def dance2():
        # heart
        AudioInterface.music('whistle.mp3')
        adam.env.adam.set_servo_angle(
            left={'angle': [141.3, 17.2, -41.7, -58.5, 71.1, -24.1], 'speed': 50, 'wait': True},  # init
            right={'angle': [-141.3, 17.2, -41.7, 58.5, 71.1, 24.1], 'speed': 50, 'wait': True}
        )
        adam.check_adam_status("dance2", AdamTaskStatus.dancing)

        adam.env.adam.set_position(
            left={'x': 0, 'y': 60, 'z': 930, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 450, 'wait': True},
            right={'x': 0, 'y': -60, 'z': 930, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 200, 'wait': True}
        )
        adam.check_adam_status("dance2", AdamTaskStatus.dancing)

        for i in range(3):
            adam.check_adam_status("dance2", AdamTaskStatus.dancing)
            adam.env.adam.set_position(
                left={'x': 0, 'y': 160, 'z': 930, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 350,
                      'wait': False},
                right={'x': 0, 'y': 40, 'z': 930, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 350,
                       'wait': False}
            )
            adam.env.adam.set_position(
                left={'x': 0, 'y': -40, 'z': 930, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 350,
                      'wait': False},
                right={'x': 0, 'y': -160, 'z': 930, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 350,
                       'wait': False}
            )

        adam.env.adam.set_position(
            left={'x': 0, 'y': 60, 'z': 930, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 250, 'wait': True},
            right={'x': 0, 'y': -60, 'z': 930, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 250, 'wait': True}
        )
        adam.check_adam_status("dance2", AdamTaskStatus.dancing)

        adam.env.adam.set_servo_angle(
            left={'angle': [148.5, 20, -46.3, -52.1, 74.7, -23.9], 'speed': 20, 'wait': True},
            right={'angle': [-148.5, 20, -46.3, 52.1, 74.7, 23.9], 'speed': 27, 'wait': True},
        )
        adam.check_adam_status("dance2", AdamTaskStatus.dancing)

    def dance3():
        # cheer

        def get_position_value(position, **kwargs):
            v = ['x', 'y', 'z', 'roll', 'pitch', 'yaw']
            value = dict(zip(v, position))
            kwargs.setdefault('speed', 1000)
            kwargs.setdefault('mvacc', 1000)
            return dict(value, **kwargs)

        def set_adam_position(point_name, left_speed=None, right_speed=None, wait=False, mvacc=None, radius=10):
            left_speed = left_speed or default_speed
            right_speed = right_speed or default_speed
            left = get_position_value(data[Arm.left][point_name]['position'],
                                      wait=wait, radius=radius, speed=left_speed, mvacc=mvacc)
            right = get_position_value(data[Arm.right][point_name]['position'],
                                       wait=wait, radius=radius, speed=right_speed, mvacc=mvacc)
            adam.env.adam.set_position(left, right)

        def get_next_point_speed(point_name):
            left_p, right_p = adam.env.adam.position
            [x1, y1, z1] = left_p[:3]
            [x2, y2, z2] = data[Arm.left][point_name]['position'][:3]
            left_d = ((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2) ** 0.5
            [x1, y1, z1] = right_p[:3]
            [x2, y2, z2] = data[Arm.right][point_name]['position'][:3]
            right_d = ((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2) ** 0.5
            if left_d > right_d:
                s = int(left_d / right_d * default_speed)
                return default_speed, s
            else:
                s = int(left_d / right_d * default_speed)
                return s, default_speed

        data = utils.read_resource_json('/adam/data/dance.json')
        AudioInterface.music('wa.mp3')

        set_adam_position('zero', wait=True)
        adam.check_adam_status("dance3", AdamTaskStatus.dancing)
        # 同时运动到挥手位置
        left_speed, right_speed = get_next_point_speed('huang-you')
        set_adam_position('huang-you', left_speed=left_speed, right_speed=right_speed)
        adam.check_adam_status("dance3", AdamTaskStatus.dancing)
        # 左右挥手
        start_hui_time = time.perf_counter()
        for i in range(3):
            adam.check_adam_status("dance3", AdamTaskStatus.dancing)
            set_adam_position('huang-zuo', left_speed=1000, right_speed=1000, mvacc=1000)
            set_adam_position('huang-you', left_speed=1000, right_speed=1000, mvacc=1000)
        set_adam_position('huang-you', wait=True)
        adam.check_adam_status("dance3", AdamTaskStatus.dancing)
        logger.info('hui-show used time={}'.format(time.perf_counter() - start_hui_time))
        # 挥手后回到初始位置
        left_speed, right_speed = get_next_point_speed('zero')
        set_adam_position('zero', left_speed=left_speed, right_speed=right_speed, wait=True)
        adam.check_adam_status("dance3", AdamTaskStatus.dancing)

    def dance4():
        logger.info('dance4!!!')
        AudioInterface.music('YouNeverCanTell.mp3')
        for i in range(4):
            # 两者手臂左右晃动

            adam.env.adam.set_position(
                right={'x': 310, 'y': -550, 'z': 250, 'roll': 11, 'pitch': 90, 'yaw': 11, 'speed': 400,
                       'wait': True},
                left={'x': 310, 'y': 550, 'z': 250, 'roll': -11, 'pitch': 90, 'yaw': -11, 'speed': 400,
                      'wait': True}
            )
            adam.check_adam_status("dance4", AdamTaskStatus.dancing)

            for i in range(3):
                adam.env.adam.set_position(  #
                    right={'x': 336, 'y': -187, 'z': 631, 'roll': -33, 'pitch': -4, 'yaw': -42, 'speed': 400,
                           'wait': False},
                    left={'x': 336, 'y': 247, 'z': 521, 'roll': 33, 'pitch': 4, 'yaw': 42, 'speed': 400,
                          'wait': True}
                )
                adam.check_adam_status("dance4", AdamTaskStatus.dancing)
                adam.env.adam.set_position(
                    right={'x': 336, 'y': -247, 'z': 521, 'roll': -33, 'pitch': -4, 'yaw': -42, 'speed': 400,
                           'wait': False},
                    left={'x': 336, 'y': 187, 'z': 631, 'roll': 33, 'pitch': 4, 'yaw': 42, 'speed': 400,
                          'wait': True}
                )
                adam.check_adam_status("dance4", AdamTaskStatus.dancing)
            # 胸前两只手臂左右摇晃
            adam.env.adam.set_position(
                right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 400,
                       'wait': True},
                left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 400,
                      'wait': True}
            )
            adam.check_adam_status("dance4", AdamTaskStatus.dancing)

            adam.env.adam.set_position(
                left={'x': 395, 'y': 105, 'z': 763, 'roll': 0, 'pitch': 0, 'yaw': -90, 'speed': 400,
                      'wait': False},
                right={'x': 395, 'y': -105, 'z': 763, 'roll': -0, 'pitch': 0, 'yaw': 90, 'speed': 400,
                       'wait': True}
            )
            adam.check_adam_status("dance4", AdamTaskStatus.dancing)

            for i in range(3):
                adam.env.adam.set_position(  #
                    right={'x': 395, 'y': -300, 'z': 863, 'roll': 0, 'pitch': -40, 'yaw': 90, 'speed': 400,
                           'wait': False},
                    left={'x': 395, 'y': -10, 'z': 763, 'roll': 0, 'pitch': 40, 'yaw': -90, 'speed': 400,
                          'wait': True}
                )
                adam.check_adam_status("dance4", AdamTaskStatus.dancing)
                adam.env.adam.set_position(
                    right={'x': 395, 'y': 10, 'z': 763, 'roll': 0, 'pitch': 40, 'yaw': 90, 'speed': 400,
                           'wait': False},
                    left={'x': 395, 'y': 300, 'z': 863, 'roll': 0, 'pitch': -40, 'yaw': -90, 'speed': 400,
                          'wait': True}
                )
                adam.check_adam_status("dance4", AdamTaskStatus.dancing)

            adam.env.adam.set_position(
                right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 400,
                       'wait': False},
                left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 400,
                      'wait': True}
            )
            adam.check_adam_status("dance4", AdamTaskStatus.dancing)
            # 动作剪刀手
            for i in range(3):
                adam.env.adam.set_position(
                    left={'x': 395, 'y': 107, 'z': 429, 'roll': -70, 'pitch': 82, 'yaw': -154, 'speed': 400,
                          'wait': False},
                    right={'x': 283, 'y': -107, 'z': 830, 'roll': 34, 'pitch': 10, 'yaw': 177, 'speed': 400,
                           'wait': True}
                )
                adam.check_adam_status("dance4", AdamTaskStatus.dancing)
                adam.env.adam.set_position(
                    right={'x': 395, 'y': -107, 'z': 429, 'roll': 70, 'pitch': 82, 'yaw': 154, 'speed': 400,
                           'wait': False},
                    left={'x': 283, 'y': 107, 'z': 830, 'roll': -34, 'pitch': 0, 'yaw': -177, 'speed': 400,
                          'wait': True}
                )
                adam.check_adam_status("dance4", AdamTaskStatus.dancing)

    def dance5():
        logger.info('dance5!!!')

        adam.env.adam.set_tcp_offset(dict(offset=[0] * 6), dict(offset=[0] * 6))
        adam.env.adam.set_state(dict(state=0), dict(state=0))
        default_speed = 600
        start_time = time.perf_counter()

        left_angles, right_angles = adam.get_initial_position()
        logger.info('left_angles={}, right_angles={}'.format(left_angles, right_angles))
        adam.env.adam.set_servo_angle(dict(angle=left_angles, speed=20, wait=True),
                                      dict(angle=right_angles, speed=20, wait=True))
        AudioInterface.music('dance.mp3')

        def get_position_value(position, **kwargs):
            v = ['x', 'y', 'z', 'roll', 'pitch', 'yaw']
            value = dict(zip(v, position))
            kwargs.setdefault('speed', 1000)
            kwargs.setdefault('mvacc', 1000)
            return dict(value, **kwargs)

        def set_adam_position(point_name, left_speed=None, right_speed=None, wait=False, mvacc=None, radius=10):
            left_speed = left_speed or default_speed
            right_speed = right_speed or default_speed
            left = get_position_value(data[Arm.left][point_name]['position'],
                                      wait=wait, radius=radius, speed=left_speed, mvacc=mvacc)
            right = get_position_value(data[Arm.right][point_name]['position'],
                                       wait=wait, radius=radius, speed=right_speed, mvacc=mvacc)
            adam.env.adam.set_position(left, right)

        def get_next_point_speed(point_name):
            left_p, right_p = adam.env.adam.position
            [x1, y1, z1] = left_p[:3]
            [x2, y2, z2] = data[Arm.left][point_name]['position'][:3]
            left_d = ((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2) ** 0.5
            [x1, y1, z1] = right_p[:3]
            [x2, y2, z2] = data[Arm.right][point_name]['position'][:3]
            right_d = ((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2) ** 0.5
            if left_d > right_d:
                s = int(left_d / right_d * default_speed)
                return default_speed, s
            else:
                s = int(left_d / right_d * default_speed)
                return s, default_speed

        data = utils.read_resource_json('/adam/data/dance1.json')
        for i in range(6):
            adam.check_adam_status("dance5", AdamTaskStatus.dancing)
            # 回到舞蹈初始点
            set_adam_position('zero')
            adam.check_adam_status("dance5", AdamTaskStatus.dancing)
            # hello
            adam.env.adam.set_position(None, get_position_value(data[Arm.right]['hello1']['position'], wait=True))
            adam.check_adam_status("dance5", AdamTaskStatus.dancing)
            # hello 2次
            for i in range(2):
                adam.env.adam.set_position(None, get_position_value(data[Arm.right]['hello2']['position']))
                adam.env.adam.set_position(None, get_position_value(data[Arm.right]['hello1']['position']))
                adam.check_adam_status("dance5", AdamTaskStatus.dancing)

            # # 回到舞蹈初始点
            set_adam_position('zero', wait=True)
            adam.check_adam_status("dance5", AdamTaskStatus.dancing)
            # # 同时运动到挥手位置
            left_speed, right_speed = get_next_point_speed('huang-you')
            set_adam_position('huang-you', left_speed=left_speed, right_speed=right_speed)
            adam.check_adam_status("dance5", AdamTaskStatus.dancing)

            # # 左右挥手
            start_hui_time = time.perf_counter()
            for i in range(6):
                set_adam_position('huang-zuo', left_speed=1000, right_speed=1000, mvacc=1000)
                set_adam_position('huang-you', left_speed=1000, right_speed=1000, mvacc=1000)
                adam.check_adam_status("dance5", AdamTaskStatus.dancing)
            set_adam_position('huang-you', wait=True)
            adam.check_adam_status("dance5", AdamTaskStatus.dancing)
            logger.info('hui-show used time={}'.format(time.perf_counter() - start_hui_time))
            # 挥手后回到初始位置
            left_speed, right_speed = get_next_point_speed('zero')
            set_adam_position('zero', left_speed=left_speed, right_speed=right_speed, wait=True)
            adam.check_adam_status("dance5", AdamTaskStatus.dancing)
            # 切菜
            set_adam_position('qian_shen', wait=True)
            adam.check_adam_status("dance5", AdamTaskStatus.dancing)
            fu_du = 50
            for i in range(8):
                left_position = deepcopy(data[Arm.left]['qie-cai']['position'])
                right_position = deepcopy(data[Arm.right]['qie-cai']['position'])
                if i % 2 == 0:
                    left_position[2] += fu_du
                    right_position[2] -= fu_du
                else:
                    left_position[2] -= fu_du
                    right_position[2] += fu_du
                y_pian = [0, -50, -100, -50, 0, 50, 100, 50]
                left_position[1] += y_pian[i]
                right_position[1] += y_pian[i]
                left = get_position_value(left_position, radius=50)
                right = get_position_value(right_position, radius=50)
                adam.env.adam.set_position(left, right)
                adam.check_adam_status("dance5", AdamTaskStatus.dancing)
            # zero
            set_adam_position('zero', wait=True)
            adam.check_adam_status("dance5", AdamTaskStatus.dancing)
            # 画圆
            # 比爱心
            set_adam_position('ai-zhong', left_speed=400, right_speed=400)
            adam.check_adam_status("dance5", AdamTaskStatus.dancing)
            set_adam_position('ai', left_speed=400, right_speed=400)
            adam.check_adam_status("dance5", AdamTaskStatus.dancing)
            # 爱心左右移动
            for i in range(2):
                set_adam_position('ai-left')
                adam.check_adam_status("dance5", AdamTaskStatus.dancing)
                set_adam_position('ai-right')
                adam.check_adam_status("dance5", AdamTaskStatus.dancing)
            # 回到标准爱心位置
            set_adam_position('ai')
            adam.check_adam_status("dance5", AdamTaskStatus.dancing)
            # 回到舞蹈初始点
            set_adam_position('ai-zhong', left_speed=400, right_speed=400)
            adam.check_adam_status("dance5", AdamTaskStatus.dancing)
            set_adam_position('zero', left_speed=400, right_speed=400, wait=True)
            adam.check_adam_status("dance5", AdamTaskStatus.dancing)
            set_adam_position('prepare', wait=True)
            adam.check_adam_status("dance5", AdamTaskStatus.dancing)
            logger.info('dance use_time={}'.format(time.perf_counter() - start_time))

    def dance6():
        logger.info('dance6!!!')
        AudioInterface.music('Saturday_night_fever_dance.mp3')

        for i in range(7):
            # 抱胸姿势
            adam.env.adam.set_position(  #
                right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 800,
                       'wait': False},
                left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 800,
                      'wait': True}
            )
            adam.check_adam_status("dance6", AdamTaskStatus.dancing)
            # 右手胸前摇晃
            for i in range(3):
                adam.right.set_position(x=355, y=-100, z=630, roll=0, pitch=60, yaw=90, speed=800, wait=True)
                adam.check_adam_status("dance6", AdamTaskStatus.dancing)
                adam.right.set_position(x=515, y=-161, z=593, roll=64, pitch=17.7, yaw=126, speed=800, wait=True)
                adam.check_adam_status("dance6", AdamTaskStatus.dancing)

            # 左右手交替胸前摇晃
            for i in range(3):
                adam.env.adam.set_position(
                    right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 800,
                           'wait': False},
                    left={'x': 515, 'y': 161, 'z': 593, 'roll': -64, 'pitch': 17.7, 'yaw': -126, 'speed': 800,
                          'wait': True}
                )
                adam.check_adam_status("dance6", AdamTaskStatus.dancing)
                adam.env.adam.set_position(
                    right={'x': 515, 'y': -161, 'z': 593, 'roll': 64, 'pitch': 17.7, 'yaw': 126, 'speed': 800,
                           'wait': False},
                    left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 800,
                          'wait': True}
                )
                adam.check_adam_status("dance6", AdamTaskStatus.dancing)
            # 两只手交替往前伸出
            for i in range(3):
                adam.env.adam.set_position(
                    left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 800,
                          'wait': False},
                    right={'x': 505, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 800,
                           'wait': True}
                )
                adam.check_adam_status("dance6", AdamTaskStatus.dancing)
                adam.env.adam.set_position(
                    left={'x': 505, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 800,
                          'wait': False},
                    right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 800,
                           'wait': True}
                )
                adam.check_adam_status("dance6", AdamTaskStatus.dancing)
            # 右手挥手
            for i in range(3):
                adam.right.set_position(x=245, y=-437, z=908, roll=22, pitch=-5, yaw=1, speed=800, wait=False)
                adam.right.set_position(x=278, y=-242, z=908, roll=-15, pitch=1, yaw=-1, speed=800, wait=False)
                adam.check_adam_status("dance6", AdamTaskStatus.dancing)

            adam.right.set_position(x=355, y=-100, z=630, roll=0, pitch=60, yaw=90, speed=800, wait=True)
            adam.check_adam_status("dance6", AdamTaskStatus.dancing)

            # 左手挥手
            for i in range(3):
                adam.left.set_position(x=245, y=437, z=908, roll=-22, pitch=-5, yaw=1, speed=800, wait=False)
                adam.left.set_position(x=278, y=242, z=908, roll=15, pitch=1, yaw=-1, speed=800, wait=False)
                adam.check_adam_status("dance6", AdamTaskStatus.dancing)

            adam.env.adam.set_position(
                left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 800,
                      'wait': False},
                right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 800,
                       'wait': True}
            )
            adam.check_adam_status("dance6", AdamTaskStatus.dancing)

    def dance7():
        logger.info('dance9!!!')
        # AudioInterface.music_fade_out('Because_of_You.mp3')
        AudioInterface.music('Because_of_You.mp3')

        for i in range(1):
            right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
            left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
            # 右拍手
            right_Pos1 = {'x': 326, 'y': -320, 'z': 1049, 'roll': 0, 'pitch': 0, 'yaw': 90}
            left_Pos1 = {'x': 326, 'y': -20, 'z': 1049, 'roll': 0, 'pitch': 0, 'yaw': -90}
            right_Pos2 = {'x': 326, 'y': -260, 'z': 1049, 'roll': 0, 'pitch': 0, 'yaw': 90}
            left_Pos2 = {'x': 326, 'y': -80, 'z': 1049, 'roll': 0, 'pitch': 0, 'yaw': -90}
            # 左拍手
            right_Pos3 = {'x': 326, 'y': 20, 'z': 1049, 'roll': 0, 'pitch': 0, 'yaw': 90}
            left_Pos3 = {'x': 326, 'y': 320, 'z': 1049, 'roll': 0, 'pitch': 0, 'yaw': -90}
            right_Pos4 = {'x': 326, 'y': 80, 'z': 1049, 'roll': 0, 'pitch': 0, 'yaw': 90}
            left_Pos4 = {'x': 326, 'y': 260, 'z': 1049, 'roll': 0, 'pitch': 0, 'yaw': -90}
            speed1 = 100
            speed5 = 500

            adam.right.set_position(**right_init, wait=False, speed=speed5, radius=50)
            adam.left.set_position(**left_init, wait=True, speed=speed5, radius=50)
            adam.check_adam_status("dance7", AdamTaskStatus.dancing)

            # 左右肩的上方拍手动作
            # adam.right.set_position(**right_Pos1, wait=False, speed=speed5, radius=50)
            # adam.left.set_position(**left_Pos1, wait=True, speed=speed5, radius=50)
            for _ in range(3):
                adam.right.set_position(**right_Pos1, wait=False, speed=speed5, radius=50)
                adam.left.set_position(**left_Pos1, wait=True, speed=speed5, radius=50)
                adam.check_adam_status("dance7", AdamTaskStatus.dancing)
                adam.right.set_position(**right_Pos2, wait=False, speed=speed5, radius=50)
                adam.left.set_position(**left_Pos2, wait=True, speed=speed5, radius=50)
                adam.check_adam_status("dance7", AdamTaskStatus.dancing)

            adam.right.set_position(**right_init, wait=False, speed=speed5, radius=50)
            adam.left.set_position(**left_init, wait=True, speed=speed5, radius=50)
            adam.check_adam_status("dance7", AdamTaskStatus.dancing)

            for _ in range(3):
                adam.right.set_position(**right_Pos3, wait=False, speed=speed5, radius=50)
                adam.left.set_position(**left_Pos3, wait=True, speed=speed5, radius=50)
                adam.check_adam_status("dance7", AdamTaskStatus.dancing)
                adam.right.set_position(**right_Pos4, wait=False, speed=speed5, radius=50)
                adam.left.set_position(**left_Pos4, wait=True, speed=speed5, radius=50)
                adam.check_adam_status("dance7", AdamTaskStatus.dancing)

            adam.left.set_position(**left_init, wait=False, speed=speed5, radius=50)
            adam.right.set_position(**right_init, wait=True, speed=speed5, radius=50)
            adam.check_adam_status("dance7", AdamTaskStatus.dancing)

            # 敲鼓动作
            right_Pos5 = {'x': 428, 'y': -116, 'z': 378, 'roll': -84, 'pitch': 84, 'yaw': -12}
            left_Pos5 = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
            right_Pos6 = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
            left_Pos6 = {'x': 428, 'y': 116, 'z': 378, 'roll': 84, 'pitch': 84, 'yaw': 12}

            for i in range(5):
                adam.left.set_position(**left_Pos5, wait=False, speed=speed5, radius=50)
                adam.right.set_position(**right_Pos5, wait=True, speed=speed5, radius=50)
                adam.check_adam_status("dance7", AdamTaskStatus.dancing)
                adam.right.set_position(**right_Pos6, wait=False, speed=speed5, radius=50)
                adam.left.set_position(**left_Pos6, wait=True, speed=speed5, radius=50)
                adam.check_adam_status("dance7", AdamTaskStatus.dancing)

            # 左右手交替护胸口
            right_Pos14 = {'x': 441, 'y': -99, 'z': 664, 'roll': 36, 'pitch': 33, 'yaw': 153}
            left_Pos14 = {'x': 555, 'y': 198, 'z': 240, 'roll': 100, 'pitch': 75, 'yaw': 41}

            right_Pos15 = {'x': 274, 'y': -20, 'z': 664, 'roll': 36, 'pitch': 33, 'yaw': 153}

            right_Pos16 = {'x': 555, 'y': -198, 'z': 240, 'roll': -100, 'pitch': 75, 'yaw': -41}
            left_Pos16 = {'x': 441, 'y': 99, 'z': 664, 'roll': -36, 'pitch': 33, 'yaw': -153}

            left_Pos17 = {'x': 274, 'y': 20, 'z': 664, 'roll': -36, 'pitch': 33, 'yaw': -153}

            adam.right.set_position(**right_Pos14, wait=False, speed=speed5, radius=50)
            adam.left.set_position(**left_Pos14, wait=True, speed=speed5, radius=50)
            adam.check_adam_status("dance7", AdamTaskStatus.dancing)
            for i in range(2):
                adam.right.set_position(**right_Pos15, wait=False, speed=speed5, radius=50)
                adam.right.set_position(**right_Pos14, wait=True, speed=speed5, radius=50)
                adam.check_adam_status("dance7", AdamTaskStatus.dancing)
            adam.right.set_position(**right_Pos16, wait=False, speed=speed5, radius=50)
            adam.left.set_position(**left_Pos16, wait=True, speed=speed5, radius=50)
            adam.check_adam_status("dance7", AdamTaskStatus.dancing)
            for i in range(2):
                adam.left.set_position(**left_Pos17, wait=False, speed=speed5, radius=50)
                adam.left.set_position(**left_Pos16, wait=True, speed=speed5, radius=50)
                adam.check_adam_status("dance7", AdamTaskStatus.dancing)
            adam.right.set_position(**right_init, wait=False, speed=speed5, radius=50)
            adam.left.set_position(**left_init, wait=True, speed=speed5, radius=50)
            adam.check_adam_status("dance7", AdamTaskStatus.dancing)

            # # 敲鼓动作
            # right_Pos5 = {'x': 428, 'y': -116, 'z': 378, 'roll': -84, 'pitch': 84, 'yaw': -12}
            # left_Pos5 = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
            # right_Pos6 = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
            # left_Pos6 = {'x': 428, 'y': 116, 'z': 378, 'roll': 84, 'pitch': 84, 'yaw': 12}
            #
            # for i in range(3):
            #     adam.left.set_position(**left_Pos5, wait=False, speed=speed1, radius=50)
            #     adam.right.set_position(**right_Pos5, wait=True, speed=speed1, radius=50)
            #     adam.check_adam_status("dance7", AdamTaskStatus.dancing)
            #     adam.right.set_position(**right_Pos6, wait=False, speed=speed1, radius=50)
            #     adam.left.set_position(**left_Pos6, wait=True, speed=speed1, radius=50)
            #     adam.check_adam_status("dance7", AdamTaskStatus.dancing)

            # 敬礼动作
            right_angle1 = [-59.2, -16.7, -35.8, 126.4, -2.1, -20.5]
            left_angle1 = [152.4, 1, -31.9, -27.6, 8.1, -53.1]
            right_angle2 = [-152.4, 1, -31.9, 27.6, 8.1, 53.1]
            left_angle2 = [59.2, -16.7, -35.8, -126.4, -2.1, 20.5]
            for i in range(3):
                adam.left.set_servo_angle(angle=left_angle1, speed=90, wait=False)
                adam.right.set_servo_angle(angle=right_angle1, speed=90, wait=True)
                adam.check_adam_status("dance7", AdamTaskStatus.dancing)
                adam.left.set_servo_angle(angle=left_angle2, speed=90, wait=False)
                adam.right.set_servo_angle(angle=right_angle2, speed=90, wait=True)
                adam.check_adam_status("dance7", AdamTaskStatus.dancing)

            # 加油
            adam.right.set_position(**right_init, wait=False, speed=speed5, radius=50)
            adam.left.set_position(**left_init, wait=True, speed=speed5, radius=50)
            adam.check_adam_status("dance7", AdamTaskStatus.dancing)
            right_Pos7 = {'x': 400, 'y': -100, 'z': 1000, 'roll': 0, 'pitch': 0, 'yaw': 90}
            left_Pos7 = {'x': 400, 'y': 100, 'z': 1000, 'roll': 0, 'pitch': 0, 'yaw': -90}
            right_Pos8 = {'x': 400, 'y': -100, 'z': 850, 'roll': 0, 'pitch': 0, 'yaw': 90}
            left_Pos8 = {'x': 400, 'y': 100, 'z': 850, 'roll': 0, 'pitch': 0, 'yaw': -90}
            adam.right.set_position(**right_Pos7, wait=True, speed=speed5, radius=50)
            adam.check_adam_status("dance7", AdamTaskStatus.dancing)
            adam.right.set_position(**right_Pos8, wait=True, speed=speed5, radius=50)
            adam.check_adam_status("dance7", AdamTaskStatus.dancing)
            adam.left.set_position(**left_Pos7, wait=True, speed=speed5, radius=50)
            adam.check_adam_status("dance7", AdamTaskStatus.dancing)
            adam.left.set_position(**left_Pos8, wait=True, speed=speed5, radius=50)
            adam.check_adam_status("dance7", AdamTaskStatus.dancing)

            # 逆时针画圈
            right_pos_A = {'x': 500, 'y': -100, 'z': 850, 'roll': 0, 'pitch': 0, 'yaw': 90}
            left_pos_A = {'x': 500, 'y': 100, 'z': 850, 'roll': 0, 'pitch': 0, 'yaw': -90}
            right_pos_B = [440, -40, 850, 0, 0, 90]
            right_pos_C = [440, -160, 850, 0, 0, 90]
            adam.right.set_position(**right_pos_A, speed=100, wait=False)
            adam.right.move_circle(right_pos_B, right_pos_C, percent=300, speed=100, wait=False)
            adam.right.move_circle(right_pos_C, right_pos_B, percent=300, speed=100, wait=False)
            adam.check_adam_status("dance7", AdamTaskStatus.dancing)
            # 顺时针画圈
            left_pos_B = [440, 160, 850, 0, 0, -90]
            left_pos_C = [440, 40, 850, 0, 0, -90]
            adam.left.set_position(**left_pos_A, speed=100, wait=False)
            adam.left.move_circle(left_pos_B, left_pos_C, percent=300, speed=100, wait=False)
            adam.left.move_circle(left_pos_C, left_pos_B, percent=300, speed=100, wait=False)
            adam.check_adam_status("dance7", AdamTaskStatus.dancing)

            # 亚当肚子前方拍手动作
            right_Pos11 = {'x': 724, 'y': -137, 'z': 514, 'roll': 90, 'pitch': 0, 'yaw': 90}
            left_Pos11 = {'x': 724, 'y': 137, 'z': 514, 'roll': -90, 'pitch': 0, 'yaw': -90}
            right_Pos12 = {'x': 724, 'y': -80, 'z': 514, 'roll': 90, 'pitch': 0, 'yaw': 90}
            left_Pos12 = {'x': 724, 'y': 80, 'z': 514, 'roll': -90, 'pitch': 0, 'yaw': -90}
            for _ in range(5):
                adam.right.set_position(**right_Pos11, wait=False, speed=speed5, radius=50)
                adam.left.set_position(**left_Pos11, wait=True, speed=speed5, radius=50)
                adam.check_adam_status("dance7", AdamTaskStatus.dancing)
                adam.right.set_position(**right_Pos12, wait=False, speed=speed5, radius=50)
                adam.left.set_position(**left_Pos12, wait=True, speed=speed5, radius=50)
                adam.check_adam_status("dance7", AdamTaskStatus.dancing)

            # 上下搓手
            right_Pos14 = {'x': 724, 'y': -80, 'z': 564, 'roll': 90, 'pitch': 0, 'yaw': 90}
            left_Pos14 = {'x': 724, 'y': 80, 'z': 464, 'roll': -90, 'pitch': 0, 'yaw': -90}
            right_Pos15 = {'x': 724, 'y': -80, 'z': 464, 'roll': 90, 'pitch': 0, 'yaw': 90}
            left_Pos15 = {'x': 724, 'y': 80, 'z': 564, 'roll': -90, 'pitch': 0, 'yaw': -90}
            for _ in range(3):
                adam.right.set_position(**right_Pos14, wait=False, speed=speed1, radius=50)
                adam.left.set_position(**left_Pos14, wait=False, speed=speed1, radius=50)
                adam.right.set_position(**right_Pos15, wait=False, speed=speed1, radius=50)
                adam.left.set_position(**left_Pos15, wait=False, speed=speed1, radius=50)
                adam.check_adam_status("dance7", AdamTaskStatus.dancing)

            adam.right.set_position(**right_Pos12, wait=False, speed=speed5, radius=50)
            adam.left.set_position(**left_Pos12, wait=True, speed=speed5, radius=50)
            adam.check_adam_status("dance7", AdamTaskStatus.dancing)

            # 一个手和两个手往前指
            adam.right.set_position(**right_init, wait=False, speed=speed5, radius=50)
            adam.left.set_position(**left_init, wait=True, speed=speed5, radius=50)
            adam.check_adam_status("dance7", AdamTaskStatus.dancing)
            right_Pos13 = {'x': 817, 'y': -118, 'z': 646, 'roll': 90, 'pitch': 0, 'yaw': 90}
            left_Pos13 = {'x': 817, 'y': 118, 'z': 646, 'roll': -90, 'pitch': 0, 'yaw': -90}

            adam.right.set_position(**right_Pos13, wait=True, speed=speed5, radius=50)
            adam.check_adam_status("dance7", AdamTaskStatus.dancing)
            adam.left.set_position(**left_Pos13, wait=True, speed=speed5, radius=50)
            adam.check_adam_status("dance7", AdamTaskStatus.dancing)

            def reduce_sound():
                for i in range(100, -1, -1):
                    os.system(f"amixer set PCM {i}%")
                    time.sleep(0.08)

            def init_adam():
                adam.right.set_position(**right_init, wait=False, speed=100, radius=50)
                adam.left.set_position(**left_init, wait=True, speed=100, radius=50)
                adam.check_adam_status("dance7", AdamTaskStatus.dancing)

            adam.check_adam_status("dance7", AdamTaskStatus.dancing)
            step_thread = [threading.Thread(target=reduce_sound), threading.Thread(target=init_adam)]
            for t in step_thread:
                t.start()
            for t in step_thread:
                t.join()

    def dance8():
        logger.info('dance8!!!')
        # AudioInterface.music('BLACKPINK_Shut_Down.mp3')

        # 抱胸位置
        right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
        left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}

        # 左右手初始位置
        def init_adam(speed):
            adam.right.set_position(**right_init, wait=False, speed=speed, radius=50)
            adam.left.set_position(**left_init, wait=True, speed=speed, radius=50)
            adam.check_adam_status("dance8", AdamTaskStatus.dancing)

        # 平举上
        right_Pos1 = {'x': 380, 'y': -70, 'z': 700, 'roll': -90, 'pitch': 90, 'yaw': 0}
        left_Pos1 = {'x': 380, 'y': 70, 'z': 700, 'roll': 90, 'pitch': 90, 'yaw': 0}
        # 平举下
        right_Pos2 = {'x': 380, 'y': -70, 'z': 450, 'roll': -90, 'pitch': 90, 'yaw': 0}
        left_Pos2 = {'x': 380, 'y': 70, 'z': 450, 'roll': 90, 'pitch': 90, 'yaw': 0}

        # 双手平举
        def raise_down(speed):
            adam.right.set_position(**right_Pos1, wait=False, speed=speed, radius=50)
            adam.left.set_position(**left_Pos1, wait=True, speed=speed, radius=50)
            adam.check_adam_status("dance8", AdamTaskStatus.dancing)
            adam.right.set_position(**right_Pos2, wait=False, speed=speed, radius=50)
            adam.left.set_position(**left_Pos2, wait=True, speed=speed, radius=50)
            adam.check_adam_status("dance8", AdamTaskStatus.dancing)

        # 上下交替
        right_Pos3 = {'x': 480, 'y': -200, 'z': 800, 'roll': 0, 'pitch': 60, 'yaw': 90}
        left_Pos3 = {'x': 480, 'y': 200, 'z': 800, 'roll': 0, 'pitch': 60, 'yaw': -90}

        def alter_up_down(speed):
            adam.right.set_position(**right_Pos3, wait=False, speed=speed, radius=50)
            adam.right.set_position(**right_init, wait=True, speed=speed, radius=50)
            adam.check_adam_status("dance8", AdamTaskStatus.dancing)
            adam.left.set_position(**left_Pos3, wait=False, speed=speed, radius=50)
            adam.left.set_position(**left_init, wait=True, speed=speed, radius=50)
            adam.check_adam_status("dance8", AdamTaskStatus.dancing)

        # 画圆
        def right_round(speed):
            #     right_pos_A = {'x': 700, 'y': -350, 'z': 500, 'roll': 0, 'pitch': 90, 'yaw': 0}
            #     right_pos_B = {'x': 700, 'y': -250, 'z': 400, 'roll': 0, 'pitch': 90, 'yaw': 0}
            #     right_pos_C = {'x': 700, 'y': -450, 'z': 400, 'roll': 0, 'pitch': 90, 'yaw': 0}
            right_pos_A = {'x': 700, 'y': -350, 'z': 500, 'roll': 0, 'pitch': 90, 'yaw': 0}
            right_pos_B = [700, -250, 400, 0, 90, 0]
            right_pos_C = [700, -450, 400, 0, 90, 0]
            adam.right.set_position(**right_pos_A, speed=speed, wait=True)
            adam.check_adam_status("dance8", AdamTaskStatus.dancing)
            adam.right.move_circle(right_pos_B, right_pos_C, percent=200, speed=200, wait=True)
            adam.check_adam_status("dance8", AdamTaskStatus.dancing)

        def left_round(speed):
            left_pos_A = {'x': 700, 'y': 350, 'z': 500, 'roll': 0, 'pitch': 90, 'yaw': 0}
            left_pos_B = [700, 250, 400, 0, 90, 0]
            left_pos_C = [700, 450, 400, 0, 90, 0]
            adam.left.set_position(**left_pos_A, speed=speed, wait=True)
            adam.check_adam_status("dance8", AdamTaskStatus.dancing)
            adam.left.move_circle(left_pos_B, left_pos_C, percent=200, speed=200, wait=True)
            adam.check_adam_status("dance8", AdamTaskStatus.dancing)

        # 加油上
        right_Pos4 = {'x': 30, 'y': -650, 'z': 1250, 'roll': 0, 'pitch': 0, 'yaw': 90}
        left_Pos4 = {'x': 30, 'y': 650, 'z': 1250, 'roll': 0, 'pitch': 0, 'yaw': -90}
        # 加油下
        right_Pos5 = {'x': 30, 'y': -650, 'z': 1100, 'roll': 0, 'pitch': 0, 'yaw': 90}
        left_Pos5 = {'x': 30, 'y': 650, 'z': 1100, 'roll': 0, 'pitch': 0, 'yaw': -90}

        def come_on_right(speed):
            adam.right.set_position(**right_Pos4, wait=False, speed=speed, radius=50)
            adam.right.set_position(**right_Pos5, wait=False, speed=speed, radius=50)
            adam.check_adam_status("dance8", AdamTaskStatus.dancing)

        def come_on_left(speed):
            adam.left.set_position(**left_Pos4, wait=False, speed=speed, radius=50)
            adam.left.set_position(**left_Pos5, wait=False, speed=speed, radius=50)
            adam.check_adam_status("dance8", AdamTaskStatus.dancing)

        # 右上下加油
        right_Pos6 = {'x': 400, 'y': -400, 'z': 1000, 'roll': 0, 'pitch': -20, 'yaw': 90}
        left_Pos6 = {'x': 400, 'y': -200, 'z': 1000, 'roll': 0, 'pitch': 20, 'yaw': -90}

        right_Pos7 = {'x': 400, 'y': -260, 'z': 650, 'roll': 0, 'pitch': -20, 'yaw': 90}
        left_Pos7 = {'x': 400, 'y': -60, 'z': 650, 'roll': 0, 'pitch': 20, 'yaw': -90}

        def right_up_down(speed):
            adam.right.set_position(**right_Pos6, wait=False, speed=speed, radius=50)
            adam.left.set_position(**left_Pos6, wait=False, speed=speed, radius=50)
            adam.right.set_position(**right_Pos7, wait=False, speed=speed, radius=50)
            adam.left.set_position(**left_Pos7, wait=True, speed=speed, radius=50)
            adam.check_adam_status("dance8", AdamTaskStatus.dancing)

        # 左上下加油
        right_Pos8 = {'x': 400, 'y': 200, 'z': 1000, 'roll': 0, 'pitch': 20, 'yaw': 90}
        left_Pos8 = {'x': 400, 'y': 400, 'z': 1000, 'roll': 0, 'pitch': -20, 'yaw': -90}

        right_Pos9 = {'x': 400, 'y': 60, 'z': 650, 'roll': 0, 'pitch': 20, 'yaw': 90}
        left_Pos9 = {'x': 400, 'y': 260, 'z': 650, 'roll': 0, 'pitch': -20, 'yaw': -90}

        def left_up_down(speed):
            adam.right.set_position(**right_Pos8, wait=False, speed=speed, radius=50)
            adam.left.set_position(**left_Pos8, wait=False, speed=speed, radius=50)
            adam.right.set_position(**right_Pos9, wait=False, speed=speed, radius=50)
            adam.left.set_position(**left_Pos9, wait=True, speed=speed, radius=50)
            adam.check_adam_status("dance8", AdamTaskStatus.dancing)

        right_init1 = {'x': 400, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 0, 'yaw': 90}
        left_init1 = {'x': 400, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 0, 'yaw': -90}

        def parallel_init(speed):
            adam.right.set_position(**right_init1, wait=False, speed=speed, radius=50)
            adam.left.set_position(**left_init1, wait=True, speed=speed, radius=50)
            adam.check_adam_status("dance8", AdamTaskStatus.dancing)

        # 削水果
        right_Pos10 = {'x': 580, 'y': -100, 'z': 400, 'roll': -35, 'pitch': 90, 'yaw': 40}
        left_Pos10 = {'x': 580, 'y': 100, 'z': 400, 'roll': 35, 'pitch': 90, 'yaw': -40}

        right_up_Pos1 = {'x': 580, 'y': 0, 'z': 500, 'roll': -35, 'pitch': 90, 'yaw': 40}
        right_down_Pos1 = {'x': 580, 'y': 0, 'z': 300, 'roll': -35, 'pitch': 90, 'yaw': 40}

        left_up_Pos1 = {'x': 580, 'y': 0, 'z': 500, 'roll': 35, 'pitch': 90, 'yaw': -40}
        left_down_Pos1 = {'x': 580, 'y': 0, 'z': 300, 'roll': 35, 'pitch': 90, 'yaw': -40}

        right_front_Pos1 = {'x': 700, 'y': -200, 'z': 500, 'roll': -35, 'pitch': 90, 'yaw': 60}

        left_front_Pos1 = {'x': 700, 'y': 200, 'z': 500, 'roll': 35, 'pitch': 90, 'yaw': -60}

        def peel_fruit(speed):
            adam.right.set_position(**right_Pos10, wait=False, speed=speed, radius=50)
            adam.left.set_position(**left_Pos10, wait=True, speed=speed, radius=50)
            adam.check_adam_status("dance8", AdamTaskStatus.dancing)

        def right_up_left_down(speed):
            adam.left.set_position(**left_down_Pos1, wait=False, speed=speed, radius=50)
            adam.right.set_position(**right_up_Pos1, wait=True, speed=speed, radius=50)
            adam.check_adam_status("dance8", AdamTaskStatus.dancing)
            for _ in range(3):
                adam.right.set_position(**right_front_Pos1, wait=True, speed=speed, radius=50)
                adam.right.set_position(**right_up_Pos1, wait=True, speed=speed, radius=50)
                adam.check_adam_status("dance8", AdamTaskStatus.dancing)

        def left_up_right_down(speed):
            adam.right.set_position(**right_down_Pos1, wait=False, speed=speed, radius=50)
            adam.left.set_position(**left_up_Pos1, wait=True, speed=speed, radius=50)
            adam.check_adam_status("dance8", AdamTaskStatus.dancing)
            for _ in range(3):
                adam.left.set_position(**left_front_Pos1, wait=True, speed=speed, radius=50)
                adam.left.set_position(**left_up_Pos1, wait=True, speed=speed, radius=50)
                adam.check_adam_status("dance8", AdamTaskStatus.dancing)

        # 拉小提琴
        left_Pos_violin1 = {'x': 230, 'y': 250, 'z': 900, 'roll': -30, 'pitch': 30, 'yaw': -150}
        right_Pos_violin1 = {'x': 360, 'y': 230, 'z': 670, 'roll': 30, 'pitch': 45, 'yaw': 150}
        right_Pos_violin2 = {'x': 400, 'y': 170, 'z': 600, 'roll': 30, 'pitch': 45, 'yaw': 150}

        def violin_prepare(speed):
            adam.left.set_position(**left_Pos_violin1, wait=False, speed=speed, radius=50)
            adam.right.set_position(**right_Pos_violin1, wait=True, speed=speed, radius=50)
            adam.check_adam_status("dance8", AdamTaskStatus.dancing)

        def play_violin(speed):
            adam.right.set_position(**right_Pos_violin1, wait=False, speed=speed, radius=50)
            adam.right.set_position(**right_Pos_violin2, wait=False, speed=speed, radius=50)
            adam.check_adam_status("dance8", AdamTaskStatus.dancing)

        right_Pos11 = {'x': 420, 'y': -20, 'z': 600, 'roll': -70, 'pitch': 90, 'yaw': 20}
        left_Pos11 = {'x': 420, 'y': 20, 'z': 600, 'roll': 70, 'pitch': 90, 'yaw': -20}

        right_Pos12 = {'x': 500, 'y': -250, 'z': 300, 'roll': -90, 'pitch': 40, 'yaw': -40}
        left_Pos12 = {'x': 500, 'y': 250, 'z': 300, 'roll': 90, 'pitch': 40, 'yaw': 40}

        def alter_left_right(speed):
            adam.left.set_position(**left_Pos11, wait=False, speed=speed, radius=50)
            adam.right.set_position(**right_Pos12, wait=True, speed=speed, radius=50)
            adam.check_adam_status("dance8", AdamTaskStatus.dancing)
            adam.right.set_position(**right_Pos11, wait=False, speed=speed, radius=50)
            adam.left.set_position(**left_Pos12, wait=True, speed=speed, radius=50)
            adam.check_adam_status("dance8", AdamTaskStatus.dancing)

        speed2 = 200
        speed3 = 300
        speed4 = 400
        speed5 = 500

        violin_prepare(speed2)
        time.sleep(1)
        AudioInterface.music('BLACKPINK_Shut_Down.mp3')

        for _ in range(15):
            play_violin(300)

        adam.right.set_position(**right_Pos_violin2, wait=True, speed=300, radius=50)
        adam.check_adam_status("dance8", AdamTaskStatus.dancing)
        adam.left.set_position(**left_Pos_violin1, wait=True, speed=100, radius=50)
        adam.check_adam_status("dance8", AdamTaskStatus.dancing)
        init_adam(speed5)

        # 平举
        for _ in range(3):
            raise_down(speed5)
        init_adam(speed5)

        # 左上右上交替
        for _ in range(3):
            alter_up_down(speed5)
        init_adam(speed5)

        # 左右加油交替
        for _ in range(2):
            come_on_right(speed4)
        adam.right.set_position(**right_Pos4, wait=True, speed=speed4, radius=50)
        adam.check_adam_status("dance8", AdamTaskStatus.dancing)

        adam.right.set_position(**right_init, wait=False, speed=speed5, radius=50)
        for _ in range(2):
            come_on_left(speed4)
        adam.left.set_position(**left_Pos4, wait=True, speed=speed4, radius=50)
        adam.check_adam_status("dance8", AdamTaskStatus.dancing)

        adam.left.set_position(**left_init, wait=False, speed=speed5, radius=50)
        init_adam(speed5)

        # 画圆
        right_round(speed3)
        init_adam(speed5)
        left_round(speed3)
        init_adam(speed5)

        adam.left.set_position(**left_Pos11, wait=False, speed=250, radius=50)
        adam.right.set_position(**right_Pos12, wait=True, speed=speed4, radius=50)
        adam.check_adam_status("dance8", AdamTaskStatus.dancing)

        for _ in range(2):
            alter_left_right(speed4)

        init_adam(speed5)

        # 左上下加油
        right_up_down(speed4)
        left_up_down(speed4)
        right_up_down(speed4)
        left_up_down(speed4)
        parallel_init(speed4)

        # init_adam(speed2)

        def reduce_sound():
            for i in range(100, -1, -1):
                os.system(f"amixer set PCM {i}%")
                time.sleep(0.08)

        def init_adam():
            adam.right.set_position(**right_init, wait=False, speed=100, radius=50)
            adam.left.set_position(**left_init, wait=True, speed=100, radius=50)
            adam.check_adam_status("dance8", AdamTaskStatus.dancing)

        adam.check_adam_status("dance8", AdamTaskStatus.dancing)
        step_thread = [threading.Thread(target=reduce_sound), threading.Thread(target=init_adam)]
        for t in step_thread:
            t.start()
        for t in step_thread:
            t.join()

        # # 削水果
        # peel_fruit(speed4)
        # right_up_left_down(speed4)
        # peel_fruit(speed4)
        # left_up_right_down(speed4)
        # init_adam(speed4)

    def dance9():
        logger.info('dance9!!!')
        AudioInterface.music('Dance_The_Night.mp3')

        adam.env.adam.set_position(
            left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 500, 'wait': True},
            right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 500, 'wait': True}
        )
        adam.check_adam_status("dance9", AdamTaskStatus.dancing)

        # 波浪 wave
        left_Pos3_1 = {'x': 380, 'y': 330, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': -90}

        right_Pos3_1 = {'x': 380, 'y': 100, 'z': 700, 'roll': 0, 'pitch': 60, 'yaw': 90}

        right_Pos3_2 = {'x': 380, 'y': 100, 'z': 700, 'roll': 0, 'pitch': 45, 'yaw': 90}

        right_Pos3_3 = {'x': 380, 'y': -50, 'z': 700, 'roll': 0, 'pitch': 60, 'yaw': 90}

        right_Pos3_4 = {'x': 380, 'y': -50, 'z': 700, 'roll': 0, 'pitch': 45, 'yaw': 90}

        right_Pos3_5 = {'x': 380, 'y': -200, 'z': 700, 'roll': 0, 'pitch': 60, 'yaw': 90}

        right_Pos3_6 = {'x': 380, 'y': -200, 'z': 700, 'roll': 0, 'pitch': 45, 'yaw': 90}

        left_Pos4_1 = {'x': 380, 'y': -330, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 90}

        right_Pos4_1 = {'x': 380, 'y': -100, 'z': 700, 'roll': 0, 'pitch': 60, 'yaw': -90}

        right_Pos4_2 = {'x': 380, 'y': -100, 'z': 700, 'roll': 0, 'pitch': 45, 'yaw': -90}

        right_Pos4_3 = {'x': 380, 'y': 50, 'z': 700, 'roll': 0, 'pitch': 60, 'yaw': -90}

        right_Pos4_4 = {'x': 380, 'y': 50, 'z': 700, 'roll': 0, 'pitch': 45, 'yaw': -90}

        right_Pos4_5 = {'x': 380, 'y': 200, 'z': 700, 'roll': 0, 'pitch': 60, 'yaw': -90}

        right_Pos4_6 = {'x': 380, 'y': 200, 'z': 700, 'roll': 0, 'pitch': 45, 'yaw': -90}

        def new_pos1(speed):
            adam.right.set_position(**right_Pos3_1, wait=False, speed=speed, radius=50)
            adam.left.set_position(**left_Pos3_1, wait=True, speed=speed, radius=50)
            adam.check_adam_status("dance9", AdamTaskStatus.dancing)
            adam.right.set_position(**right_Pos3_2, wait=False, speed=speed, radius=50)
            adam.right.set_position(**right_Pos3_3, wait=False, speed=speed, radius=50)
            adam.right.set_position(**right_Pos3_4, wait=False, speed=speed, radius=50)
            adam.right.set_position(**right_Pos3_5, wait=False, speed=speed, radius=50)
            adam.right.set_position(**right_Pos3_6, wait=True, speed=speed, radius=50)
            adam.check_adam_status("dance9", AdamTaskStatus.dancing)

        def new_pos2(speed):
            adam.left.set_position(**right_Pos4_1, wait=False, speed=speed, radius=50)
            adam.right.set_position(**left_Pos4_1, wait=True, speed=speed, radius=50)
            adam.check_adam_status("dance9", AdamTaskStatus.dancing)
            adam.left.set_position(**right_Pos4_2, wait=False, speed=speed, radius=50)
            adam.left.set_position(**right_Pos4_3, wait=False, speed=speed, radius=50)
            adam.left.set_position(**right_Pos4_4, wait=False, speed=speed, radius=50)
            adam.left.set_position(**right_Pos4_5, wait=False, speed=speed, radius=50)
            adam.left.set_position(**right_Pos4_6, wait=True, speed=speed, radius=50)
            adam.check_adam_status("dance9", AdamTaskStatus.dancing)

        for _ in range(2):
            new_pos1(200)

        right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
        left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
        adam.left.set_position(**left_init, wait=False, speed=300, radius=50)
        adam.right.set_position(**right_init, wait=True, speed=300, radius=50)
        adam.check_adam_status("dance9", AdamTaskStatus.dancing)

        for _ in range(2):
            new_pos2(200)

        # run
        for i in range(6):
            adam.env.adam.set_position(
                left={'x': 205, 'y': 550, 'z': 250, 'roll': -110, 'pitch': 0, 'yaw': -90, 'speed': 700},
                right={'x': 405, 'y': -550, 'z': 350, 'roll': 70, 'pitch': 0, 'yaw': 90, 'speed': 700}
            )
            adam.check_adam_status("dance9", AdamTaskStatus.dancing)
            adam.env.adam.set_position(
                left={'x': 405, 'y': 550, 'z': 350, 'roll': -70, 'pitch': 0, 'yaw': -90, 'speed': 700},
                right={'x': 205, 'y': -550, 'z': 250, 'roll': 110, 'pitch': 0, 'yaw': 90, 'speed': 700}
            )
            adam.check_adam_status("dance9", AdamTaskStatus.dancing)

        adam.env.adam.set_position(
            left={'x': 305, 'y': 550, 'z': 250, 'roll': -90, 'pitch': 0, 'yaw': -90, 'speed': 500, 'wait': True},
            right={'x': 305, 'y': -550, 'z': 250, 'roll': 90, 'pitch': 0, 'yaw': 90, 'speed': 500, 'wait': True}
        )
        adam.check_adam_status("dance9", AdamTaskStatus.dancing)

        adam.env.adam.set_position(
            left={'x': 500, 'y': 200, 'z': 700, 'roll': 0, 'pitch': 0, 'yaw': -90, 'speed': 500, 'wait': True},
            right={'x': 500, 'y': -200, 'z': 700, 'roll': 0, 'pitch': 0, 'yaw': 90, 'speed': 500, 'wait': True}
        )
        adam.check_adam_status("dance9", AdamTaskStatus.dancing)

        # clap
        for i in range(3):
            adam.env.adam.set_position(
                left={'x': 500, 'y': 50, 'z': 700, 'roll': 0, 'pitch': 0, 'yaw': -90, 'speed': 250},
                right={'x': 500, 'y': -50, 'z': 700, 'roll': 0, 'pitch': 0, 'yaw': 90, 'speed': 250}
            )
            adam.check_adam_status("dance9", AdamTaskStatus.dancing)
            adam.env.adam.set_position(
                left={'x': 500, 'y': 200, 'z': 700, 'roll': 0, 'pitch': 0, 'yaw': -90, 'speed': 250},
                right={'x': 500, 'y': -200, 'z': 700, 'roll': 0, 'pitch': 0, 'yaw': 90, 'speed': 250}
            )
            adam.check_adam_status("dance9", AdamTaskStatus.dancing)

        # heart
        adam.env.adam.set_position(
            left={'x': 300, 'y': 200, 'z': 830, 'roll': 35, 'pitch': 25, 'yaw': -70, 'speed': 500, 'wait': False},
            right={'x': 300, 'y': -200, 'z': 830, 'roll': -35, 'pitch': 25, 'yaw': 70, 'speed': 500, 'wait': False}
        )
        adam.check_adam_status("dance9", AdamTaskStatus.dancing)
        adam.env.adam.set_position(
            left={'x': 0, 'y': 60, 'z': 930, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 500, 'wait': True},
            right={'x': 0, 'y': -60, 'z': 930, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 400, 'wait': True}
        )
        adam.check_adam_status("dance9", AdamTaskStatus.dancing)

        for i in range(6):
            adam.env.adam.set_position(
                left={'x': 0, 'y': 160, 'z': 930, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 200, 'wait': False},
                right={'x': 0, 'y': 40, 'z': 930, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 200, 'wait': False}
            )
            adam.check_adam_status("dance9", AdamTaskStatus.dancing)
            adam.env.adam.set_position(
                left={'x': 0, 'y': -40, 'z': 930, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 200, 'wait': False},
                right={'x': 0, 'y': -160, 'z': 930, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 200, 'wait': False}
            )
            adam.check_adam_status("dance9", AdamTaskStatus.dancing)

        adam.env.adam.set_position(
            left={'x': 0, 'y': 60, 'z': 930, 'roll': 180, 'pitch': -60, 'yaw': -90, 'speed': 250, 'wait': True},
            right={'x': 0, 'y': -60, 'z': 930, 'roll': 180, 'pitch': 60, 'yaw': -90, 'speed': 250, 'wait': True}
        )
        adam.check_adam_status("dance9", AdamTaskStatus.dancing)

        adam.env.adam.set_servo_angle(
            left={'angle': [148.5, 20, -46.3, -52.1, 74.7, -23.9], 'speed': 60, 'wait': True},
            right={'angle': [-148.5, 20, -46.3, 52.1, 74.7, 23.9], 'speed': 70, 'wait': True},
        )
        adam.check_adam_status("dance9", AdamTaskStatus.dancing)

        # move circle
        adam.env.adam.set_position(
            left={'x': 580, 'y': 100, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 0, 'speed': 500, 'wait': True},
            right={'x': 580, 'y': -100, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 180, 'speed': 500, 'wait': True}
        )
        adam.check_adam_status("dance9", AdamTaskStatus.dancing)
        # for i in range(3):
        adam.env.adam.move_circle(
            left={'pose1': [580, 200, 900, 0, 0, 0], 'pose2': [580, 0, 900, 0, 0, 0], 'percent': 300,
                  'speed': 200, 'wait': False},
            right={'pose1': [580, -0, 900, 0, 0, 180], 'pose2': [580, -200, 900, 0, 0, 180], 'percent': 300,
                   'speed': 200, 'wait': False}
        )
        adam.check_adam_status("dance9", AdamTaskStatus.dancing)

        adam.env.adam.set_position(
            left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 500, 'wait': True},
            right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 500, 'wait': True}
        )
        adam.check_adam_status("dance9", AdamTaskStatus.dancing)

        def init_round(speed):
            adam.env.adam.set_position(
                left={'x': 520, 'y': 50, 'z': 530, 'roll': 40, 'pitch': 90, 'yaw': -50, 'speed': speed, 'wait': True},
                right={'x': 520, 'y': -50, 'z': 530, 'roll': -40, 'pitch': 90, 'yaw': 50, 'speed': speed, 'wait': True}
            )
            adam.check_adam_status("dance9", AdamTaskStatus.dancing)

        def right_round(speed, percent):
            # a = {'x': 520, 'y': -50, 'z': 450, 'roll': -40, 'pitch': 90, 'yaw': 50}
            right_pos_A = {'x': 520, 'y': -50, 'z': 530, 'roll': -40, 'pitch': 90, 'yaw': 50}
            right_pos_B = [600, -50, 450, -40, 90, 50]
            right_pos_C = [440, -50, 450, -40, 90, 50]
            adam.right.set_position(**right_pos_A, speed=speed, wait=True)
            adam.check_adam_status("dance9", AdamTaskStatus.dancing)
            adam.right.move_circle(right_pos_B, right_pos_C, percent=percent, speed=300, wait=True)
            adam.check_adam_status("dance9", AdamTaskStatus.dancing)

        def left_round(speed, percent):
            left_pos_A = {'x': 520, 'y': 50, 'z': 530, 'roll': 40, 'pitch': 90, 'yaw': -50}
            left_pos_B = [600, 50, 450, 40, 90, -50]
            left_pos_C = [440, 50, 450, 40, 90, -50]
            adam.left.set_position(**left_pos_A, speed=speed, wait=True)
            adam.check_adam_status("dance9", AdamTaskStatus.dancing)
            adam.left.move_circle(left_pos_B, left_pos_C, percent=percent, speed=300, wait=True)
            adam.check_adam_status("dance9", AdamTaskStatus.dancing)

        def all_round(speed, percent):
            right_pos_A = {'x': 520, 'y': -50, 'z': 370, 'roll': -40, 'pitch': 90, 'yaw': 50}
            right_pos_B = [600, -50, 450, -40, 90, 50]
            right_pos_C = [440, -50, 450, -40, 90, 50]
            adam.right.set_position(**right_pos_A, speed=speed, wait=False)
            adam.right.move_circle(right_pos_C, right_pos_B, percent=percent, speed=300, wait=False)
            adam.check_adam_status("dance9", AdamTaskStatus.dancing)
            left_pos_A = {'x': 520, 'y': 50, 'z': 530, 'roll': 40, 'pitch': 90, 'yaw': -50}
            left_pos_B = [600, 50, 450, 40, 90, -50]
            left_pos_C = [440, 50, 450, 40, 90, -50]
            adam.left.set_position(**left_pos_A, speed=speed, wait=False)
            adam.left.move_circle(left_pos_B, left_pos_C, percent=percent, speed=300, wait=False)
            adam.check_adam_status("dance9", AdamTaskStatus.dancing)

        init_round(500)
        for _ in range(2):
            right_round(200, 100)
            left_round(200, 100)
        right_round(200, 50)
        all_round(200, 600)
        init_round(500)

        def reduce_sound():
            for i in range(100, -1, -1):
                os.system(f"amixer set PCM {i}%")
                time.sleep(0.05)

        def init_adam():
            right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
            left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
            adam.left.set_position(**left_init, wait=False, speed=100, radius=50)
            adam.right.set_position(**right_init, wait=True, speed=100, radius=50)
            adam.check_adam_status("dance9", AdamTaskStatus.dancing)

        adam.check_adam_status("dance9", AdamTaskStatus.dancing)
        step_thread = [threading.Thread(target=reduce_sound), threading.Thread(target=init_adam)]
        for t in step_thread:
            t.start()
        for t in step_thread:
            t.join()

    def dance10():
        logger.info('dance10!!!')
        AudioInterface.music('Jingle_Bells.mp3')

        adam.env.adam.set_position(
            left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 500, 'wait': True},
            right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 500, 'wait': True}
        )
        adam.check_adam_status("dance10", AdamTaskStatus.dancing)

        # 拉小提琴
        for _ in range(1):
            adam.env.adam.set_position(
                left={'x': 230, 'y': 250, 'z': 900, 'roll': -30, 'pitch': 30, 'yaw': -150, 'speed': 200, 'wait': True},
                right={'x': 360, 'y': 230, 'z': 670, 'roll': 30, 'pitch': 45, 'yaw': 150, 'speed': 200, 'wait': True}
            )
            adam.check_adam_status("dance10", AdamTaskStatus.dancing)

            for i in range(3):
                adam.right.set_servo_angle(servo_id=6, angle=98, speed=80, wait=False)
                adam.right.set_servo_angle(servo_id=6, angle=38, speed=80, wait=False)
                adam.check_adam_status("dance10", AdamTaskStatus.dancing)

            for i in range(3):
                adam.left.set_servo_angle(servo_id=6, angle=-141, speed=80, wait=False)
                adam.left.set_servo_angle(servo_id=6, angle=-81, speed=80, wait=False)
                adam.check_adam_status("dance10", AdamTaskStatus.dancing)

            adam.right.set_servo_angle(servo_id=6, angle=98, speed=80, wait=False)
            adam.left.set_servo_angle(servo_id=6, angle=-141, speed=80, wait=True)
            adam.check_adam_status("dance10", AdamTaskStatus.dancing)

            left_Pos_violin1 = {'x': 360, 'y': -230, 'z': 670, 'roll': -30, 'pitch': 45, 'yaw': -150}
            right_Pos_violin1 = {'x': 230, 'y': -250, 'z': 900, 'roll': 30, 'pitch': 30, 'yaw': 150}
            adam.right.set_position(**right_Pos_violin1, wait=False, speed=200, radius=50)
            adam.check_adam_status("dance10", AdamTaskStatus.dancing)
            time.sleep(1)
            adam.left.set_position(**left_Pos_violin1, wait=True, speed=350, radius=50)
            adam.check_adam_status("dance10", AdamTaskStatus.dancing)

            adam.env.adam.set_position(
                left={'x': 360, 'y': -230, 'z': 670, 'roll': -30, 'pitch': 45, 'yaw': -150, 'speed': 100, 'wait': True},
                right={'x': 230, 'y': -250, 'z': 900, 'roll': 30, 'pitch': 30, 'yaw': 150, 'speed': 100, 'wait': True}
            )
            adam.check_adam_status("dance10", AdamTaskStatus.dancing)

            for i in range(3):
                adam.right.set_servo_angle(servo_id=6, angle=141, speed=80, wait=False)
                adam.right.set_servo_angle(servo_id=6, angle=81, speed=80, wait=False)
                adam.check_adam_status("dance10", AdamTaskStatus.dancing)

            for i in range(3):
                adam.left.set_servo_angle(servo_id=6, angle=-98, speed=80, wait=False)
                adam.left.set_servo_angle(servo_id=6, angle=-38, speed=80, wait=False)
                adam.check_adam_status("dance10", AdamTaskStatus.dancing)

            # init
            adam.env.adam.set_position(
                left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 200, 'wait': True},
                right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 200, 'wait': True}
            )
            adam.check_adam_status("dance10", AdamTaskStatus.dancing)

        right_Pos3_1 = {'x': 380, 'y': -330, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 90}
        left_Pos3_1 = {'x': 380, 'y': 330, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': -90}

        right_Pos3_2 = {'x': 380, 'y': -100, 'z': 500, 'roll': 90, 'pitch': 90, 'yaw': 180}
        left_Pos3_2 = {'x': 380, 'y': 100, 'z': 500, 'roll': -90, 'pitch': 90, 'yaw': -180}

        for _ in range(4):
            adam.right.set_position(**right_Pos3_2, wait=False, speed=300, radius=50)
            adam.left.set_position(**left_Pos3_1, wait=True, speed=300, radius=50)
            adam.check_adam_status("dance10", AdamTaskStatus.dancing)
            adam.right.set_position(**right_Pos3_1, wait=False, speed=300, radius=50)
            adam.left.set_position(**left_Pos3_2, wait=True, speed=300, radius=50)
            adam.check_adam_status("dance10", AdamTaskStatus.dancing)

        # init
        adam.env.adam.set_position(
            left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 200, 'wait': True},
            right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 200, 'wait': True}
        )
        adam.check_adam_status("dance10", AdamTaskStatus.dancing)

        # 切菜 tcp
        right_Pos12 = {'x': 724, 'y': -80, 'z': 514, 'roll': 90, 'pitch': 0, 'yaw': 90}
        left_Pos12 = {'x': 724, 'y': 80, 'z': 514, 'roll': -90, 'pitch': 0, 'yaw': -90}
        right_Pos12_left = {'x': 724, 'y': 0, 'z': 514, 'roll': 90, 'pitch': 0, 'yaw': 90}
        left_Pos12_left = {'x': 724, 'y': 160, 'z': 514, 'roll': -90, 'pitch': 0, 'yaw': -90}
        right_Pos12_right = {'x': 724, 'y': -160, 'z': 514, 'roll': 90, 'pitch': 0, 'yaw': 90}
        left_Pos12_right = {'x': 724, 'y': 0, 'z': 514, 'roll': -90, 'pitch': 0, 'yaw': -90}

        # 上下搓手
        right_Pos14 = {'x': 724, 'y': -80, 'z': 564, 'roll': 90, 'pitch': 0, 'yaw': 90}
        left_Pos14 = {'x': 724, 'y': 80, 'z': 464, 'roll': -90, 'pitch': 0, 'yaw': -90}
        right_Pos15 = {'x': 724, 'y': -80, 'z': 464, 'roll': 90, 'pitch': 0, 'yaw': 90}
        left_Pos15 = {'x': 724, 'y': 80, 'z': 564, 'roll': -90, 'pitch': 0, 'yaw': -90}

        right_Pos16 = {'x': 724, 'y': 0, 'z': 564, 'roll': 90, 'pitch': 0, 'yaw': 90}
        left_Pos16 = {'x': 724, 'y': 160, 'z': 464, 'roll': -90, 'pitch': 0, 'yaw': -90}
        right_Pos17 = {'x': 724, 'y': 0, 'z': 464, 'roll': 90, 'pitch': 0, 'yaw': 90}
        left_Pos17 = {'x': 724, 'y': 160, 'z': 564, 'roll': -90, 'pitch': 0, 'yaw': -90}

        right_Pos18 = {'x': 724, 'y': -160, 'z': 564, 'roll': 90, 'pitch': 0, 'yaw': 90}
        left_Pos18 = {'x': 724, 'y': 0, 'z': 464, 'roll': -90, 'pitch': 0, 'yaw': -90}
        right_Pos19 = {'x': 724, 'y': -160, 'z': 464, 'roll': 90, 'pitch': 0, 'yaw': 90}
        left_Pos19 = {'x': 724, 'y': 0, 'z': 564, 'roll': -90, 'pitch': 0, 'yaw': -90}

        adam.right.set_position(**right_Pos12, wait=False, speed=200, radius=50)
        adam.left.set_position(**left_Pos12, wait=True, speed=200, radius=50)
        adam.check_adam_status("dance10", AdamTaskStatus.dancing)

        for _ in range(3):
            adam.right.set_position(**right_Pos14, wait=False, speed=200, radius=50)
            adam.left.set_position(**left_Pos14, wait=False, speed=200, radius=50)
            adam.right.set_position(**right_Pos15, wait=False, speed=200, radius=50)
            adam.left.set_position(**left_Pos15, wait=False, speed=200, radius=50)
            adam.check_adam_status("dance10", AdamTaskStatus.dancing)

        adam.right.set_position(**right_Pos12, wait=False, speed=200, radius=50)
        adam.left.set_position(**left_Pos12, wait=True, speed=200, radius=50)
        adam.check_adam_status("dance10", AdamTaskStatus.dancing)

        adam.right.set_position(**right_Pos12_left, wait=False, speed=200, radius=50)
        adam.left.set_position(**left_Pos12_left, wait=True, speed=200, radius=50)
        adam.check_adam_status("dance10", AdamTaskStatus.dancing)

        for _ in range(3):
            adam.right.set_position(**right_Pos16, wait=False, speed=200, radius=50)
            adam.left.set_position(**left_Pos16, wait=False, speed=200, radius=50)
            adam.right.set_position(**right_Pos17, wait=False, speed=200, radius=50)
            adam.left.set_position(**left_Pos17, wait=False, speed=200, radius=50)
            adam.check_adam_status("dance10", AdamTaskStatus.dancing)

        adam.right.set_position(**right_Pos12_left, wait=False, speed=200, radius=50)
        adam.left.set_position(**left_Pos12_left, wait=True, speed=200, radius=50)
        adam.check_adam_status("dance10", AdamTaskStatus.dancing)

        adam.right.set_position(**right_Pos12_right, wait=False, speed=200, radius=50)
        adam.left.set_position(**left_Pos12_right, wait=True, speed=200, radius=50)
        adam.check_adam_status("dance10", AdamTaskStatus.dancing)

        for _ in range(3):
            adam.right.set_position(**right_Pos18, wait=False, speed=200, radius=50)
            adam.left.set_position(**left_Pos18, wait=False, speed=200, radius=50)
            adam.right.set_position(**right_Pos19, wait=False, speed=200, radius=50)
            adam.left.set_position(**left_Pos19, wait=False, speed=200, radius=50)

        adam.right.set_position(**right_Pos12_right, wait=False, speed=200, radius=50)
        adam.left.set_position(**left_Pos12_right, wait=True, speed=200, radius=50)
        adam.check_adam_status("dance10", AdamTaskStatus.dancing)


        adam.right.set_position(**right_Pos12, wait=False, speed=200, radius=50)
        adam.left.set_position(**left_Pos12, wait=True, speed=200, radius=50)
        adam.check_adam_status("dance10", AdamTaskStatus.dancing)

        for _ in range(3):
            right_Pos11 = {'x': 724, 'y': -137, 'z': 514, 'roll': 90, 'pitch': 0, 'yaw': 90}
            left_Pos11 = {'x': 724, 'y': 137, 'z': 514, 'roll': -90, 'pitch': 0, 'yaw': -90}

            adam.right.set_position(**right_Pos11, wait=False, speed=500, radius=50)
            adam.left.set_position(**left_Pos11, wait=True, speed=500, radius=50)
            adam.check_adam_status("dance10", AdamTaskStatus.dancing)
            adam.right.set_position(**right_Pos12, wait=False, speed=500, radius=50)
            adam.left.set_position(**left_Pos12, wait=True, speed=500, radius=50)
            adam.check_adam_status("dance10", AdamTaskStatus.dancing)

            right_Pos_round1 = {'x': 724, 'y': -337, 'z': 514, 'roll': 90, 'pitch': 0, 'yaw': 90}
            right_Pos_round2 = [724, -287, 464, 90, 0, 90]
            right_Pos_round3 = [724, -387, 464, 90, 0, 90]
            left_Pos_round1 = {'x': 724, 'y': 337, 'z': 514, 'roll': -90, 'pitch': 0, 'yaw': -90}
            left_Pos_round2 = [724, 387, 464, -90, 0, -90]
            left_Pos_round3 = [724, 287, 464, -90, 0, -90]

            adam.right.set_position(**right_Pos_round1, speed=200, wait=False)
            adam.right.move_circle(right_Pos_round2, right_Pos_round3, percent=100, speed=100, wait=False)
            adam.check_adam_status("dance10", AdamTaskStatus.dancing)

            adam.left.set_position(**left_Pos_round1, speed=200, wait=False)
            adam.left.move_circle(left_Pos_round3, left_Pos_round2, percent=100, speed=100, wait=False)
            adam.check_adam_status("dance10", AdamTaskStatus.dancing)

        # init
        adam.env.adam.set_position(
            left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 200, 'wait': True},
            right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 200, 'wait': True}
        )
        adam.check_adam_status("dance10", AdamTaskStatus.dancing)

        def reduce_sound():
            for i in range(100, -1, -1):
                os.system(f"amixer set PCM {i}%")
                time.sleep(0.05)

        def init_adam():
            right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
            left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
            adam.left.set_position(**left_init, wait=False, speed=100, radius=50)
            adam.right.set_position(**right_init, wait=True, speed=100, radius=50)
            adam.check_adam_status("dance10", AdamTaskStatus.dancing)

        adam.check_adam_status("dance10", AdamTaskStatus.dancing)
        step_thread = [threading.Thread(target=reduce_sound), threading.Thread(target=init_adam)]
        for t in step_thread:
            t.start()
        for t in step_thread:
            t.join()

    def dance11():
        logger.info('dance11!!!')
        # os.system("amixer set PCM 85%")
        AudioInterface.music('Break_The_Ice.mp3')
        # init
        adam.env.adam.set_position(
            left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 500, 'wait': True, 'timeout': 0.5},
            right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 500, 'wait': True, 'timeout': 0.5}
        )
        adam.check_adam_status("dance11", AdamTaskStatus.dancing)

        # one
        right_Pos1_0 = {'x': 310, 'y': -550, 'z': 300, 'roll': 0, 'pitch': 90, 'yaw': 0}
        left_Pos1_0 = {'x': 310, 'y': 550, 'z': 300, 'roll': 0, 'pitch': 90, 'yaw': 0}
        adam.env.adam.set_position(
            left={'x': 310, 'y': 550, 'z': 300, 'roll': 0, 'pitch': 90, 'yaw': 0, 'speed': 200, 'wait': True},
            right={'x': 310, 'y': -550, 'z': 300, 'roll': 0, 'pitch': 90, 'yaw': 0, 'speed': 200, 'wait': True}
        )
        adam.check_adam_status("dance11", AdamTaskStatus.dancing)

        right_Pos1_1 = {'x': 310, 'y': -550, 'z': 230, 'roll': 0, 'pitch': 90, 'yaw': 0}
        left_Pos1_1 = {'x': 310, 'y': 550, 'z': 230, 'roll': 0, 'pitch': 90, 'yaw': 0}
        right_Pos1_2 = {'x': 310, 'y': -550, 'z': 370, 'roll': 0, 'pitch': 90, 'yaw': 0}
        left_Pos1_2 = {'x': 310, 'y': 550, 'z': 370, 'roll': 0, 'pitch': 90, 'yaw': 0}

        def one_pos(speed):
            adam.left.set_position(**left_Pos1_1, wait=False, speed=speed, radius=50)
            adam.right.set_position(**right_Pos1_2, wait=True, speed=speed, radius=50, timeout=0.5)
            adam.check_adam_status("dance11", AdamTaskStatus.dancing)
            adam.left.set_position(**left_Pos1_2, wait=False, speed=speed, radius=50)
            adam.right.set_position(**right_Pos1_1, wait=True, speed=speed, radius=50, timeout=0.5)
            adam.check_adam_status("dance11", AdamTaskStatus.dancing)
        # two
        def left_round():
            left_Pos_round1 = {'x': 600, 'y': 400, 'z': 300, 'roll': 0, 'pitch': 90, 'yaw': 0}
            left_Pos_round2 = [600, 300, 350, 0, 90, 0]
            left_Pos_round3 = [600, 500, 350, 0, 90, 0]
            adam.left.set_position(**left_Pos_round1, speed=450, wait=True)
            adam.check_adam_status("dance11", AdamTaskStatus.dancing)
            adam.left.move_circle(left_Pos_round3, left_Pos_round2, percent=100, speed=200, wait=True)
            adam.check_adam_status("dance11", AdamTaskStatus.dancing)

        def right_round():
            right_Pos_round1 = {'x': 600, 'y': -400, 'z': 300, 'roll': 0, 'pitch': 90, 'yaw': 0}
            right_Pos_round2 = [600, -500, 350, 0, 90, 0]
            right_Pos_round3 = [600, -300, 350, 0, 90, 0]
            adam.right.set_position(**right_Pos_round1, speed=450, wait=True)
            adam.check_adam_status("dance11", AdamTaskStatus.dancing)
            adam.right.move_circle(right_Pos_round2, right_Pos_round3, percent=100, speed=200, wait=True)
            adam.check_adam_status("dance11", AdamTaskStatus.dancing)

        for _ in range(5):
            one_pos(300)

        adam.env.adam.set_position(
            left={'x': 310, 'y': 550, 'z': 300, 'roll': 0, 'pitch': 90, 'yaw': 0, 'speed': 200, 'wait': True, 'timeout': 0.5},
            right={'x': 310, 'y': -550, 'z': 300, 'roll': 0, 'pitch': 90, 'yaw': 0, 'speed': 200, 'wait': True, 'timeout': 0.5}
        )
        adam.check_adam_status("dance11", AdamTaskStatus.dancing)

        for _ in range(1):
            right_round()
            adam.right.set_position(**right_Pos1_0, wait=False, speed=450, radius=50)
            left_round()
            adam.left.set_position(**left_Pos1_0, wait=False, speed=450, radius=50)
            adam.check_adam_status("dance11", AdamTaskStatus.dancing)

        adam.left.set_position(**left_Pos1_0, wait=True, speed=450, radius=50)
        adam.check_adam_status("dance11", AdamTaskStatus.dancing)

        adam.env.adam.set_position(
            left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 200, 'wait': True},
            right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 200, 'wait': True}
        )
        adam.check_adam_status("dance11", AdamTaskStatus.dancing)

        # 3
        # 加油上
        right_Pos4 = {'x': 30, 'y': -650, 'z': 1250, 'roll': 0, 'pitch': 0, 'yaw': 90}
        left_Pos4 = {'x': 30, 'y': 650, 'z': 1250, 'roll': 0, 'pitch': 0, 'yaw': -90}
        # 加油下
        right_Pos5 = {'x': 30, 'y': -650, 'z': 1100, 'roll': 0, 'pitch': 0, 'yaw': 90}
        left_Pos5 = {'x': 30, 'y': 650, 'z': 1100, 'roll': 0, 'pitch': 0, 'yaw': -90}

        def come_on_right(speed):
            adam.right.set_position(**right_Pos4, wait=False, speed=speed, radius=50)
            adam.right.set_position(**right_Pos5, wait=False, speed=speed, radius=50)
            adam.check_adam_status("dance11", AdamTaskStatus.dancing)

        def come_on_left(speed):
            adam.left.set_position(**left_Pos5, wait=False, speed=speed, radius=50)
            adam.left.set_position(**left_Pos4, wait=False, speed=speed, radius=50)
            adam.check_adam_status("dance11", AdamTaskStatus.dancing)

        adam.right.set_position(**right_Pos4, wait=False, speed=250, radius=50)
        adam.left.set_position(**left_Pos5, wait=True, speed=250, radius=50)
        adam.check_adam_status("dance11", AdamTaskStatus.dancing)

        for _ in range(5):
            come_on_right(250)
            come_on_left(250)

        adam.env.adam.set_position(
            left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 200, 'wait': True},
            right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 200, 'wait': True}
        )
        adam.check_adam_status("dance11", AdamTaskStatus.dancing)

        # 4
        right_Pos3_1 = {'x': 380, 'y': -330, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 90}
        left_Pos3_1 = {'x': 380, 'y': 330, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': -90}

        right_Pos3_2 = {'x': 380, 'y': -100, 'z': 500, 'roll': 90, 'pitch': 90, 'yaw': 180}
        left_Pos3_2 = {'x': 380, 'y': 100, 'z': 500, 'roll': -90, 'pitch': 90, 'yaw': -180}

        for _ in range(1):
            adam.right.set_position(**right_Pos3_2, wait=False, speed=300, radius=50)
            adam.left.set_position(**left_Pos3_1, wait=True, speed=300, radius=50)
            adam.check_adam_status("dance11", AdamTaskStatus.dancing)
            adam.right.set_position(**right_Pos3_1, wait=False, speed=300, radius=50)
            adam.left.set_position(**left_Pos3_2, wait=True, speed=300, radius=50)
            adam.check_adam_status("dance11", AdamTaskStatus.dancing)

        # init
        adam.env.adam.set_position(
            left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 200, 'wait': True},
            right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 200, 'wait': True}
        )
        adam.check_adam_status("dance11", AdamTaskStatus.dancing)

        def reduce_sound():
            for i in range(100, -1, -1):
                os.system(f"amixer set PCM {i}%")
                time.sleep(0.05)

        def init_adam():
            right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
            left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
            adam.left.set_position(**left_init, wait=False, speed=100, radius=50)
            adam.right.set_position(**right_init, wait=True, speed=100, radius=50)
            adam.check_adam_status("dance11", AdamTaskStatus.dancing)

        adam.check_adam_status("dance11", AdamTaskStatus.dancing)
        step_thread = [threading.Thread(target=reduce_sound), threading.Thread(target=init_adam)]
        for t in step_thread:
            t.start()
        for t in step_thread:
            t.join()

    def dance12():
        logger.info('dance12!!!')
        os.system("amixer set PCM 100%")
        AudioInterface.music('Sugar.mp3')
        # init
        adam.env.adam.set_position(
            left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 500, 'wait': True, 'timeout': 0.5},
            right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 500, 'wait': True, 'timeout': 0.5}
        )
        adam.check_adam_status("dance12", AdamTaskStatus.dancing)

        # one
        right_Pos1_0 = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
        left_Pos1_0 = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}

        right_Pos1_1 = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 30, 'yaw': 90}
        left_Pos1_1 = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 30, 'yaw': -90}

        for _ in range(4):
            adam.right.set_position(**right_Pos1_1, wait=False, speed=180, radius=50)
            adam.left.set_position(**left_Pos1_1, wait=False, speed=180, radius=50)
            adam.right.set_position(**right_Pos1_0, wait=False, speed=180, radius=50)
            adam.left.set_position(**left_Pos1_0, wait=False, speed=180, radius=50)
            adam.check_adam_status("dance12", AdamTaskStatus.dancing)

        for _ in range(10):
            adam.right.set_position(**right_Pos1_1, wait=False, speed=300, radius=50)
            adam.left.set_position(**left_Pos1_1, wait=False, speed=300, radius=50)
            adam.right.set_position(**right_Pos1_0, wait=False, speed=300, radius=50)
            adam.left.set_position(**left_Pos1_0, wait=False, speed=300, radius=50)
            adam.check_adam_status("dance12", AdamTaskStatus.dancing)

        for _ in range(2):
            # init
            adam.env.adam.set_position(
                left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 200, 'wait': True},
                right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 200, 'wait': True}
            )
            adam.check_adam_status("dance12", AdamTaskStatus.dancing)

            # move circle
            adam.env.adam.set_position(
                left={'x': 450, 'y': 200, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 0, 'speed': 500, 'wait': True},
                right={'x': 450, 'y': 0, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 180, 'speed': 500, 'wait': True}
            )
            adam.check_adam_status("dance12", AdamTaskStatus.dancing)
            for i in range(5):
                adam.env.adam.move_circle(
                    left={'pose1': [450, 100, 900, 0, 0, 0], 'pose2': [450, 100, 700, 0, 0, 0], 'percent': 50,
                          'speed': 300, 'wait': False},
                    right={'pose1': [450, -100, 900, 0, 0, 180], 'pose2': [450, -100, 700, 0, 0, 180], 'percent': 50,
                           'speed': 300, 'wait': False}
                )
                adam.check_adam_status("dance12", AdamTaskStatus.dancing)

                adam.env.adam.move_circle(
                    left={'pose1': [450, 100, 900, 0, 0, 0], 'pose2': [450, 100, 700, 0, 0, 0], 'percent': 50,
                          'speed': 300, 'wait': False},
                    right={'pose1': [450, -100, 900, 0, 0, 180], 'pose2': [450, -100, 700, 0, 0, 180], 'percent': 50,
                           'speed': 300, 'wait': False}
                )
                adam.check_adam_status("dance12", AdamTaskStatus.dancing)

            for _ in range(2):
                # 3 open the window
                adam.env.adam.set_position(
                    left={'x': 450, 'y': 100, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 0, 'speed': 250, 'wait': False},
                    right={'x': 450, 'y': -100, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 180, 'speed': 250, 'wait': False}
                )
                adam.check_adam_status("dance12", AdamTaskStatus.dancing)

                adam.env.adam.set_position(
                    left={'x': 600, 'y': 180, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 0, 'speed': 250, 'wait': False},
                    right={'x': 600, 'y': -180, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 180, 'speed': 250, 'wait': False}
                )
                adam.check_adam_status("dance12", AdamTaskStatus.dancing)

                adam.env.adam.set_position(
                    left={'x': 450, 'y': 180, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 0, 'speed': 250, 'wait': False},
                    right={'x': 450, 'y': -180, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 180, 'speed': 250, 'wait': False}
                )
                adam.check_adam_status("dance12", AdamTaskStatus.dancing)

                adam.env.adam.set_position(
                    left={'x': 600, 'y': 400, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 0, 'speed': 250, 'wait': False},
                    right={'x': 600, 'y': -400, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 180, 'speed': 250, 'wait': False}
                )
                adam.check_adam_status("dance12", AdamTaskStatus.dancing)

                adam.env.adam.set_position(
                    left={'x': 450, 'y': 400, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 0, 'speed': 250, 'wait': False},
                    right={'x': 450, 'y': -400, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 180, 'speed': 250, 'wait': False}
                )
                adam.check_adam_status("dance12", AdamTaskStatus.dancing)

                # close the window
                adam.env.adam.set_position(
                    left={'x': 600, 'y': 100, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 0, 'speed': 250, 'wait': False},
                    right={'x': 600, 'y': -100, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 180, 'speed': 250, 'wait': False}
                )
                adam.check_adam_status("dance12", AdamTaskStatus.dancing)

                adam.env.adam.set_position(
                    left={'x': 450, 'y': 100, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 0, 'speed': 250, 'wait': False},
                    right={'x': 450, 'y': -100, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 180, 'speed': 250, 'wait': False}
                )
                adam.check_adam_status("dance12", AdamTaskStatus.dancing)

            right_Pos4_0 = {'x': 300, 'y': -240, 'z': 850, 'roll': 0, 'pitch': 60, 'yaw': 90}
            right_Pos4_1 = {'x': 300, 'y': -240, 'z': 850, 'roll': 0, 'pitch': 30, 'yaw': 90}
            left_Pos4_0 = {'x': 300, 'y': 240, 'z': 850, 'roll': 0, 'pitch': 60, 'yaw': -90}
            left_Pos4_1 = {'x': 300, 'y': 240, 'z': 850, 'roll': 0, 'pitch': 30, 'yaw': -90}

            def right_salute_shake():
                adam.right.set_position(**right_Pos4_0, wait=False, speed=300, radius=50)
                adam.right.set_position(**right_Pos4_1, wait=True, speed=300, radius=50)
                adam.check_adam_status("dance12", AdamTaskStatus.dancing)

            def left_salute_shake():
                adam.left.set_position(**left_Pos4_0, wait=False, speed=300, radius=50)
                adam.left.set_position(**left_Pos4_1, wait=True, speed=300, radius=50)
                adam.check_adam_status("dance12", AdamTaskStatus.dancing)

            # init
            adam.env.adam.set_position(
                left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 300, 'wait': True},
                right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 300, 'wait': True}
            )
            adam.check_adam_status("dance12", AdamTaskStatus.dancing)

            adam.right.set_position(**right_Pos4_1, wait=False, speed=300, radius=50)
            adam.left.set_position(**left_Pos4_1, wait=False, speed=300, radius=50)
            adam.check_adam_status("dance12", AdamTaskStatus.dancing)
            for _ in range(4):
                right_salute_shake()
                left_salute_shake()

        def reduce_sound():
            for i in range(100, -1, -1):
                os.system(f"amixer set PCM {i}%")
                time.sleep(0.05)

        def init_adam():
            right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
            left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
            adam.left.set_position(**left_init, wait=False, speed=100, radius=50)
            adam.right.set_position(**right_init, wait=True, speed=100, radius=50)
            adam.check_adam_status("dance12", AdamTaskStatus.dancing)

        adam.check_adam_status("dance12", AdamTaskStatus.dancing)
        step_thread = [threading.Thread(target=reduce_sound), threading.Thread(target=init_adam)]
        for t in step_thread:
            t.start()
        for t in step_thread:
            t.join()

    def dance13():
        logger.info('dance13!!!')
        os.system("amixer set PCM 100%")
        # AudioInterface.music('Worth_It.mp3')
        # init
        adam.env.adam.set_position(
            left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 500, 'wait': True, 'timeout': 0.5},
            right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 500, 'wait': True, 'timeout': 0.5}
        )
        adam.check_adam_status("dance13", AdamTaskStatus.dancing)

        # one
        right_Pos1 = {'x': 320, 'y': 0, 'z': 800, 'roll': 50, 'pitch': 15, 'yaw': 170}
        left_Pos1 = {'x': 490, 'y': 0, 'z': 830, 'roll': -50, 'pitch': 15, 'yaw': -170}

        right_Pos2 = {'x': 320, 'y': 0, 'z': 800, 'roll': 60, 'pitch': 15, 'yaw': 170}
        left_Pos2 = {'x': 490, 'y': 0, 'z': 830, 'roll': -60, 'pitch': 15, 'yaw': -170}

        adam.right.set_position(**right_Pos2, wait=False, speed=200, radius=50)
        adam.left.set_position(**left_Pos2, wait=True, speed=200, radius=50)
        adam.check_adam_status("dance13", AdamTaskStatus.dancing)

        AudioInterface.music('Worth_It.mp3')
        time.sleep(1)

        for _ in range(9):
            adam.right.set_position(**right_Pos2, wait=False, speed=120, radius=50)
            adam.left.set_position(**left_Pos2, wait=False, speed=120, radius=50)
            adam.right.set_position(**right_Pos1, wait=False, speed=120, radius=50)
            adam.left.set_position(**left_Pos1, wait=False, speed=120, radius=50)
            adam.check_adam_status("dance13", AdamTaskStatus.dancing)

        right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
        left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
        adam.left.set_position(**left_init, wait=False, speed=400, radius=50)
        adam.right.set_position(**right_init, wait=True, speed=400, radius=50)
        adam.check_adam_status("dance13", AdamTaskStatus.dancing)

        def right_round(speed, percent):
            # a = {'x': 520, 'y': -50, 'z': 450, 'roll': -40, 'pitch': 90, 'yaw': 50}
            right_pos_A = {'x': 520, 'y': -50, 'z': 530, 'roll': -40, 'pitch': 90, 'yaw': 50}
            right_pos_B = [600, -50, 450, -40, 90, 50]
            right_pos_C = [440, -50, 450, -40, 90, 50]
            adam.right.set_position(**right_pos_A, speed=speed, wait=True)
            adam.check_adam_status("dance13", AdamTaskStatus.dancing)
            adam.right.move_circle(right_pos_B, right_pos_C, percent=percent, speed=300, wait=True)
            adam.check_adam_status("dance13", AdamTaskStatus.dancing)

        def left_round(speed, percent):
            left_pos_A = {'x': 520, 'y': 50, 'z': 530, 'roll': 40, 'pitch': 90, 'yaw': -50}
            left_pos_B = [600, 50, 450, 40, 90, -50]
            left_pos_C = [440, 50, 450, 40, 90, -50]
            adam.left.set_position(**left_pos_A, speed=speed, wait=True)
            adam.check_adam_status("dance13", AdamTaskStatus.dancing)
            adam.left.move_circle(left_pos_B, left_pos_C, percent=percent, speed=300, wait=True)
            adam.check_adam_status("dance13", AdamTaskStatus.dancing)

        def all_round(speed, percent):
            right_pos_A = {'x': 520, 'y': -50, 'z': 370, 'roll': -40, 'pitch': 90, 'yaw': 50}
            right_pos_B = [600, -50, 450, -40, 90, 50]
            right_pos_C = [440, -50, 450, -40, 90, 50]
            adam.right.set_position(**right_pos_A, speed=speed, wait=False)
            adam.right.move_circle(right_pos_C, right_pos_B, percent=percent, speed=300, wait=False)
            adam.check_adam_status("dance13", AdamTaskStatus.dancing)
            left_pos_A = {'x': 520, 'y': 50, 'z': 530, 'roll': 40, 'pitch': 90, 'yaw': -50}
            left_pos_B = [600, 50, 450, 40, 90, -50]
            left_pos_C = [440, 50, 450, 40, 90, -50]
            adam.left.set_position(**left_pos_A, speed=speed, wait=False)
            adam.left.move_circle(left_pos_B, left_pos_C, percent=percent, speed=300, wait=False)
            adam.check_adam_status("dance13", AdamTaskStatus.dancing)

        left_pos_A = {'x': 520, 'y': 50, 'z': 530, 'roll': 40, 'pitch': 90, 'yaw': -50}
        adam.left.set_position(**left_pos_A, speed=200, wait=False)
        adam.check_adam_status("dance13", AdamTaskStatus.dancing)
        right_round(200, 50)
        all_round(200, 800)

        adam.env.adam.set_position(
            left={'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90, 'speed': 500, 'wait': True, 'timeout': 0.5},
            right={'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90, 'speed': 500, 'wait': True, 'timeout': 0.5}
        )
        adam.check_adam_status("dance13", AdamTaskStatus.dancing)

        right_Pos_zhong1 = {'x': 370, 'y': -270, 'z': 850, 'roll': -10, 'pitch': -30, 'yaw': 100}
        left_Pos_zhong1 = {'x': 370, 'y': 270, 'z': 850, 'roll': 10, 'pitch': -30, 'yaw': -100}

        right_Pos_zhong2 = {'x': 370, 'y': -150, 'z': 1000, 'roll': -10, 'pitch': -30, 'yaw': 100}
        left_Pos_zhong2 = {'x': 370, 'y': 390, 'z': 1000, 'roll': 10, 'pitch': -30, 'yaw': -100}

        right_Pos_zhong3 = {'x': 370, 'y': -390, 'z': 1000, 'roll': -10, 'pitch': -30, 'yaw': 100}
        left_Pos_zhong3 = {'x': 370, 'y': 150, 'z': 1000, 'roll': 10, 'pitch': -30, 'yaw': -100}

        def zhong():
            adam.right.set_position(**right_Pos_zhong1, wait=False, speed=300, radius=50)
            adam.left.set_position(**left_Pos_zhong1, wait=True, speed=300, radius=50)
            adam.check_adam_status("dance13", AdamTaskStatus.dancing)

        def zhong_right():
            adam.right.set_position(**right_Pos_zhong2, wait=False, speed=300, radius=50)
            adam.left.set_position(**left_Pos_zhong2, wait=False, speed=300, radius=50)
            adam.check_adam_status("dance13", AdamTaskStatus.dancing)

        def zhong_left():
            adam.right.set_position(**right_Pos_zhong3, wait=False, speed=300, radius=50)
            adam.left.set_position(**left_Pos_zhong3, wait=False, speed=300, radius=50)
            adam.check_adam_status("dance13", AdamTaskStatus.dancing)

        for _ in range(4):
            zhong()
            zhong_right()
            zhong()
            zhong_left()
            zhong()

        right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
        left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}

        adam.left.set_position(**left_init, wait=False, speed=300, radius=50)
        adam.right.set_position(**right_init, wait=True, speed=300, radius=50)
        adam.check_adam_status("dance13", AdamTaskStatus.dancing)

        left_Pos3_1 = {'x': 380, 'y': 330, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': -90}

        right_Pos3_1 = {'x': 380, 'y': 100, 'z': 700, 'roll': 0, 'pitch': 60, 'yaw': 90}

        right_Pos3_2 = {'x': 380, 'y': 100, 'z': 700, 'roll': 0, 'pitch': 45, 'yaw': 90}

        right_Pos3_3 = {'x': 380, 'y': -50, 'z': 700, 'roll': 0, 'pitch': 60, 'yaw': 90}

        right_Pos3_4 = {'x': 380, 'y': -50, 'z': 700, 'roll': 0, 'pitch': 45, 'yaw': 90}

        right_Pos3_5 = {'x': 380, 'y': -200, 'z': 700, 'roll': 0, 'pitch': 60, 'yaw': 90}

        right_Pos3_6 = {'x': 380, 'y': -200, 'z': 700, 'roll': 0, 'pitch': 45, 'yaw': 90}

        left_Pos4_1 = {'x': 380, 'y': -330, 'z': 800, 'roll': 0, 'pitch': 0, 'yaw': 90}

        right_Pos4_1 = {'x': 380, 'y': -100, 'z': 700, 'roll': 0, 'pitch': 60, 'yaw': -90}

        right_Pos4_2 = {'x': 380, 'y': -100, 'z': 700, 'roll': 0, 'pitch': 45, 'yaw': -90}

        right_Pos4_3 = {'x': 380, 'y': 50, 'z': 700, 'roll': 0, 'pitch': 60, 'yaw': -90}

        right_Pos4_4 = {'x': 380, 'y': 50, 'z': 700, 'roll': 0, 'pitch': 45, 'yaw': -90}

        right_Pos4_5 = {'x': 380, 'y': 200, 'z': 700, 'roll': 0, 'pitch': 60, 'yaw': -90}

        right_Pos4_6 = {'x': 380, 'y': 200, 'z': 700, 'roll': 0, 'pitch': 45, 'yaw': -90}

        def new_pos1(speed):
            adam.right.set_position(**right_Pos3_1, wait=False, speed=speed, radius=50)
            adam.left.set_position(**left_Pos3_1, wait=True, speed=speed, radius=50)
            adam.check_adam_status("dance13", AdamTaskStatus.dancing)
            adam.right.set_position(**right_Pos3_2, wait=False, speed=speed, radius=50)
            adam.right.set_position(**right_Pos3_3, wait=False, speed=speed, radius=50)
            adam.right.set_position(**right_Pos3_4, wait=False, speed=speed, radius=50)
            adam.right.set_position(**right_Pos3_5, wait=False, speed=speed, radius=50)
            adam.right.set_position(**right_Pos3_6, wait=True, speed=speed, radius=50)
            adam.check_adam_status("dance13", AdamTaskStatus.dancing)

        def new_pos2(speed):
            adam.left.set_position(**right_Pos4_1, wait=False, speed=speed, radius=50)
            adam.right.set_position(**left_Pos4_1, wait=True, speed=speed, radius=50)
            adam.check_adam_status("dance13", AdamTaskStatus.dancing)
            adam.left.set_position(**right_Pos4_2, wait=False, speed=speed, radius=50)
            adam.left.set_position(**right_Pos4_3, wait=False, speed=speed, radius=50)
            adam.left.set_position(**right_Pos4_4, wait=False, speed=speed, radius=50)
            adam.left.set_position(**right_Pos4_5, wait=False, speed=speed, radius=50)
            adam.left.set_position(**right_Pos4_6, wait=True, speed=speed, radius=50)
            adam.check_adam_status("dance13", AdamTaskStatus.dancing)

        for _ in range(2):
            new_pos1(200)

        right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
        left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
        adam.left.set_position(**left_init, wait=False, speed=300, radius=50)
        adam.right.set_position(**right_init, wait=True, speed=300, radius=50)
        adam.check_adam_status("dance13", AdamTaskStatus.dancing)

        for _ in range(2):
            new_pos2(200)

        def reduce_sound():
            for i in range(100, -1, -1):
                os.system(f"amixer set PCM {i}%")
                time.sleep(0.05)

        def init_adam():
            right_init = {'x': 355, 'y': -100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': 90}
            left_init = {'x': 355, 'y': 100, 'z': 630, 'roll': 0, 'pitch': 60, 'yaw': -90}
            adam.left.set_position(**left_init, wait=False, speed=100, radius=50)
            adam.right.set_position(**right_init, wait=True, speed=100, radius=50)
            adam.check_adam_status("dance13", AdamTaskStatus.dancing)

        adam.check_adam_status("dance13", AdamTaskStatus.dancing)
        step_thread = [threading.Thread(target=reduce_sound), threading.Thread(target=init_adam)]
        for t in step_thread:
            t.start()
        for t in step_thread:
            t.join()

    def run_dance(choice):
        try:
            adam.goto_gripper_position(Arm.left, 0, wait=False)
            adam.goto_gripper_position(Arm.right, 0, wait=False)
            if choice != 5:
                left_angles, right_angles = adam.get_initial_position()
                logger.info('left_angles={}, right_angles={}'.format(left_angles, right_angles))
                adam.env.adam.set_servo_angle(dict(angle=left_angles, speed=20, wait=True),
                                              dict(angle=right_angles, speed=20, wait=True))
            AudioInterface.stop()
            choice = choice
            with MySuperContextManager() as db:
                adam_crud.update_single_dance(db, choice, 1)
            adam.check_adam_status("run_dance", AdamTaskStatus.dancing)
            if choice == 1:
                logger.info('run dance1 hi.mp3')
                dance1()
            elif choice == 2:
                logger.info('run dance2 whistle.mp3')
                dance2()
            elif choice == 3:
                logger.info('run dance3 wa.mp3')
                dance3()
            elif choice == 4:
                logger.info('run dance4 YouNeverCanTell.mp3')
                dance4()
            elif choice == 5:
                logger.info('run dance5 dance.mp3')
                dance5()
            elif choice == 6:
                logger.info('run dance6 Saturday_night_fever_dance.mp3')
                dance6()
            elif choice == 7:
                logger.info('run dance7 Because_of_You.mp3')
                dance7()
            elif choice == 8:
                logger.info('run dance8 BLACKPINK_Shut_Down.mp3')
                dance8()
            elif choice == 9:
                logger.info('run dance9 Dance_The_Night.mp3')
                dance9()
            elif choice == 10:
                logger.info('run dance10 Jingle_Bells.mp3')
                dance10()
            elif choice == 11:
                logger.info('run dance11 Break_The_Ice.mp3')
                dance11()
            elif choice == 12:
                logger.info('run dance12 Sugar.mp3')
                dance12()
            elif choice == 13:
                logger.info('run dance13 Worth_It.mp3')
                dance13()
            adam.goto_standby_pose()
        except Exception as e:
            logger.error('random dance have a error is {}'.format(str(e)))
            logger.error(traceback.format_exc())
            adam.task_status = AdamTaskStatus.dead
            adam.dead_before_manual()
        finally:
            AudioInterface.stop()
            with MySuperContextManager() as db:
                adam_crud.update_single_dance(db, choice, 0)
            os.system("amixer set PCM 100%")
            adam.env.init_adam()

    if adam.task_status != AdamTaskStatus.idle:
        return adam.task_status
    adam.change_adam_status(AdamTaskStatus.dancing)
    run_dance(choice)
    # t = threading.Thread(target=run_dance, args=(choice,))
    # t.setDaemon(True)
    # t.start()
    # t.join()
    if adam.task_status != AdamTaskStatus.making:
        adam.task_status = AdamTaskStatus.idle
    return adam.task_status
