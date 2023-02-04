from dataclasses import dataclass

from typing import TypeVar


T = TypeVar("T")


@dataclass
class Point:
    x: T
    y: T
