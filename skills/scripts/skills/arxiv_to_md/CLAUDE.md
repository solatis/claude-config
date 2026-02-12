# arxiv_to_md/

arXiv paper to markdown conversion workflows.

## Index

| File           | Contents (WHAT)                                             | Read When (WHEN)                                   |
| -------------- | ----------------------------------------------------------- | -------------------------------------------------- |
| `main.py`      | Orchestrator workflow, mode detection, sub-agent dispatch  | Converting papers, debugging orchestration flow    |
| `sub_agent.py` | Sub-agent workflow, 6-step conversion pipeline             | Debugging conversion steps, modifying pipeline     |
| `tex_utils.py` | TeX preprocessing, input expansion, encoding normalization  | Debugging preprocessing, modifying TeX handling    |
| `__init__.py`  | Package marker                                              | Never (empty module)                               |
| `README.md`    | Path resolution architecture, template system design       | Understanding sys.path injection, f-string traps   |
