#!/bin/bash
# PreToolUse hook: block file access outside the project directory
# Applies to: Read, Edit, Write, Glob, Grep

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')

# Extract the path — different tools use different field names
case "$TOOL_NAME" in
  Read|Edit|Write)
    TARGET=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
    ;;
  Glob|Grep)
    TARGET=$(echo "$INPUT" | jq -r '.tool_input.path // empty')
    ;;
  *)
    exit 0
    ;;
esac

# If no path provided (e.g. Glob/Grep default to cwd), allow it
if [[ -z "$TARGET" ]]; then
  exit 0
fi

# Resolve to absolute path (handles ../ tricks)
RESOLVED=$(realpath -m "$TARGET" 2>/dev/null || echo "$TARGET")
PROJECT_DIR=$(realpath -m "$CLAUDE_PROJECT_DIR" 2>/dev/null || echo "$CLAUDE_PROJECT_DIR")

# Allow if path is within project directory
if [[ "$RESOLVED" == "$PROJECT_DIR"* ]]; then
  exit 0
fi

# Also allow Claude's own plan/memory files (needed for plan mode)
CLAUDE_HOME="$HOME/.claude"
if [[ "$RESOLVED" == "$CLAUDE_HOME"* ]]; then
  exit 0
fi

echo "BLOCKED: $TARGET is outside project directory ($PROJECT_DIR)" >&2
exit 2
