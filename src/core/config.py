import os
import socket
import sys
import tomllib
from datetime import datetime
from typing import Any, Dict

import yaml
from loguru import logger

from core.path import PathTo


class Configuration:
    file_path: str
    latest_generation_id: int
    latest_working_generation_id: int
    configuration_dictionary: Dict[str, Any]

    @classmethod
    def load(cls) -> None:
        """
        Load configuration from file or create a new one from the template if it doesn't exist.
        """
        logger.info("Loading configuration...")
        cls.latest_generation_id = cls.get_latest_generation_id()
        cls.latest_working_generation_id = cls.get_latest_working_generation_id()

        if cls.latest_generation_id == 0:
            cls.create_new_configuration_from_template()

        cls.file_path = cls.get_latest_working_generation_filepath()
        try:
            with open(cls.file_path, "r") as f:
                cls.configuration_dictionary = yaml.safe_load(f)
            logger.info("Successfully loaded the configuration file.")
        except Exception:
            cls.critical_exit(f"Failed to load configuration file '{cls.file_path}'")

    @classmethod
    def create_new_configuration_from_template(cls) -> None:
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
            data["Metadata"]["version"] = cls.get_version_from_pyproject()
            # TODO: TZ should come from the execution environment or config
            data["Metadata"]["created_at"] = datetime.now().isoformat(
                sep=" ", timespec="minutes"
            )
            logger.debug("Metadata updated with current time and version.")
            if not cls.create_new_config_generation(data):
                cls.critical_exit(
                    "Failed to create a new configuration generation from the template."
                )
        except FileNotFoundError:
            Configuration.critical_exit(
                f"Template config file not found: {template_file_path}"
            )
        except yaml.YAMLError:
            Configuration.critical_exit(
                f"Error parsing template config file: {template_file_path}"
            )

    @classmethod
    def create_new_config_generation(cls, config: Dict[str, Any]) -> bool:
        """
        Create a new configuration generation by saving the current configuration to a new file.

        :param config: The configuration dictionary to save.
        :return: True if the generation was created successfully, False otherwise.
        """
        if not os.path.exists(PathTo.GENERATIONS_FOLDER):
            os.makedirs(PathTo.GENERATIONS_FOLDER)
            logger.debug("Generations folder created.")
        if config["Metadata"]["id"] != cls.latest_generation_id + 1:
            logger.error(
                "The provided configuration ID does not match the expected next ID."
            )
            return False
        if config["Metadata"]["id"] > 1 and config["Metadata"]["origin"] != "user":
            logger.error(
                "The provided configuration is not from a user and cannot be used to create a new generation."
            )
            config["Metadata"]["origin"] = "user"

        cls.latest_generation_id += 1
        cls.latest_working_generation_id = cls.latest_generation_id
        generation_file_path = os.path.join(
            PathTo.GENERATIONS_FOLDER,
            f"generation_{config['Metadata']['id']}.yaml",
        )

        is_saved = cls.save(config)
        if not is_saved:
            logger.error(
                f"Failed to save the new generation at {generation_file_path}"
            )
            return False
        logger.info(f"New generation created: {generation_file_path}")
        return True

    @classmethod
    def save(cls, config: Dict[str, Any], is_broken: bool = False) -> bool:
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

    @classmethod
    def get(cls, *keys: str, default: Any = None, required: bool = False) -> Any:
        """
        Reads a value from the class dictionary using a variable number of keys.

        :param keys: Variable number of keys to navigate through the dictionary hierarchy.
        :param default: Default value to return if the key path doesn't exist.
        :param required: If True, flags the configuration as broken if key is missing or None.
        :return: The value at the specified key path, or the default value if not found.
        """
        if not keys:
            return cls.configuration_dictionary

        current = cls.configuration_dictionary
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                logger.debug(f"Key path not found: {' -> '.join(keys)}")
                if required and default is None:
                    cls.critical_exit(
                        f"Required key path not found: {' -> '.join(keys)}"
                    )
                return default

        if required and current is None:
            cls.critical_exit(f"Required key path has None value: {' -> '.join(keys)}")

        logger.debug(f"Found value at: {' -> '.join(keys)}")
        return current

    @classmethod
    def get_from_module(
        cls, module_name: str, *keys: str, default: Any = None, required: bool = False
    ) -> Any:
        """
        Reads a value from the module's configuration using a variable number of keys.

        :param module_name: The name of the module.
        :param keys: Variable number of keys to navigate through the module's dictionary hierarchy.
        :param default: Default value to return if the key path doesn't exist.
        :param required: If True, flags the configuration as broken if the key path is not found.
        :return: The value at the specified key path, or the default value if not found.
        """
        return cls.get(
            "Modules", module_name, *keys, default=default, required=required
        )

    @classmethod
    def get_from_app(
        cls, app_name: str, *keys: str, default: Any = None, required: bool = False
    ) -> Any:
        """
        Reads a value from the application's configuration using a variable number of keys.

        :param app_name: The name of the application.
        :param keys: Variable number of keys to navigate through the application's dictionary hierarchy.
        :param default: Default value to return if the key path doesn't exist.
        :param required: If True, flags the configuration as broken if the key path is not found.
        :return: The value at the specified key path, or the default value if not found.
        """
        return cls.get("Apps", app_name, *keys, default=default, required=required)

    @classmethod
    def get_from_app_meta(
        cls, app_name: str, *keys: str, default: Any = None, required: bool = False
    ) -> Any:
        """
        Reads a value from the application's meta configuration using a variable number of keys.

        :param app_name: The name of the application.
        :param keys: Variable number of keys to navigate through the application's meta dictionary hierarchy.
        :param default: Default value to return if the key path doesn't exist.
        :param required: If True, flags the configuration as broken if the key path is not found.
        :return: The value at the specified key path, or the default value if not found.
        """
        return cls.get(
            "Apps", app_name, "meta", *keys, default=default, required=required
        )

    @classmethod
    def get_from_app_config(
        cls, app_name: str, *keys: str, default: Any = None, required: bool = False
    ) -> Any:
        """
        Reads a value from the application's config using a variable number of keys.

        :param app_name: The name of the application.
        :param keys: Variable number of keys to navigate through the application's config dictionary hierarchy.
        :param default: Default value to return if the key path doesn't exist.
        :param required: If True, flags the configuration as broken if the key path is not found.
        :return: The value at the specified key path, or the default value if not found.
        """
        return cls.get(
            "Apps", app_name, "config", *keys, default=default, required=required
        )

    @classmethod
    def set(cls, *keys: str, value: Any) -> bool:
        """
        Sets a value in the configuration dictionary using a variable number of keys.

        :param keys: Variable number of keys to navigate through the dictionary hierarchy.
        :param value: The value to set at the specified key path.
        :return: True if the value was set successfully, False otherwise.
        """
        if not keys:
            logger.error("No keys provided to set a value.")
            return False
        try:
            current = cls.configuration_dictionary
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

    @classmethod
    def get_version_from_pyproject(cls) -> str:
        """
        Reads the version from the pyproject.toml file.

        :return: The version string if found, otherwise 'unknown'.
        """
        with open(PathTo.PYPROJECT_FILE, "rb") as f:
            data = tomllib.load(f)

        version = data.get("project", {}).get("version", "unknown")
        return version

    @classmethod
    def get_generation_filenames(cls) -> list[str]:
        """
        Retrieves all generation filenames from the generations folder.

        :return: A list of generation filenames.
        """
        try:
            return [
                f for f in os.listdir(PathTo.GENERATIONS_FOLDER) if f.endswith(".yaml")
            ]
        except FileNotFoundError:
            logger.error(
                f"Generations folder not found: {PathTo.GENERATIONS_FOLDER}"
            )
            return []

    @classmethod
    def get_latest_generation_id(cls) -> int:
        """
        Retrieves the latest generation ID from all the generations available in the generations folder.

        :return: The latest generation ID.
        """
        generation_files = cls.get_generation_filenames()
        if not generation_files:
            return 0

        latest_id = 0
        for file in generation_files:
            try:
                # The file format is expected to be like: generation_<id>.yaml
                generation_id = int(file.split("_")[1].split(".")[0])
                if generation_id > latest_id:
                    latest_id = generation_id
            except (ValueError, IndexError):
                logger.error(f"Invalid generation file name: {file}")

        logger.debug(f"Latest generation ID found: {latest_id}")
        return latest_id

    @classmethod
    def get_latest_working_generation_id(cls) -> int:
        """
        Retrieves the latest working generation ID from all the generations available in the generations folder.

        :return: The latest working generation ID.
        """
        generation_files = cls.get_generation_filenames()
        if not generation_files:
            return 0

        latest_id = 0
        for file in generation_files:
            try:
                # The file format is expected to be like:
                # generation_<id>.broken.yaml for broken generations
                if file.endswith(".broken.yaml"):
                    continue  # Skip broken generations
                generation_id = int(file.split("_")[1].split(".")[0])
                if generation_id > latest_id:
                    latest_id = generation_id
            except (ValueError, IndexError):
                logger.error(f"Invalid generation file name: {file}")

        logger.debug(f"Latest working generation ID found: {latest_id}")
        return latest_id

    @classmethod
    def get_latest_working_generation_filepath(cls) -> str:
        """
        Retrieves the filepath of the latest working generation.

        :return: The filepath of the latest working generation.
        """
        latest_id = cls.get_latest_working_generation_id()
        if latest_id == 0:
            return ""

        return os.path.join(PathTo.GENERATIONS_FOLDER, f"generation_{latest_id}.yaml")

    @classmethod
    def get_addresses(cls) -> str:
        """
        Retrieves the local IP address of the machine and the hostname.

        :return: A tuple of the hostname and local IP address.
        """
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
            s.close()

    @classmethod
    def flag_current_generation_as_broken(cls, reason: str) -> None:
        """
        Flags the current generation as broken and saves the reason.

        :param reason: The reason for marking the generation as broken.
        """
        try:
            cls.set("Metadata", "is_broken", value=True)
            cls.set("Metadata", "broken_reason", value=reason)

            original_path = cls.file_path
            broken_path = original_path.replace(".yaml", ".broken.yaml")
            if cls.latest_generation_id == 1:
                os.remove(original_path)
                logger.debug(
                    "Deleting first generation, will be rebuilt from template in the next boot."
                )
                return
            if not cls.save(cls.configuration_dictionary, is_broken=True):
                logger.error(
                    f"Failed to save broken configuration to {broken_path}"
                )
            logger.info(
                f"Current generation flagged as broken and saved to {broken_path}"
            )

        except Exception as e:
            logger.error(f"Failed to flag generation as broken: {e}")

    @classmethod
    def critical_exit(cls, reason: str) -> None:
        """
        Handles critical errors by logging the reason, flagging the current generation as broken,
        and exiting the program.

        :param reason: The reason for the critical exit.
        """
        cls.flag_current_generation_as_broken(reason)
        logger.critical(f"Critical error occurred: {reason}")
        logger.critical("Exiting program.")
        sys.exit(1)
