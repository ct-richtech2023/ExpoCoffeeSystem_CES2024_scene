import time

from xarm.wrapper import XArmAPI

arm = XArmAPI('192.168.2.240')
arm.motion_enable()
arm.clean_warn()
arm.set_mode()
arm.set_state()


def control_rou_chu(action=None):
    if action == 'open':
        arm.set_cgpio_digital(8, 0)
        arm.set_cgpio_digital(9, 1)
    elif action == 'close':
        arm.set_cgpio_digital(8, 1)
        arm.set_cgpio_digital(9, 0)
    else:
        arm.set_cgpio_digital(8, 0)
        arm.set_cgpio_digital(9, 0)


for i in range(10):
    control_rou_chu('open')
    time.sleep(1)
    control_rou_chu('close')
    time.sleep(1)
