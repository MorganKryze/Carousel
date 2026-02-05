import socket
import subprocess
import threading
import time
from typing import Any, Dict

from flask import Flask, jsonify, redirect, render_template, request, url_for
from loguru import logger

from core.config import Configuration
from core.path import PathTo


class WebServer:
    """Web server for configuring Carousel settings"""

    def __init__(self):
        """Initialize the web server"""
        self.is_connected = False
        self.lock = threading.Lock()
        self.app = Flask(
            __name__,
            template_folder=PathTo.TEMPLATES_FOLDER,
            static_folder=PathTo.STATIC_FOLDER,
        )
        self._register_routes()
        self.server_thread = None

    def _register_routes(self):
        """Register all routes with the Flask app"""
        # Landing page
        self.app.add_url_rule("/", "index", self.index)

        # Home page with configuration categories
        self.app.add_url_rule("/home", "homepage", self.homepage)

        # Edit sections
        self.app.add_url_rule(
            "/section/<section_name>", "edit_section", self.edit_section
        )
        self.app.add_url_rule(
            "/section/<section_name>/<subsection>", "edit_section", self.edit_section
        )

        # Update configuration
        self.app.add_url_rule(
            "/update", "update_config", self.update_config, methods=["POST"]
        )

        # System control
        self.app.add_url_rule(
            "/restart", "restart_system", self.restart_system, methods=["POST"]
        )
        self.app.add_url_rule(
            "/close", "close_connection", self.close_connection, methods=["POST"]
        )

    def save_config(self, config: Dict[str, Any]) -> None:
        """Save configuration to a temporary file"""
        config["Metadata"]["id"] += 1
        Configuration.save(config)

    def index(self):
        """Welcome page with warnings"""
        with self.lock:
            self.is_connected = True
        return render_template("index.html")

    def homepage(self):
        """Main page showing configuration categories"""
        config = Configuration.configuration_dictionary

        # Split configuration into three main categories
        apps = config.get("Apps", {})
        modules = config.get("Modules", {})
        system = config.get("System", {})

        return render_template("home.html", apps=apps, modules=modules, system=system)

    def edit_section(self, section_name, subsection=None):
        """Edit a specific section/subsection of the configuration"""
        config = Configuration.configuration_dictionary

        if section_name in config:
            if subsection and subsection in config[section_name]:
                # Edit a specific subsection
                return render_template(
                    "section.html",
                    section_name=section_name,
                    subsection=subsection,
                    section_data=config[section_name][subsection],
                )
            else:
                # Edit the whole section
                return render_template(
                    "section.html",
                    section_name=section_name,
                    section_data=config[section_name],
                )

        return redirect(url_for("homepage"))

    def update_config(self):
        """Update the configuration with form data"""
        config = Configuration.configuration_dictionary
        data = request.form.to_dict()

        section = data.get("section")
        subsection = data.get("subsection")

        if section and section in config:
            if subsection and subsection in config[section]:
                # Update subsection
                for key, value in data.items():
                    if (
                        key not in ["section", "subsection"]
                        and key in config[section][subsection]
                    ):
                        # Convert values to appropriate types
                        if isinstance(config[section][subsection][key], bool):
                            config[section][subsection][key] = value.lower() == "true"
                        elif isinstance(config[section][subsection][key], int):
                            try:
                                config[section][subsection][key] = int(value)
                            except ValueError:
                                pass
                        elif isinstance(config[section][subsection][key], float):
                            try:
                                config[section][subsection][key] = float(value)
                            except ValueError:
                                pass
                        else:
                            config[section][subsection][key] = value
            else:
                # Update main section
                for key, value in data.items():
                    if key != "section" and key in config[section]:
                        # Convert values to appropriate types
                        if isinstance(config[section][key], bool):
                            config[section][key] = value.lower() == "true"
                        elif isinstance(config[section][key], int):
                            try:
                                config[section][key] = int(value)
                            except ValueError:
                                pass
                        elif isinstance(config[section][key], float):
                            try:
                                config[section][key] = float(value)
                            except ValueError:
                                pass
                        else:
                            config[section][key] = value

        self.save_config(config)
        return redirect(url_for("homepage"))

    def restart_system(self):
        """Restart the Raspberry Pi to apply configuration changes"""
        logger.info("System restart requested from web interface")

        def restart():
            time.sleep(1)  # Brief delay to allow response to be sent
            subprocess.call(["sudo", "reboot"])

        threading.Thread(target=restart).start()
        return jsonify({"status": "Restarting to apply configuration changes..."})

    def close_connection(self):
        """Close the connection and re-enable matrix control"""
        with self.lock:
            self.is_connected = False

        return jsonify({"status": "Connection closed"})

    def is_user_connected(self) -> bool:
        """Check if anyone is connected to the web interface"""
        with self.lock:
            return self.is_connected

    def start(self, port: int, debug: bool) -> threading.Thread:
        """Start the web server in a separate thread"""

        def run_server():
            self.app.run(host="0.0.0.0", port=port, debug=debug)

        self.server_thread = threading.Thread(target=run_server)
        self.server_thread.daemon = True
        self.server_thread.start()

        logger.info(f"Web server started on port {port}")
        return self.server_thread

    @staticmethod
    def check_internet_connectivity() -> bool:
        """
        Check if internet connectivity is available by trying to reach a reliable host.

        :return: bool: True if internet is reachable, False otherwise.
        """
        GOOGLE_DNS = "8.8.8.8"
        CLOUDFLARE_DNS = "1.1.1.1"
        DNS_PORT = 53
        TIMEOUT = 5
        try:
            socket.create_connection((GOOGLE_DNS, DNS_PORT), timeout=TIMEOUT)
            return True
        except OSError:
            try:
                socket.create_connection((CLOUDFLARE_DNS, DNS_PORT), timeout=TIMEOUT)
                return True
            except OSError:
                return False
                return False
