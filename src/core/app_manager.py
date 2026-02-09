import sys
from typing import Callable, Dict, List, Optional

from loguru import logger

from apps import gif_viewer, life, main_screen, pomodoro
from core.system_context import SystemContext
from models.application import Application
from models.module import Module


class AppManager:
    """
    Singleton application lifecycle manager.
    Ensures only one instance manages all apps.
    """

    _instance: Optional["AppManager"] = None

    def __new__(cls) -> "AppManager":
        if cls._instance is None:
            cls._instance = super(AppManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Initialize AppManager state. Apps loaded separately via init_apps()."""
        self.context: SystemContext = None
        self.current_app_index: int = 0
        self.modules: Dict[str, Module] = {}
        self.apps: List[Application] = []
        self.enabled_apps: List[Application] = []
        self.carousel: List[Application] = []
        self._initialized = False

    def init_apps(self) -> None:
        """
        Initialize the applications with SystemContext.
        Must be called after SystemContext is initialized.
        Safe to call multiple times (subsequent calls are no-op).
        """
        if self._initialized:
            logger.debug("AppManager already initialized, skipping.")
            return

        self.context = SystemContext()
        if not self.context.is_initialized():
            logger.error("SystemContext not initialized before AppManager.init_apps()!")
            raise RuntimeError("SystemContext must be initialized first")

        logger.debug("Initializing apps.")
        try:
            self.modules = self._load_modules()
            self.apps = self._load_apps()
            self.enabled_apps = [app for app in self.apps if app.enabled]
            self.carousel = self._filter_apps_for_carousel()
            self._initialized = True
            logger.debug("All enabled apps initialized.")
        except Exception as e:
            logger.critical(f"Failed to initialize apps: {e}")
            logger.critical("Exiting program.")
            sys.exit(1)

    def is_initialized(self) -> bool:
        """Check if AppManager has been initialized with apps."""
        return self._initialized

    def _load_modules(self) -> Dict[str, Module]:
        """Load and initialize the modules."""
        return {
            # "notifications": modules.notification_module.Notifications(),
            # "weather": modules.weather_module.WeatherModule(),
            # "spotify": modules.spotify_module.SpotifyModule(),
        }

    def _load_apps(self) -> List[Application]:
        """Load and initialize the apps with dependency injection."""
        callbacks: Dict[str, Callable] = {
            "toggle_display": self.toggle_display,
            "switch_next_app": self.switch_next_app,
            "switch_prev_app": self.switch_prev_app,
            "increase_brightness": self.increase_brightness,
            "decrease_brightness": self.decrease_brightness,
            "get_app_by_name": self.get_app_by_name,
            "get_module_by_name": self.get_module_by_name,
        }
        return [
            main_screen.MainScreen(self.context, callbacks),
            gif_viewer.GifPlayer(self.context, callbacks),
            pomodoro.Pomodoro(self.context, callbacks),
            life.GameOfLife(self.context, callbacks),
        ]

    def _filter_apps_for_carousel(self) -> List[Application]:
        """Filter enabled applications for carousel display."""
        return [
            app for app in self.enabled_apps if app.provides_horizontal_content is True
        ]

    def get_app_by_name(self, app_name: str) -> Optional[Application]:
        """Get an application by its name."""
        for app in self.enabled_apps:
            if app.name == app_name:
                return app
        logger.error(f"Application '{app_name}' not found.")
        return None

    def get_module_by_name(self, module_name: str) -> Module:
        """Get a module by its name."""
        if module_name in self.modules:
            return self.modules[module_name]
        raise ValueError(f"Module '{module_name}' not found.")

    def get_current_app(self) -> Application:
        """Get the current application."""
        if not self._initialized:
            raise RuntimeError("AppManager not initialized. Call init_apps() first.")
        return self.carousel[self.current_app_index]

    def switch_next_app(self) -> bool:
        """Switch to the next application."""
        try:
            self.current_app_index = (self.current_app_index + 1) % len(self.carousel)
            logger.debug("Switched to next app.")
            return True
        except Exception as e:
            logger.error(f"Failed to switch to next app: {e}")
            self.current_app_index = 0
            return False

    def switch_prev_app(self) -> bool:
        """Switch to the previous application."""
        try:
            self.current_app_index = (self.current_app_index - 1) % len(self.carousel)
            logger.debug("Switched to previous app.")
            return True
        except Exception as e:
            logger.error(f"Failed to switch to previous app: {e}")
            self.current_app_index = 0
            return False

    def toggle_display(self) -> bool:
        """Toggle the display on or off."""
        try:
            self.context.state.is_display_on = not self.context.state.is_display_on
            logger.debug(
                f"Display set to: {'on' if self.context.state.is_display_on else 'off'}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to toggle display: {e}")
            self.context.state.is_display_on = True
            return False

    def increase_brightness(self) -> bool:
        """Increase the brightness of the display."""
        from core.system_state import SystemState

        initial_value = self.context.state.brightness
        try:
            self.context.display.update_brightness(
                min(
                    SystemState.BRIGHTNESS_MAX,
                    self.context.state.brightness + SystemState.BRIGHTNESS_STEP,
                )
            )
            logger.debug(f"Brightness increased to {self.context.state.brightness}")
            return True
        except Exception as e:
            logger.error(f"Failed to increase brightness: {e}")
            self.context.state.brightness = initial_value
            return False

    def decrease_brightness(self) -> bool:
        """Decrease the brightness of the display."""
        from core.system_state import SystemState

        initial_value = self.context.state.brightness
        try:
            self.context.display.update_brightness(
                max(
                    SystemState.BRIGHTNESS_MIN,
                    self.context.state.brightness - SystemState.BRIGHTNESS_STEP,
                )
            )
            logger.debug(f"Brightness decreased to {self.context.state.brightness}")
            return True
        except Exception as e:
            logger.error(f"Failed to decrease brightness: {e}")
            self.context.state.brightness = initial_value
            return False
