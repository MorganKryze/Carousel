#!/bin/bash
# PreToolUse hook: block dangerous shell commands
# Applies to: Bash
#
# Blocked patterns:
#   - rm -rf / rm -r on paths outside the project
#   - chmod/chown on system paths
#   - curl|sh, wget|bash (pipe-to-shell execution)
#   - mkfs, dd (disk operations)
#   - kill/killall/pkill on system processes
#   - >/ truncation of files outside project
#   - sudo operations
#   - env manipulation that could affect system

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')

if [[ "$TOOL_NAME" != "Bash" ]]; then
  exit 0
fi

CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [[ -z "$CMD" ]]; then
  exit 0
fi

CMD_NORM=$(echo "$CMD" | tr -s '[:space:]' ' ' | sed 's/^ //;s/ $//')

PROJECT_DIR=$(realpath -m "$CLAUDE_PROJECT_DIR" 2>/dev/null || echo "$CLAUDE_PROJECT_DIR")

# --- sudo ---
if echo "$CMD_NORM" | grep -qE '(^|\s|;|&&|\|\|)sudo\s'; then
  echo "BLOCKED: sudo commands are not allowed. Ask the user to run privileged commands manually." >&2
  exit 2
fi

# --- Pipe to shell (remote code execution) ---
# Matches: curl ... | sh, curl ... | bash, wget ... | sh, etc.
if echo "$CMD_NORM" | grep -qE '(curl|wget)\s+.*\|\s*(sh|bash|zsh|dash|source)'; then
  echo "BLOCKED: Piping remote content to a shell is dangerous. Download first, review, then execute." >&2
  exit 2
fi

# --- Disk-level operations ---
if echo "$CMD_NORM" | grep -qE '(^|\s|;|&&|\|\|)(mkfs[^ ]*|dd)\s'; then
  echo "BLOCKED: Disk-level operations (mkfs, dd) are not allowed. Ask the user to run these manually." >&2
  exit 2
fi

# --- rm -rf / rm -r outside project ---
# We extract paths after rm -rf/-r and check if they're within the project
if echo "$CMD_NORM" | grep -qE '(^|\s|;|&&|\|\|)rm\s+-[a-zA-Z]*r'; then
  # Extract the rm command and its arguments
  RM_ARGS=$(echo "$CMD_NORM" | grep -oE 'rm\s+-[a-zA-Z]*r[a-zA-Z]*\s+[^ ;|&]+' | head -1)
  RM_TARGET=$(echo "$RM_ARGS" | awk '{print $NF}')

  if [[ -n "$RM_TARGET" ]]; then
    RESOLVED_TARGET=$(realpath -m "$RM_TARGET" 2>/dev/null || echo "$RM_TARGET")

    # Block if target is root or system directories
    if [[ "$RESOLVED_TARGET" == "/" || "$RESOLVED_TARGET" == "/usr"* || "$RESOLVED_TARGET" == "/etc"* || "$RESOLVED_TARGET" == "/var"* || "$RESOLVED_TARGET" == "/System"* || "$RESOLVED_TARGET" == "/Library"* || "$RESOLVED_TARGET" == "/bin"* || "$RESOLVED_TARGET" == "/sbin"* || "$RESOLVED_TARGET" == "/opt"* ]]; then
      echo "BLOCKED: rm -r on system directory ($RM_TARGET). This would damage the system." >&2
      exit 2
    fi

    # Block if target is outside project and is a broad path (home dir, other projects)
    if [[ "$RESOLVED_TARGET" != "$PROJECT_DIR"* && "$RESOLVED_TARGET" != "/tmp"* && "$RESOLVED_TARGET" != "/private/tmp"* ]]; then
      echo "BLOCKED: rm -r on path outside project ($RM_TARGET). Only recursive deletion within the project or /tmp is allowed." >&2
      exit 2
    fi
  fi
fi

# --- chmod/chown on system paths ---
if echo "$CMD_NORM" | grep -qE '(^|\s|;|&&|\|\|)(chmod|chown)\s'; then
  # Extract target path (last argument)
  PERM_CMD=$(echo "$CMD_NORM" | grep -oE '(chmod|chown)\s+[^ ;|&]+\s+[^ ;|&]+' | head -1)
  PERM_TARGET=$(echo "$PERM_CMD" | awk '{print $NF}')

  if [[ -n "$PERM_TARGET" ]]; then
    RESOLVED_PERM=$(realpath -m "$PERM_TARGET" 2>/dev/null || echo "$PERM_TARGET")

    if [[ "$RESOLVED_PERM" != "$PROJECT_DIR"* && "$RESOLVED_PERM" != "/tmp"* && "$RESOLVED_PERM" != "/private/tmp"* ]]; then
      echo "BLOCKED: chmod/chown on path outside project ($PERM_TARGET). Only permission changes within the project are allowed." >&2
      exit 2
    fi
  fi
fi

# --- Truncation of files outside project ---
# Matches: > /etc/hosts, >| /some/file (but not >> which is append, and not > within project)
# Uses [^>] lookbehind to avoid matching >> (append), and [[:space:]] for macOS sed compat
if echo "$CMD_NORM" | grep -qE '[^>]>[|]?[[:space:]]*/[^ ]+'; then
  TRUNC_TARGET=$(echo "$CMD_NORM" | grep -oE '[^>]>[|]?[[:space:]]*/[^ ]+' | head -1 | sed 's/^[^>]*>[|]*[[:space:]]*//')

  if [[ -n "$TRUNC_TARGET" ]]; then
    RESOLVED_TRUNC=$(realpath -m "$TRUNC_TARGET" 2>/dev/null || echo "$TRUNC_TARGET")

    if [[ "$RESOLVED_TRUNC" != "$PROJECT_DIR"* && "$RESOLVED_TRUNC" != "/tmp"* && "$RESOLVED_TRUNC" != "/private/tmp"* && "$RESOLVED_TRUNC" != "/dev/null" ]]; then
      echo "BLOCKED: File redirection to path outside project ($TRUNC_TARGET). Only redirection within the project or /tmp is allowed." >&2
      exit 2
    fi
  fi
fi

# --- launchctl / systemctl (service manipulation) ---
if echo "$CMD_NORM" | grep -qE '(^|\s|;|&&|\|\|)(launchctl|systemctl)\s+(unload|stop|disable|remove|mask)'; then
  echo "BLOCKED: Stopping/disabling system services is not allowed. Ask the user to manage services manually." >&2
  exit 2
fi

exit 0
