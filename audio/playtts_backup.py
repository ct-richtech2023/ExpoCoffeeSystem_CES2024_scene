import threading
import time

from google.cloud import texttospeech
from loguru import logger
from pydub import AudioSegment
from pydub.playback import play

from common.db.crud.audio import get_next_speak, done
from common.define import AudioConstant


class PlayThread(threading.Thread):
    def __init__(self, gtts_out):
        """
        thread for recording arm's angles every 0.5s
        :param arm: XArmAPI obj
        :param file_path: where to save records
        :param desc:
        """
        super().__init__()
        self.gclient = texttospeech.TextToSpeechClient()
        self.gtts_out = gtts_out
        self.pause_flag = False
        self.stop_flag = False
        self.paused = 1

    def pause(self):
        """
        pause playing
        """
        logger.info('pause this play thread')
        self.pause_flag = True
        while not self.paused:
            time.sleep(0.5)

    def stop(self):
        logger.info('pause this play thread')
        self.stop_flag = True

    def proceed(self):
        logger.info('continue to play')
        self.pause_flag = False

    def generate_mp3(self, text):
        if text.endswith('.mp3'):
            # 以MP3结尾说明是本地文件，直接返回文件名
            logger.debug('text={}'.format(text))
            return text
        else:
            # 生成mp3文件并返回生成的文件名
            voice = texttospeech.VoiceSelectionParams(
                language_code="en-US", name='en-US-Wavenet-D',
                ssml_gender=texttospeech.SsmlVoiceGender.MALE
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=0.89,  # 稍微加快语速
                pitch=0.80,  # 提高音调来表示更高兴的情绪
                volume_gain_db=16.0
            )
            # for file_name, text in gene_map.items():
            synthesis_input = texttospeech.SynthesisInput(text=text)
            try:
                response = self.gclient.synthesize_speech(
                    input=synthesis_input, voice=voice, audio_config=audio_config, timeout=3
                )
                with open(self.gtts_out, "wb") as out:
                    out.write(response.audio_content)
                    print('Audio content written to file "gtts_out.mp3"')
            except Exception as e:
                logger.error('generate mp3 error, err={}'.format(str(e)))
                # return None
                return AudioConstant.get_mp3_file(AudioConstant.TextCode.generate_failed)
            return self.gtts_out

    def play_voice(self, file_name, voice_db: int = 10):
        self.paused = 0
        if file_name is not None:
            voice = AudioSegment.from_mp3(file_name) + voice_db
            play(voice)
        self.paused = 1

    def run(self):
        while True:
            next_speak = get_next_speak()
            if next_speak:
                if self.pause_flag:
                    logger.info('paused')
                    time.sleep(1)
                    continue
                if not self.stop_flag:
                    play_file = self.generate_mp3(next_speak.text)
                    logger.debug('play_file={}'.format(play_file))
                    self.play_voice(file_name=play_file)
                    done(next_speak)
            else:
                logger.info('sleep')
                self.paused = 1
                time.sleep(1)
