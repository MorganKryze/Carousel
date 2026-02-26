# Carousel

RGB LED matrix dashboard for Raspberry Pi Zero, displaying apps (clock, GIF player, Pomodoro, Game of Life, Spotify, weather, etc.) with a web-based configuration interface and recovery mode.

## Quick Reference

| Action                | Command              |
| --------------------- | -------------------- |
| Run (emulator, dev)   | `make dev-emulator`  |
| Run (hardware, debug) | `make dev`           |
| Run (hardware, prod)  | `make run`           |
| Install dev deps      | `make install-dev`   |
| Install prod deps     | `make install`       |
| Docker deploy         | `make docker-deploy` |
| Clean bytecode        | `make clean-python`  |

## Tech Stack

- **Python 3.11+** — entry point: `src/__main__.py` (run via `python src`)
- **Flask + Waitress** — web config server on port 9000
- **Pydantic** — config schema validation (`src/core/config_schema.py`)
- **Pillow** — image/frame generation for the LED matrix
- **loguru** — all logging (never use `print()`)
- **PyYAML** — config file format
- **pigpio / gpiozero** — GPIO on Raspberry Pi (production only)
- **RGBMatrixEmulator + pynput** — desktop development (emulator only)

## Architecture

### Singleton Pattern

All core components are singletons via `__new__` + `_initialize()`:

- `Configuration` — generational config with automatic fallback
- `SystemContext` — dependency injection container (display, input, config, state)
- `GameLoop` — async render loop at configurable FPS
- `AppManager` — app lifecycle, loading, switching
- `NetworkManager` — WiFi connect with hotspot fallback

**Important:** Always access singletons via their constructor: `Configuration()`, `SystemContext()`, etc. Never instantiate twice with different args.

### Directory Layout

```plain
src/
├── __main__.py          # CLI entry point (--debug, --emulator)
├── core/                # System singletons and orchestration
│   ├── config.py        # Configuration singleton (generational versioning)
│   ├── config_helpers.py    # YAML I/O, validation helpers
│   ├── config_schema.py     # Pydantic models (ConfigRoot, AppConfig, etc.)
│   ├── system_context.py    # DI container (display, input, config, state)
│   ├── game_loop.py         # Async render loop, frame processing
│   ├── app_manager.py       # App loading, switching, lifecycle
│   ├── webserver.py         # Flask/Waitress web server
│   ├── network_manager.py   # WiFi/hotspot via nmcli
│   └── system_state.py      # Runtime state (tilt, encoder, brightness)
├── apps/                # Application implementations
│   ├── main_screen.py       # Clock/date display
│   ├── gif_viewer.py        # GIF playback
│   ├── pomodoro.py          # Pomodoro timer
│   ├── life.py              # Conway's Game of Life
│   ├── recovery_mode.py     # Recovery mode display
│   ├── spotify_player.py, stocks.py, weather.py, notion.py, subcount.py
├── models/              # Base classes
│   ├── application.py       # Application base (generate + error handling)
│   ├── module.py            # Module base (shared services for apps)
│   └── input_controller.py  # Input interface
├── modules/             # Service modules (weather, spotify, notifications)
├── hardware/            # Display + input controllers (GPIO vs keyboard)
├── display/             # Frame generation, animations, custom frames
├── enums/               # ServiceStatus, EncoderInput, TiltState
└── utils/               # PathTo (paths), logs (loguru setup)
```

### Key Patterns

**Application base class** (`src/models/application.py`):

- Every app extends `Application`, receives `SystemContext` + `callbacks` dict
- Must implement `generate(tilt_state, encoder_input) -> Image`
- Reads enabled/meta/config from `Configuration` using the class name as key
- Tracks status via `ServiceStatus` enum (DISABLED, INITIALIZING, RUNNING, ERROR\_\*)

**App registration** (`src/core/app_manager.py`):

- `app_registry` dict maps config names to classes
- Apps loaded in order defined by `order` field in config YAML
- To add a new app: add class to `src/apps/`, register in `app_registry`, add config section to `template.config.yaml`

**Config system** (`src/core/config.py`):

- Generational versioning: `configs/generation_N.yaml`
- Broken configs renamed to `.broken.yaml` with reason in metadata
- Recovery mode triggered when latest generation is broken (no separate trigger file)
- Template: `template.config.yaml`, Recovery: `recovery.config.yaml`
- Config access: `config.get("Apps", "MainScreen", "config", "use_24_hour")`
- Shorthand: `config.get_from_app_config("MainScreen", "use_24_hour")`

**Web server** (`src/core/webserver.py`):

- Normal mode: edit live config, save creates new generation
- Recovery mode: edit broken generation, then apply/rollback/generate-new
- Auto-starts on port 9000 in recovery mode

### Execution Flow

1. `__main__.py` → parse args → set paths → start logger
2. `NetworkManager.init_connectivity()` (hardware only)
3. `GameLoop(use_emulator)` → `SystemContext` → `AppManager.init_apps()`
4. Loading animation → async `render_loop()` at target FPS
5. Each frame: drain encoder queue → get current app → `app.generate()` → display if changed

## Configuration Schema

Top-level YAML structure validated by Pydantic (`ConfigRoot`):

```yaml
Metadata: { id, version, created_at, origin, is_broken, broken_reason }
System: { Matrix, Tilt-switch, Encoder, Network }
Modules: { ModuleName: { enabled, meta, config } }
Apps: { AppName: { enabled, order, meta, config, dependencies } }
```

- `extra="forbid"` on all Pydantic models — unknown fields are rejected
- Apps reference modules via `dependencies` list (validated against `Modules` keys)
- App `order` must be unique across all apps

## Conventions

- **Commit messages:** emoji prefix format — `🌟 feat:`, `🚑 fix:`, `📖 docs:`, `♻️ refactor:`, `🧪 test:`
- **Logging:** always use `loguru.logger`, never `print()`
- **Error states:** use `ServiceStatus` enum, never raw strings
- **Config access:** use `Configuration()` methods, never read YAML directly
- **Hardware safety:** `GameLoop.cleanup()` must release GPIO/display before restart
- **Type hints:** use throughout, Pydantic for validation at boundaries
- **No tests yet** — the project has no test suite currently

## Common Pitfalls

- Singleton args are only used on first instantiation — `SystemContext(use_emulator=True)` only works the first time
- `config.get(..., required=True)` calls `critical_exit()` on missing keys, which triggers recovery mode and process restart
- Web server runs in a daemon thread — don't block the main async event loop
- `os.execv` is used for restart — all hardware must be cleaned up before calling it
- The `rpi-rgb-led-matrix` submodule must be cloned recursively (`git submodule update --init --recursive`)
