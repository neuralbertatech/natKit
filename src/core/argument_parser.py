import argparse
import pathlib
from src.data.board.supported import get_supported_boards
from src.utility.result import Result
from src.utility.type_conversion import string_to_int


DEFAULT_ARGS = {
    "baud": Result.failure("No default value"),
    "board": Result.failure("No default value"),
    "channels": Result.failure("No default value"),
    "com_port": Result.failure("No default value"),
    "in_file": Result.failure("No default value"),
    "out_file": Result.failure("No default value"),
}


def parse() -> argparse.Namespace:
    """Helper function to parse the command line agruments
    Returns:
        A populated argeparse.Namespace with the parsed attributes
    """
    parser = argparse.ArgumentParser()
    commandParser = parser.add_subparsers(dest="command")

    parser.add_argument(
        "--com-port",
        help="The COM port to connect to for serial data",
        type=str,
        metavar="COM",
    )
    parser.add_argument(
        "--channels",
        help="The number of channels connected",
        type=int,
        metavar="Channels",
    )

    connectParser = commandParser.add_parser(
        "connect", help="Connect to a board to stream data"
    )
    connectParser.add_argument(
        "board", help="The boards to connect to", choices=get_supported_boards()
    )
    connectParser.add_argument(
        "--output", help="Output stream to file", type=pathlib.Path, metavar="File"
    )
    connectParser.add_argument("--graph-output", help="Graph the output stream")

    simulateParser = commandParser.add_parser(
        "simulate", help="Simulate data from a given board"
    )
    simulateParser.add_argument(
        "board", help="The boards to connect to", choices=get_supported_boards()
    )
    simulateParser.add_argument(
        "--input",
        help="Input simulated data from file",
        type=pathlib.Path,
        metavar="File",
    )

    args = parser.parse_args()
    return args


def is_simulate_command(args: argparse.Namespace) -> bool:
    return args.command == "simulate"


def is_connect_command(args: argparse.Namespace) -> bool:
    return args.command == "connect"


def get_baud_rate(args: argparse.Namespace) -> Result[str]:
    arg = vars(args).get("baud")
    if arg is None:
        return DEFAULT_ARGS["baud"]
    else:
        return Result.success(arg)


def get_board(args: argparse.Namespace) -> Result[str]:
    arg = args.board
    arg = vars(args).get("board")
    if arg is None:
        return DEFAULT_ARGS["board"]
    else:
        return Result.success(arg)


def get_channels(args: argparse.Namespace) -> Result[int]:
    arg = vars(args).get("channels")
    if arg is None:
        return DEFAULT_ARGS["channels"]
    else:
        return Result.success(string_to_int(arg))


def get_com_port(args: argparse.Namespace) -> Result[str]:
    arg = vars(args).get("com-port")
    if arg is None:
        return DEFAULT_ARGS["com_port"]
    else:
        return Result.success(arg)


def get_in_file(args: argparse.Namespace) -> Result[str]:
    arg = vars(args).get("input")
    if arg is None:
        return DEFAULT_ARGS["in_file"]
    else:
        return Result.success(arg)


def get_out_file(args: argparse.Namespace) -> Result[str]:
    arg = vars(args).get("output")
    if arg is None:
        return DEFAULT_ARGS["out_file"]
    else:
        return Result.success(arg)
