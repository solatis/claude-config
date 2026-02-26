# arxiv-to-md/

Convert arXiv papers to LLM-consumable markdown. IMMEDIATELY invoke the script
when user provides an arXiv ID or URL. Do NOT explore first.

## Files

| File        | What                              | When to read                 |
| ----------- | --------------------------------- | ---------------------------- |
| `SKILL.tpl.md`  | Skill invocation                  | Using this skill             |
| `README.md` | Architecture, invisible knowledge | Understanding design choices |

Python code in `scripts/skills/arxiv_to_md/`:

| File           | What                              |
| -------------- | --------------------------------- |
| `main.py`      | Orchestrator (discover, dispatch) |
| `sub_agent.py` | Worker (single paper conversion)  |
| `tex_utils.py` | TeX preprocessing utilities       |

## Prerequisites

- pandoc binary installed
