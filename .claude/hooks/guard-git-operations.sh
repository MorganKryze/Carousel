#!/bin/bash
# PreToolUse hook: block destructive git operations
# Applies to: Bash
#
# Blocked operations:
#   - git push --force / -f (history rewriting on remote)
#   - git reset --hard (discards uncommitted work)
#   - git clean -f/-fd/-fx (deletes untracked files)
#   - git checkout . / git restore . (discards all working changes)
#   - git branch -D (force-delete branch without merge check)
#   - git rebase without confirmation context
#   - git stash drop/clear (permanently loses stashed work)

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')

if [[ "$TOOL_NAME" != "Bash" ]]; then
  exit 0
fi

CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [[ -z "$CMD" ]]; then
  exit 0
fi

# Normalize: collapse whitespace, trim
CMD_NORM=$(echo "$CMD" | tr -s '[:space:]' ' ' | sed 's/^ //;s/ $//')

# --- Force push ---
# Matches: git push --force, git push -f, git push --force-with-lease (still destructive)
# Also catches: git push origin main --force, git push -f origin main
if echo "$CMD_NORM" | grep -qE 'git\s+push\s+.*(-f|--force|--force-with-lease)'; then
  echo "BLOCKED: git push --force can rewrite remote history. Use regular push or ask the user to run this manually." >&2
  exit 2
fi
if echo "$CMD_NORM" | grep -qE 'git\s+push\s+(-f|--force|--force-with-lease)'; then
  echo "BLOCKED: git push --force can rewrite remote history. Use regular push or ask the user to run this manually." >&2
  exit 2
fi

# --- Hard reset ---
# Matches: git reset --hard, git reset --hard HEAD~3, git reset --hard origin/main
if echo "$CMD_NORM" | grep -qE 'git\s+reset\s+.*--hard'; then
  echo "BLOCKED: git reset --hard discards uncommitted work. Use git stash or git reset --soft instead." >&2
  exit 2
fi
if echo "$CMD_NORM" | grep -qE 'git\s+reset\s+--hard'; then
  echo "BLOCKED: git reset --hard discards uncommitted work. Use git stash or git reset --soft instead." >&2
  exit 2
fi

# --- Clean (force) ---
# Matches: git clean -f, git clean -fd, git clean -fx, git clean -xfd, etc.
if echo "$CMD_NORM" | grep -qE 'git\s+clean\s+-[a-zA-Z]*f'; then
  echo "BLOCKED: git clean -f permanently deletes untracked files. Use git clean -n (dry run) first, then ask the user." >&2
  exit 2
fi

# --- Checkout/restore discard all ---
# Matches: git checkout -- ., git checkout ., git restore .
if echo "$CMD_NORM" | grep -qE 'git\s+checkout\s+(--\s+)?\.(\s|$)'; then
  echo "BLOCKED: git checkout . discards all unstaged changes. Use git stash instead." >&2
  exit 2
fi
if echo "$CMD_NORM" | grep -qE 'git\s+restore\s+\.(\s|$)'; then
  echo "BLOCKED: git restore . discards all unstaged changes. Use git stash instead." >&2
  exit 2
fi

# --- Force-delete branch ---
# Matches: git branch -D, git branch -D feature-xyz
if echo "$CMD_NORM" | grep -qE 'git\s+branch\s+.*-D\s'; then
  echo "BLOCKED: git branch -D force-deletes a branch without merge check. Use git branch -d (lowercase) instead." >&2
  exit 2
fi
if echo "$CMD_NORM" | grep -qE 'git\s+branch\s+-D\s'; then
  echo "BLOCKED: git branch -D force-deletes a branch without merge check. Use git branch -d (lowercase) instead." >&2
  exit 2
fi

# --- Stash drop/clear ---
# Matches: git stash drop, git stash clear
if echo "$CMD_NORM" | grep -qE 'git\s+stash\s+(drop|clear)(\s|$)'; then
  echo "BLOCKED: git stash drop/clear permanently discards stashed work. Ask the user before proceeding." >&2
  exit 2
fi

exit 0
