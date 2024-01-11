from threading import Thread
from queue import Queue
from loguru import logger

import time

from common.api import ASWServerInterface
from common.db.database import MySuperContextManager
from common.db.crud.coffee import get_one_cleaning_history, update_cleaning_history


class CleaningHistoryThread(Thread):
    def __init__(self):
        super(CleaningHistoryThread, self).__init__()

    def report(self):
        with MySuperContextManager() as db:
            next_cleaning_record = get_one_cleaning_history(db)
            if next_cleaning_record:
                try:
                    new_record = next_cleaning_record.to_dict()
                    new_record["flag"] = 1
                    logger.debug(f'cleaning_record {new_record}')
                    ASWServerInterface.add_cleaning_history(new_record)
                    update_cleaning_history(db, next_cleaning_record.id)
                except Exception as e:
                    logger.warning(str(e))
                    logger.warning('cleaning_history {} report failed'.format(next_cleaning_record.name))

    def run(self):
        while True:
            self.report()
            time.sleep(2)
