# Carousel Webserver Redesign — Specification & UI/UX Plan

> Status: DRAFT — edit freely, this is the living spec.
> Generated: 2026-02-27

---

## 1. Why This Redesign

### 1.1 Problem

The current webserver has two issues:

**Scope problem:** The webserver only auto-starts in recovery mode. This wastes its potential
as a configuration interface. The web UI should always be available — the user should not need
to break their config to access settings.

**UX problem:** The current UI is a raw YAML form editor. The user must navigate blindly
through a hierarchy of section names, with no context about what each app does, no categories,
no visual feedback, and changes are saved immediately with no review step. One wrong edit
restarts the system.

### 1.2 Goals

- Always-on webserver at `http://<device-ip>:9000`
- App-store-style catalog with categories and per-app detail pages
- Staged changes: no immediate writes — the user reviews all changes before committing
- One-shot save: a single "Confirm & Restart" action creates a new config generation and reboots
- Recovery mode flow preserved exactly — same behavior, new styling

### 1.3 Non-goals (for this iteration)

- Authentication (placeholder in the frontend for password only — no logic - always lets the user in)
- WebSocket live preview of the matrix display
- Per-app custom icons (mockup.png placeholder for now)
- Test suite (project has none currently)

---

## 2. Values & Constraints to Preserve

These must never change, regardless of UI rework:

| Value                     | What it means in practice                                                                                                                                                                                       |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Generational config       | Every save creates `configs/generation_N.yaml`. Never overwrite an existing generation.                                                                                                                         |
| Atomic saves              | `create_new_config_generation(config)` handles versioning — call it, never write YAML directly.                                                                                                                 |
| Recovery mode             | Triggered when latest generation is broken. `/recovery-mode` and its three actions (apply/rollback/generate_new) must work identically.                                                                         |
| Singleton pattern         | `WebServer`, `Configuration`, `GameLoop` are singletons via `__new__`. Never double-initialize.                                                                                                                 |
| Restart via execv         | `Configuration().restart()` → `GameLoop.cleanup()` → `os.execv()`. Hardware GPIO is released before restart.                                                                                                    |
| PathTo constants          | All file paths go through `PathTo`. Never hardcode paths.                                                                                                                                                       |
| Pydantic `extra="forbid"` | All Pydantic models reject unknown fields. `AppMeta` is removed in this redesign. The per-app model covers only `enabled`, `order`, `config`. Do not add fields to any config model without a schema migration. |
| loguru only               | Never use `print()`. Use `logger.info/warning/error/critical`.                                                                                                                                                  |
| Daemon thread for server  | Webserver runs in a daemon thread and must not block the async render loop.                                                                                                                                     |

---

## 3. Architecture Overview

### 3.1 Startup Sequence (new)

```plain
__main__.py: async_main()
  ├─ PathTo.set_base_directory()
  ├─ PathTo.ensure_data_directories()
  ├─ start_logger()
  ├─ NetworkManager().init_connectivity()   [hardware only]
  ├─ WebServer().start(port=9000)           ← ALWAYS, new location
  ├─ GameLoop(use_emulator)
  │    └─ [NO webserver start here anymore]
  ├─ Animations.loading_animation()
  └─ asyncio.create_task(game_loop.render_loop())
```

**Change in `game_loop.py`:** Remove `_start_webserver_for_recovery_mode()` and the
`if self.context.config.is_recovery_mode():` block in `_initialize()`.

**Change in `__main__.py`:** Add `WebServer().start(port=9000, debug=use_debug)` before `GameLoop()`.

**Change in `webserver.py`:** Convert `WebServer` to a proper `__new__` singleton (currently
it relies on single-call convention only, which is fragile after the startup change):

```python
_instance: Optional["WebServer"] = None

def __new__(cls) -> "WebServer":
    if cls._instance is None:
        cls._instance = super().__new__(cls)
        cls._instance._do_init()
    return cls._instance
```

### 3.2 Staged Changes Pattern

The current webserver mutates `configuration_dictionary` in-place on every form POST, then
saves. The new pattern introduces a staging layer:

```plain
User edits field
      ↓
POST /api/stage-change   →  _pending_changes dict updated (server memory)
      ↓
Unsaved banner appears (count of staged changes)
      ↓
User clicks "Review & Save"
      ↓
GET /review              →  Diff view of all _pending_changes
      ↓
User clicks "Confirm & Restart"
      ↓
POST /api/save-changes   →  Deep copy config → apply all pending → create_new_config_generation() → restart
```

**Nothing is written to disk until `POST /api/save-changes`.**
If the user closes the browser, `_pending_changes` is lost (in-memory only). This is intentional
and safe: the live config is unchanged.

### 3.3 Pending Changes Data Structure

```python
# WebServer instance attribute:
self._pending_changes: Dict[str, Dict] = {}

# Key: dotted path string, e.g. "Apps.MainScreen.config.use_24_hour"
# Value:
{
    "path": "Apps.MainScreen.config.use_24_hour",
    "path_parts": ["Apps", "MainScreen", "config", "use_24_hour"],
    "section": "Apps",
    "subsection": "MainScreen",
    "label": "use_24_hour",
    "display_path": "Apps › MainScreen › config",
    "old": True,
    "new": False,
    "type": "bool",   # "bool" | "int" | "float" | "str" | "null"
}
```

**Key rule:** If `new == old` (user reverted to original), remove the key from `_pending_changes`.
This keeps the count accurate and prevents phantom diffs.

### 3.4 App Catalog (`src/core/app_catalog.py`)

The current config mixes two distinct concerns in the user YAML:

```yaml
# BEFORE — user config carries both declaration and intent
Apps:
  MainScreen:
    enabled: true # ← user intent
    order: 1 # ← user intent
    config: # ← user intent
      use_24_hour: true
    meta: # ← app declaration (not user-editable)
      name: 'Main Screen'
      description: 'Clock and date display'
      orientations: [horizontal, vertical]
    dependencies: [] # ← app declaration (not user-editable)
```

`meta` and `dependencies` are facts about the code, not user preferences. Moving them to a
developer-maintained Python catalog separates these layers cleanly:

```yaml
# AFTER — user config contains only user intent
Apps:
  MainScreen:
    enabled: true
    order: 1
    config:
      use_24_hour: true
```

**`src/core/app_catalog.py`** is a pure declaration module with no imports from the rest of
the codebase:

```python
from dataclasses import dataclass, field
from typing import Dict, List

@dataclass(frozen=True)
class AppEntry:
    name: str
    description: str
    category: str
    orientations: List[str]
    dependencies: List[str] = field(default_factory=list)

APP_CATALOG: Dict[str, AppEntry] = {
    "MainScreen": AppEntry(
        name="Main Screen",
        description="Clock and date display with multiple themes.",
        category="Top",
        orientations=["horizontal", "vertical"],
    ),
    "GifPlayer": AppEntry(
        name="GIF Player",
        description="Plays animated GIFs from the data/gifs directory.",
        category="Entertainment",
        orientations=["horizontal", "vertical"],
    ),
    "Pomodoro": AppEntry(
        name="Pomodoro",
        description="Focus timer with work/break cycles.",
        category="Productivity",
        orientations=["horizontal", "vertical"],
    ),
    "GameOfLife": AppEntry(
        name="Game of Life",
        description="Conway's Game of Life cellular automaton.",
        category="Games",
        orientations=["horizontal", "vertical"],
    ),
    "Spotify": AppEntry(
        name="Spotify",
        description="Now-playing display for Spotify.",
        category="Music",
        orientations=["horizontal"],
        dependencies=["Spotify"],
    ),
    "Notion": AppEntry(
        name="Notion",
        description="Displays tasks from a Notion database.",
        category="Productivity",
        orientations=["horizontal"],
        dependencies=["Notion"],
    ),
    "Youtube": AppEntry(
        name="YouTube",
        description="Subscriber count display.",
        category="Social",
        orientations=["horizontal"],
        dependencies=["Youtube"],
    ),
    "Pushbullet": AppEntry(
        name="Pushbullet",
        description="Push notification display.",
        category="Notifications",
        orientations=["horizontal"],
        dependencies=["Pushbullet"],
    ),
    "Weather": AppEntry(
        name="Weather",
        description="Current conditions and forecast.",
        category="Info",
        orientations=["horizontal", "vertical"],
        dependencies=["Weather"],
    ),
}

CATEGORY_ORDER: List[str] = [
    "Top", "Entertainment", "Productivity",
    "Games", "Music", "Social", "Notifications", "Info",
]
```

**Usage across the codebase:**

| Consumer     | What it reads                                                                    |
| ------------ | -------------------------------------------------------------------------------- |
| `WebServer`  | `name`, `description`, `category` for UI rendering; `CATEGORY_ORDER` for sidebar |
| `AppManager` | `orientations` to filter apps by tilt state; `dependencies` to validate modules  |

**Schema migration:** The per-app Pydantic model in `config_schema.py` drops the `meta` and
`dependencies` fields. `AppMeta` is removed entirely. The slimmed model becomes:

```python
class AppRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    order: int
    config: Dict[str, Any]
```

`template.config.yaml` is regenerated without `meta`/`dependencies` sections. Existing
`generation_N.yaml` files with these fields will fail Pydantic validation — this is a
**breaking config migration** and must be handled before deploying.

---

## 4. Complete Route Map

### Normal Mode Routes

| Method | Path                               | Handler               | Description                                                 |
| ------ | ---------------------------------- | --------------------- | ----------------------------------------------------------- |
| `GET`  | `/`                                | `index`               | Landing/warning page, no logic, redirects to `/catalog`     |
| `GET`  | `/catalog`                         | `catalog`             | App store grid (all categories)                             |
| `GET`  | `/catalog/<category>`              | `catalog`             | App store grid (filtered)                                   |
| `GET`  | `/app/<app_name>`                  | `app_detail`          | Per-app detail + config editor                              |
| `GET`  | `/settings`                        | `settings`            | System config hub (Matrix, Network, Encoder, Tilt, Modules) |
| `GET`  | `/settings/<section>/<subsection>` | `settings_section`    | Subsection form editor                                      |
| `GET`  | `/review`                          | `review_changes`      | Diff view of all pending changes                            |
| `GET`  | `/api/pending-changes`             | `get_pending_changes` | Return pending changes as JSON                              |
| `POST` | `/api/stage-change`                | `stage_change`        | Stage one field change (JSON body)                          |
| `POST` | `/api/toggle-app`                  | `toggle_app`          | Toggle app enabled/disabled                                 |
| `POST` | `/api/discard-changes`             | `discard_changes`     | Clear all staged changes                                    |
| `POST` | `/api/save-changes`                | `save_changes`        | Apply staged changes, new generation, restart               |
| `POST` | `/restart`                         | `restart_system`      | Reboot RPi (preserved)                                      |
| `POST` | `/close`                           | `close_connection`    | Disconnect (preserved)                                      |

### Recovery Mode Routes (unchanged)

| Method | Path                          | Description                         |
| ------ | ----------------------------- | ----------------------------------- |
| `GET`  | `/recovery-mode`              | Recovery mode page                  |
| `POST` | `/recovery-mode/apply`        | Apply edited broken config          |
| `POST` | `/recovery-mode/rollback`     | Restore previous working generation |
| `POST` | `/recovery-mode/generate_new` | Create from template                |

### Removed Routes

| Route                       | Replaced by                                          |
| --------------------------- | ---------------------------------------------------- |
| `GET /home`                 | `GET /catalog`                                       |
| `GET /section/<name>`       | `GET /app/<name>` or `GET /settings/<section>/<sub>` |
| `GET /section/<name>/<sub>` | `GET /settings/<section>/<sub>`                      |
| `POST /update`              | `POST /api/stage-change`                             |

---

## 5. File Map

### Files to Modify

| File                        | Change                                                                                             |
| --------------------------- | -------------------------------------------------------------------------------------------------- |
| `src/__main__.py`           | Add `WebServer().start(port=9000)` before `GameLoop()`                                             |
| `src/core/game_loop.py`     | Remove `_start_webserver_for_recovery_mode()` and recovery-only conditional                        |
| `src/core/webserver.py`     | Major rewrite: new routes, `_pending_changes`, catalog import, context processor, proper singleton |
| `src/core/app_manager.py`   | Replace `meta`/`dependencies` reads from config with lookups into `APP_CATALOG`                    |
| `src/core/config_schema.py` | Remove `AppMeta` model; strip `meta` and `dependencies` from per-app Pydantic model                |
| `template.config.yaml`      | Regenerate without `meta`/`dependencies` sections under each app                                   |

### Files to Create

**Source (`src/core/`):**

| File                      | Role                                                                                |
| ------------------------- | ----------------------------------------------------------------------------------- |
| `src/core/app_catalog.py` | Frozen `AppEntry` dataclass + `APP_CATALOG` dict + `CATEGORY_ORDER` list (see §3.4) |

**Templates (`resources/web/templates/`):**

| File                           | Role                                                                           |
| ------------------------------ | ------------------------------------------------------------------------------ |
| `base.html`                    | Layout shell: `<head>`, sidebar include, banner include, `{% block content %}` |
| `landing.html`                 | Warning page → replaces `index.html`                                           |
| `catalog.html`                 | App store grid → replaces `home.html`                                          |
| `app_detail.html`              | Per-app config → replaces `section.html` for apps                              |
| `settings.html`                | System + modules hub                                                           |
| `settings_section.html`        | Subsection form editor → replaces `section.html` for system/modules            |
| `review_changes.html`          | Diff view + confirm button                                                     |
| `partials/sidebar.html`        | Left navigation with categories + bottom buttons                               |
| `partials/unsaved_banner.html` | Sticky top banner (only when pending_count > 0)                                |
| `partials/app_card.html`       | Single card in the catalog grid                                                |
| `partials/field_row.html`      | Single form field (bool/int/float/str) with JS staging                         |
| `partials/change_row.html`     | Single row in the diff view                                                    |

**Static (`resources/web/static/`):**

| File            | Role                                                             |
| --------------- | ---------------------------------------------------------------- |
| `style.css`     | Full rewrite: CSS variables, dark theme, layout, buttons, badges |
| `main.js`       | Global: banner update, fetch helper, discard handler             |
| `app_detail.js` | Field staging on change, toggle-app handler                      |
| `review.js`     | Confirm flow, loading overlay, discard + redirect                |

### Files to Delete (after migration confirmed)

- `resources/web/templates/index.html` → replaced by `landing.html`
- `resources/web/templates/home.html` → replaced by `catalog.html`
- `resources/web/templates/section.html` → replaced by `app_detail.html` + `settings_section.html`

### Files Preserved Verbatim

- `resources/web/templates/recovery_mode.html` → refactored to extend `base.html` but content unchanged
- `resources/web/static/mockup.png` → kept as app icon placeholder

---

## 6. UI/UX Design Specification

### 6.1 Design Tokens (CSS Variables)

Define at `:root` in `style.css`. Dark theme, hardware-admin aesthetic:

```css
:root {
  /* Colors */
  --color-bg: #0f1117; /* page background */
  --color-surface: #1a1d27; /* card / panel background */
  --color-surface-hi: #22263a; /* hovered card */
  --color-border: #2a2d3a; /* dividers */
  --color-accent: #6c8fff; /* primary — blue-indigo */
  --color-accent-hi: #8fa8ff; /* hover state */
  --color-text: #e2e4ed; /* primary text */
  --color-muted: #8b8fa8; /* secondary text, labels */
  --color-success: #22c55e; /* enabled badges, confirm */
  --color-warning: #f59e0b; /* unsaved banner */
  --color-danger: #ef4444; /* destructive, recovery mode */
  --color-recovery: #dc2626; /* recovery mode sidebar tint */

  /* Layout */
  --sidebar-width: 240px;
  --banner-height: 48px; /* 0px when banner hidden */
  --content-max-width: 1100px;

  /* Shape */
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;

  /* Typography */
  --font-sans: system-ui, -apple-system, 'Segoe UI', sans-serif;
  --font-mono: 'Courier New', Courier, monospace;
  --font-size-base: 14px;
}
```

### 6.2 Layout Structure

```plain
┌─────────────────────────────────────────────────────────┐
│  UNSAVED BANNER (sticky top, z-index: 100)              │   48px
│  "● 3 unsaved changes  [Review & Save]  [Discard All]" │
├─────────────────────────────────────────────────────────┤
│  SIDEBAR (fixed left)     │  MAIN CONTENT               │
│  ─────────────────────    │  (scrollable)               │
│  [●] Carousel             │                             │
│                           │  {% block content %}        │
│  Categories               │                             │
│  ▸ All Apps               │                             │
│  ▸ Top                    │                             │
│  ▸ Entertainment          │                             │
│  ▸ Productivity           │                             │
│  ▸ Games                  │                             │
│  ▸ Music                  │                             │
│  ▸ Social                 │                             │
│  ▸ Notifications          │                             │
│  ▸ Info                   │                             │
│                           │                             │
│  ─ (flex push to bottom)  │                             │
│  [?] Help                 │                             │
│  [⚙] Settings            │                             │
│  [◉] Profile (stub)       │                             │
└───────────────────────────┴─────────────────────────────┘
```

Mobile breakpoint (< 768px): sidebar collapses, hamburger menu appears.

### 6.3 Landing Page (`landing.html`)

- Full-page centered card, no sidebar
- Carousel logo / wordmark
- Warning copy: "This interface directly controls your Carousel matrix. Changes will restart the device."
- Grey auth placeholder block: `<!-- Auth: login form will go here -->` with a disabled "Sign in" button stub
- Bold "Enter Configuration →" button → navigates to `/catalog`

**UX principle:** The warning is not a blocker. The button is prominent. The user should not
feel locked out of their own device.

### 6.4 Catalog Page (`catalog.html`)

- `grid-template-columns: repeat(auto-fill, minmax(180px, 1fr))` card grid
- Cards are sorted: enabled apps first (by `order`), then disabled apps alphabetically
- Category filter via sidebar: clicking a category re-renders the same page with `?category=X`
- Client-side search input: JS `filter()` on card data attributes — no server round-trip
- Each card:
  - App icon (64×64px, `mockup.png` placeholder)
  - `APP_CATALOG[app_key].name` (bold)
  - `APP_CATALOG[app_key].description` (2-line clamp, `overflow: hidden`)
  - Status badge: green "ENABLED" or grey "DISABLED"
  - Full card is a link to `/app/<app_key>`

**UX principle:** The catalog is browse-first. Status is immediately visible without opening
an app.

### 6.5 App Detail Page (`app_detail.html`)

```plain
← Back to All Apps

  [icon]  Main Screen                    ● ENABLED    [Toggle]
  Category: Top  ·  Carousel position: 1
  "Clock and date display with multiple themes."

  ── Configuration ─────────────────────────────────────────
  use_24_hour          [true ▾]
  date_format          [DD-MM          ]
  cycle_duration       [20             ] seconds

  ── Metadata ──────────────────────────────────────────────
  Orientations supported:  Horizontal  Vertical
  Module dependencies:     —
```

- Each field change → `POST /api/stage-change` via `fetch()` on `change` or `blur` event
- No "Save" button on this page — save is deferred to the banner
- If the field is currently staged, its input shows a yellow left-border highlight
- If the app has module dependencies that are disabled, show:
  `⚠ The "Weather" module is disabled. Enable it in Settings to use this app.`
- Carousel position (`order`) is shown read-only (not editable here to prevent order conflicts)

**Field type rendering (via `partials/field_row.html`):**

| Config value type | Input element                                                                                                                          |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `bool`            | `<select>` with `true` / `false` options                                                                                               |
| `int`             | `<input type="number" step="1">`                                                                                                       |
| `float`           | `<input type="number" step="0.01">`                                                                                                    |
| `str`             | `<input type="text">` (or `type="password"` for tokens/secrets — detected by key name containing "token", "password", "secret", "key") |
| `None`            | `<input type="text" placeholder="(not set)">`                                                                                          |

**UX principles:**

- Progressive disclosure: config fields are the most important thing; metadata is collapsed by default
- Instant visual feedback on staging (yellow border) without a page reload
- No modal dialogs — all actions are inline

### 6.6 Unsaved Banner (`partials/unsaved_banner.html`)

```html
<div
  id="unsaved-banner"
  class="unsaved-banner"
  {%
  if
  pending_count=""
  ="0"
  %}style="display:none"
  {%
  endif
  %}
>
  <span class="unsaved-dot">●</span>
  <span id="unsaved-count">{{ pending_count }}</span> unsaved change{{
  pending_count|pluralize }}
  <a href="/review" class="btn-banner-primary">Review & Save</a>
  <button id="banner-discard" class="btn-banner-ghost">Discard All</button>
</div>
```

JS in `main.js` updates `#unsaved-count` and shows/hides the banner after every
`/api/stage-change` or `/api/discard-changes` response.

**UX principle:** The banner is persistent but unobtrusive. It does not interrupt the user's
browsing flow.

### 6.7 Changes Review Page (`review_changes.html`)

```plain
Review 3 Pending Changes
─────────────────────────────────────────────────────
These changes will be saved as a new configuration (generation N+1)
and the Carousel will restart automatically.

Apps › MainScreen › config
  use_24_hour          true  →  false

Apps › GifPlayer › config
  play_limit           5     →  10

Apps › MainScreen
  enabled              true  →  false

─────────────────────────────────────────────────────
[Discard All Changes]                  [Confirm & Restart →]
```

- Changes are grouped by `display_path` (Apps › AppName › config)
- Old value shown in muted red, new value in green
- "Confirm & Restart" is a POST button. On click:
  1. Button disabled, text changes to "Saving…" with spinner
  2. `POST /api/save-changes`
  3. On `{"status": "success"}`: full-screen overlay: "Restarting... reconnect in ~10 seconds"
  4. On `{"status": "error"}`: inline error message below the button
- "Discard All Changes": calls `POST /api/discard-changes`, redirects to `/catalog`

**UX principle:** The review page is the last chance to catch mistakes. Make the diff readable,
not technical. Use plain labels, not dotted path strings, where possible.

### 6.8 Settings Page (`settings.html`)

Two panels:

**System panel** (links to subsection form):

- Matrix (LED rows, cols, brightness, FPS, hardware mapping)
- Network (SSID, password, hotspot settings)
- Encoder (GPIO pins, bounce time, press windows)
- Tilt Switch (GPIO pin, bounce time)

Each system section shows a "⚠ System-level setting — incorrect values may prevent boot" badge.

**Modules panel** (cards like the app catalog):

- Notifications, Weather, Spotify
- Each shows enabled badge, description
- Click → same `app_detail.html` template reused with module data (or a dedicated `module_detail.html`)

### 6.9 Recovery Mode (`recovery_mode.html`)

**No functional changes.** The three actions (apply/rollback/generate_new) are preserved.
The only change is extending `base.html` and adding `body_class="recovery"` which:

- Paints the sidebar red (`--color-recovery`)
- Hides the unsaved banner
- Shows "⚠ RECOVERY MODE" badge in the sidebar header

---

## 7. API Endpoint Contracts

### `POST /api/stage-change`

Request:

```json
{ "path": "Apps.MainScreen.config.use_24_hour", "new_value": false }
```

Response:

```json
{ "status": "ok", "pending_count": 1 }
```

Server logic:

1. Split `path` by `.` → `path_parts`
2. Walk `configuration_dictionary` with `path_parts` to get `old_value`
3. Infer type from `old_value`
4. If `new_value == old_value`: remove key from `_pending_changes`
5. Else: upsert entry into `_pending_changes`
6. Return `pending_count`

### `POST /api/toggle-app`

Request:

```json
{ "app_key": "MainScreen" }
```

Shorthand: reads current `enabled` value, stages the opposite. Same as calling `stage-change`
with `path = "Apps.MainScreen.enabled"`.

### `GET /api/pending-changes`

Response:

```json
{
  "count": 2,
  "changes": [
    {
      "path": "Apps.MainScreen.config.use_24_hour",
      "display_path": "Apps › MainScreen › config",
      "label": "use_24_hour",
      "old": true,
      "new": false,
      "type": "bool"
    }
  ]
}
```

### `POST /api/discard-changes`

Request: empty body `{}`

Response:

```json
{ "status": "ok", "pending_count": 0 }
```

Clears `self._pending_changes`.

### `POST /api/save-changes`

Request: empty body `{}`

Response:

```json
{
  "status": "success",
  "message": "Configuration saved as generation N. Restarting..."
}
```

Or on validation failure:

```json
{ "status": "error", "message": "Validation failed: <Pydantic error detail>" }
```

Server logic:

1. `import copy; config_copy = copy.deepcopy(self.configuration_dictionary)`
2. Walk `_pending_changes` and apply each entry to `config_copy` by `path_parts`
3. `self.config_manager.create_new_config_generation(config_copy)` (validates via Pydantic)
4. On success: `self._pending_changes.clear()`, `self._delayed_restart()`, return success JSON
5. On `ValidationError`: return error JSON, do NOT restart, do NOT clear pending changes

---

## 8. Jinja2 Context Processor

Add to `WebServer._register_routes()`:

```python
from src.core.app_catalog import APP_CATALOG, CATEGORY_ORDER  # top of webserver.py

@self.app.context_processor
def inject_globals():
    return {
        "pending_count": len(self._pending_changes),
        "is_recovery_mode": self.config_manager.is_recovery_mode(),
        "categories": CATEGORY_ORDER,
    }
```

This makes `pending_count`, `is_recovery_mode`, and `categories` available in every template
without per-handler passing. The banner and sidebar use these. Route handlers that render
app cards or detail pages pass `APP_CATALOG[app_key]` as `catalog_entry` to the template.

---

## 9. JavaScript Architecture

### Principles

- Vanilla JS only — no jQuery, no npm, no bundler
- All state lives server-side (`_pending_changes` dict)
- JS only updates the DOM after server confirms the staged change
- No optimistic UI: wait for server response before updating count

### `main.js` (loaded globally via `base.html`)

```javascript
// Shared fetch utility
function postJSON(url, body) {
  return fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  }).then(r => r.json());
}

// Update banner count and visibility
function updatePendingCount(n) {
  const banner = document.getElementById('unsaved-banner');
  const count = document.getElementById('unsaved-count');
  if (!banner) return;
  count.textContent = n;
  banner.style.display = n > 0 ? 'flex' : 'none';
}

// Discard button in banner
document
  .getElementById('banner-discard')
  ?.addEventListener('click', function () {
    if (!confirm('Discard all unsaved changes?')) return;
    postJSON('/api/discard-changes', {}).then(d =>
      updatePendingCount(d.pending_count)
    );
  });
```

### `app_detail.js` (loaded only on app detail page)

```javascript
// Stage field change on input blur/change
document.querySelectorAll('[data-path]').forEach(function (input) {
  input.addEventListener('change', function () {
    const path = this.dataset.path;
    let value = this.type === 'checkbox' ? this.checked : this.value;
    // Type coercion: booleans come as strings from select elements
    if (value === 'true') value = true;
    if (value === 'false') value = false;
    if (this.type === 'number') value = Number(value);

    postJSON('/api/stage-change', { path: path, new_value: value }).then(
      function (d) {
        updatePendingCount(d.pending_count);
        // Yellow border if staged, normal border if reverted
        input.classList.toggle('staged', d.pending_count > 0);
      }
    );
  });
});

// Toggle enable/disable button
document
  .getElementById('toggle-app-btn')
  ?.addEventListener('click', function () {
    const appKey = this.dataset.appKey;
    postJSON('/api/toggle-app', { app_key: appKey }).then(function (d) {
      updatePendingCount(d.pending_count);
      // Update badge UI locally for immediate feedback
      const badge = document.getElementById('enabled-badge');
      const currentEnabled = badge.dataset.enabled === 'true';
      badge.dataset.enabled = String(!currentEnabled);
      badge.textContent = !currentEnabled ? 'ENABLED' : 'DISABLED';
      badge.className = !currentEnabled
        ? 'badge badge-success'
        : 'badge badge-muted';
    });
  });
```

### `review.js` (loaded only on review page)

```javascript
document
  .getElementById('confirm-restart-btn')
  ?.addEventListener('click', function () {
    const btn = this;
    btn.disabled = true;
    btn.textContent = 'Saving…';

    postJSON('/api/save-changes', {}).then(function (d) {
      if (d.status === 'success') {
        document.getElementById('restart-overlay').style.display = 'flex';
      } else {
        document.getElementById('save-error').textContent = d.message;
        document.getElementById('save-error').style.display = 'block';
        btn.disabled = false;
        btn.textContent = 'Confirm & Restart';
      }
    });
  });
```

---

## 10. Webserver.py Changes — Detailed

### New Instance Attributes (add in `_do_init()`)

```python
self._pending_changes: Dict[str, Dict] = {}
```

### New Helper Methods

```python
def _get_live_value(self, path_parts: List[str]) -> Any:
    """Navigate configuration_dictionary by path_parts list."""
    node = self.config_manager.configuration_dictionary
    for part in path_parts:
        node = node[part]
    return node

def _apply_pending_to_config(self, config_copy: Dict) -> Dict:
    """Apply all _pending_changes to a deep copy of the config."""
    for entry in self._pending_changes.values():
        node = config_copy
        for part in entry["path_parts"][:-1]:
            node = node[part]
        node[entry["path_parts"][-1]] = entry["new"]
    return config_copy

def _get_staged_values_for_app(self, app_name: str) -> Dict[str, Any]:
    """Return {field_key: new_value} for all staged changes under Apps.<app_name>."""
    prefix = f"Apps.{app_name}."
    return {
        k.replace(prefix, ""): v["new"]
        for k, v in self._pending_changes.items()
        if k.startswith(prefix)
    }
```

### Methods to Preserve Verbatim

- `_delayed_restart()`
- `restart_system()`
- `close_connection()`
- `is_user_connected()`
- `start()`
- `_get_editable_config()` / `_set_editable_config()`
- All four recovery mode route handlers
- `save_config()` (renamed `_save_new_generation()` for clarity, called by `save_changes()`)

### Methods to Remove

- `update_config()` — replaced by `stage_change()` API
- `homepage()` — replaced by `catalog()`
- `edit_section()` — replaced by `app_detail()` + `settings_section()`

---

## 11. UI/UX Best Practices (Reference)

### Information Architecture

- **Progressive disclosure:** Show basic config fields by default; collapse advanced or rarely-changed fields behind a "Show advanced" toggle. System section fields are advanced by default.
- **Status always visible:** The enabled/disabled state of an app should be visible from the catalog grid without needing to open the app.
- **Breadcrumb navigation:** Every detail page shows its path (e.g. "All Apps › Productivity › Pomodoro") so the user never feels lost.

### Interaction Design

- **No modal dialogs for destructive actions:** Use inline confirmation flows (the review page IS the confirmation step). Reserve `confirm()` dialogs only for "Discard All" as a lightweight safeguard.
- **Keyboard accessibility:** All interactive elements must be reachable via `Tab`. The "Confirm & Restart" button should have `autofocus` on the review page.
- **Loading states:** Any button that triggers a server action must disable itself and show text feedback ("Saving…", "Restarting…") within the same click event. Never let the user click twice.
- **Error placement:** Errors go inline, adjacent to the relevant input or action, not in an alert box. Use `role="alert"` for screen reader compatibility.

### Visual Hierarchy

- **Typography scale:** Use only 3 sizes: `--font-size-base` (14px body), `1.25rem` (section headers), `1.75rem` (page titles). Resist adding more.
- **Color for meaning:** Green = enabled/success, amber = pending/warning, red = destructive/recovery mode, blue-indigo = primary action. Do not use color for decoration.
- **Whitespace generosity:** Give cards 1.5rem padding and 1.5rem grid gap. Dense UIs cause errors.
- **Active state clarity:** The active sidebar category gets a `2px solid var(--color-accent)` left border plus a `10%` tint background. Both cues together are unambiguous.

### Responsiveness

- Sidebar collapses to a top hamburger nav at `max-width: 768px`
- App grid reflows naturally via `auto-fill` + `minmax`
- Touch targets minimum 44×44px (WCAG 2.5.5)
- The unsaved banner stacks vertically on mobile

### Security Notes (even for LAN-only)

- Sensitive config fields (tokens, passwords, secrets) must use `type="password"` input with a show/hide toggle
- Detect by checking if the field key contains: `"token"`, `"password"`, `"secret"`, `"key"`, `"api_key"`, `"client_secret"`
- No CSRF protection needed (LAN-only single-user device — overhead not justified)
- Auth placeholder is UI-only; actual auth implementation is a future concern

### Recovery Mode UX

- Visually distinct: red sidebar, red header badge, no normal catalog accessible
- Only the three recovery actions are available (apply/rollback/generate_new)
- Clear explanation of what broke and why (from `broken_reason` in config metadata)
- Recovery page accessible via redirect from all normal routes when `is_recovery_mode == True`

---

## 12. Future Extension Points

These are intentionally out of scope for this iteration but the design should not block them:

| Future feature                  | Where it slots in                                                                                   |
| ------------------------------- | --------------------------------------------------------------------------------------------------- |
| Authentication                  | `landing.html` auth slot (comment placeholder exists)                                               |
| Per-app icons                   | Replace `mockup.png` with `resources/web/static/icons/<app_key>.png`, with fallback to `mockup.png` |
| WebSocket live matrix preview   | New `<div id="matrix-preview">` in `base.html` sidebar footer                                       |
| App install (new app upload)    | New `POST /install-app` route + upload dialog in catalog                                            |
| Config export/import            | Buttons in Settings page, new routes                                                                |
| Carousel position drag-and-drop | Replace read-only `order` in app detail with a sortable list in catalog                             |
| Dark/light theme toggle         | Toggle stored in `localStorage`, CSS variable swap                                                  |
| Granular user roles             | Extend auth placeholder in landing                                                                  |

---

## 13. Verification Checklist

After implementation, verify manually:

- [ ] `make dev-emulator` logs show "Webserver started on port 9000" before render loop
- [ ] `curl http://localhost:9000/` returns 200 with landing page HTML
- [ ] `curl http://localhost:9000/catalog` returns 200 with app list HTML
- [ ] Changing a field and checking `GET /api/pending-changes` shows count = 1
- [ ] Reverting a field back to its original value shows count = 0
- [ ] `/review` page shows the pending change in the diff
- [ ] `POST /api/save-changes` creates a new `configs/generation_N+1.yaml`
- [ ] `POST /api/discard-changes` clears `_pending_changes` and banner disappears
- [ ] `POST /api/save-changes` with invalid values returns `{"status": "error", ...}` and does NOT restart
- [ ] Recovery mode: manually create a `.broken.yaml` as newest generation → all routes redirect to `/recovery-mode`
- [ ] Recovery mode: apply/rollback/generate_new all function identically to before
- [ ] Sidebar category filter works (click "Productivity" → only Pomodoro + Notion visible)
- [ ] Toggle enable on an app stages `Apps.<name>.enabled` with old=true, new=false
- [ ] Closing and reopening the browser clears pending changes (in-memory, not persisted)
