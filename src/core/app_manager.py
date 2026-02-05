import sys
from typing import Callable, Dict, List, Optional

from loguru import logger

from apps import gif_viewer, main_screen, pomodoro
from core.system_state import SystemState
from models.application import Application
from models.module import Module


class AppManager:
    """
    Manages the current application and provides methods to switch between applications.
    """

    current_app_index: int = 0
    modules: Dict[str, Module]
    apps: List[Application]
    enabled_apps: List[Application]
    carousel: List[Application]

    @classmethod
    def init_apps(cls) -> None:
        """
        Initialize the applications.
        """
        logger.debug("Initializing apps.")
        try:
            cls.modules = cls.load_modules()
            cls.apps = cls.load_apps()
            cls.enabled_apps = [app for app in cls.apps if app.enabled]
            cls.carousel = cls.filter_apps_for_carousel()
            logger.debug("All enabled app initialized.")
        except Exception as e:
            logger.critical(f"Failed to initialize apps: {e}")
            logger.critical("Exiting program.")
            sys.exit(1)

    @staticmethod
    def load_modules() -> Dict[str, Module]:
        """
        Load and initialize the modules.

        :return: Dict[str, Module]: A dictionary of initialized modules.
        """
        return {
            # "notifications": modules.notification_module.Notifications(),
            # "weather": modules.weather_module.WeatherModule(),
            # "spotify": modules.spotify_module.SpotifyModule(),
        }

    @staticmethod
    def load_apps() -> List[Application]:
        """
        Load and initialize the apps.

        :return: List[Application]: A list of initialized applications.
        """
        callbacks: Dict[str, Callable] = {
            "toggle_display": AppManager.toggle_display,
            "switch_next_app": AppManager.switch_next_app,
            "switch_prev_app": AppManager.switch_prev_app,
            "increase_brightness": AppManager.increase_brightness,
            "decrease_brightness": AppManager.decrease_brightness,
            "get_app_by_name": AppManager.get_app_by_name,
            "get_module_by_name": AppManager.get_module_by_name,
        }
        return [
            main_screen.MainScreen(callbacks),
            gif_viewer.GifPlayer(callbacks),
            pomodoro.Pomodoro(callbacks),
            # life.GameOfLifeScreen(callbacks),
            # weather.WeatherScreen(config, modules, callbacks),
            # notion.NotionScreen(config, modules, callbacks),
            # subcount.SubcountScreen(config, modules, callbacks),
            # spotify_player.SpotifyScreen(config, modules, callbacks),
        ]

    @classmethod
    def filter_apps_for_carousel(cls) -> List[Application]:
        """
        Filter the enabled applications to only include those that are in the carousel.

        :return: List[Application]: A list of applications that are in the carousel.
        """
        return [
            app
            for app in cls.enabled_apps
            if app.provides_horizontal_content is True
            or app.horizontal_replacement_app_name is not None
        ]

    @classmethod
    def get_app_by_name(cls, app_name: str) -> Optional[Application]:
        """
        Get an application by its name.

        :param app_name: The name of the application.
        :return: Application: The application instance.
        """
        for app in cls.enabled_apps:
            if app.name == app_name:
                return app
        logger.error(f"Application '{app_name}' not found.")
        return None

    @classmethod
    def get_module_by_name(cls, module_name: str) -> Module:
        """
        Get a module by its name.

        :param module_name: The name of the module.
        :return: Module: The module instance.
        """
        if module_name in cls.modules:
            return cls.modules[module_name]
        raise ValueError(f"Module '{module_name}' not found.")

    @classmethod
    def get_current_app(cls) -> Application:
        """
        Get the current application.

        Returns:
            Any: The current application.
        """
        return cls.carousel[cls.current_app_index]

    @classmethod
    def switch_next_app(cls) -> bool:
        """
        Switch to the next application.

        :return: bool: True if the switch was successful, False otherwise.
        """
        try:
            cls.current_app_index = (cls.current_app_index + 1) % len(cls.carousel)
            logger.debug("Switched to next app.")
            return True
        except Exception as e:
            logger.error(f"Failed to switch to next app: {e}")
            cls.current_app_index = 0
            logger.debug("Resetting to first app.")
            return False

    @classmethod
    def switch_prev_app(cls) -> bool:
        """
        Switch to the previous application.

        :return: bool: True if the switch was successful, False otherwise.
        """
        try:
            cls.current_app_index = (cls.current_app_index - 1) % len(cls.carousel)
            logger.debug("Switched to previous app.")
            return True
        except Exception as e:
            logger.error(f"Failed to switch to previous app: {e}")
            cls.current_app_index = 0
            logger.debug("Resetting to first app.")
            return False

    @staticmethod
    def toggle_display() -> bool:
        """
        Toggle the display on or off.

        :return: bool: True if the display was successfully toggled, False otherwise.
        """
        try:
            SystemState().is_display_on = not SystemState().is_display_on
            logger.debug(
                f"Display set to: {'on' if SystemState().is_display_on else 'off'}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to toggle display: {e}")
            SystemState().is_display_on = True
            logger.debug("Display turned off due to error.")
            return False

    @staticmethod
    def increase_brightness() -> bool:
        """
        Increase the brightness of the display.

        :return: bool: True if brightness was successfully increased, False otherwise.
        """
        initial_value: int = SystemState().brightness
        try:
            SystemState().brightness = min(
                SystemState.BRIGHTNESS_MAX,
                SystemState().brightness + SystemState.BRIGHTNESS_STEP,
            )
            logger.debug(f"Brightness increased to {SystemState().brightness}")
        except Exception as e:
            logger.error(f"Failed to increase brightness: {e}")
            SystemState().brightness = initial_value
            logger.debug(
                f"Brightness reset to default: {SystemState().brightness}"
            )
            return False

    @staticmethod
    def decrease_brightness() -> bool:
        """
        Decrease the brightness of the display.

        :return: bool: True if brightness was successfully decreased, False otherwise.
        """
        initial_value: int = SystemState().brightness
        try:
            SystemState().brightness = max(
                SystemState.BRIGHTNESS_MIN,
                SystemState().brightness - SystemState.BRIGHTNESS_STEP,
            )
            logger.debug(f"Brightness decreased to {SystemState().brightness}")
            return True
        except Exception as e:
            logger.error(f"Failed to decrease brightness: {e}")
            SystemState().brightness = initial_value
            logger.debug(
                f"Brightness reset to default: {SystemState().brightness}"
            )
            return False
