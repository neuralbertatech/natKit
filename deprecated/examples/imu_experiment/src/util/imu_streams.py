from __future__ import annotations

from natKit.common.kafka import Stream
from dataclasses import dataclass
from typing import List

from . import ImuConnectionStatus
from . import ImuCalibrationStatus


@dataclass
class ImuStreams:
    left_wrist: Stream = None
    left_elbow: Stream = None
    left_shoulder: Stream = None
    trunk: Stream = None
    right_shoulder: Stream = None
    right_elbow: Stream = None
    right_wrist: Stream = None

    @staticmethod
    def createFromList(streams: List[Stream]) -> ImuStreams:
        imu_streams = ImuStreams()
        imu_stream_locations = [
            imu_streams.left_wrist,
            imu_streams.left_elbow,
            imu_streams.left_shoulder,
            imu_streams.trunk,
            imu_streams.right_shoulder,
            imu_streams.right_elbow,
            imu_streams.right_wrist,
        ]
        for i, stream in enumerate(streams[: len(imu_stream_locations)]):
            imu_streams.set_at_index(stream, i)

        return imu_streams

    def get_streams(self):
        return list(
            filter(
                lambda stream: stream is not None,
                [
                    self.left_wrist,
                    self.left_elbow,
                    self.left_shoulder,
                    self.trunk,
                    self.right_shoulder,
                    self.right_elbow,
                    self.right_wrist,
                ],
            )
        )

    def get_streams_and_names(self):
        streams = self.get_streams()
        names = self.get_names()[: len(streams)]
        return zip(streams, names)

    def get_streams_and_labels(self):
        streams = self.get_streams()
        names = self.get_labels()[: len(streams)]
        return zip(streams, names)

    def set_at_index(self, stream: Stream, index: int):
        if index == 0:
            self.left_wrist = stream
        elif index == 1:
            self.left_elbow = stream
        elif index == 2:
            self.left_shoulder = stream
        elif index == 3:
            self.trunk = stream
        elif index == 4:
            self.right_shoulder = stream
        elif index == 5:
            self.right_elbow = stream
        elif index == 6:
            self.right_wrist = stream

    def get_at_index(self, index):
        imu_stream_locations = [
            self.left_wrist,
            self.left_elbow,
            self.left_shoulder,
            self.trunk,
            self.right_shoulder,
            self.right_elbow,
            self.right_wrist,
        ]
        if index >= len(imu_stream_locations) or index < 0:
            return None
        else:
            return imu_stream_locations[index]

    @staticmethod
    def get_names() -> List[str]:
        return [
            "Left Wrist",
            "Left Elbow",
            "Left Shoulder",
            "Trunk",
            "Right Shoulder",
            "Right Elbow",
            "Right Wrist",
        ]

    @staticmethod
    def get_labels() -> List[str]:
        return [
            "IMU {} ({})".format(i, label)
            for i, label in enumerate(ImuStreams.get_names())
        ]

    @staticmethod
    def get_connection_status(stream: Stream) -> ImuConnectionStatus:
        if stream is None:
            return ImuConnectionStatus.DISCONNECTED
        else:
            return ImuConnectionStatus.CONNECTED

    def get_calibration_status(stream: Stream) -> ImuCalibrationStatus:
        if stream is None:
            return ImuCalibrationStatus.UNKNOWN
        else:
            calibration = stream.read_data().calibration
            if calibration == 0:
                return ImuCalibrationStatus.UNRELIABLE
            elif calibration == 1:
                return ImuCalibrationStatus.ACCURACY_LOW
            elif calibration == 2:
                return ImuCalibrationStatus.ACCURACY_MEDIUM
            elif calibration == 3:
                return ImuCalibrationStatus.ACCURACY_HIGH
            else:
                return ImuCalibrationStatus.UNKNOWN
