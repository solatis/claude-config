---
name: arxiv-to-md
description: Convert arXiv papers to LLM-consumable markdown. Invoke when user provides an arXiv ID or URL, or when syncing academic papers from a PDF folder to a markdown destination.
---

# arXiv to Markdown

Convert arXiv papers (TeX source) to clean markdown for LLM consumption.

## Invocation

<invoke working-dir="{{SKILLS_DIR}}" cmd="python3 -m skills.arxiv_to_md.main --step 1" />

Do NOT explore or analyze first. Run the script and follow its output.
