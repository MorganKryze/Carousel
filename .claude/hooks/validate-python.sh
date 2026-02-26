#!/bin/bash
# PostToolUse hook: validate Python syntax after Edit/Write on .py files
# Receives JSON on stdin with tool_input.file_path

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Only check Python files
if [[ "$FILE_PATH" != *.py ]]; then
  exit 0
fi

# Only check if file exists (Write might create new files)
if [[ ! -f "$FILE_PATH" ]]; then
  exit 0
fi

# Compile check — catches syntax errors
OUTPUT=$(python3 -c "import py_compile; py_compile.compile('$FILE_PATH', doraise=True)" 2>&1)
if [[ $? -ne 0 ]]; then
  echo "Syntax error in $FILE_PATH:" >&2
  echo "$OUTPUT" >&2
  exit 1
fi

exit 0
