---
name: prompt-optimizer
description: Optimize system prompts for Claude Code agents using proven prompt engineering patterns. Use when users request prompt improvement, optimization, or refinement for agent workflows, tool instructions, or system behaviors.
---

# Prompt Optimizer

This skill optimizes system prompts for Claude Code agents by applying proven prompt engineering patterns from production systems.

## When to Use This Skill

Use this skill when:
- User provides a prompt and requests optimization
- User asks for prompt improvement or refinement
- User wants to apply best practices to agent instructions
- User needs help with tool-use prompts or workflow automation

## Process Overview

This skill uses a two-phase optimization approach:

**Phase 1: Section-by-Section Analysis**
- Decompose the prompt into logical sections
- Analyze each section independently
- Apply relevant patterns with explicit attribution
- Present findings per section

**Phase 2: Full-Pass Integration**
- Review the complete optimized prompt holistically
- Ensure cross-section coherence
- Eliminate redundancies
- Verify global consistency

## Required Resources

Before beginning optimization, ALWAYS read:
```
references/prompt-engineering.md
```

This file contains the complete catalog of prompt engineering patterns that MUST be applied during optimization.

## Phase 1: Section-by-Section Optimization

### Step 1: Decompose the Prompt

Break the prompt into logical sections. Common sections include:

- **Role Definition**: Who/what the agent is
- **Core Capabilities**: What the agent can do
- **Tool Instructions**: How to use specific tools
- **Constraints**: What the agent must not do
- **Output Format**: How to structure responses
- **Safety Instructions**: Security and safety guidelines
- **Workflow Automation**: Multi-step procedures
- **Examples**: Demonstrations of correct behavior
- **Error Handling**: How to handle failures

Not all prompts will have all sections. Identify what exists in the provided prompt.

### Step 2: Analyze Each Section

For each section identified:

1. **State the section name and current content**
2. **Identify applicable patterns** from prompt-engineering.md
3. **For EACH proposed change:**
   - Pattern name (e.g., "Progressive Disclosure")
   - Why this pattern applies here
   - Expected behavioral impact
   - Show the specific change (before/after)

**CRITICAL**: Every change must have explicit pattern attribution. Changes without attribution are incomplete.

### Step 3: Present Section Analysis

Present findings in this format:

```markdown
## Section: [Section Name]

### Current Content
[Original text]

### Applied Patterns

#### Change 1
**Pattern**: [Pattern Name from prompt-engineering.md]
**Rationale**: [Why this pattern applies]
**Impact**: [Expected behavioral change]
**Change**:
Before: [original text]
After: [optimized text]

#### Change 2
[Same structure...]
```

### Step 4: Handle Pattern Conflicts

When multiple patterns could apply to the same text, present options:

```markdown
### Pattern Conflict Detected

**Context**: [Section and text in question]

**Option A**: [Pattern Name]
- Application: [How it would be applied]
- Benefits: [What it achieves]
- Trade-offs: [What you might lose]

**Option B**: [Pattern Name]
- Application: [How it would be applied]
- Benefits: [What it achieves]
- Trade-offs: [What you might lose]

**Recommendation**: [Which option and why]
```

Ask the user which approach they prefer before proceeding.

## Phase 2: Full-Pass Integration

After completing section-by-section optimization and receiving user approval:

### Step 1: Assemble the Optimized Prompt

Combine all optimized sections into a complete prompt.

### Step 2: Global Analysis

Review the complete prompt for:

1. **Cross-section coherence**: Do sections work together harmoniously?
2. **Redundancy elimination**: Are any instructions repeated unnecessarily?
3. **Consistency**: Do all sections use consistent terminology and style?
4. **Flow**: Does the prompt follow a logical progression?
5. **Completeness**: Are there gaps between sections?

### Step 3: Apply Global Patterns

Identify and apply patterns that only become apparent at the full-prompt level:

- **Emphasis Hierarchy**: Are the most critical instructions properly emphasized?
- **Progressive Disclosure**: Does complexity increase appropriately?
- **Rule Hierarchies**: Are there conflicting priorities that need ordering?
- **Default Behaviors**: Are failure modes and edge cases handled?

### Step 4: Present Final Optimization

Present the complete optimized prompt with:

```markdown
## Final Optimized Prompt

[Complete optimized prompt]

## Global Changes Applied

### Change 1
**Pattern**: [Pattern Name]
**Rationale**: [Why this global pattern was needed]
**Impact**: [Expected improvement]
**Sections Affected**: [Which sections were modified]

[Additional global changes...]

## Summary

**Total Changes**: [Number]
**Patterns Applied**: [List of unique patterns used]
**Key Improvements**: [3-5 bullet points of major improvements]
```

## Quality Checklist

Before presenting the final optimized prompt, verify:

- [ ] Every change has explicit pattern attribution
- [ ] No section contradicts another section
- [ ] Critical instructions use appropriate emphasis (CAPITAL, NEVER/ALWAYS, etc.)
- [ ] Examples are provided where complexity is high
- [ ] Anti-patterns are explicitly called out where relevant
- [ ] Safety-critical operations have verbose instructions
- [ ] Output format requirements are unambiguous
- [ ] Tool usage hierarchies are clear
- [ ] Default behaviors are specified for edge cases
- [ ] The prompt follows progressive disclosure principles

## Best Practices

### Token Efficiency
- Remove redundant explanations
- Use concise examples over verbose descriptions
- Consolidate related instructions

### Behavioral Clarity
- Use imperative voice ("Use X" not "You should use X")
- State absolutes clearly (NEVER, ALWAYS, MUST)
- Provide specific examples for complex behaviors

### Safety and Reliability
- Longer instructions for dangerous operations
- Explicit anti-patterns for common mistakes
- Clear error handling procedures

### Pattern Application Discipline

**DO**:
- Apply multiple patterns per section when beneficial
- Explain why each pattern is appropriate
- Show concrete before/after examples
- Consider the user's specific use case

**DON'T**:
- Apply patterns mechanically without rationale
- Change text without identifying the pattern used
- Assume patterns are obvious (always attribute)
- Optimize for optimization's sake (preserve working patterns)

## Notes

- This process is systematic but not mechanical. Use judgment about which patterns provide value for the specific prompt.
- When the user's prompt already uses a pattern well, acknowledge it rather than changing it.
- Focus attribution on changes, not on what was already done well.
- If the user requests specific optimizations (e.g., "make it more concise"), prioritize those patterns while maintaining completeness.
