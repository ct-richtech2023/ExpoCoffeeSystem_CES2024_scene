import threading
from queue import Queue
from threading import Thread
import time
from loguru import logger

from common.utils import update_threads_step


class CheckThread(Thread):
    def __init__(self, arm, stop_func, thread_name='making.check', steps_queue: Queue = None):
        super(CheckThread, self).__init__()
        self.arm = arm
        self.stop_func = stop_func
        self.run_flag = True
        self.name = thread_name
        self.steps_queue = steps_queue
        # self.update_step('create')

    def update_step(self, step):
        if self.steps_queue is not None:
            update_threads_step(status_queue=self.steps_queue, thread=self, step=step)

    def stop(self):
        self.run_flag = False
        logger.info('check thread stopped')

    def run(self):
        logger.info('check thread started')
        self.update_step('start')
        while self.run_flag:
            state = self.arm.get_state()
            if state[0] != 0 or state[1] == 4:
                logger.warning('state is {}'.format(state))
                self.stop_func('check thread find state = {}'.format(state))
                break
            else:
                time.sleep(1)
        self.update_step('end')
