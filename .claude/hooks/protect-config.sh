#!/bin/bash
# PreToolUse hook: prevent accidental edits to recovery.config.yaml and generation files
# Receives JSON on stdin with tool_input.file_path

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

# Block direct edits to recovery config (should only be edited manually as a last resort)
if [[ "$FILE_PATH" == *"recovery.config.yaml" ]]; then
  echo "Blocked: recovery.config.yaml should not be edited by agents. It is a static fallback config." >&2
  exit 2
fi

# Block direct edits to generation files (managed by Configuration singleton)
if [[ "$FILE_PATH" == *"configs/generation_"* ]]; then
  echo "Blocked: generation files are managed by the Configuration system. Use the Configuration API instead." >&2
  exit 2
fi

exit 0
