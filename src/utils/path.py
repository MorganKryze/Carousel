import inspect
import os
import sys


class PathTo:
    base_directory: str = ""

    GENERATIONS_FOLDER: str = "configs/"
    TEMPLATE_CONFIG_FILE: str = "template.config.yaml"
    RECOVERY_CONFIG_FILE: str = "recovery.config.yaml"
    PYPROJECT_FILE: str = "pyproject.toml"

    LOGS_FOLDER: str = "logs"
    RESOURCES_FOLDER: str = "resources"
    GIF_FOLDER: str = os.path.join(RESOURCES_FOLDER, "gif/horizontal/")
    LIFE_PATTERNS_FOLDER: str = os.path.join(RESOURCES_FOLDER, "life_patterns/")
    MAIN_SCREEN_BACKGROUND_FOLDER: str = os.path.join(RESOURCES_FOLDER, "main_screen/")
    FONT_FILE: str = os.path.join(RESOURCES_FOLDER, "fonts/tiny.otf")
    TEMPLATES_FOLDER: str = "../resources/web/templates"
    STATIC_FOLDER: str = "../resources/web/static"

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
