# Refactor

LLM-generated code accumulates technical debt faster than hand-written code. The
LLM does not see duplication across files. It does not notice god functions
growing. It cannot detect that three modules implement the same validation logic
differently.

This skill catches what the LLM misses. It explores multiple smell categories in
parallel, validates findings against evidence, and outputs prioritized work
items.

## Workflow

```
refactor.py                          explore.py (x10 parallel)
===========                          =========================

Step 1: Dispatch -----------------> Step 1: Domain Context
        (launch 10 exploration sub-agents)  Step 2: Principle + Violations
                                    Step 3: Pattern Generation
                                    Step 4: Search
                                    Step 5: Synthesis
                                           |
        <------------------------------<---+
        (collect smell_reports)

Step 2: Triage
        (structure findings with IDs)

Step 3: Cluster
        (group by shared root cause)

Step 4: Contextualize
        (extract user intent, prioritize)

Step 5: Synthesize
        (generate work items)
```

| Phase         | Question                 | Output                     |
| ------------- | ------------------------ | -------------------------- |
| Dispatch      | What smells exist?       | Parallel smell_reports     |
| Triage        | What did we find?        | Structured smells with IDs |
| Cluster       | Which share root causes? | Grouped issues             |
| Contextualize | What does the user want? | Prioritized issues         |
| Synthesize    | What should be done?     | Actionable work items      |

## Design Decisions

### 1. Five-Step Exploration Workflow

The original 2-step explore workflow conflated multiple cognitive tasks in a
single step. LLMs perform better when each cognitive task gets focused attention.

```
Step 1: Domain Context    - Understand the project before analyzing it
Step 2: Principle Extract - Understand the smell before hunting for it
Step 3: Pattern Generate  - Translate abstract hints to project-specific patterns
Step 4: Search            - Execute with generated patterns
Step 5: Synthesis         - Format findings
```

### 2. Domain Context Per-Category (Not Lifted to Parent)

Each exploration sub-agent does its own domain context analysis, rather than refactor.py
doing it once and passing to all agents.

Rationale: Different smell categories need different domain context aspects. A
"naming precision" category cares about naming conventions; a "module structure"
category cares about import patterns. The 30-second overhead per agent is
acceptable for category-specific context.

Rejected alternative: Lift domain context to refactor.py Step 1. Rejected
because it assumes all categories need identical context.

### 3. Violation Patterns Before Grep Patterns (Separate Steps)

Pattern generation is split into two steps: first violation patterns (Step 2),
then grep patterns (Step 3).

Rationale: Analogical prompting works better in phases. The model first
understands WHAT to look for conceptually (violation patterns matching the
principle), then translates to HOW to search operationally (grep-able patterns).

```
Step 2: "What does 'vague naming' look like in a Python/Django project?"
        -> "Service classes with generic names, Blueprint handlers called 'do_thing'"

Step 3: "How do I grep for those?"
        -> "class.*Service:", "def handle_", "Blueprint.*utils"
```

### 4. Grep-Hints as Exemplars Requiring Translation

The markdown files contain generic patterns like `Manager, Handler, Utils` from
language-agnostic examples. Using these literally in a Go codebase would miss
`Store, Controller` patterns.

Solution: Treat grep-hints as abstract exemplars that must be translated to
project-specific equivalents based on domain context.

### 5. Self-Generated Examples in Synthesis

The synthesis step requires the model to generate a project-specific example
work item before producing the full list. This calibrates output specificity to
the actual project rather than assuming a particular language/framework.

### 6. "Illustrative, Not Exhaustive" Framing

LLMs tend to interpret lists as complete. Without explicit framing, the model
searches only for listed patterns and misses analogous violations.

Mechanisms used:

- "Illustrative patterns (not exhaustive -- similar violations exist)"
- "e.g.," prefix on examples
- Open-ended escape hatches: "Any X that causes Y"
- DOMAIN TRANSLATION instruction to translate abstract to project-specific

## Code Quality Categories

Categories are defined in `conventions/code-quality/` and organized by cognitive
mode:

| File                               | Scope                      | Cognitive Mode  |
| ---------------------------------- | -------------------------- | --------------- |
| `01-naming-and-types.md`           | Names, types, interfaces   | Local           |
| `02-structure-and-composition.md`  | Functions, control flow    | Local           |
| `03-patterns-and-idioms.md`        | Language idioms, patterns  | Local           |
| `04-repetition-and-consistency.md` | Duplication, uniformity    | Cross-Reference |
| `05-documentation-and-tests.md`    | Comments, tests, examples  | Local           |
| `06-module-and-dependencies.md`    | Module structure, imports  | Local           |
| `07-cross-file-consistency.md`     | Shared concerns, contracts | Cross-Reference |
| `08-codebase-patterns.md`          | Architecture, system view  | System          |

Each file contains numbered categories (`## N. Title`) with:

- `<principle>`: The core rule
- `<grep-hints>`: Abstract search patterns (exemplars, not exhaustive)
- `<violations>`: Illustrative patterns with severity
- `<exceptions>`: When not to flag
- `<threshold>`: When to flag

The parser extracts categories by line range. Content within categories is
free-form -- the parser passes raw text, the LLM interprets structure.

## Philosophy

Proposals pass validation against four principles:

| Principle      | Test                                              |
| -------------- | ------------------------------------------------- |
| COMPOSABILITY  | Can this piece combine cleanly with others?       |
| PRECISION      | Does the name create a new semantic level?        |
| NO SPECULATION | Have I seen this pattern 3+ times?                |
| SIMPLICITY     | Is this the simplest thing that removes friction? |

Proposals that predict futures or abstract from single instances get killed.

## Usage

```
Use your refactor skill on src/services/
```

With focus area:

```
Use your refactor skill on src/ -- focus on shared abstractions
```

## What It Does NOT Do

- Generate refactored code (recommendations only)
- Run linters or static analysis
- Apply style fixes
- Propose changes beyond what evidence supports
