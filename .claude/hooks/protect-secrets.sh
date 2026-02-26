#!/bin/bash
# PreToolUse hook: block access to secret/credential files even within the project
# Applies to: Read, Edit, Write, Glob, Grep
#
# Protected patterns:
#   - .env, .env.local, .env.production, .env.* (environment files)
#   - *.pem, *.key, *.p12, *.pfx, *.jks (certificates/keys)
#   - *.secret, *.secrets (secret files)
#   - credentials.json, secrets.yaml, secrets.yml
#   - .netrc, .pgpass, .my.cnf (service credentials)
#   - id_rsa, id_ed25519, id_ecdsa (SSH keys)
#   - *.keystore, *.truststore (Java keystores)
#   - token.json, tokens.json (OAuth tokens)

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')

# Extract target path based on tool
case "$TOOL_NAME" in
  Read|Edit|Write)
    TARGET=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
    ;;
  Glob)
    # For Glob, check the pattern itself for secret file patterns
    PATTERN=$(echo "$INPUT" | jq -r '.tool_input.pattern // empty')
    TARGET=$(echo "$INPUT" | jq -r '.tool_input.path // empty')
    # Check if the glob pattern explicitly targets secret files
    if [[ -n "$PATTERN" ]]; then
      if echo "$PATTERN" | grep -qEi '(\.env|\.pem|\.key|\.p12|\.pfx|\.secret|credentials|\.netrc|\.pgpass|id_rsa|id_ed25519|\.keystore|token\.json)'; then
        echo "BLOCKED: Glob pattern ($PATTERN) targets secret/credential files." >&2
        exit 2
      fi
    fi
    # If no explicit path, nothing more to check
    if [[ -z "$TARGET" ]]; then
      exit 0
    fi
    ;;
  Grep)
    TARGET=$(echo "$INPUT" | jq -r '.tool_input.path // empty')
    if [[ -z "$TARGET" ]]; then
      exit 0
    fi
    ;;
  *)
    exit 0
    ;;
esac

if [[ -z "$TARGET" ]]; then
  exit 0
fi

# Extract just the filename for pattern matching
FILENAME=$(basename "$TARGET")

# --- Environment files ---
if [[ "$FILENAME" == .env || "$FILENAME" == .env.* ]]; then
  echo "BLOCKED: $FILENAME is an environment file that may contain secrets. Access denied." >&2
  exit 2
fi

# --- Certificates and private keys ---
if echo "$FILENAME" | grep -qEi '\.(pem|key|p12|pfx|jks|keystore|truststore)$'; then
  echo "BLOCKED: $FILENAME appears to be a certificate/key file. Access denied." >&2
  exit 2
fi

# --- Secret files ---
if echo "$FILENAME" | grep -qEi '\.(secret|secrets)$'; then
  echo "BLOCKED: $FILENAME appears to be a secrets file. Access denied." >&2
  exit 2
fi

# --- Known credential filenames ---
if echo "$FILENAME" | grep -qEi '^(credentials\.json|secrets\.yaml|secrets\.yml|secrets\.json|service[-_]?account\.json)$'; then
  echo "BLOCKED: $FILENAME is a known credential file. Access denied." >&2
  exit 2
fi

# --- Service credential files ---
if [[ "$FILENAME" == ".netrc" || "$FILENAME" == ".pgpass" || "$FILENAME" == ".my.cnf" ]]; then
  echo "BLOCKED: $FILENAME is a service credential file. Access denied." >&2
  exit 2
fi

# --- SSH private keys ---
if echo "$FILENAME" | grep -qE '^id_(rsa|ed25519|ecdsa|dsa)$'; then
  echo "BLOCKED: $FILENAME is an SSH private key. Access denied." >&2
  exit 2
fi

# --- OAuth/API token files ---
if echo "$FILENAME" | grep -qEi '^tokens?\.json$'; then
  echo "BLOCKED: $FILENAME may contain OAuth/API tokens. Access denied." >&2
  exit 2
fi

exit 0
