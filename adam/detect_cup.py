import threading
import time
import traceback

import requests
from common import conf
from common.api import AudioInterface
from common.schemas import total as total_schema
from loguru import logger
from common.db.database import get_db
from common.db.crud.coffee import update_detect_by_name
from common.utils import update_threads_step


class DetectCupStandThread(threading.Thread):
    def __init__(self, desc=None, steps_queue=None):
        super().__init__()
        self.stopped = False  # exit thread or not
        self.run_flag = True
        self.desc = desc
        self.machine_config = total_schema.MachineConfig(**conf.get_machine_config())
        detect_ip = self.machine_config.jetson_ip
        self.url = "http://{}:5000/detect".format(detect_ip)
        self.db_session = next(get_db())
        self.steps_queue = steps_queue

        # boundary error
        # self.cup_error_num = {'Left': 50, 'Right': 50, 'Top': 50, 'Bottom': 50}
        # self.cup_error_num = {'Left': 10, 'Right': 10, 'Top': 10, 'Bottom': 10}
        # self.foam_error_num = {'Left': 10, 'Right': 10, 'Top': 10, 'Bottom': 10}
        # self.steel_error_num = {'Left': 10, 'Right': 10, 'Top': 10, 'Bottom': 10}

        logger.info('start Detect Cold and Hot Cup Thread')

    def update_step(self, step):
        if self.steps_queue is not None:
            update_threads_step(status_queue=self.steps_queue, thread=threading.current_thread(), step=step)

    def pause(self):
        logger.info('{} is start, Detect Cold and Hot Cup Thread pause recording'.format(self.desc))
        self.run_flag = False
        self.update_step('pause')

    def proceed(self):
        logger.info('{} is end, Detect Cold and Hot Cup Thread continue to record'.format(self.desc))
        self.run_flag = True
        self.update_step('proceed')

    def stop(self):
        logger.info('{} Detect Cold and Hot Cup Thread thread stopped'.format(self.desc))
        self.stopped = True

    def get_data(self):
        try:
            headers = {}
            with requests.session() as s:
                response = s.request("GET", self.url, headers=headers, timeout=2)
                self.network = True
                response_date = response.json()
                return response_date
        except ConnectionError as err:
            self.network = False
            logger.warning('sth error in get_data, err = {}'.format(err))
            time.sleep(5)
        except Exception as e:
            self.network = False
            logger.warning('sth error in get_data, err = {}'.format(e))
            time.sleep(5)

    @staticmethod
    def in_range(detection_pose, boundary, error_num):
        if abs(boundary.left - detection_pose['Left']) < error_num['Left'] and abs(
                boundary.right - detection_pose['Right']) < error_num['Right'] and abs(
            boundary.top - detection_pose['Top']) < error_num['Top'] and abs(
            boundary.bottom - detection_pose['Bottom']) < error_num['Bottom']:
            return True
        return False

    def run(self) -> None:
        """
        {
            "espress_cup": 0, 0有东西1无东西
            "foam_cup": 0, 0有东西1无东西
            "left_cup_stand1": 0, # 无东西
            "left_cup_stand2": 1, # 有东西
            "left_cup_stand3": 0,
            "right_cup_stand4": 0,
            "right_cup_stand5": 0,
            "right_cup_stand6": 0,
        }
        """
        self.update_step('start')
        while not self.stopped:
            while self.run_flag:
                try:
                    response_date = self.get_data().get("cup")
                    # logger.info(f"response_date:{response_date}")
                    if response_date:
                        # update status in database
                        for key, value in response_date.items():
                            # if key in ["foam_cup", "espresso_cup"]:
                            #     if value == 1:
                            #         update_detect_by_name(self.db_session, key, 0)
                            #     else:
                            #         update_detect_by_name(self.db_session, key, 1)
                            # else:
                            #     update_detect_by_name(self.db_session, key, value)

                            update_detect_by_name(self.db_session, key, value)

                except Exception as e:
                    self.network = False
                    logger.warning('sth error in get_data, err = {}'.format(traceback.format_exc()))
                    time.sleep(5)
                finally:
                    time.sleep(1)
            else:
                time.sleep(10)
        self.update_step('end')
