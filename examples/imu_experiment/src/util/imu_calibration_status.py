from enum import Enum
from random import randint


class ImuCalibrationStatus(Enum):
    UNKNOWN = 0
    UNRELIABLE = 1
    ACCURACY_LOW = 2
    ACCURACY_MEDIUM = 3
    ACCURACY_HIGH = 4

    @staticmethod
    def get_random_status():
        random_status = randint(0, 4)
        if random_status == 0:
            return ImuCalibrationStatus.UNKNOWN
        elif random_status == 1:
            return ImuCalibrationStatus.UNRELIABLE
        elif random_status == 2:
            return ImuCalibrationStatus.ACCURACY_LOW
        elif random_status == 3:
            return ImuCalibrationStatus.ACCURACY_MEDIUM
        elif random_status == 4:
            return ImuCalibrationStatus.ACCURACY_HIGH

    def to_string(self):
        if self == ImuCalibrationStatus.UNKNOWN:
            return "UNKNOWN"
        elif self == ImuCalibrationStatus.UNRELIABLE:
            return "UNRELIABLE"
        elif self == ImuCalibrationStatus.ACCURACY_LOW:
            return "ACCURACY_LOW"
        elif self == ImuCalibrationStatus.ACCURACY_MEDIUM:
            return "ACCURACY_MEDIUM"
        elif self == ImuCalibrationStatus.ACCURACY_HIGH:
            return "ACCURACY_HIGH"
