import os

from loguru import logger

from audio_process import AudioManage
from common import conf
from common.db.crud import audio as audio_crud
from common.define import audio_dir, AudioConstant
from common.schemas import total as total_schema
from playtts import PlayThread
from chat import ChatThread

os.environ[
    'GOOGLE_APPLICATION_CREDENTIALS'] = '/richtech/audio/adamtts-tts.json'
music_dir = os.path.join(audio_dir, 'musics')
sound_dir = os.path.join(audio_dir, 'sounds')
gtts_out = os.path.join(audio_dir, 'voices', 'gtts_out.mp3')


def get_audio_obj():
    if not Audio.Instance:
        Audio.Instance = Audio()
    return Audio.Instance


def get_resource_name():
    return {
        "sound": os.listdir(sound_dir) if os.path.isdir(sound_dir) else [],
        "music": os.listdir(music_dir) if os.path.isdir(music_dir) else []
    }


class Audio:
    Instance = None

    def __init__(self):
        os.system("amixer set PCM 100%")
        logger.info('cmd is amixer set Master 100%')
        # self.audiodev = total_schema.MachineConfig(
        #     **conf.get_machine_config()).sound.AUDIODEV
        self.audiodev = self._get_audiodev()
        self.set_default_audiodev()
        self.music_subprocess = AudioManage(self.audiodev)
        self.sound_subprocess = AudioManage(self.audiodev)
        self.tts_subprocess = AudioManage(self.audiodev)
        self.gtts_thread = PlayThread(gtts_out)
        self.gtts_thread.setDaemon(True)
        self.chat_thread = ChatThread()
        self.chat_thread.setDaemon(True)
        # audio_crud.done_all()
        self.gtts_thread.start()
        self.chat_thread.start()

    def _get_audiodev(self):
        cmd = "aplay -l |grep USB |awk -F \" \" '{print $2}'"
        with os.popen(cmd) as p:
            card = p.readline().strip()
            if card and len(card) >= 2:
                logger.info('card is {}, len={}'.format(card, len(card)))
                return '{},0'.format(card[:-1])
        raise Exception('Audio start error, no USB sound card')

    @property
    def status(self):
        logger.info('get current audio status')
        return self.get_audio_status()

    @property
    def audio_resource(self):
        logger.info('get audio resource')
        return get_resource_name()

    def set_default_audiodev(self):
        default_card = self.audiodev.split(',')[0].strip()
        content = 'defaults.ctl.card {}\ndefaults.pcm.card {}\ndefaults.timer.card {}\n'.format(
            default_card,
            default_card,
            default_card)
        with open('/etc/asound.conf', 'w') as f:
            f.write(content)

    def stop_audio(self):
        logger.info("stop_audio")
        os.system('ps -ef|grep ffplay|grep -v grep|cut -c 9-16|xargs kill -9')

    def get_audio_status(self):
        result = self.music_subprocess.get_status()
        logger.info("get_audio_status result='{}'".format(result))
        return {'status': result}

    def tts(self, text: str, sync: bool = True):
        logger.info("tts sync={} text={}".format(sync, text))
        if sync:
            self.tts_subprocess.text_to_speech_checkoutput(text)
        else:
            self.tts_subprocess.text_to_speech(text)


    def gtts(self, text, level=1, sync=False):
        logger.info('gtts text={}, level={}'.format(text, level))
        if sync:
            audio_crud.add_speak(text, AudioConstant.Level.now,
                                 AudioConstant.SpeakStatus.said)
            if self.gtts_thread and self.gtts_thread.is_alive():
                self.gtts_thread.pause()
            play_file = self.gtts_thread.generate_mp3(text)
            if play_file and os.path.exists(play_file):
                self.gtts_thread.play_voice(file_name=play_file)
            if self.gtts_thread and self.gtts_thread.is_alive():
                self.gtts_thread.proceed()
        else:
            audio_crud.add_speak(text, level)
            if self.gtts_thread is None or not self.gtts_thread.is_alive():
                self.gtts_thread = PlayThread(gtts_out)
                self.gtts_thread.start()
