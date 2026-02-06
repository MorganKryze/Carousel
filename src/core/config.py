import os
import socket
import sys
import tomllib
from datetime import datetime
from typing import Any, Dict, Optional

import yaml
from loguru import logger

from utils.path import PathTo


class Configuration:
    """
    Singleton configuration manager.
    Handles loading, saving, and accessing configuration data.
    """

    _instance: Optional["Configuration"] = None

    def __new__(cls) -> "Configuration":
        if cls._instance is None:
            cls._instance = super(Configuration, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Initialize configuration state."""
        self.file_path: str = ""
        self.latest_generation_id: int = 0
        self.latest_working_generation_id: int = 0
        self.configuration_dictionary: Dict[str, Any] = {}

    def load(self) -> None:
        """
        Load configuration from file or create a new one from the template if it doesn't exist.
        """
        logger.info("Loading configuration...")
        self.latest_generation_id = self.get_latest_generation_id()
        self.latest_working_generation_id = self.get_latest_working_generation_id()

        if self.latest_generation_id == 0:
            self.create_new_configuration_from_template()

        self.file_path = self.get_latest_working_generation_filepath()
        try:
            with open(self.file_path, "r") as f:
                self.configuration_dictionary = yaml.safe_load(f)
            logger.info("Successfully loaded the configuration file.")
        except Exception:
            self.critical_exit(f"Failed to load configuration file '{self.file_path}'")

    def create_new_configuration_from_template(self) -> None:
        """
        Initialize the configuration from a template file.
        """
        logger.info("Using template config file to create a new config.")
        template_file_path = PathTo.TEMPLATE_CONFIG_FILE
        try:
            with open(template_file_path, "r") as template_file:
                data = yaml.safe_load(template_file)
                logger.debug("Template config file loaded successfully.")
            data["Metadata"]["id"] = 1
            data["Metadata"]["version"] = get_version_from_pyproject()
            data["Metadata"]["created_at"] = datetime.now().isoformat(
                sep=" ", timespec="minutes"
            )
            logger.debug("Metadata updated with current time and version.")
            if not self.create_new_config_generation(data):
                self.critical_exit(
                    "Failed to create a new configuration generation from the template."
                )
        except FileNotFoundError:
            self.critical_exit(f"Template config file not found: {template_file_path}")
        except yaml.YAMLError:
            self.critical_exit(
                f"Error parsing template config file: {template_file_path}"
            )

    def create_new_config_generation(self, config: Dict[str, Any]) -> bool:
        """
        Create a new configuration generation by saving the current configuration to a new file.

        :param config: The configuration dictionary to save.
        :return: True if the generation was created successfully, False otherwise.
        """
        if not os.path.exists(PathTo.GENERATIONS_FOLDER):
            os.makedirs(PathTo.GENERATIONS_FOLDER)
            logger.debug("Generations folder created.")
        if config["Metadata"]["id"] != self.latest_generation_id + 1:
            logger.error(
                "The provided configuration ID does not match the expected next ID."
            )
            return False
        if config["Metadata"]["id"] > 1 and config["Metadata"]["origin"] != "user":
            logger.error(
                "The provided configuration is not from a user and cannot be used to create a new generation."
            )
            config["Metadata"]["origin"] = "user"

        self.latest_generation_id += 1
        self.latest_working_generation_id = self.latest_generation_id
        generation_file_path = os.path.join(
            PathTo.GENERATIONS_FOLDER,
            f"generation_{config['Metadata']['id']}.yaml",
        )

        is_saved = self.save(config)
        if not is_saved:
            logger.error(f"Failed to save the new generation at {generation_file_path}")
            return False
        logger.info(f"New generation created: {generation_file_path}")
        return True

    def save(self, config: Dict[str, Any], is_broken: bool = False) -> bool:
        """
        Save the configuration dictionary to a YAML file.

        :return: True if the file was written successfully, False otherwise.
        """
        normal_path = os.path.join(
            PathTo.GENERATIONS_FOLDER, f"generation_{config['Metadata']['id']}.yaml"
        )
        broken_path = normal_path.replace(".yaml", ".broken.yaml")

        try:
            if os.path.exists(normal_path) and not is_broken:
                logger.warning(
                    f"Configuration file already exists: {normal_path}. Overwriting."
                )
            with open(normal_path, "w") as f:
                yaml.safe_dump(config, f, default_flow_style=False)
            logger.info(f"Configuration saved to {normal_path}")
            if is_broken:
                os.rename(normal_path, broken_path)
                logger.info(
                    f"Configuration marked as broken and saved to {broken_path}"
                )
            return True
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False

    def get(self, *keys: str, default: Any = None, required: bool = False) -> Any:
        """
        Reads a value from the configuration dictionary using a variable number of keys.

        :param keys: Variable number of keys to navigate through the dictionary hierarchy.
        :param default: Default value to return if the key path doesn't exist.
        :param required: If True, flags the configuration as broken if key is missing or None.
        :return: The value at the specified key path, or the default value if not found.
        """
        if not keys:
            return self.configuration_dictionary

        current = self.configuration_dictionary
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                logger.debug(f"Key path not found: {' -> '.join(keys)}")
                if required and default is None:
                    self.critical_exit(
                        f"Required key path not found: {' -> '.join(keys)}"
                    )
                return default

        if required and current is None:
            self.critical_exit(f"Required key path has None value: {' -> '.join(keys)}")

        logger.debug(f"Found value at: {' -> '.join(keys)}")
        return current

    def get_from_module(
        self, module_name: str, *keys: str, default: Any = None, required: bool = False
    ) -> Any:
        """
        Reads a value from the module's configuration using a variable number of keys.
        """
        return self.get(
            "Modules", module_name, *keys, default=default, required=required
        )

    def get_from_app(
        self, app_name: str, *keys: str, default: Any = None, required: bool = False
    ) -> Any:
        """
        Reads a value from the application's configuration using a variable number of keys.
        """
        return self.get("Apps", app_name, *keys, default=default, required=required)

    def get_from_app_meta(
        self, app_name: str, *keys: str, default: Any = None, required: bool = False
    ) -> Any:
        """
        Reads a value from the application's meta configuration using a variable number of keys.
        """
        return self.get(
            "Apps", app_name, "meta", *keys, default=default, required=required
        )

    def get_from_app_config(
        self, app_name: str, *keys: str, default: Any = None, required: bool = False
    ) -> Any:
        """
        Reads a value from the application's config using a variable number of keys.
        """
        return self.get(
            "Apps", app_name, "config", *keys, default=default, required=required
        )

    def set(self, *keys: str, value: Any) -> bool:
        """
        Sets a value in the configuration dictionary using a variable number of keys.
        """
        if not keys:
            logger.error("No keys provided to set a value.")
            return False
        try:
            current = self.configuration_dictionary
            for key in keys[:-1]:
                if key not in current or not isinstance(current[key], dict):
                    current[key] = {}
                current = current[key]

            current[keys[-1]] = value
            logger.info(f"Set value at: {' -> '.join(keys)} to {value}")
            return True
        except Exception as e:
            logger.error(f"Failed to set value at {' -> '.join(keys)}: {e}")
            return False

    def get_generation_filenames(self) -> list[str]:
        """
        Retrieves all generation filenames from the generations folder.
        """
        try:
            return [
                f for f in os.listdir(PathTo.GENERATIONS_FOLDER) if f.endswith(".yaml")
            ]
        except FileNotFoundError:
            logger.error(f"Generations folder not found: {PathTo.GENERATIONS_FOLDER}")
            return []

    def get_latest_generation_id(self) -> int:
        """
        Retrieves the latest generation ID from all the generations available in the generations folder.
        """
        generation_files = self.get_generation_filenames()
        if not generation_files:
            return 0

        latest_id = 0
        for file in generation_files:
            try:
                generation_id = int(file.split("_")[1].split(".")[0])
                if generation_id > latest_id:
                    latest_id = generation_id
            except (ValueError, IndexError):
                logger.error(f"Invalid generation file name: {file}")

        logger.debug(f"Latest generation ID found: {latest_id}")
        return latest_id

    def get_latest_working_generation_id(self) -> int:
        """
        Retrieves the latest working generation ID from all the generations available in the generations folder.
        """
        generation_files = self.get_generation_filenames()
        if not generation_files:
            return 0

        latest_id = 0
        for file in generation_files:
            try:
                if file.endswith(".broken.yaml"):
                    continue
                generation_id = int(file.split("_")[1].split(".")[0])
                if generation_id > latest_id:
                    latest_id = generation_id
            except (ValueError, IndexError):
                logger.error(f"Invalid generation file name: {file}")

        logger.debug(f"Latest working generation ID found: {latest_id}")
        return latest_id

    def get_latest_working_generation_filepath(self) -> str:
        """
        Retrieves the filepath of the latest working generation.
        """
        latest_id = self.get_latest_working_generation_id()
        if latest_id == 0:
            return ""

        return os.path.join(PathTo.GENERATIONS_FOLDER, f"generation_{latest_id}.yaml")

    def flag_current_generation_as_broken(self, reason: str) -> None:
        """
        Flags the current generation as broken and saves the reason.
        """
        try:
            self.set("Metadata", "is_broken", value=True)
            self.set("Metadata", "broken_reason", value=reason)

            original_path = self.file_path
            broken_path = original_path.replace(".yaml", ".broken.yaml")
            if self.latest_generation_id == 1:
                os.remove(original_path)
                logger.debug(
                    "Deleting first generation, will be rebuilt from template in the next boot."
                )
                return
            if not self.save(self.configuration_dictionary, is_broken=True):
                logger.error(f"Failed to save broken configuration to {broken_path}")
            logger.info(
                f"Current generation flagged as broken and saved to {broken_path}"
            )

        except Exception as e:
            logger.error(f"Failed to flag generation as broken: {e}")

    def critical_exit(self, reason: str) -> None:
        """
        Handles critical errors by logging the reason, flagging the current generation as broken,
        and exiting the program.
        """
        self.flag_current_generation_as_broken(reason)
        logger.critical(f"Critical error occurred: {reason}")
        logger.critical("Exiting program.")
        sys.exit(1)


def get_version_from_pyproject() -> str:
    """
    Reads the version from the pyproject.toml file.
    """
    with open(PathTo.PYPROJECT_FILE, "rb") as f:
        data = tomllib.load(f)
    version = data.get("project", {}).get("version", "unknown")
    return version


def get_addresses() -> tuple[str, str]:
    """
    Retrieves the local IP address of the machine and the hostname.
    """
    s = None
    try:
        hostname = socket.gethostname()
        local_hostname = f"{hostname}.local"
        dummy_target = "10.255.255.255"
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((dummy_target, 1))
        local_ip = s.getsockname()[0]
        return local_hostname, local_ip
    except Exception as e:
        logger.warning(f"Failed to retrieve hostname or public IP: {e}")
        return "unknown", "unknown"
    finally:
        if s:
            s.close()


# TODO: Add functions to validate configuration values and structure, and to handle configuration migrations when the structure changes in future versions.
