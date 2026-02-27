import inspect
import os
import sys
from typing import List


class PathTo:
    base_directory: str = ""

    GENERATIONS_FOLDER: str = "configs/"
    TEMPLATE_CONFIG_FILE: str = "template.config.yaml"
    RECOVERY_CONFIG_FILE: str = "recovery.config.yaml"
    PYPROJECT_FILE: str = "pyproject.toml"

    LOGS_FOLDER: str = "logs"
    RESOURCES_FOLDER: str = "resources"
    SHARED_FOLDER: str = os.path.join(RESOURCES_FOLDER, "shared")
    APP_RESOURCES_FOLDER: str = os.path.join(RESOURCES_FOLDER, "apps")
    DATA_FOLDER: str = "data"

    FONT_FILE: str = os.path.join(RESOURCES_FOLDER, "shared/fonts/tiny.otf")
    TEMPLATES_FOLDER: str = os.path.join(RESOURCES_FOLDER, "web/templates")
    STATIC_FOLDER: str = os.path.join(RESOURCES_FOLDER, "web/static")

    DEFAULT_GIF_FOLDER: str = os.path.join(RESOURCES_FOLDER, "apps/gif_player")
    DEFAULT_LIFE_PATTERNS_FOLDER: str = os.path.join(RESOURCES_FOLDER, "apps/life")
    DEFAULT_MAIN_SCREEN_FOLDER: str = os.path.join(RESOURCES_FOLDER, "apps/main_screen")
    DEFAULT_WEATHER_FOLDER: str = os.path.join(RESOURCES_FOLDER, "apps/weather")
    DEFAULT_STOCKS_FOLDER: str = os.path.join(RESOURCES_FOLDER, "apps/stocks")
    DEFAULT_SUBCOUNT_FOLDER: str = os.path.join(RESOURCES_FOLDER, "apps/subcount")

    USER_GIF_FOLDER: str = os.path.join(DATA_FOLDER, "gif_player")
    USER_LIFE_PATTERNS_FOLDER: str = os.path.join(DATA_FOLDER, "life")
    USER_MAIN_SCREEN_FOLDER: str = os.path.join(DATA_FOLDER, "main_screen")

    @classmethod
    def set_base_directory(cls) -> None:
        """
        Sets the base directory for the script by finding the project root.
        Looks for pyproject.toml as a marker file to identify the project root.
        """
        current_script_path = os.path.abspath(inspect.getfile(inspect.currentframe()))
        current_dir = os.path.dirname(current_script_path)

        max_levels = 5
        for _ in range(max_levels):
            if os.path.exists(os.path.join(current_dir, "pyproject.toml")):
                cls.base_directory = current_dir
                break
            parent = os.path.dirname(current_dir)
            if parent == current_dir:
                break
            current_dir = parent
        else:
            cls.base_directory = os.path.abspath(
                os.path.join(os.path.dirname(current_script_path), "..")
            )

        os.chdir(cls.base_directory)
        sys.path.append(cls.base_directory)

    @classmethod
    def add_library_to_path(cls) -> None:
        """
        Adds the library rpi-rgb-led-matrix path to the system path.
        """
        sys.path.append(
            os.path.join(cls.base_directory, "rpi-rgb-led-matrix", "bindings", "python")
        )

    @classmethod
    def ensure_data_directories(cls) -> None:
        """
        Creates user data directories under data/ if they don't exist.
        Called once at startup so apps can always read from user dirs safely.
        """
        for folder in [
            cls.USER_GIF_FOLDER,
            cls.USER_LIFE_PATTERNS_FOLDER,
            cls.USER_MAIN_SCREEN_FOLDER,
        ]:
            os.makedirs(folder, exist_ok=True)

    @classmethod
    def list_assets(cls, default_dir: str, user_dir: str, extension: str) -> List[str]:
        """
        Returns a merged list of absolute file paths from the default (shipped)
        and user (custom) directories, filtered by file extension.

        :param default_dir: Path to the app's shipped default resource directory.
        :param user_dir: Path to the user-overridable data directory.
        :param extension: File extension to filter on (e.g. ".gif").
        :return: List of matching file paths from both directories.
        """
        files: List[str] = []
        for directory in [default_dir, user_dir]:
            if os.path.isdir(directory):
                for filename in sorted(os.listdir(directory)):
                    if filename.endswith(extension):
                        files.append(os.path.join(directory, filename))
        return files
