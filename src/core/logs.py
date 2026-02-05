import os
import sys
from datetime import datetime

from loguru import logger

from core.config import Configuration
from core.path import PathTo


class Logs:
    @classmethod
    def start(cls, file_level: str = "DEBUG", console_level: str = "WARNING") -> None:
        """Starts logging with the specified log levels.

        :param file_level: The log level for file logging (default is "DEBUG").
        :param console_level: The log level for console logging (default is "WARNING").
        """
        cls._create_logger(file_level, console_level)
        logger.info(
            "--------------------------------------------------------------------------------------------------------------------------------"
        )
        logger.info(
            f"Application started, version: {Configuration.get_version_from_pyproject()}, "
            f"file log level: {file_level}, "
            f"console log level: {console_level}."
        )
        hostname, ip_address = Configuration.get_addresses()
        logger.info(f"Application running on {hostname} ({ip_address}).")

    @classmethod
    def _create_logger(
        cls, file_level: str = "DEBUG", console_level: str = "WARNING"
    ) -> None:
        """Creates a logger with the specified log levels.

        :param file_level: The log level for file logging (default is "DEBUG").
        :param console_level: The log level for console logging (default is "WARNING").
        """
        logger.remove()

        os.makedirs(PathTo.LOGS_FOLDER, exist_ok=True)

        log_filename = datetime.now().strftime("%Y-%m-%d") + ".log"
        log_file_path = os.path.join(PathTo.LOGS_FOLDER, log_filename)

        logger.add(
            log_file_path,
            level=file_level,
            rotation="00:00",
            retention="30 days",
            enqueue=True,
        )

        logger.add(sys.stdout, level=console_level, enqueue=True, colorize=True)
