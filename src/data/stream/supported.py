from enum import Enum


class StreamType(Enum):
    NONE = 0
    STD = 1
    FILE = 2
    SERIAL = 3


STREAM_TYPE_MAP = {
        'std': StreamType.STD,
        'file': StreamType.FILE,
        'serial': StreamType.SERIAL,
    }


def get_supported_streams() -> [str]:
    return STREAM_TYPE_MAP.keys()


def get_stream_type(stream: str) -> StreamType:
    if stream is None:
        return StreamType.NONE
    else:
        return STREAM_TYPE_MAP[stream.lower()]
