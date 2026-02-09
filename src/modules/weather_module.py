import time
from queue import LifoQueue
from threading import Thread
from typing import Any, Dict, Optional

from loguru import logger
from pyowm.owm import OWM
from pyowm.weatherapi25.weather_manager import WeatherManager

from core.config import Configuration

# Constants
UPDATE_INTERVAL_SECONDS = 600


class WeatherModule:
    def __init__(self) -> None:
        """
        Initialize the WeatherModule with the given configuration.
        """
        config = Configuration()
        self.enabled: bool = config.get_from_module("Weather", "enabled", required=True)
        if not self.enabled:
            logger.info("Disabled")
            return

        logger.debug("Initializing")
        self.current_weather: Optional[Dict[str, Any]] = None
        self.weather_queue: LifoQueue = LifoQueue()

        token: str = config.get_from_module("Weather", "config", "token", required=True)
        latitude: float = config.get_from_module(
            "Weather", "config", "latitude", required=True
        )
        longitude: float = config.get_from_module(
            "Weather", "config", "longitude", required=True
        )
        self.temperature_unit: str = config.get_from_module(
            "Weather", "config", "temperature_unit", required=True
        )
        if self.temperature_unit not in ["celsius", "fahrenheit"]:
            logger.error(
                "Invalid temperature unit. Must be 'celsius' or 'fahrenheit'."
            )
            self.enabled = False
            return

        try:
            self.weather_manager: WeatherManager = OWM(token).weather_manager()
            self.update_thread: Thread = Thread(
                target=update_weather,
                args=(
                    self.weather_manager,
                    self.weather_queue,
                    float(latitude),
                    float(longitude),
                ),
            )
            self.update_thread.start()
            logger.info("Initialized")
        except Exception as e:
            logger.error(f"Initialization error: {e}")
            self.enabled = False

    def get_weather(self) -> Optional[Dict[str, Any]]:
        """
        Get the current weather information.

        Returns:
            Optional[Dict[str, Any]]: The current weather information.
        """
        if not self.enabled:
            return None

        if not self.weather_queue.empty():
            self.current_weather = self.weather_queue.get()
            self.weather_queue.queue.clear()
        return self.current_weather

    def get_temperature(self) -> Optional[float]:
        """
        Get the current temperature.

        Returns:
            Optional[float]: The current temperature.
        """
        if not self.enabled:
            return None

        weather: Optional[Dict[str, Any]] = self.get_weather()
        if weather is not None:
            return round(weather.current.temperature(self.temperature_unit)["temp"])
        return None


def update_weather(
    weather_manager: WeatherManager,
    weather_queue: LifoQueue,
    latitude: float,
    longitude: float,
) -> None:
    """
    Update the weather information periodically.

    Args:
        weather_manager (WeatherManager): The weather manager.
        weather_queue (LifoQueue): The queue to store weather information.
        latitude (float): The latitude.
        longitude (float): The longitude.
    """
    last_update_time: float = 0
    while True:
        current_time: float = time.time()
        if current_time - last_update_time >= 600:
            try:
                weather_queue.put(weather_manager.one_call(lat=latitude, lon=longitude))
                last_update_time = current_time
            except Exception as e:
                logger.error(f"Error updating weather: {e}")
            except Exception as e:
                logger.error(f"Error updating weather: {e}")
