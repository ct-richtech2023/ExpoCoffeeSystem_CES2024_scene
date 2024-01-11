from threading import Thread
import time
from loguru import logger


class CheckThread(Thread):
    def __init__(self, arm, stop_func):
        super(CheckThread, self).__init__()
        self.arm = arm
        self.stop_func = stop_func
        self.run_flag = True

    def stop(self):
        self.run_flag = False
        logger.info('check thread stopped')

    def run(self):
        logger.info('check thread started')
        while self.run_flag:
            state = self.arm.get_state()
            if state[0] != 0 or state[1] == 4:
                logger.warning('state is {}'.format(state))
                self.stop_func('check thread find state = {}'.format(state))
                break
            else:
                time.sleep(1)
