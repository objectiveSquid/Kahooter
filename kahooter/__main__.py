import argparse
import logging

from log_stuff import create_colored_logger
from manager import BotManager


def main() -> None:
    parser = argparse.ArgumentParser(description="Kahoot Bot", add_help=False)

    parser.add_argument(
        "lobby_id",
        type=int,
        help="Lobby ID",
    )
    parser.add_argument(
        "bot_count",
        type=int,
        help="Number of bots to create",
    )
    parser.add_argument(
        "--help", action="store_true", help="Show this help message and exit"
    )
    parser.add_argument(
        "-h",
        "--headless",
        action="store_true",
        help="Run instances without a window",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose logging (print debug messages)",
    )
    parser.add_argument(
        "-no",
        "--no-optimize",
        action="store_true",
        help="Do not optimize the running chrome by disabling unused features",
    )

    args = parser.parse_args()

    if args.help:
        parser.print_help()
        return

    if args.verbose:
        manager_logger = create_colored_logger("bot_manager", logging.DEBUG)
    else:
        manager_logger = create_colored_logger("bot_manager", logging.INFO)

    manager = BotManager(
        manager_logger,
        args.lobby_id,
        args.bot_count,
        args.headless,
    )
    manager.run()


if __name__ == "__main__":
    main()
