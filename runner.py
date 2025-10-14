import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from bunpro_client import BunproClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if __name__ == "__main__":
    """
    CLI for backup / restore.

    Examples:
      # backup a deck (deck_url can be a relative path or full URL)
      python bunpro_client.py backup /decks/nn10ai/Bunpro-N5-Grammar \
          --email you@example.com --password yourpassword

      # restore from a custom file
      python bunpro_client.py restore --data-file ./my_deck.json \
          --email you@example.com --password yourpassword

      # alternatively, set credentials via .env or environment variables:
      BUNPRO_EMAIL=you@example.com
      BUNPRO_PASSWORD=yourpassword
    """

    load_dotenv()

    parser = argparse.ArgumentParser(
        prog="bunpro_client",
        description="Backup or restore Bunpro deck SRS data.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # backup subcommand
    p_backup = subparsers.add_parser(
        "backup",
        help="Scrape the provided deck URL/path and save SRS data to a JSON file.",
    )
    p_backup.add_argument("deck_url", help="Deck path or full URL to backup.")
    p_backup.add_argument(
        "--data-file",
        "-o",
        default="deck_data.json",
        help="Path to write the JSON backup (default: deck_data.json)",
    )

    # restore subcommand
    p_restore = subparsers.add_parser(
        "restore",
        help="Restore SRS/streaks from a previously saved JSON file.",
    )
    p_restore.add_argument(
        "--data-file",
        "-i",
        default="deck_data.json",
        help="Path to read the JSON backup from (default: deck_data.json)",
    )

    # shared/global args
    parser.add_argument(
        "--email",
        "-e",
        help="Bunpro login email (overrides .env / environment variable)",
    )
    parser.add_argument(
        "--password",
        "-p",
        help="Bunpro login password (overrides .env / environment variable)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable INFO logging output.",
    )

    args = parser.parse_args()

    # configure logging
    log_level = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    # resolve credentials
    email = args.email or os.getenv("BUNPRO_EMAIL")
    password = args.password or os.getenv("BUNPRO_PASSWORD")

    if not (email and password):
        logger.error(
            "Missing credentials. Provide --email/--password"
            " or set BUNPRO_EMAIL and BUNPRO_PASSWORD in env/.env.",
        )
        sys.exit(2)

    # initialize client
    client = BunproClient(email=email, password=password)
    data_file = Path(getattr(args, "data_file", "deck_data.json"))
    client.data_file = data_file

    try:
        if args.command == "backup":
            logger.info("Starting backup for %s -> %s", args.deck_url, data_file)
            client.backup(args.deck_url)
            logger.info("Backup finished: %s", data_file)
        elif args.command == "restore":
            logger.info("Starting restore from %s", data_file)
            client.restore()
            logger.info("Restore finished")
    except Exception:
        logger.exception("Operation failed")
        sys.exit(1)
