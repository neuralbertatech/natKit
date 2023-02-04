from typing import NoReturn


class Event:
    """
    An interface gui events
    """

    def start(self) -> NoReturn:
        assert 0, "Abstract function not implemented!"

    def end(self) -> NoReturn:
        assert 0, "Abstract function not implemented!"


class DurationEvent:
    def __init__(self, start, end, event) -> NoReturn:
        self.start = start
        self.end = end
        self.event = event


class OneShotEvent:
    def __init__(self, at, event) -> NoReturn:
        self.at = at
        self.event = event
