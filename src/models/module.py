"""Module model class."""

from typing import Optional

from loguru import logger

from core.system_context import SystemContext
from enums.service_status import ServiceStatus


class Module:
    """Modules are components that provide resources or functionnalities that can be used by multiple applications."""

    def __init__(self, context: Optional[SystemContext] = None):
        self.status: ServiceStatus = ServiceStatus.INITIALIZING

        self.context = context or SystemContext()
        logger.debug(f"[{self.__class__.__name__}] Initializing metadata...")
        self.enabled: bool = self.context.config.get_from_module(
            self.__class__.__name__, "enabled", default=True
        )
        self.name: str = self.context.config.get_from_module(
            self.__class__.__name__, "meta", "name", required=True
        )
        self.description: str = self.context.config.get_from_module(
            self.__class__.__name__, "meta", "description", required=True
        )
        logger.debug("Initializing configuration...")

    def self_test(self) -> None:
        """
        Perform a self-test to ensure the module is functioning correctly.
        This method should be overridden by subclasses to implement specific self-test logic.
        """
        raise NotImplementedError(
            "self_test method not implemented. Please implement this method logic in the subclass."
        )
