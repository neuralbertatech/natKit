from enum import Enum
from random import randint


class ImuConnectionStatus(Enum):
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2

    def get_color(self):
        if self == ImuConnectionStatus.DISCONNECTED:
            return "#FF0000"
        elif self == ImuConnectionStatus.CONNECTING:
            return "#FFFF00"
        elif self == ImuConnectionStatus.CONNECTED:
            return "#00FF00"

    @staticmethod
    def get_random_status():
        random_status = randint(0, 2)
        if random_status == 0:
            return ImuConnectionStatus.DISCONNECTED
        elif random_status == 1:
            return ImuConnectionStatus.CONNECTING
        elif random_status == 2:
            return ImuConnectionStatus.CONNECTED
