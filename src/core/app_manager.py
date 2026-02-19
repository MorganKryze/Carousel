import sys
from typing import Callable, Dict, List, Optional

from loguru import logger

from apps import gif_viewer, life, main_screen, pomodoro, recovery_mode
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
            if self.context.config.is_recovery_mode():
                logger.warning(
                    "System in RECOVERY MODE - loading RecoveryMode app only"
                )
                self.modules = {}
                self.apps = self._load_recovery_mode_app()
            else:
                self.modules = self._load_modules()
                self.apps = self._load_apps()

            self.enabled_apps = self._filter_apps_for_carousel()
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

    def _load_recovery_mode_app(self) -> List[Application]:
        """Load the RecoveryMode app when system is in recovery mode.

        Returns a single-item list containing only the RecoveryMode app,
        which displays error information and recovery instructions.

        :return: List containing only the RecoveryMode application.
        """
        callbacks: Dict[str, Callable] = {
            "toggle_display": self.toggle_display,
            "switch_next_app": self.switch_next_app,
            "switch_prev_app": self.switch_prev_app,
            "increase_brightness": self.increase_brightness,
            "decrease_brightness": self.decrease_brightness,
            "get_app_by_name": self.get_app_by_name,
            "get_module_by_name": self.get_module_by_name,
        }

        try:
            recovery_mode_app = recovery_mode.RecoveryMode(self.context, callbacks)
            logger.info("RecoveryMode app loaded successfully")
            return [recovery_mode_app]
        except Exception as e:
            logger.critical(f"Failed to load RecoveryMode app: {e}")
            logger.critical(
                "Unable to load RecoveryMode app for critical error recovery. Exiting."
            )
            sys.exit(1)

    def _load_apps(self) -> List[Application]:
        """Load and initialize the apps with dependency injection, in configured order.

        Apps are loaded in the order specified by the 'order' field in the configuration.
        This provides a clean, declarative way to manage app ordering without relying
        on hardcoded creation order.
        """
        callbacks: Dict[str, Callable] = {
            "toggle_display": self.toggle_display,
            "switch_next_app": self.switch_next_app,
            "switch_prev_app": self.switch_prev_app,
            "increase_brightness": self.increase_brightness,
            "decrease_brightness": self.decrease_brightness,
            "get_app_by_name": self.get_app_by_name,
            "get_module_by_name": self.get_module_by_name,
        }

        app_registry: Dict[str, type] = {
            "MainScreen": main_screen.MainScreen,
            "GifPlayer": gif_viewer.GifPlayer,
            "Pomodoro": pomodoro.Pomodoro,
            "GameOfLife": life.GameOfLife,
        }

        app_names_in_order = self.context.config.get_app_names_in_order()

        apps: List[Application] = []
        for app_name in app_names_in_order:
            if app_name in app_registry:
                try:
                    app_class = app_registry[app_name]
                    app = app_class(self.context, callbacks)
                    apps.append(app)
                    logger.debug(f"Loaded app: {app_name}")
                except Exception as e:
                    logger.error(f"Failed to load app '{app_name}': {e}")
            else:
                app_config = self.context.config.get("Apps", app_name, default={})
                if isinstance(app_config, dict) and app_config.get("enabled", False):
                    logger.warning(
                        f"App '{app_name}' is enabled but not found in app registry."
                    )
                else:
                    logger.debug(
                        f"App '{app_name}' not in registry (disabled, skipping)."
                    )

        return apps

    def _filter_apps_for_carousel(self) -> List[Application]:
        """Filter enabled applications for carousel display."""
        return [
            app for app in self.apps if app.enabled is True
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
        return self.enabled_apps[self.current_app_index]

    def switch_next_app(self) -> bool:
        """Switch to the next application."""
        try:
            self.current_app_index = (self.current_app_index + 1) % len(self.enabled_apps)
            logger.debug("Switched to next app.")
            return True
        except Exception as e:
            logger.error(f"Failed to switch to next app: {e}")
            self.current_app_index = 0
            return False

    def switch_prev_app(self) -> bool:
        """Switch to the previous application."""
        try:
            self.current_app_index = (self.current_app_index - 1) % len(self.enabled_apps)
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
