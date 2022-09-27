from enum import Enum


class BoardType(Enum):
    NONE = 0
    EXG_PILL = 1
    MUSE_S = 2
    MUSE_2 = 3


BOARD_TYPE_MAP = {
        'exg-pill': BoardType.EXG_PILL,
        'muse-s': BoardType.MUSE_S,
        'muse-2': BoardType.MUSE_2,
    }


def get_supported_boards() -> [str]:
    return BOARD_TYPE_MAP.keys()


def get_board_type(board: str) -> BoardType:
    return BOARD_TYPE_MAP[board.lower()]
