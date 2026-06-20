"""Temporal contamination detection criteria.

WHY: Detection questions were duplicated in two places:
- plan_docs_qr.py:158-164 (XML format for QR agent)
- plan_docs.py:203-209 (prose format for TW agent)

Both need the same criteria but different formats. This module
defines the criteria once and provides formatters for each use case.

It also provides a DETERMINISTIC scanner (scan_text) used as a post-fix
gate (F2 in PLANNER-HARNESS-FIX-ROADMAP.md): the temporal class was a
whack-a-mole during QR fix loops because the fixer patched only the named
findings, leaving sibling instances for the next verify pass to re-surface.
A deterministic scan the fixer must pass with ZERO hits before reporting
PASS closes the whole class in one iteration.
"""

import re
from dataclasses import dataclass

@dataclass
class DetectionQuestion:
    id: str
    text: str
    signals: list[str]
    action: str  # DELETE, TRANSFORM, EXTRACT

# WHY these 5 specific detection questions:
# These represent the exhaustive taxonomy of temporal contamination patterns.
# Each question targets a distinct failure mode:
#
# 1. CHANGE_RELATIVE: "Added X" -> Assumes reader knows previous state
#    Comments survive across refactors; "added" becomes meaningless
#
# 2. BASELINE_REFERENCE: "Instead of X" -> Compares to deleted code
#    Baseline code is gone; comparison is permanently broken
#
# 3. LOCATION_DIRECTIVE: "After line 50" -> Encodes diff application instructions
#    Line numbers change; developer can't follow stale directions
#
# 4. PLANNING_ARTIFACT: "TODO: implement" -> Future intent leaks into present code
#    Code is either done or not; "will implement" contradicts existence
#
# 5. INTENT_LEAKAGE: "Chose X deliberately" -> Documents decision process, not result
#    Future reader needs justification, not author's mental state
#
# WHY actions are prescriptive:
# - DELETE: Information is redundant with code/diff
# - TRANSFORM: Information is valuable but phrasing is temporal
# - EXTRACT: Temporal wrapper around timeless technical fact
TEMPORAL_DETECTION_QUESTIONS = [
    DetectionQuestion(
        id="CHANGE_RELATIVE",
        text="Does it describe an action taken?",
        signals=["Added", "Replaced", "Now uses"],
        action="TRANSFORM to timeless present"
    ),
    DetectionQuestion(
        id="BASELINE_REFERENCE",
        text="Does it compare to removed code?",
        signals=["Instead of", "Previously", "Replaces"],
        action="TRANSFORM to timeless present"
    ),
    DetectionQuestion(
        id="LOCATION_DIRECTIVE",
        text="Does it describe WHERE to put code?",
        signals=["After", "Before", "Insert"],
        action="DELETE (diff encodes location)"
    ),
    DetectionQuestion(
        id="PLANNING_ARTIFACT",
        text="Does it describe future intent?",
        signals=["TODO", "Will", "Planned"],
        action="DELETE or REFRAME as current constraint"
    ),
    DetectionQuestion(
        id="INTENT_LEAKAGE",
        text="Does it describe author's choice?",
        signals=["intentionally", "deliberately", "chose"],
        action="EXTRACT technical justification"
    ),
]

def format_as_xml() -> str:
    """Format detection questions as XML for QR agents."""
    lines = ['<detection_questions category="temporal-contamination">']
    for q in TEMPORAL_DETECTION_QUESTIONS:
        signals = ", ".join(f"'{s}'" for s in q.signals)
        lines.append(f'  <question id="{q.id}" text="{q.text} Signal: {signals}" />')
    lines.append('</detection_questions>')
    return "\n".join(lines)

def format_as_prose() -> str:
    """Format detection questions as prose for TW agents."""
    lines = ["For EACH comment, evaluate against 5 detection questions:"]
    for i, q in enumerate(TEMPORAL_DETECTION_QUESTIONS, 1):
        lines.append(f"  {i}. {q.text} ({q.id.lower().replace('_', ' ')})")
    return "\n".join(lines)

def format_actions() -> str:
    """Format recommended actions for each detection type."""
    lines = []
    for q in TEMPORAL_DETECTION_QUESTIONS:
        lines.append(f"  - {q.id}: {q.action}")
    return "\n".join(lines)


# =============================================================================
# Deterministic scanner (post-fix gate)
# =============================================================================


@dataclass
class TemporalHit:
    """One detected temporal-contamination signal."""
    field: str       # where it was found (e.g. "CC-M-001-001.doc_diff")
    line_no: int     # 1-based line within that field's text
    question_id: str  # which DetectionQuestion fired
    signal: str      # the literal signal phrase matched
    text: str        # the offending line (stripped)


# Precompiled word-boundary patterns per signal. Word boundaries keep the scan
# from firing inside larger tokens (e.g. "Will" must not match "Willing");
# case-insensitive because comment prose varies.
_SIGNAL_PATTERNS = [
    (q.id, signal, re.compile(rf"\b{re.escape(signal)}\b", re.IGNORECASE))
    for q in TEMPORAL_DETECTION_QUESTIONS
    for signal in q.signals
]


def scan_text(text: str, field: str = "") -> list[TemporalHit]:
    """Scan free text for temporal-contamination signals.

    Deterministic counterpart to the LLM detection questions: returns one hit
    per (line, signal) match. Used as the F2 post-fix gate -- the fixer must
    drive this to zero hits over the documentation/comment surface before
    reporting PASS, which forces a whole-class sweep instead of patching only
    the QR-named instances.
    """
    hits: list[TemporalHit] = []
    if not text:
        return hits
    for line_no, line in enumerate(text.splitlines(), start=1):
        for question_id, signal, pattern in _SIGNAL_PATTERNS:
            if pattern.search(line):
                hits.append(TemporalHit(
                    field=field,
                    line_no=line_no,
                    question_id=question_id,
                    signal=signal,
                    text=line.strip(),
                ))
    return hits


def scan_plan_docs(plan: dict) -> list[TemporalHit]:
    """Scan the documentation/comment surface of a plan.json dict.

    Scopes the scan to fields that hold prose destined to become code
    comments or docs -- where timeless present tense is required. These live
    on each milestone:
      - code_changes[].doc_diff, .comments, and the ADDED ("+") lines of
        .diff (context/removed lines are not ours to own)
      - documentation.module_comment
      - documentation.function_blocks[].comment
      - documentation.inline_comments[].comment
      - documentation.docstrings[].docstring

    Deliberately EXCLUDES decision/rejection reasoning (planning_context),
    where words like "chose"/"deliberately" are legitimate and expected --
    scanning those would false-fire and defeat the gate.
    """
    hits: list[TemporalHit] = []
    for ms in plan.get("milestones", []) or []:
        mid = ms.get("id", "?")
        for change in ms.get("code_changes", []) or []:
            cid = change.get("id", mid)
            hits += scan_text(change.get("doc_diff", ""), f"{cid}.doc_diff")
            hits += scan_text(change.get("comments", ""), f"{cid}.comments")
            # Only added lines of a code diff carry our new comments.
            added = "\n".join(
                ln[1:] for ln in (change.get("diff", "") or "").splitlines()
                if ln.startswith("+") and not ln.startswith("+++")
            )
            hits += scan_text(added, f"{cid}.diff(+)")
        doc = ms.get("documentation") or {}
        hits += scan_text(doc.get("module_comment") or "", f"{mid}.module_comment")
        for fb in doc.get("function_blocks", []) or []:
            hits += scan_text(fb.get("comment", ""), f"{mid}.function_blocks")
        for ic in doc.get("inline_comments", []) or []:
            hits += scan_text(ic.get("comment", ""), f"{mid}.inline_comments")
        for ds in doc.get("docstrings", []) or []:
            hits += scan_text(ds.get("docstring", ""), f"{mid}.docstrings")
    return hits


def format_scan_report(hits: list[TemporalHit]) -> str:
    """Render scan hits as an XML-ish report for agent consumption."""
    if not hits:
        return "<temporal_scan>PASS: zero temporal-contamination hits.</temporal_scan>"
    lines = [f'<temporal_scan hits="{len(hits)}">']
    for h in hits:
        lines.append(
            f'  <hit field="{h.field}" line="{h.line_no}" '
            f'class="{h.question_id}" signal="{h.signal}">{h.text}</hit>'
        )
    lines.append("</temporal_scan>")
    return "\n".join(lines)
