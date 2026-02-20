"""Network management: WiFi connect attempts with hotspot fallback."""

import platform
import shutil
import subprocess
import time
from typing import Optional

from loguru import logger

from core.config import Configuration


class NetworkManager:
    """Manage WiFi connectivity and recovery hotspot fallback."""

    _instance: Optional["NetworkManager"] = None
    _initialized: bool = False

    def __new__(cls) -> "NetworkManager":
        if cls._instance is None:
            cls._instance = super(NetworkManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        if NetworkManager._initialized:
            logger.debug("NetworkManager already initialized, skipping.")
            return
        logger.info("Initializing NetworkManager...")
        self.config = Configuration()
        network = self._network_config()
        logger.info(
            "Network configuration loaded "
            f"(interface={self._interface(network)}, "
            f"max_attempts={self._max_attempts(network)}, "
            f"wpa_level={self._wpa_level(network)})"
        )
        NetworkManager._initialized = True

    def init_connectivity(self, force_hotspot: bool = False) -> bool:
        """Try WiFi first, then start hotspot fallback.

        :param force_hotspot: If True, skip WiFi attempts and start hotspot directly.
        :return: True if either WiFi or hotspot startup succeeded.
        """
        if not self._can_manage_networks():
            logger.warning(
                "Skipping network management: unsupported platform or missing tools"
            )
            return False

        if force_hotspot:
            logger.warning("Network state: recovery mode forces hotspot startup")
            return self.start_hotspot()

        network = self._network_config()
        ssid = self._clean(network.get("ssid"))
        password = self._clean(network.get("password"))
        max_attempts = self._max_attempts(network)

        if not ssid or not password:
            logger.warning(
                "Network state: WiFi credentials missing in config; "
                "starting hotspot fallback"
            )
            return self.start_hotspot()

        logger.info(
            f"Network state: attempting WiFi connection on interface '{self._interface(network)}'"
        )

        interface = self._interface(network)
        if self._is_connected_to_ssid(interface=interface, ssid=ssid):
            logger.info(
                f"Network state: already connected to WiFi network '{ssid}' on '{interface}'"
            )
            return True

        for attempt in range(1, max_attempts + 1):
            logger.info(f"WiFi connect attempt {attempt}/{max_attempts} to '{ssid}'")
            connected, output = self._connect_wifi(
                ssid=ssid, password=password, interface=interface
            )
            if connected:
                logger.info(f"Connected to WiFi network '{ssid}'")
                return True

            failure_reason = self._classify_wifi_failure(output)
            logger.warning(
                f"Network state: WiFi attempt {attempt}/{max_attempts} failed ({failure_reason})"
            )

            if attempt < max_attempts:
                wait_seconds = min(2 ** (attempt - 1), 5)
                logger.info(
                    f"Network state: retrying WiFi connection in {wait_seconds}s"
                )
                time.sleep(wait_seconds)

        logger.error(
            "Network state: WiFi connection failed after max attempts; "
            "starting hotspot fallback"
        )
        return self.start_hotspot()

    def start_hotspot(self) -> bool:
        """Start a local hotspot for recovery access.

        :return: True if hotspot started successfully, False otherwise.
        """
        if not self._can_manage_networks():
            logger.warning(
                "Network state: cannot start hotspot (unsupported platform or missing tools)"
            )
            return False

        network = self._network_config()
        hotspot_ssid = self._clean(network.get("hotspot_ssid")) or "Carousel-Recovery"
        hotspot_password = self._valid_hotspot_password(
            self._clean(network.get("hotspot_password"))
        )
        interface = self._interface(network)
        wpa_level = self._wpa_level(network)

        command = [
            "nmcli",
            "device",
            "wifi",
            "hotspot",
            "ifname",
            interface,
            "ssid",
            hotspot_ssid,
        ]

        if wpa_level > 0 and not hotspot_password:
            logger.error(
                "Network state: secured hotspot requested but no valid password was provided; "
                "refusing to start hotspot"
            )
            return False

        if hotspot_password and wpa_level > 0:
            command.extend(["password", hotspot_password])

        if wpa_level == 0:
            logger.warning("Network state: hotspot configured as OPEN (wpa_level=0)")

        logger.warning(
            f"Network state: starting local hotspot on '{interface}' with SSID '{hotspot_ssid}'"
        )

        success, output = self._run_nmcli(command)
        if success:
            logger.warning(
                f"Network state: hotspot active (SSID='{hotspot_ssid}', interface='{interface}')"
            )
            return True

        logger.error(f"Network state: failed to start hotspot: {output}")
        return False

    def _connect_wifi(self, ssid: str, password: str, interface: str) -> tuple[bool, str]:
        command = [
            "nmcli",
            "device",
            "wifi",
            "connect",
            ssid,
            "password",
            password,
            "ifname",
            interface,
        ]
        success, output = self._run_nmcli(command)
        return success, output

    def _is_connected_to_ssid(self, interface: str, ssid: str) -> bool:
        success, output = self._run_nmcli(
            ["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi", "list", "ifname", interface]
        )
        if not success:
            logger.debug(
                f"Network state: unable to check active WiFi SSID on '{interface}': {output}"
            )
            return False

        for line in output.splitlines():
            if line.startswith("yes:"):
                active_ssid = line.split(":", 1)[1].strip()
                return active_ssid == ssid
        return False

    @staticmethod
    def _classify_wifi_failure(output: str) -> str:
        message = (output or "").lower()
        if "secrets were required" in message or "invalid secrets" in message:
            return "invalid password"
        if "no network with ssid" in message or "not found" in message:
            return "ssid not found"
        if "device" in message and "unavailable" in message:
            return "wireless interface unavailable"
        if "timed out" in message or "timeout" in message:
            return "connection timeout"
        if message:
            return message.splitlines()[0][:120]
        return "unknown error"

    @staticmethod
    def _run_nmcli(command: list[str]) -> tuple[bool, str]:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=20,
            )
            message = (completed.stdout or completed.stderr or "").strip()
            return completed.returncode == 0, message
        except Exception as error:
            return False, str(error)

    @staticmethod
    def _clean(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = str(value).strip()
        return stripped if stripped else None

    @staticmethod
    def _valid_hotspot_password(password: Optional[str]) -> Optional[str]:
        if password and len(password) >= 8:
            return password
        if password:
            logger.warning(
                "Hotspot password is shorter than 8 characters and will be ignored"
            )
        else:
            logger.warning("Hotspot password is not configured")
        return None

    @staticmethod
    def _max_attempts(network: dict) -> int:
        raw_value = network.get("max_attempts", 3)
        try:
            value = int(raw_value)
            return value if value > 0 else 3
        except (TypeError, ValueError):
            return 3

    @staticmethod
    def _wpa_level(network: dict) -> int:
        raw_value = network.get("wpa_level", 2)
        try:
            value = int(raw_value)
            return value if value >= 0 else 2
        except (TypeError, ValueError):
            return 2

    @staticmethod
    def _interface(network: dict) -> str:
        interface = str(network.get("interface", "wlan0")).strip()
        return interface or "wlan0"

    def _network_config(self) -> dict:
        value = self.config.get("System", "Network", default={})
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _can_manage_networks() -> bool:
        return (
            platform.system().lower() == "linux" and shutil.which("nmcli") is not None
        )
