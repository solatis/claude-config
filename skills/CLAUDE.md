# skills/

Script-based agent workflows with shared orchestration framework.

## MANDATORY: Read Before Modifying

**STOP. Before editing ANY Python file in `skills/scripts/`, you MUST read `README.md`.**

The README defines:

- File section ordering (SHARED PROMPTS -> CONFIGURATION -> MESSAGE TEMPLATES -> MESSAGE BUILDERS -> STEP DEFINITIONS -> OUTPUT FORMATTING -> ENTRY POINT)
- Step-delimited prompt organization within MESSAGE TEMPLATES
- Naming conventions for prompt constants (`[PHASE]_[TYPE]`)
- Patterns for dispatch prompts (static templates vs builder functions)
- Anti-patterns to avoid (action factories, forward references)

Failure to follow these patterns creates technical debt and inconsistency across skills. The patterns exist because they solve real problems with prompt readability and maintenance.

**Read `README.md` now if you haven't already.**

## Files

| File        | What                                                      | When to read                    |
| ----------- | --------------------------------------------------------- | ------------------------------- |
| `README.md` | File organization, prompt patterns, naming, anti-patterns | BEFORE modifying any skill code |

## Subdirectories

| Directory             | What                                      | When to read                             |
| --------------------- | ----------------------------------------- | ---------------------------------------- |
| `scripts/`            | Python package root for all skill code    | Executing skills, debugging behavior     |
| `planner/`            | Planning and execution workflows          | Creating implementation plans            |
| `refactor/`           | Refactoring analysis across dimensions    | Technical debt review, code quality      |
| `problem-analysis/`   | Structured problem decomposition          | Understanding complex issues             |
| `decision-critic/`    | Decision stress-testing and critique      | Validating architectural choices         |
| `deepthink/`          | Structured reasoning for open questions   | Analytical questions without frameworks  |
| `codebase-analysis/`  | Systematic codebase exploration           | Repository architecture review           |
| `prompt-engineer/`    | Prompt optimization and engineering       | Improving agent prompts                  |
| `incoherence/`        | Consistency detection                     | Finding spec/implementation mismatches   |
| `doc-sync/`           | Documentation synchronization             | Syncing docs across repos                |
| `leon-writing-style/` | Style-matched content generation          | Writing content matching user's style    |
| `arxiv-to-md/`        | arXiv paper to markdown conversion        | Converting papers for LLM consumption    |
| `cc-history/`         | Claude Code conversation history analysis | Querying past conversations, token usage |

## Script Invocation

All Python skill scripts are invoked as modules from `scripts/`. When working
from `~/.claude/` directly (development), use the literal path:

<invoke working-dir=".claude/skills/scripts" cmd="python3 -m skills.<skill_name>.<module> --step 1" />

Example:

<invoke working-dir=".claude/skills/scripts" cmd="python3 -m skills.problem_analysis.analyze --step 1" />

Note: SKILL.md files in each skill directory use `{{SKILLS_DIR}}` as a template
variable instead of the literal path. The installer substitutes the correct
path per target tool (e.g., `.claude/skills/scripts` for Claude Code,
`.pi/agent/skills/scripts` for Pi) during installation. This CLAUDE.md is a
development artifact and is never installed.
