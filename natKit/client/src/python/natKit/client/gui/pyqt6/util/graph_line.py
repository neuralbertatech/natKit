from natKit.common.util import Fifo
from natKit.common.util import Point

from typing import List
from typing import NoReturn
from typing import Tuple


class GraphLine:
    def __init__(self, number_of_points: int) -> NoReturn:
        self.number_of_points = number_of_points
        self.data = Fifo(self.number_of_points)

    def append(self, point: Point) -> NoReturn:
        self.data.push(point)

    def to_list(self) -> List[float]:
        return self.data.to_list()

    def to_split_list(self) -> Tuple[List[float], List[float]]:
        points = self.to_list()
        xs = [point.x for point in points]
        ys = [point.y for point in points]
        return (xs, ys)
