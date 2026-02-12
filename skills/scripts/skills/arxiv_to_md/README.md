# arxiv_to_md Architecture

## Path Resolution

**Problem**: The sub-agent workflow includes a bash heredoc that must inject the correct `sys.path` entry to import `skills.arxiv_to_md.tex_utils`. A hardcoded path like `/Users/lmergen/.claude/skills/scripts` only works on the original author's machine.

**Solution**: Compute `SCRIPTS_DIR` at module load time using `Path(__file__).resolve().parent.parent.parent`, which traverses from `skills/arxiv_to_md/sub_agent.py` up to `skills/scripts/`.

**Why `__file__`**: Works universally across installations without configuration. The module's location on disk determines the path dynamically.

**Rejected alternatives**:
- `os.getcwd()`: Sub-agent Bash tool cwd may differ from invoke working-dir, causing fragile runtime failures
- `os.path.expanduser('~/.claude/skills/scripts')`: This repository lives at `Documents/GitHub/claude-config/.claude`, not `~/.claude`

## Template System

**PHASES dict structure**: The `PHASES` dictionary contains strings that are printed verbatim as sub-agent workflow instructions. These strings are NOT executed by `sub_agent.py` itself - they're executed by a Claude sub-agent via the Bash tool.

**F-string trap**: Phase 2's bash heredoc contains `print(f"Preprocessed: {result}")` on line 103. This is literal Python code within the template string meant for the sub-agent to execute. If the PHASES string were an f-string, Python would attempt to evaluate `{result}` at module load time, causing a `NameError`.

**Why string concatenation**: The path injection uses `"sys.path.insert(0, '" + SCRIPTS_DIR + "')"` instead of an f-string to avoid brace collision. Only the single line containing the path uses concatenation; all other template strings remain regular strings.

**Alternative rejected**: `str.format()` would require escaping all literal braces as `{{ }}` throughout the template, making the bash heredoc harder to maintain.

## Invariants

- `PHASES` dict strings are printed verbatim, not executed by sub_agent.py
- The bash heredoc runs in a separate process via Claude Bash tool
- `{result}` on line 103 must remain a literal template placeholder, not evaluated at module load
- `SCRIPTS_DIR` must resolve to an absolute path that works in the sub-agent's execution context
