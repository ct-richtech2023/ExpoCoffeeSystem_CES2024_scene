import json
import time

import redis
from loguru import logger

from common import conf


class Redis:
    _Instance = None
    _Client = None

    def __new__(cls, *args, **kwargs):
        if cls._Instance is None:
            cls._Instance = object.__new__(cls)
        return cls._Instance

    def __init__(self):
        if not Redis._Client:
            self.redis_client = self._create_client()

    @staticmethod
    def _create_client():
        host = 'webdis' if conf.check_is_production() else '127.0.0.1'
        redis_client = redis.StrictRedis(host=host, port=6379, db=0)
        logger.info('create redis connect pool client')
        Redis._Client = redis_client
        return redis_client

    @property
    def client(self):
        return self.redis_client

    def publish(self, channel: str, msg: str):
        self.client.publish(channel, msg)
        logger.info('publish channel={} msg={}'.format(channel, msg))

    def set_json(self, key, value: dict, timeout: int = None):
        value_string = json.dumps(value)
        if timeout:
            self.client.setex(key, timeout, value_string)
        else:
            self.client.set(key, value_string)

    def get_json(self, key) -> dict:
        value = self.client.get(key)
        if not value:
            return value
        json_string = bytes.decode(value)
        try:
            json_dict = json.loads(json_string)
            return json_dict
        except Exception as e:
            err_msg = 'json loads failed, str is {}, err={}'.format(json_string, str(e))
            logger.warning(err_msg)
            raise Exception(err_msg)

    def frontend_get_value_from_backend(self, key, channel, publish_value, timeout=2):
        try:
            value = self.get_json(key)
            if value:
                return (400, value['error']) if 'error' in value else (200, value)

            if isinstance(publish_value, dict):
                publish_value = json.dumps(publish_value)
            self.publish(channel, publish_value)
            start_time = time.perf_counter()
            while True:
                time.sleep(0.5)
                value = self.get_json(key)
                if value:
                    return (400, value['error']) if 'error' in value else (200, value)
                if time.perf_counter() - start_time > timeout:
                    return 400, 'get status timeout'
        except Exception as e:
            return 400, str(e)
