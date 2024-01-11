from threading import Thread
import time
from loguru import logger

from common.db.crud.center import get_constant_setting
from common.db.database import get_db
from common.define import Constant
from common.api import AdamInterface, AudioInterface, CoffeeInterface

class FreshThread(Thread):
    def __init__(self):
        super(FreshThread, self).__init__()
        self.run_flag = True
        self.pause_flag = False
        self.db = next(get_db())
        self.milk_settings = {}
        self.clean_flag = {}
        self.init()

    def init(self):
        constants = get_constant_setting(self.db)
        if constants:
            for constant in constants:
                self.milk_settings[constant.name] = {'interval': int(constant.param.get('interval', 15)),
                                                     'last_time': int(time.time()),
                                                     'ignore': int(constant.param.get('ignore', 0)),
                                                     'clean_time': constant.param.get('clean_time', 0)}
        logger.info('milk_settings:{}'.format(self.milk_settings))

    def stop(self):
        self.run_flag = False
        logger.info('check thread stopped')

    def update_last_time(self, material_names):
        for name in material_names:
            if self.milk_settings.get(name):
                logger.info('update last_time for {}'.format(name))
                self.milk_settings[name]['last_time'] = int(time.time())

    def refresh_settings(self, material_name, interval=None, ignore=None, clean_time=None):
        if self.milk_settings.get(material_name):
            if interval:
                self.milk_settings[material_name]['interval'] = int(interval)
            if ignore is not None:
                self.milk_settings[material_name]['ignore'] = int(ignore)
            if clean_time is not None:
                self.milk_settings[material_name]['clean_time'] = int(clean_time)
            self.update_last_time([material_name])
        logger.info('update milk setting to {} in thread'.format(self.milk_settings))

    def pause(self):
        self.pause_flag = True

    def proceed(self):
        self.pause_flag = False

    def run(self):
        logger.info('fresh check thread started')
        speak_again = True
        wait_time = 0
        while self.run_flag:
            sleep_time = 30  #30
            need_to_fresh = set()
            for material, fresh_dict in self.milk_settings.items():
                if fresh_dict.get('ignore') == 1:
                    logger.info('ignored {}'.format(material))
                    continue
                if int(time.time()) - fresh_dict.get('last_time') >= fresh_dict.get('interval') * 60:
                    materialtuple = (material, fresh_dict.get('clean_time'))
                    need_to_fresh.add(materialtuple)


            if need_to_fresh:
                try:
                    if speak_again == True or wait_time > 30:
                        # AudioInterface.gtts('need to clean')
                        wait_time = 0
                        speak_again = False
                    CoffeeInterface.pause_making()
                    zero_dict = AdamInterface.zero()
                    # zero_dict = {'msg': 'ok'}
                    if zero_dict.get('msg') == 'not ok':
                        sleep_time = 1
                        wait_time += 1
                    else:
                        # b = [1] * len(need_to_fresh)
                        # self.clean_flag = dict(zip(need_to_fresh, b))
                        for b in need_to_fresh:
                            self.clean_flag[b[0]] = 1
                        logger.info(f" self.clean_flag  {self.clean_flag}")

                        AudioInterface.gtts('I\'m going to clean the milk tube')
                        logger.info('call adam to fresh the milk tap')
                        AdamInterface.clean_milk_pipe(list(need_to_fresh))
                        CoffeeInterface.proceed_making()
                        material_names_list = []
                        for tap in list(need_to_fresh):
                            material_names_list.append(tap[0])
                        self.update_last_time(material_names_list)
                        need_to_fresh.clear()
                        self.clean_flag.clear()

                        sleep_time = 30
                        wait_time = 0
                except Exception as e:
                    logger.warning('have error in clean_milk_tap: {}'.format(str(e)))
            time.sleep(sleep_time)
