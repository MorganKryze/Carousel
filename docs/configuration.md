# Configuration

> This guide will help you configure the project using a single configuration [YAML](https://yaml.org/) file. We will tackle all categories, but an example configuration is provided at the [end of this document](#example-configuration) and in the `config` folder of the repository at [`configs/example.config.yaml`](../configs/example.config.yaml).

## Important notes

<!-- TODO: Address and workflow liekly to change here. -->

The configuration file are NOT meant to be edited by hand. The recommended way to edit the configuration is to use the provided web editor running on the Raspberry Pi. You can access it by navigating to `http://<raspberry-pi-ip>:9000` in your web browser.

If you may confider editing the configuration manually, please be aware of the following:

- The configuration file is written in [YAML](https://yaml.org/) format, which is a human-readable data serialization standard. Not properly formatting the file will lead to errors when loading the configuration and flagging the file as broken making it unusable.
- The configuration file is divided into sections, each section containing specific configuration options. Each section will be explained in detail below.
- The project uses a single configuration file to manage all aspects of the system, including system configuration, module configuration, and application configuration.
- The configuration file is located in the `configs/generations/` folder of the repository and is named following the pattern `generation_<id>.yaml`, where `<id>` is the generation number.
- Broken configurations files follow the naming pattern `generation_<id>.broken.yaml`. These files are created when the configuration file is not valid and cannot be loaded by the system or has produced a critical error during the runtime. These files will be ignored when the system will try to load the latest configuration.
- When using the web editor and saving the new configuration, the system will automatically create a new generation of the configuration file, incrementing the generation number. The previous generation will remain unaltered.

## Variables

### Metadata

> `Metadata` is used to store information about the configuration file, these settings will not alter how the project works, but help the program to choose which file to load and provide information about the configuration file itself.

- `id` (integer, ex: `2`): The unique identifier of the configuration file. This is used to differentiate between different generations of the configuration file. The `example.config.yaml` file has an `id` of `0`, the first generation will have an `id` of `1`, and so on.
- `version` (string, ex: `1.6.3`): The version of the project, saved in the configuration file in the moment of the generation.
- `created_at` (string, ex: `2025-01-01 12:00`): The date and time when the configuration file was created.
- `origin` (string, values: `default`, `user`): The origin of the configuration file. This can be `default` if the file is the original template provided by the project, or `user` if the file has been modified by the user.
- `is_broken` (boolean, ex: `false`): A flag indicating whether the configuration is broken or not. If the file is broken, it will not be loaded by the system.
- `broken_reason` (string, ex: `Invalid syntax`): A description of the reason why the configuration is broken. This will be set to `None` if the file is

### System

> `System` is used to declare the hardware configuration of the matrix and the pinout of the connected peripherals. This section is crucial for the correct functioning of the project, as it defines how the hardware is connected and how it should behave.

- `Matrix` (object): Contains the configuration for the LED matrix.
  - `led_rows` (integer, ex: `32`): The number of rows in the LED matrix.
  - `led_cols` (integer, ex: `64`): The number of columns in the LED matrix.
  - `brightness` (integer, ex: `100`): The brightness level of the LED matrix, from `0` to `100`.
  - `disable_hardware_pulsing` (boolean, ex: `true`): Whether to disable hardware pulsing for the matrix.
  - `hardware_mapping` (string, values: `regular`, `adafruit-hat`): The hardware mapping used for the matrix.
  - `refresh_rate` (float, ex: `0.05`): The refresh rate of the matrix in seconds.
- `Tilt-switch` (object): Contains the configuration for the tilt switch.
  - `gpio` (integer, ex: `19`): The GPIO pin number used for the tilt switch.
  - `bounce_time` (float, ex: `0.25`): The debounce time for the tilt switch in seconds.
- `Encoder` (object): Contains the configuration for the rotary encoder.
  - `gpio_clk` (integer, ex: `5`): The GPIO pin number used for the clock signal of the rotary encoder.
  - `gpio_dt` (integer, ex: `6`): The GPIO pin number used for the data signal of the rotary encoder.
  - `gpio_sw` (integer, ex: `13`): The GPIO pin number used for the switch signal of the rotary encoder.
- `Network` (object): Contains WiFi client credentials and hotspot fallback settings.
  - `ssid` (string, ex: `MyHomeWiFi`): WiFi network name to connect to on boot.
  - `password` (string, ex: `super-secret-pass`): WiFi password for `ssid`.
  - `wpa_level` (integer, values: `0`, `1`, `2`): Hotspot security level. `0` creates an open hotspot, values above `0` use password protection.
  - `hotspot_ssid` (string, ex: `Carousel-Recovery`): Local hotspot SSID used when WiFi connection fails.
  - `hotspot_password` (string, optional): Local hotspot password (minimum 8 chars). Required when `wpa_level` is `1` or `2`.
  - `max_attempts` (integer, ex: `3`): Number of WiFi connection retries before hotspot fallback.
  - `interface` (string, ex: `wlan0`): Wireless interface used for WiFi and hotspot commands.

### Modules

> `Modules` are the toolboxes used by applications. They provide additional functionality to the applications and can be enabled or disabled based on the user's needs. Disabled modules will result in the corresponding applications not being available and disabled.

Each module is defined as an object with the following common metadata:

- `name` (string, ex: `Notifications`): The name of the module.
- `description` (string, ex: `Provides notification services to applications.`): A brief description of the module's functionality.

Each module can have additional configuration options specific to its functionality.

- `Notifications` (object): Provides notification services to applications.
  - `app_white_list` (list of strings, ex: `["MainScreen", "Pomodoro"]`): A list of applications that are allowed to use this module.
  - `websocket_url` (string, ex: `ws://localhost:9000`): The URL of the WebSocket server used by the module.
  - `retry_delay_on_error` (integer, ex: `1000`): The delay in milliseconds before retrying an operation after an error.
- `Weather` (object): Provides weather information to applications.
  - `token` (string, ex: `your_api_token`): The API token for accessing weather data.
  - `latitude` (float, ex: `37.7749`): The latitude of the location for which weather data is requested.
  - `longitude` (float, ex: `-122.4194`): The longitude of the location for which weather data is requested.
  - `temperature_unit` (string, values: `celcius`, `fahrenheit`): The unit of temperature to be used in the weather data.
- `Spotify` (object): Provides Spotify integration to applications.
  - `client_id` (string, ex: `your_spotify_client_id`): The client ID for the Spotify API.
  - `client_secret` (string, ex: `your_spotify_client_secret`): The client secret for the Spotify API.
  - `redirect_uri` (string, ex: `http://localhost:9000/callback`): The redirect URI for the Spotify API authentication.

### Apps

> `Apps` are the applications that are available to the user. Each app can provide horizontal and/or vertical content, and can be configured to replace other apps in the same orientation. Disabled apps will not be available to the user.
> Also note that only apps that provide horizontal content will be shown in the app carousel. An app that onlu provides vertical content will only shown on screen if selected as a replacement app for another app that provides horizontal content.

Each app is defined as an object with the following common metadata:

- `enabled` (boolean, ex: `true`): Whether the app is enabled or not. Disabled apps will not be available to the user and will not be loaded by the system.
- `name` (string, ex: `Main Screen`): The name of the app.
- `description` (string, ex: `The main screen of the matrix, displaying time, date, and other information.`): A brief description of the app's functionality.
- `provides_horizontal_content` (boolean, ex: `true`): Whether the app provides horizontal content or not. Apps that provide horizontal content will be shown in the app carousel.
- `provides_vertical_content` (boolean, ex: `false`): Whether the app provides vertical content or not.

Metadata is not intended to be edited by the user, but is provided for informational purposes on the webui platform for instance.

All apps share the following common configuration options:

- `horizontal_replacement_app` (string, ex: `None`): The app that will replace this app when it is displayed in horizontal orientation. If set to `None`, the app will not be replaced.
- `vertical_replacement_app` (string, ex: `Pomodoro`): The app that will replace this app when it is displayed in vertical orientation. If set to `None`, the app will not be replaced.
- `dependencies` (list of strings): A list of module names that this app depends on. If the required modules are not enabled, the app will not be available to the user.

Each app can have additional configuration options specific to its functionality, as well as a list of dependencies on modules.

- `MainScreen` (object): The main screen of the matrix, displaying time, date, and other information.
  - `config` (object): Contains the configuration options for the app.
    - `use_24_hour` (boolean, ex: `true`): Whether to use 24-hour format for time display.
    - `date_format` (string, ex: `DD-MM`): The format of the date to be displayed.
    - `cycle_duration_in_seconds` (integer, ex: `20`): The duration of the cycle in seconds.
- `Pomodoro` (object): A productivity timer that helps you focus on tasks.
  - `config` (object): Contains the configuration options for the app.
    - `work_duration_in_minutes` (integer, ex: `25`): The duration of the work session in minutes.
    - `break_duration_in_minutes` (integer, ex: `5`): The duration of the break session in minutes.
    - `long_break_duration_in_minutes` (integer, ex: `15`): The duration of the long break session in minutes.
- `GifPlayer` (object): Displays animated GIFs on the matrix.
  - `config` (object): Contains the configuration options for the app.
    - `play_limit` (integer, ex: `5`): The maximum number of GIFs to play in a single session.
- `GameOfLife` (object): A cellular automaton simulation that displays patterns on the matrix.
  - `config` (object): Contains the configuration options for the app.
    - No additional configuration options.
- `Spotify` (object): Displays the current playing track from Spotify.
  - `config` (object): Contains the configuration options for the app.
    - No additional configuration options.
  - `dependencies` (list of strings): A list of module names that this app depends on. In this case, it depends on the `Spotify` module.
- `Notion` (object): Displays information from Notion databases.
  - `config` (object): Contains the configuration options for the app.
    - `token_v2` (string, ex: `your_notion_token`): The token used to access the Notion API.
    - `source` (string, ex: `your_notion_source`): The source from which to fetch data in Notion.
- `Youtube` (object): Displays the latest videos from a YouTube channel.
  - `config` (object): Contains the configuration options for the app.
    - `key` (string, ex: `your_youtube_api_key`): The API key used to access the YouTube API.
- `Pushbullet` (object): Displays notifications from Pushbullet.
  - `config` (object): Contains the configuration options for the app.
    - No additional configuration options.
- `Weather` (object): Displays the current weather conditions.
  - `config` (object): Contains the configuration options for the app.
    - No additional configuration options.

## Example configuration

```yaml
# WARNING: Bad configuration of modules can lead to apps not loading correctly and bad
# system configuration will lead to system crashes. Please be careful when editing this
# file. Feel free to ask for help on the GitHub repository and read the documentation.

# ------------------------- Metadata -----------------------
# Metadata is used to store information about the configuration file, such as the
# version, date of creation, and author. This information can be useful for debugging
# and tracking changes to the configuration file.

# Please do not edit this section unless you know what you are doing.
# The metadata is automatically generated and should not be modified manually.

Metadata:
  id: 0
  version: 0.0.0
  created_at: 2025-01-01 12:00
  author: author
  is_broken: false
  broken_reason:

# ------------------ System Configuration ------------------
# System configuration is used to declare the hardware configuration of the matrix and
# the pinout of the connected peripherals.

# Please note that the following "gpio" values are NOT PIN numbers, but GPIO numbers.
# See https://pinout.xyz/ for more information.

System:
  Matrix:
    led_rows: 32
    led_cols: 64
    brightness: 100
    disable_hardware_pulsing: true
    hardware_mapping: regular
    refresh_rate: 0.05
  Tilt-switch:
    gpio: 19
    bounce_time: 0.25
  Encoder:
    gpio_clk: 5
    gpio_dt: 6
    gpio_sw: 13
  Network:
    ssid:
    password:
    wpa_level: 0
    hotspot_ssid: Carousel-Recovery
    hotspot_password:
    max_attempts: 3
    interface: wlan0

# ------------------ Module Configuration ------------------
# Modules are the toolboxes used by applications. Disabled modules will result in the
# corresponding applications not being available and disabled.

Modules:
  Notifications:
    name: Notifications
    description: Provides notification services to applications.
    app_white_list:
    websocket_url:
    retry_delay_on_error: 1000
  Weather:
    name: Weather
    description: Provides weather information to applications.
    token:
    latitude:
    longitude:
    temperature_unit: celcius
  Spotify:
    name: Spotify
    description: Provides Spotify integration to applications.
    client_id:
    client_secret:
    redirect_uri:

# -------------------- Apps Configuration ------------------
# Apps are the applications that are available to the user. Disabled apps will not be
# available to the user.

Apps:
  MainScreen:
    enabled: true
    meta:
      name: Main Screen
      description: The main screen of the matrix, displaying time, date, and other information.
      provides_horizontal_content: true
      provides_vertical_content: false
    config:
      # horizontal_replacement_app: None # IGNORED because has horizontal content
      vertical_replacement_app: Pomodoro
      use_24_hour: true
      date_format: DD-MM
      cycle_duration_in_seconds: 20
    dependencies:
  Pomodoro:
    enabled: true
    meta:
      name: Pomodoro
      description: A productivity timer that helps you focus on tasks.
      provides_horizontal_content: false
      provides_vertical_content: true
    config:
      horizontal_replacement_app: None
      # vertical_replacement_app: None # IGNORED because has vertical content
      work_duration_in_minutes: 25
      break_duration_in_minutes: 5
      long_break_duration_in_minutes: 15
    dependencies:
  GifPlayer:
    enabled: true
    meta:
      name: GIF Player
      description: Displays animated GIFs on the matrix.
      provides_horizontal_content: true
      provides_vertical_content: false
    config:
      # horizontal_replacement_app: None # IGNORED because has horizontal content
      vertical_replacement_app: None
      play_limit: 5
    dependencies:
  GameOfLife:
    enabled: false
    meta:
      name: Game of Life
      description: A cellular automaton simulation that displays patterns on the matrix.
      provides_horizontal_content: true
      provides_vertical_content: false
    config:
      # horizontal_replacement_app: None # IGNORED because has horizontal content
      vertical_replacement_app: None
    dependencies:
  Spotify:
    enabled: false
    meta:
      name: Spotify
      description: Displays the current playing track from Spotify.
      provides_horizontal_content: true
      provides_vertical_content: false
    config:
      # horizontal_replacement_app: None # IGNORED because has horizontal content
      vertical_replacement_app: None
    dependencies:
      - Spotify
  Notion:
    enabled: false
    meta:
      name: Notion
      description: Displays information from Notion databases.
      provides_horizontal_content: true
      provides_vertical_content: false
    config:
      # horizontal_replacement_app: None # IGNORED because has horizontal content
      vertical_replacement_app: None
      token_v2:
      source:
    dependencies:
  Youtube:
    enabled: false
    meta:
      name: YouTube
      description: Displays the latest videos from a YouTube channel.
      provides_horizontal_content: true
      provides_vertical_content: false
    config:
      # horizontal_replacement_app: None # IGNORED because has horizontal content
      vertical_replacement_app: None
      key:
    dependencies:
  Pushbullet:
    enabled: false
    meta:
      name: Pushbullet
      description: Displays notifications from Pushbullet.
      provides_horizontal_content: true
      provides_vertical_content: false
    config:
      # horizontal_replacement_app: None # IGNORED because has horizontal content
      vertical_replacement_app: None
    dependencies:
      - Notifications
  Weather:
    enabled: false
    meta:
      name: Weather
      description: Displays the current weather conditions.
      provides_horizontal_content: true
      provides_vertical_content: false
    config:
      # horizontal_replacement_app: None # IGNORED because has horizontal content
      vertical_replacement_app: None
    dependencies:
      - Weather
```
