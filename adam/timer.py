import threading
import asyncio
import time
from loguru import logger

import requests

import aiohttp

RUN = True


class TimerThread(threading.Thread):
    def __init__(self, total_duration, call_interval):
        super().__init__()
        self.total_duration = total_duration
        self.call_interval = call_interval

        self.pause_flag = False
        self.start_time = 0

    def pause(self):
        self.pause_flag = True
        self.total_duration = 0

    def proceed(self, total_minutes) -> None:
        self.total_duration = total_minutes * 60
        self.pause_flag = False

    def run(self) -> None:
        call = 1
        while True:
            if not self.pause_flag:
                if not self.start_time:
                    self.start_time = int(time.time())
                    requests.get('http://127.0.0.1:5001/start')
                    call = 1
                remain_time = self.total_duration - (int(time.time()) - self.start_time)
                if remain_time > 1:
                    try:
                        logger.info(f'第{call}次调用, 剩余{remain_time}s')
                        requests.get('http://127.0.0.1:5001/sleep', timeout=remain_time)
                        call += 1
                    except requests.Timeout:
                        self.pause()
                        requests.get('http://127.0.0.1:5001/end')
                        logger.info('计时器到时间，请求退出')
                    except Exception:
                        pass
                logger.info(f'sleep {self.call_interval}')
                time.sleep(self.call_interval)
                logger.info('sleep end')
            else:
                logger.info('计时器暂停')
                time.sleep(1)


# 示例用的异步任务
async def example_task():
    async with aiohttp.ClientSession() as session:
        async with session.get("http://example.com") as response:
            result = await response.text()
            logger.info("异步任务结果:", result)


# 定义一个模拟的耗时异步任务
async def simulated_long_running_task(i):
    logger.info(f"耗时任务开始{i}")
    for i in range(10):
        if RUN:
            logger.info(i + 1)
            await asyncio.sleep(1)  # 异步等待 10 秒
        else:
            logger.info('计时结束')
            break
    logger.info("耗时任务结束")


# 使用示例
timer_thread = TimerThread(25, 1)
# 主程序继续执行
logger.info("主程序运行中...")
timer_thread.start()
# 等待计时器线程结束
timer_thread.join()
logger.info("主程序和计时器都已完成")
