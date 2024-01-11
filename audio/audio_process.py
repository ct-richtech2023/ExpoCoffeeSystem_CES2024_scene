import os
import subprocess
from loguru import logger
from sqlalchemy import true

from common.define import audio_dir
from common.utils import get_execute_cmd_result
from common import conf, utils


class AudioStatus:
    stopped = 'stopped'
    processing = 'processing'
    other_status = 'The audio has not been played!!!'


def get_ffplay_cmd(audiodev, audio_path):
    cmd = "SDL_AUDIODRIVER=alsa AUDIODEV=hw:{} ffplay -nodisp -autoexit -hide_banner -volume 100 {}".format(
        audiodev, audio_path)
    return cmd


class AudioManage:
    def __init__(self, audiodev):
        self.audiodev = audiodev
        self.music_process = None
        self.name = None
        self.sound_process = None

    def play_music(self, audio_name):
        self.name = audio_name
        audio_path = os.path.join(audio_dir, 'musics', audio_name)
        cmd = get_ffplay_cmd(self.audiodev, audio_path)
        logger.info('play music cmd is {}'.format(cmd))
        if self.music_process is not None:
            self.music_process.kill()
        self.music_process = subprocess.Popen(cmd, shell=True, encoding='utf-8')
        logger.info('now {} is playing'.format(self.name))

    def get_tts_cmd(self, text: str):
        wav_name = "sound.wav"
        speech_path = os.path.join(audio_dir, wav_name)
        ffplay_cmd = get_ffplay_cmd(self.audiodev, speech_path)
        command = "curl -X POST -H 'Content-Type: text/plain' --output {} --data '{}' 'http://tts:5002/api/tts' " \
                  "&& {}".format(speech_path, text, ffplay_cmd)
        return command

    def text_to_speech(self, text):
        cmd = self.get_tts_cmd(text)
        logger.info('text to speech popen cmd is {}'.format(cmd))
        if self.music_process is not None:
            self.music_process.kill()
        self.sound_process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                              stderr=subprocess.PIPE, encoding='utf-8')

    def text_to_speech_checkoutput(self, text):
        if self.sound_process is not None:
            self.sound_process.kill()
        cmd = self.get_tts_cmd(text)
        logger.info('text to speech checkout cmd is {}'.format(cmd))
        get_execute_cmd_result(cmd, true)

    def play_music_checkoutput(self, audio_name):
        logger.info('audio_dir====={} '.format(audio_dir))
        audio_path = os.path.join(audio_dir, audio_name)
        cmd = get_ffplay_cmd(self.audiodev, audio_path)
        logger.info('text to speech checkout cmd is {}'.format(cmd))
        get_execute_cmd_result(cmd, true)

    def get_status(self):
        if self.music_process is not None:
            if self.music_process.returncode is None:
                logger.info('{} processing！！！'.format(self.name))
                # value_status = {'audio': AudioStatus.processing}
                # self.rc.publish('audio', json.dumps(value_status))
                return AudioStatus.processing
            else:
                logger.info('{} stopped！！！'.format(self.name))
                # value_status = {'audio': AudioStatus.stopped}
                # self.rc.publish('audio', json.dumps(value_status))
                return AudioStatus.stopped
        else:
            logger.info('The audio has not been played!!!')
            value_status = {'audio': AudioStatus.other_status}
            # self.rc.publish('audio', json.dumps(value_status))
            return AudioStatus.other_status
