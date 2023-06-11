from enum import Enum


class Encoding(Enum):
    UNKNOWN = 0
    RAW = 1
    PROTOBUF = 2
    AVRO = 3
    JSON = 4
    UTF8 = 5
