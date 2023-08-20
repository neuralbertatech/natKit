from dataclasses import dataclass


@dataclass
class Point:
    x: float = 0.0
    y: float = 0.0

    def scale(self, scaling_factor: float):
        return Point(self.x * scaling_factor, self.y * scaling_factor)
