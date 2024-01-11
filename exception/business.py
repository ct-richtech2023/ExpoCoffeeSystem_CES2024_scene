from common.db.database import get_db


def get_exception_obj():
    if not DealWithException.Instance:
        DealWithException.Instance = DealWithException()
    return DealWithException.Instance


class DealWithException:
    Instance = None

    def __init__(self):
        self.db_session = next(get_db())

    # @property
    # def db_session(self):
    #     return next(get_db())

    # def get_failed_task(self):
    #     all_task_records = center_crud.get_all_order_status(self.db_session)
    #     print(all_task_records)
    #     all_drink_records = milktea_crud.get_all_milktea_records(self.db_session)
    #     uuid_failed_msg = {record.task_uuid: record.failed_msg for record in all_drink_records}
    #     failed_record_msg = {
    #         record.task_uuid: {
    #             'order_number': record.order_number,
    #             'formula': record.formula,
    #             'status': record.status,
    #             'failed_msg': uuid_failed_msg.get(record.task_uuid, ''),
    #         }
    #         for record in all_task_records
    #     }
    #     return failed_record_msg
