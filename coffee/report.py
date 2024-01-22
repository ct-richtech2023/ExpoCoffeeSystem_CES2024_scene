from threading import Thread
from queue import Queue
from loguru import logger

import time

from common.api import ASWServerInterface
from common.db.crud.coffee import get_one_waiting_record, get_report_uuids, add_report, done_report, get_one_report_uuids


class ReportThread(Thread):
    def __init__(self):
        super(ReportThread, self).__init__()

    def report(self):
        next_report_uuid = get_one_report_uuids()
        if next_report_uuid:
            try:
                coffee = get_one_waiting_record(next_report_uuid)
                logger.debug('report {}'.format(next_report_uuid))
                if ASWServerInterface.making_report(next_report_uuid, coffee.dict()):
                    done_report(next_report_uuid)
            except Exception as e:
                logger.warning('{} report failed'.format(next_report_uuid))

    def run(self):
        while True:
            self.report()
            time.sleep(2)
