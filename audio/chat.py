import datetime
import random
import threading
import time
import urllib
import pytz

import requests
from loguru import logger
from common.db.crud import audio as audio_crud
from common.define import AudioConstant
from common.conf import get_machine_config


class TextMsg:
    # 2xx Thunderstorm 雷暴天气
    Thunderstorm1 = 'whew it is normally not so hot during a storm on my home planet.'  # 高温雷暴
    Thunderstorm2 = 'Enjoy this delicious coffee while you wait for the thunder & lightning to subside.'  # 适宜温度+雷暴

    # 3xx: Drizzle 毛毛雨天气
    Drizzle1 = 'What a nice day to watch me make coffee for you!'  # 温度适宜+毛毛雨
    Drizzle2 = 'Come inside & warm your hands with a cup of hot coffee! A sure way to warm up anyones mood!'  # 低温+毛毛雨

    # 5xx: Rain 雨天气
    Rain1 = 'Come inside & dry off with a refreshing coffee!'  # 高温+雨
    Rain2 = 'A tasty coffee can make the rain go away! Come in & stay dry with me'  # 温度适宜+雨
    Rain3 = 'Wet & cold outside? Stay warm with a hot drink that only ADAM can provide!'  # 低温+雨

    # 6xx: Snow 雪天气
    Snow1 = 'Please allow me to offer you a hot beverage to help shake off the cold! Coffee is my favorite, even in the snow.'  # 低温+雪

    # 7xx Atmosphere 雾天气
    Atmosphere1 = 'Come in to cool off with a nice cold coffee!'  # 高温+雾
    Atmosphere2 = ''  # 温度适宜+雾
    Atmosphere3 = 'It\'s so gloomy outside, would you like a coffee to help warm you up?'  # 低温+雾

    # 800 Clear 晴天
    Clear1 = 'It looks so hot outside! You can cool down with an ice cold coffee!'  # 高温+晴天
    Clear2 = 'It\'s so beautiful outside, such a nice day to enjoy coffee!'  # 温度适宜+晴天
    Clear3 = 'Come in from the cold & warm up your day with nice coffee!'  # 低温+晴天

    # 80x Clouds 多云
    Clouds1 = 'Ice cold coffee is perfect for hot days like today!'  # 低温+晴天
    Clouds2 = 'Such a nice day! Allow  to make you coffee to drink in the shade!'  # 低温+晴天
    Clouds3 = 'Come in from the cold & warm up your day with nice hot coffee!'  # 低温+晴天

    # Evening
    Evenings = ['Good evening, Welcome in!',
                'Welcome in, hope you\'ve had a wonderful day so far']

    # Afternoon
    Afternoons = ['Good afternoon, welcome to CloutTea',
                  'Good afternoon, welcome in!',
                  'Hi, Good afternoon!']

    # Morning
    Mornings = [
        'Good morning, allow me to make your favorite coffee to get your day started off right!',
        'Hello, good morning, Welcome in.']

    # Standard
    Standards = ['Hello! Welcome in!',
                 'Hi, Welcome!']


class ChatThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.weather_data = {}
        self.chat_time = time.time()
        timezone = get_machine_config().get('audio', '').get('timezone', '')
        self.local_tz = pytz.timezone(timezone)
        self.lat = get_machine_config().get('audio', '').get('lat', '')
        self.lon = get_machine_config().get('audio', '').get('lon', '')

    @property
    def space_time(self):
        return random.randint(30, 100) * 60  # 随机在30min到100min之内

    def get_weather(self, units='metric'):
        params = {'lat': self.lat, 'lon': self.lon, 'units': units,
                  'appid': '8212c42cc9824908e9f9b397a1d9c7ce',
                  'exclude': 'minutely,hourly,daily,alerts'}
        params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        url = 'https://api.openweathermap.org/data/3.0/onecall'

        # 每天获取一次天气信息
        try:
            res = requests.get(url, params=params)
            logger.info(
                'url={} params={}, result={}'.format(url, params,
                                                     res.json()))
            current_weather = res.json().get('current')
            temp = current_weather.get('temp')
            weather = current_weather.get('weather')[0].get('main')
            weather_id = str(current_weather.get('weather')[0].get('id'))
            feel_temp = current_weather.get('feels_like')

            self.weather_data['temp'] = temp
            self.weather_data['weather'] = weather
            self.weather_data['weather_id'] = weather_id
            self.weather_data['feel_temp'] = feel_temp
            self.weather_data['date'] = datetime.datetime.now(self.local_tz).strftime("%Y-%m-%d")
        except ConnectionError as e:
            pass

    def weather_msg(self):
        msg = ''
        high_temp = 30  # todo
        low_temp = 10
        right_temp = [15, 25]
        if self.weather_data.get('date') != datetime.datetime.now(self.local_tz).strftime("%Y-%m-%d"):
            self.get_weather()
        if self.weather_data['weather_id'].startswith('2'):
            # Group 2xx: Thunderstorm
            if self.weather_data['feel_temp'] >= high_temp:
                msg = TextMsg.Thunderstorm1
            elif right_temp[0] < self.weather_data['feel_temp'] < right_temp[1]:
                msg = TextMsg.Thunderstorm2
        elif self.weather_data['weather_id'].startswith('3'):
            # Group 3xx: Drizzle
            if right_temp[0] < self.weather_data['feel_temp'] < right_temp[1]:
                msg = TextMsg.Drizzle1
            elif self.weather_data['feel_temp'] <= low_temp:
                msg = TextMsg.Drizzle2
        elif self.weather_data['weather_id'].startswith('5'):
            # Group 5xx: Rain
            if self.weather_data['feel_temp'] >= high_temp:
                msg = TextMsg.Rain1
            elif right_temp[0] < self.weather_data['feel_temp'] < right_temp[1]:
                msg = TextMsg.Rain2
            elif self.weather_data['feel_temp'] <= low_temp:
                msg = TextMsg.Rain3
        elif self.weather_data['weather_id'].startswith('6'):
            # Group 6xx: Snow
            if self.weather_data['feel_temp'] <= low_temp:
                msg = TextMsg.Snow1
        elif self.weather_data['weather_id'].startswith('7'):
            # Group 7xx: Atmosphere
            if self.weather_data['feel_temp'] >= high_temp:
                msg = TextMsg.Atmosphere1
            elif right_temp[0] < self.weather_data['feel_temp'] < right_temp[1]:
                msg = TextMsg.Atmosphere2
            elif self.weather_data['feel_temp'] <= low_temp:
                msg = TextMsg.Atmosphere3
        elif self.weather_data['weather_id'] == '800':
            # Group 800: Clear
            if self.weather_data['feel_temp'] >= high_temp:
                msg = TextMsg.Clear1
            elif right_temp[0] < self.weather_data['feel_temp'] < right_temp[1]:
                msg = TextMsg.Clear2
            elif self.weather_data['feel_temp'] <= low_temp:
                msg = TextMsg.Clear3
        elif self.weather_data['weather_id'].startswith('80'):
            # Group 80x: Clouds
            if self.weather_data['feel_temp'] >= high_temp:
                msg = TextMsg.Clouds1
            elif right_temp[0] < self.weather_data['feel_temp'] < right_temp[1]:
                msg = TextMsg.Clouds2
            elif self.weather_data['feel_temp'] <= low_temp:
                msg = TextMsg.Clouds3
        # self.gtts(msg)  # speak weather msg
        return msg

    def time_msg(self):
        now = datetime.datetime.now(self.local_tz).hour
        if 7 < now < 12:
            msg = random.choice(TextMsg.Mornings)
        elif 12 < now < 17:
            msg = random.choice(TextMsg.Afternoons)
        elif 17 < now < 22:
            msg = random.choice(TextMsg.Evenings)
        else:
            msg = random.choice(TextMsg.Standards)
        return msg

    def chat(self):
        choice = random.randint(1, 2)
        self.chat_time = time.time()
        if choice == 1:
            msg = self.weather_msg()
        else:
            msg = self.time_msg()
        return msg

    def run(self):
        next_time = self.chat_time + self.space_time
        logger.info('now={}'.format(time.time()))
        logger.info('next_time={}'.format(next_time))
        while True:
            if time.time() < next_time:
                time.sleep(1)
            else:
                audio_crud.add_speak(self.chat(), AudioConstant.Level.chat)
                next_time = self.chat_time + self.space_time
                logger.info('next_time={}'.format(next_time))


