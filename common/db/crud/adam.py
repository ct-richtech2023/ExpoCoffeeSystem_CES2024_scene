from common.db.tables.adam import TapStatus, Dance
from common.db.database import MySuperContextManager
from common.define import AudioConstant
from common.myerror import DBError


def update_one_tap(name, status):
    with MySuperContextManager() as db:
        db.query(TapStatus).filter(TapStatus.material_name == name).update(dict(status=status))
        db.commit()


def init_tap():
    with MySuperContextManager() as db:
        db.query(TapStatus).filter(TapStatus.material_name != 'warm_up').update(dict(status=0))


def get_all_status():
    with MySuperContextManager() as db:
        taps = db.query(TapStatus).order_by(TapStatus.id.asc()).all()
        result = {}
        for tap in taps:
            result[tap.material_name] = tap.status
        return result


def get_warm_up_err_time():
    with MySuperContextManager() as db:
        record = db.query(TapStatus).filter(TapStatus.material_name == 'warm_up').first()
        if record:
            return record.status
        return 0


def init_dance(db):
    db.query(Dance).update(dict(sort=None, now_playing=0))


def init_dance_display(db):
    db.query(Dance).update(dict(display=None))


def get_dance_list(db):
    record_list = []
    if records := db.query(Dance).order_by(Dance.display.asc(), Dance.id.asc()).all():
        for record in records:
            record_list.append(record.to_dict())
        return record_list


def get_now_playing(db):
    record_dict = {}
    if record := db.query(Dance).filter(Dance.now_playing == 1).first():
        record_dict["result"] = record.to_dict()
    else:
        record_dict["result"] = {}
    return record_dict


def update_dance(db, dance_list):
    for dance in dance_list:
        dance.pop('id')
        dance_name = dance.pop('dance_name')
        db.query(Dance).filter(Dance.dance_name == dance_name).update(dance)


def update_single_dance(db, dance_num, now_playing):
    if dance_num:
        db.query(Dance).filter(Dance.dance_num == dance_num).update(dict(now_playing=now_playing))


def init_dance_now_playing(db):
    db.query(Dance).update(dict(now_playing=0))
