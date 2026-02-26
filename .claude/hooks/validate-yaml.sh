#!/bin/bash
# PostToolUse hook: validate YAML syntax after Edit/Write on .yaml/.yml files
# Receives JSON on stdin with tool_input.file_path

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Only check YAML files
if [[ "$FILE_PATH" != *.yaml ]] && [[ "$FILE_PATH" != *.yml ]]; then
  exit 0
fi

if [[ ! -f "$FILE_PATH" ]]; then
  exit 0
fi

OUTPUT=$(python3 -c "
import yaml, sys
try:
    with open('$FILE_PATH') as f:
        yaml.safe_load(f)
except yaml.YAMLError as e:
    print(f'YAML error: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1)

if [[ $? -ne 0 ]]; then
  echo "YAML validation failed for $FILE_PATH:" >&2
  echo "$OUTPUT" >&2
  exit 1
fi

exit 0
