from common.db.tables.audio import Speak
from common.db.database import get_db
from common.define import AudioConstant

db = next(get_db())


def add_speak(text, level=1, status=AudioConstant.SpeakStatus.waiting):
    speak = Speak(text=text, level=level, status=status)
    db.add(speak)
    try:
        db.commit()
    except Exception as e:
        pass


def get_next_speak() -> Speak:
    next_speak = db.query(Speak).filter_by(status=AudioConstant.SpeakStatus.waiting).order_by(Speak.level.desc(),
                                                                                              Speak.id.asc()).first()
    if next_speak:
        return next_speak


def done(speak: Speak):
    speak.status = AudioConstant.SpeakStatus.said
    try:
        db.commit()
    except Exception as e:
        print('done has error {} \n {}'.format(str(e), e))
        pass


def done_all():
    speaks = db.query(Speak).filter_by(status=AudioConstant.SpeakStatus.waiting).all()
    for speak in speaks:
        speak.status = AudioConstant.SpeakStatus.said
    db.commit()
