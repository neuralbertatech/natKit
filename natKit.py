from src.core import argument_parser
from src.core import commands


if __name__ == "__main__":
    args = argument_parser.parse()
    commands.handle_command(args)
