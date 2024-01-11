import os

from fastapi import APIRouter, Depends
from loguru import logger

from business import Audio, get_audio_obj
from common.define import Channel
from common.utils import get_current_func_name

router = APIRouter(
    prefix="/{}".format(Channel.audio),
    tags=[Channel.audio],
    responses={404: {"description": "Not found"}},
    on_startup=[get_audio_obj]
)


@router.post("/music", description="play music in background")
async def play_music(name: str, delay=None, obj: Audio = Depends(get_audio_obj)):
    logger.info("{} {}".format(get_current_func_name(), name))
    try:
        obj.gtts_thread.pause()
        obj.music_subprocess.play_music(os.path.join(name))
    finally:
        obj.gtts_thread.proceed()
    return 'ok'


@router.post("/sound", description='Play Sound')
async def play_sound(name: str, obj: Audio = Depends(get_audio_obj)):
    logger.info("{} {}".format(get_current_func_name(), name))
    obj.music_subprocess.play_music_checkoutput(os.path.join('sounds/', name))
    return 'ok'


@router.post("/stop", summary='Stop Music or Sound')
def stop_audio(obj: Audio = Depends(get_audio_obj)):
    obj.stop_audio()
    return 'ok'


@router.post("/tts", description='let adam say words')
async def tts(text: str, sync: bool = True, obj: Audio = Depends(get_audio_obj)):
    obj.tts(text, sync)
    return 'ok'


@router.post("/gtts", description='let adam say words')
async def gtts(text: str, level=1, sync: bool = False, obj: Audio = Depends(get_audio_obj)):
    obj.gtts(text.strip('"'), level, sync)
    return 'ok'


# @router.post("/weather", description='let adam say words')
# async def weather(lat=None, lon=None, units=None, obj: Audio = Depends(get_audio_obj)):
#     # obj.weather(lat, lon, units)
#     # obj.weather()
#     return obj.weather()


@router.get("/status", summary='get current audio status')
def get_status(obj: Audio = Depends(get_audio_obj)):
    return obj.status


@router.get("/resource", description='get audio resource')
def get_audio_resource(obj: Audio = Depends(get_audio_obj)):
    return obj.audio_resource
