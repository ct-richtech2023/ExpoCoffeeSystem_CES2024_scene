from pydantic import BaseModel


class PicovoiceConfig(BaseModel):
    udp_port: int
    audio_device_index: int
    access_key: str
