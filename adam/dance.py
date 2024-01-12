import threading
import time
from common.db.crud import adam as adam_crud
from common.api import AdamInterface, AudioInterface, VisualDetectInterface
from loguru import logger

from common.db.database import MySuperContextManager

class DanceThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.running = False
        self.stopped = False
        self.init()

    def init(self):
        with MySuperContextManager() as db_session:
            adam_crud.init_dance(db_session)

    def proceed(self):
        logger.info('dance thread proceed')
        self.running = True

    def pause(self):
        logger.info('dance thread pause')
        self.running = False

    def stop_thread(self):
        logger.info('dance thread stopped')
        self.stopped = True

    def run(self):
        # self.running = True
        while not self.stopped:
            if self.running:
                # get_dance_list
                with MySuperContextManager() as db_session:
                    dance_list = adam_crud.get_dance_list(db_session)
                if dance_list:
                    num = 0
                    for dance in dance_list:
                        if not self.running:
                            break
                        if not dance.get('sort', ''):
                            num += 1
                        if dance.get('sort', '') and dance.get('dance_num', ''):
                            AdamInterface.random_dance(dance.get('dance_num', ''))
                    if num == 10:
                        self.running = False
                time.sleep(5)  # 暂停一秒钟
            else:
                time.sleep(5)

class CountdownTimer:
    def __init__(self):
        self.remaining_time = 0
        self.timer = None
        self.is_running = False

    def edit_initial_time(self, initial_time):
        self.remaining_time = initial_time

    def start(self):
        self.is_running = True
        self.timer = threading.Thread(target=self._run)
        self.timer.start()

    def _run(self):
        start_time = time.time()

        while self.is_running and self.remaining_time > 0:
            elapsed_time = time.time() - start_time
            self.remaining_time -= elapsed_time
            start_time = time.time()

            logger.info(f"time left：{self.remaining_time:.2f} s")
            time.sleep(1)

        if self.is_running:
            self.stop()

    def stop(self):
        self.is_running = False
        # if self.timer:
            # self.timer.join()
        logger.info("Countdown ends")
        return AdamInterface.pause_dance()

    def set_time(self, new_time):
        self.remaining_time = new_time
        logger.info(f"Countdown has been modified to {self.remaining_time:.2f} s")


class FollowCountdownTimer:
    def __init__(self):
        self.remaining_time = 0
        self.timer = None
        self.is_running = False

    def edit_initial_time(self, initial_time):
        self.remaining_time = initial_time

    def start(self):
        self.is_running = True
        self.timer = threading.Thread(target=self._run)
        self.timer.start()

    def _run(self):
        start_time = time.time()

        while self.is_running and self.remaining_time > 0:
            elapsed_time = time.time() - start_time
            self.remaining_time -= elapsed_time
            start_time = time.time()

            logger.info(f"time left：{self.remaining_time:.2f} s")
            time.sleep(1)

        if self.is_running:
            self.stop()

    def stop(self, idle=True):
        self.is_running = False
        logger.info("Countdown ends")
        VisualDetectInterface.stop_following()
        AudioInterface.stop()
        AdamInterface.stop_move()
        if idle:
            AdamInterface.change_adam_status_idle("idle")


    def set_time(self, new_time):
        self.remaining_time = new_time
        logger.info(f"Countdown has been modified to {self.remaining_time:.2f} s")
