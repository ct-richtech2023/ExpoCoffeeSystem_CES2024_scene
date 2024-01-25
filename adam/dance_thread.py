import threading
import time

import requests

from common.db.crud import adam as adam_crud
from common.api import AdamInterface, AudioInterface, VisualDetectInterface
from loguru import logger
from common.define import AdamTaskStatus

from common.db.database import MySuperContextManager
from common.utils import update_threads_step


class DanceThread(threading.Thread):
    """
    self.total_duration : using
    AdamInterface.zero(idle=True): Loop call
    """

    def __init__(self, steps_queue=None):
        super().__init__()
        self.running = False
        self.total_duration = 0
        self.start_time = 0
        self.need_zero = True
        self.init()
        self.steps_queue = steps_queue

    def init(self):
        with MySuperContextManager() as db_session:
            adam_crud.init_dance(db_session)

    def update_step(self, step):
        if self.steps_queue is not None:
            update_threads_step(status_queue=self.steps_queue, thread=self, step=step)

    def proceed(self, total_duration):
        self.total_duration = total_duration
        logger.info('dance thread proceed')
        self.running = True
        self.update_step('proceed')

    def pause(self):
        self.total_duration = 0
        logger.info('dance thread pause')
        self.running = False
        self.update_step('pause')

    def stop_thread(self):
        self.update_step('stop_thread')
        self.total_duration = 0
        self.running = False
        logger.info('dance thread stopped')
        if self.need_zero:
            AdamInterface.zero(idle=True)

    def run(self):
        # self.running = True
        self.update_step('start')
        if self.total_duration > 0:
            self.start_time = int(time.time())
            while self.running:
                # get_dance_list
                with MySuperContextManager() as db_session:
                    dance_list = adam_crud.get_dance_list(db_session)
                if dance_list:
                    num = 0
                    for dance in dance_list:
                        if not self.running:
                            break
                        if not dance.get('display', ''):
                            num += 1
                        if dance.get('display', '') and dance.get('dance_num', ''):
                            remain_time = self.total_duration - (int(time.time()) - self.start_time)
                            if remain_time > 1:
                                try:
                                    AdamInterface.random_dance(dance.get('dance_num', ''), remain_time)
                                except requests.Timeout:
                                    self.stop_thread()
                            else:
                                self.stop_thread()
                    if num == len(dance_list):
                        self.stop_thread()
        self.update_step('end')


class FollowThread(threading.Thread):
    def __init__(self, total_duration, steps_queue=None):
        super().__init__()
        self.running = False
        self.total_duration = total_duration
        self.start_time = 0
        self.steps_queue = steps_queue

    def update_step(self, step):
        if self.steps_queue is not None:
            update_threads_step(status_queue=self.steps_queue, thread=self, step=step)

    def proceed(self):
        logger.info('follow thread proceed')
        self.running = True
        self.update_step('proceed')

    def pause(self):
        self.total_duration = 0
        self.running = False
        self.update_step('pause')
        logger.info('follow thread pause')

    def stop_thread(self, idle=True):
        self.update_step('stop_thread')
        self.total_duration = 0
        self.running = False
        logger.info('follow thread stopped')
        VisualDetectInterface.stop_following()
        AudioInterface.stop()
        AdamInterface.stop_move()
        if idle:
            AdamInterface.change_adam_status_idle("idle")

    def run(self):
        self.update_step('start')
        if self.total_duration > 0:
            self.start_time = int(time.time())
            while self.running:
                remain_time = self.total_duration - (int(time.time()) - self.start_time)
                if remain_time < 1:
                    AdamInterface.change_adam_status(AdamTaskStatus.idle)
        self.update_step('end')
