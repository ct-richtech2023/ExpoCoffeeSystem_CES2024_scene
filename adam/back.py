import threading
import os
import time
import csv
import numpy as np


from loguru import logger
from xarm.wrapper import XArmAPI

from common.utils import update_threads_step


class RecordThread(threading.Thread):
    def __init__(self, arm: XArmAPI, file_path, desc=None, steps_queue=None):
        """
        thread for recording arm's angles every 0.5s
        :param arm: XArmAPI obj
        :param file_path: where to save records
        :param desc:
        """
        super().__init__()
        self.record = True  # record or not
        self.stopped = False  # exit thread or not
        self.arm = arm
        self.file_path = file_path
        self.desc = desc
        self.steps_queue = steps_queue
        logger.info('start record thread, desc={}'.format(desc))

    def update_step(self, step):
        if self.steps_queue is not None:
            update_threads_step(status_queue=self.steps_queue, thread=self, step=step)

    def pause(self):
        """
        pause recording
        """
        logger.info('{} record thread pause recording'.format(self.desc))
        self.record = False
        self.update_step('pause')

    def proceed(self):
        """
        continue to record
        """
        logger.info('{} record thread continue to record'.format(self.desc))
        self.record = True
        self.update_step('proceed')

    def stop(self):
        """
        exit the thread
        """
        logger.info('{} record thread stopped'.format(self.desc))
        self.stopped = True

    def clear(self):
        """
        remove record file
        :return:
        """
        logger.info('{} record thread remove file {}'.format(self.desc, self.file_path))
        if os.path.exists(self.file_path):
            os.remove(self.file_path)
        self.update_step('clear')

    def write(self):
        """
        write a record to file
        """
        with open(self.file_path, 'a', encoding='utf-8', newline='') as f:
            ret, angles = self.arm.get_servo_angle()
            # logger.debug('writing {} ...'.format(self.file_path))
            mid_a = np.array(angles)
            mid_a_3f = np.round(mid_a, 3)
            list_new = list(mid_a_3f)
            csv_writer = csv.writer(f)
            csv_writer.writerow(list_new)

    def run(self):
        self.update_step('start')
        while not self.stopped:
            while self.record:
                if self.arm.connected and self.arm.state != 4:
                    self.write()
                    time.sleep(0.2)
                if self.arm.state == 4:
                    self.pause()
                    # self.roll()
                    # self.proceed()
            else:
                time.sleep(0.2)

        self.update_step('end')
