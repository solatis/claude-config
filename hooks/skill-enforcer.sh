#!/bin/bash
# PreToolUse hook: Enforce skill-first approach for common operations
# Blocks commands that have skill equivalents and guides to use the skill instead

INPUT=$(cat)

COMMAND=$(echo "$INPUT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('tool_input', {}).get('command', ''))" 2>/dev/null)

# Define patterns and their skill mappings
# Format: pattern|skill_name|description
SKILL_MAPPINGS=(
    "gh pr create|create-pr|PR creation"
    "gh pr new|create-pr|PR creation"
)

for mapping in "${SKILL_MAPPINGS[@]}"; do
    IFS='|' read -r pattern skill_name description <<< "$mapping"

    if echo "$COMMAND" | grep -qE "$pattern"; then
        cat << JSONEOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "SKILL AVAILABLE: Consider using Skill(skill='${skill_name}') for ${description}. Skills ensure consistent workflow and formatting. Proceeding with direct command..."
  }
}
JSONEOF
        exit 0
    fi
done

# Allow all other commands
exit 0
