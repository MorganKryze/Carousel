from hardware.display_controller import DisplayController
from hardware.input_controller import InputController
from typing import Optional

from loguru import logger

from core.config import Configuration
from core.system_state import SystemState


class SystemContext:
    """
    Singleton container for system-wide dependencies.
    Ensures only one instance of hardware controllers exists.
    """

    _instance: Optional["SystemContext"] = None
    _initialized: bool = False

    def __new__(cls, use_emulator: bool = False) -> "SystemContext":
        if cls._instance is None:
            cls._instance = super(SystemContext, cls).__new__(cls)
            cls._instance._initialize(use_emulator)
        return cls._instance

    def _initialize(self, use_emulator: bool = False) -> None:
        """
        Initialize all system components.
        Must be called once before accessing components.
        """
        if SystemContext._initialized:
            logger.debug("SystemContext already initialized, skipping.")
            return

        logger.info("Initializing SystemContext...")

        self.config = Configuration()
        self.state = SystemState()
        self.display = DisplayController(use_emulator=use_emulator)
        self.input_controller = InputController(self.config)

        SystemContext._initialized = True
        logger.info("SystemContext initialized successfully.")

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if context has been initialized."""
        return cls._initialized

