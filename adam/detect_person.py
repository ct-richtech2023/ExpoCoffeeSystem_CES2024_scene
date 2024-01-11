import threading
import time
from datetime import datetime
import random

import pytz
import requests
from common import conf
from common.api import AudioInterface
from common.schemas import total as total_schema
from loguru import logger
from common.db.database import get_db
from common.db.crud.coffee import update_detect_by_name
from common.conf import get_machine_config


class DetectPersonThread(threading.Thread):
    def __init__(self, desc=None):
        super().__init__()
        self.stopped = False  # exit thread or not
        self.run_flag = True
        self.is_person_flag = True
        self.desc = desc
        self.last_person_num = 100
        self.machine_config = total_schema.MachineConfig(**conf.get_machine_config())
        detect_ip = self.machine_config.jetson_ip
        self.url = "http://{}:5001/detect".format(detect_ip)
        self.db_session = next(get_db())
        timezone = get_machine_config().get('audio', '').get('timezone', '')
        self.local_tz = pytz.timezone(timezone)

        logger.info('start Detect Person Thread+++++++++++++++++++++++++++++++++=')

    def pause(self):
        logger.info('{} is start, Detect Person Thread pause recording'.format(self.desc))
        self.run_flag = False

    def proceed(self):
        logger.info('{} is end, Detect Person Thread continue to record'.format(self.desc))
        self.run_flag = True

    def stop(self):
        logger.info('{} Detect Person Thread thread stopped'.format(self.desc))
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
        {'data': [
            {
            'Area': 98016.953125,
            'Bottom': 719.0,
            'Center': [659.375, 554.265625],
            'ClassID': 62,
            'Confidence': 0.74951171875,
            'Left': 510.625,
            'Right': 808.125,
            'Top': 389.53125,
            'Width': 297.5
            }
        ]
        }
        """
        while not self.stopped:
            while self.run_flag:
                try:
                    update_dict = {'person': 0}  # name: status

                    response_date = self.get_data()
                    # logger.info(f"response_date:{response_date}")

                    # person detection process
                    person_list = response_date.get('person', [])
                    person_num = len(person_list)
                    if person_num > self.last_person_num:
                        # The number of people identified this time is more than the number of people identified last time
                        now_hour = datetime.now(self.local_tz).hour
                        # now = datetime.now()
                        # current_time = now.time()
                        hi_type = random.randint(0, 4)  # 1:根据时间判断 2:其余问候
                        if hi_type == 1:
                            if now_hour < 12:
                                AudioInterface.gtts('/richtech/resource/audio/voices/hi/hi1.mp3')
                            elif now_hour < 18:
                                AudioInterface.gtts('/richtech/resource/audio/voices/hi/hi2.mp3')
                            else:
                                AudioInterface.gtts('/richtech/resource/audio/voices/hi/hi3.mp3')
                        else:
                            random_num = random.randint(4, 19)
                            AudioInterface.gtts(f'/richtech/resource/audio/voices/hi/hi{random_num}.mp3')

                    self.last_person_num = person_num
                    update_dict['person'] = person_num

                except Exception as e:
                    self.network = False
                    logger.warning('sth error in get_data, err = {}'.format(e))
                    time.sleep(5)
                finally:
                    time.sleep(2)
            else:
                time.sleep(10)

"""
'hi/hi1.mp3': 'Good morning!',
'hi/hi2.mp3':'Good afternoon!',
'hi/hi3.mp3':'Good evening!',
'hi/hi4.mp3':'Hi!',
'hi/hi5.mp3':'Hello!',
'hi/hi6.mp3':'Hey!',
'hi/hi7.mp3':'How\'s it going?',
'hi/hi8.mp3':'How are you?',
'hi/hi9.mp3':'How have you been?',
'hi/hi10.mp3':'What\'s up?',
'hi/hi11.mp3':'What\'s new?',
'hi/hi12.mp3':'How\'s everything?',
'hi/hi13.mp3':'Long time no see!',
'hi/hi14.mp3':'It\'s been a while!',
'hi/hi15.mp3':'Greetings!',
'hi/hi16.mp3':'Good day!',
'hi/hi17.mp3':'Pleasure to meet you.',
'hi/hi18.mp3':'Welcome!',
'hi/hi19.mp3':'Fancy seeing you here!'
"""