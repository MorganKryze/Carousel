# Carousel

RGB LED matrix dashboard for Raspberry Pi Zero, displaying apps (clock, GIF player, Pomodoro, Game of Life, Spotify, weather, etc.) with an always-on web-based configuration interface and recovery mode.

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
- **Flask + Waitress** — always-on web config server on port 9000
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
- `WebServer` — uses `__new__` singleton via `_do_init()` (never call `__init__`)

**Important:** Always access singletons via their constructor: `Configuration()`, `SystemContext()`, etc. Never instantiate twice with different args.

### Directory Layout

```plain
src/
├── __main__.py          # CLI entry point (--debug, --emulator)
├── core/                # System singletons and orchestration
│   ├── config.py        # Configuration singleton (generational versioning)
│   ├── config_helpers.py    # YAML I/O, validation helpers
│   ├── config_schema.py     # Pydantic models (ConfigRoot, AppConfig, etc.)
│   ├── app_catalog.py       # Static app metadata (name, description, orientations)
│   ├── system_context.py    # DI container (display, input, config, state)
│   ├── game_loop.py         # Async render loop, frame processing
│   ├── app_manager.py       # App loading, switching, lifecycle
│   ├── webserver.py         # Flask/Waitress web server (always-on, staged changes)
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
- Reads `enabled` from `Configuration`; reads `name`, `description`, `orientations` from `APP_CATALOG`
- Tracks status via `ServiceStatus` enum (DISABLED, INITIALIZING, RUNNING, ERROR\_\*)

**App catalog** (`src/core/app_catalog.py`):

- Frozen `AppEntry` dataclasses — developer-maintained metadata (name, description, category, orientations, dependencies)
- `APP_CATALOG: Dict[str, AppEntry]` — keyed by the config/class name (e.g. `"MainScreen"`)
- `CATEGORY_ORDER: List[str]` — canonical sidebar order
- To add a new app: add an `AppEntry` here, add class to `src/apps/`, register in `app_manager.py` `app_registry`, add config section to `template.config.yaml`

**App registration** (`src/core/app_manager.py`):

- `app_registry` dict maps config names to classes
- Apps loaded in order defined by `order` field in config YAML

**Config system** (`src/core/config.py`):

- Generational versioning: `configs/generation_N.yaml`
- Broken configs renamed to `.broken.yaml` with reason in metadata
- Recovery mode triggered when latest generation is broken (no separate trigger file)
- Template: `template.config.yaml`, Recovery: `recovery.config.yaml`
- Config access: `config.get("Apps", "MainScreen", "config", "use_24_hour")`
- Shorthand: `config.get_from_app_config("MainScreen", "use_24_hour")`

**Web server** (`src/core/webserver.py`):

- **Always-on** — starts in `__main__.py` before `GameLoop`, available at `http://<ip>:9000`
- **Staged changes** — edits accumulate in `_pending_changes` dict (server memory only); nothing writes to disk until `POST /api/save-changes`
- If the browser is closed, `_pending_changes` is lost — this is intentional and safe
- Recovery mode: loads broken generation for editing; apply/rollback/generate-new routes unchanged
- Key API endpoints: `POST /api/stage-change`, `POST /api/toggle-app`, `POST /api/save-changes`, `POST /api/discard-changes`

### Execution Flow

1. `__main__.py` → parse args → set paths → start logger
2. `NetworkManager.init_connectivity()` (hardware only)
3. `WebServer().start(port=9000)` — always starts here, before game loop
4. `GameLoop(use_emulator)` → `SystemContext` → `AppManager.init_apps()`
5. Loading animation → async `render_loop()` at target FPS
6. Each frame: drain encoder queue → get current app → `app.generate()` → display if changed

## Configuration Schema

Top-level YAML structure validated by Pydantic (`ConfigRoot`):

```yaml
Metadata: { id, version, created_at, origin, is_broken, broken_reason }
System: { Matrix, Tilt-switch, Encoder, Network }
Modules: { ModuleName: { enabled, meta, config } }
Apps: { AppName: { enabled, order, config } }
```

- `extra="forbid"` on all Pydantic models — unknown fields are rejected
- `AppMeta` and `dependencies` were **removed** from the app schema — this data now lives in `app_catalog.py`
- App `order` must be unique across all apps
- Any `generation_*.yaml` containing `meta` or `dependencies` under `Apps` will fail validation

## Web UI Routes

| Method | Path                               | Description                              |
| ------ | ---------------------------------- | ---------------------------------------- |
| `GET`  | `/`                                | Landing/warning page → redirects to `/catalog` |
| `GET`  | `/catalog[/<category>]`            | App-store grid (all or filtered)         |
| `GET`  | `/app/<app_name>`                  | Per-app config editor                    |
| `GET`  | `/settings`                        | System + modules hub                     |
| `GET`  | `/settings/<section>/<subsection>` | Subsection form editor                   |
| `GET`  | `/review`                          | Diff view of pending changes             |
| `POST` | `/api/stage-change`                | Stage one field change                   |
| `POST` | `/api/toggle-app`                  | Toggle app enabled/disabled              |
| `POST` | `/api/save-changes`                | Apply all pending, new generation, restart |
| `POST` | `/api/discard-changes`             | Clear all staged changes                 |
| `GET`  | `/recovery-mode`                   | Recovery mode page                       |
| `POST` | `/recovery-mode/apply`             | Apply fixed broken config                |
| `POST` | `/recovery-mode/rollback`          | Restore previous working generation      |
| `POST` | `/recovery-mode/generate_new`      | Fresh config from template               |

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
- `WebServer` uses `__new__` + `_do_init()` (not `__init__`) — do not add instance setup to `__init__`
- Never add `meta` or `dependencies` back to app YAML config — that data belongs in `app_catalog.py`
- `_pending_changes` is in-memory only — a process restart clears all staged changes

## Workflow Orchestration

### 1. Plan Node Default

- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately — don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy

- Use subagents to keep the main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop

- After ANY correction from the user: update `memory/lessons.md` with the pattern
- Write rules that prevent the same mistake from recurring
- Review lessons at session start for relevant context

### 4. Verification Before Done

- Never mark a task complete without proving it works
- Diff behaviour between main and your changes when relevant
- Run the app, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)

- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: implement the elegant solution instead
- Skip this for simple, obvious fixes — don't over-engineer

### 6. Autonomous Bug Fixing

- When given a bug report: just fix it — no hand-holding needed
- Point at logs, errors, failing tests, then resolve them
- Go fix failing issues without being told how

## Core Principles

- **Simplicity First** — make every change as simple as possible; minimal code impact
- **No Laziness** — find root causes; no temporary fixes; senior developer standards
- **Minimal Impact** — changes should only touch what's necessary; avoid introducing bugs
