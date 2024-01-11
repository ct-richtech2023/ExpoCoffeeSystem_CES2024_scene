import threading
import os
import time
import csv
import numpy as np


from loguru import logger
from xarm.wrapper import XArmAPI


class RecordThread(threading.Thread):
    def __init__(self, arm: XArmAPI, file_path, desc=None):
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
        logger.info('start record thread, desc={}'.format(desc))

    def pause(self):
        """
        pause recording
        """
        logger.info('{} record thread pause recording'.format(self.desc))
        self.record = False

    def proceed(self):
        """
        continue to record
        """
        logger.info('{} record thread continue to record'.format(self.desc))
        self.record = True

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

    def roll(self):
        """
        rollback according to the records in file, not use
        """
        logger.info('before {} record thread rollback, wait for 5s'.format(self.desc))
        time.sleep(20)  # waiting for the main thread to release control of the arm
        self.arm.motion_enable(enable=True)
        self.arm.set_mode(0)
        self.arm.set_state(state=0)
        logger.info('{} record thread rolling back'.format(self.desc))
        with open(self.file_path) as f:
            p_csv = csv.reader(f)
            pos = list(p_csv)
            for i in range(len(pos)):
                pos[i] = list(map(float, pos[i]))

        count = len(pos)
        while self.arm.connected and self.arm.state != 4:
            self.arm.set_servo_angle(angle=pos[count - 1], radius=2, wait=False, speed=20)
            count = count - 1
            if count == 0:
                break
        logger.info('{} record thread rollback complete'.format(self.desc))

    def run(self):
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
