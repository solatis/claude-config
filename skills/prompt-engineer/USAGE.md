# Prompt Optimizer Skill - Usage Guide

## Overview

This skill optimizes Claude Code agent system prompts using proven prompt engineering patterns from production systems. It enforces rigorous pattern attribution to ensure every change is justified and auditable.

## Structure

```
prompt-optimizer-skill/
├── SKILL.md                           # Main skill instructions
└── references/
    └── prompt-engineering.md          # Complete pattern catalog (verbatim from your upload)
```

## How It Works

The skill implements a two-phase optimization process:

### Phase 1: Section-by-Section Analysis
1. Decomposes your prompt into logical sections
2. Analyzes each section independently 
3. Applies relevant patterns with explicit attribution
4. Presents findings per section

### Phase 2: Full-Pass Integration
1. Assembles the complete optimized prompt
2. Reviews for global coherence
3. Eliminates redundancies
4. Ensures consistency across sections

## Key Features

### Mandatory Pattern Attribution

**Every single change** requires:
- Pattern name from prompt-engineering.md
- Rationale for why it applies
- Expected behavioral impact
- Before/after comparison

This forces thoughtful application and creates an audit trail.

### Conflict Resolution

When multiple patterns could apply, the skill:
1. Identifies the conflict
2. Shows examples of each option
3. Explains trade-offs
4. Provides a recommendation
5. **Asks you which approach to use**

### Quality Assurance

Built-in checklist ensures:
- No contradictory instructions
- Proper emphasis hierarchy
- Anti-patterns explicitly addressed
- Safety-critical operations have verbose instructions
- Output formats are unambiguous
- Edge cases have default behaviors

## Usage Example

You would say:
```
Here's my agent prompt for a database query assistant. Please optimize it using the prompt-optimizer skill:

[your prompt here]
```

The skill will:
1. Read the prompt engineering guide
2. Break your prompt into sections
3. Analyze each section with pattern attribution
4. Show you conflicts and get your input
5. Assemble the optimized version
6. Do a final coherence pass
7. Present the complete result with summary

## Important Notes

### Pattern Attribution is Critical

The skill will NOT make changes without attribution. This is intentional. It forces:
- Thoughtful application of patterns
- Accountability for each change
- Learning what patterns do
- Auditability for future reference

### Hybrid Approach Implemented

As you requested, attribution uses a hybrid approach:
- **Major changes**: Individual attribution with full rationale
- **Minor changes**: Grouped by section with shared rationale
- **Global changes**: Separate attribution in Phase 2

### The Guide is Embedded Verbatim

The `prompt-engineering.md` file in `references/` is exactly as you provided it - no alterations. The skill reads this during execution to ensure it applies the correct patterns.

## Customization

You can modify `SKILL.md` to:
- Adjust the section decomposition logic
- Change the attribution format
- Add domain-specific patterns
- Modify the conflict resolution process

But **do not modify** `references/prompt-engineering.md` - it should remain the canonical pattern reference.

## Packaging the Skill

When ready to distribute, you would normally run:
```bash
python3 /mnt/skills/scripts/package_skill.py /home/claude/prompt-optimizer-skill
```

This validates and creates a `.skill` file that can be imported by others.

## Next Steps

1. Test the skill on some of your actual prompts
2. Refine based on what works/doesn't work
3. Add any domain-specific patterns you discover
4. Package when satisfied
