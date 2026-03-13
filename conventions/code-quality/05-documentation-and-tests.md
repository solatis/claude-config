<!-- applicable_phases: diff_review, codebase_review, refactor_code -->

# Documentation & Tests

Evaluate whether code is properly documented and tested.

**The core question**: Is this documented and tested? Documentation that contradicts code is worse than no documentation. Tests that don't communicate behavior fail as documentation. Schema drift causes runtime errors. Generated code without provenance documentation misleads maintainers.

**What to look for**:

- Documentation contradicting actual code
- Tests with uninformative names
- Missing provenance for generated/vendored code in project index file
- Schema-code mismatches (fields in code missing from schema, or vice versa)

**The threshold**: Flag only demonstrable incorrectness, not incompleteness. Stale docs cause hallucinations; missing docs just mean less context. Flag tests that give no behavioral information. Flag generated/vendored code without project index file documentation. Flag schema drift only when provable mismatch exists.

<design-mode>
Not applicable -- this group requires actual code to evaluate.
</design-mode>

<code-mode>
When evaluating actual code (Diff Review, Codebase Review, Refactor):

- Does documentation contradict the code?
- Do test names communicate behavior?
- Is generated/vendored code documented in project index file?
- Do schema definitions match code usage?

Evidence format: Quote code/docs with file:line showing the issue.
</code-mode>

---

## 1. Documentation Staleness

<principle>
Documentation that contradicts code is worse than no documentation. Stale docs mislead readers and cause bugs.
</principle>

Detect: Does the documentation contradict the code? Are there claims in docs that the code structurally violates?

<grep-hints>
Pattern indicators (starting points, not definitive):
Docstrings with parameter names, @param, @return, TODO, FIXME
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Active contradictions

- Parameter name in docstring not in function signature
- Docstring type conflicts with type annotation (when annotation exists)
- Any documentation making claims the code structurally contradicts

[medium] Stale claims

- Docstring describes return value that code never returns
- Comment contains strong claim ("always", "never", "must") AND code structurally contradicts it

[low] Orphaned references

- TODO/FIXME referencing completed or removed work
  </violations>

<exceptions>
Incomplete documentation. Missing docs. Outdated style in docs.
</exceptions>

<threshold>
Flag only when documentation is demonstrably incorrect, not merely incomplete. Incorrect documentation causes hallucinations.
</threshold>

## 2. Test Quality as Documentation

<principle>
Tests document expected behavior. When test names don't communicate what behavior they verify, they fail as documentation.
</principle>

Detect: Do tests communicate expected behavior? Can I understand what's being tested from the test name alone?

<grep-hints>
Pattern indicators (starting points, not definitive):
`test_works`, `test_ok`, `test_success`, `test_case_`, `test_1`, `assert True`
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Uninformative tests

- Test name matches low-information pattern (e.g., test_works, test_ok, test_success, test_case_1)
- Test contains 0 assertions
- Any test where the name gives no behavioral information

[medium] Weak naming

- Test name shorter than 3 tokens (excluding test\_ prefix)
- Test name describes implementation, not behavior

[low] Test smells

- Test only asserts True, None, or trivial values
- Multiple similar test functions with minor input variations (use parameterized/table-driven)
  </violations>

<exceptions>
Tests referencing ticket numbers (e.g., TEST-1234, JIRA-567) for traceability. Smoke tests named test_works.
</exceptions>

<threshold>
Flag when test name gives no behavioral information AND is not a ticket/regression reference.
</threshold>

## 3. Generated and Vendored Code Awareness

<principle>
Non-maintainable code (generated, vendored) must be clearly marked. Without provenance documentation, maintainers may try to modify code that should be regenerated.
</principle>

Detect: Is non-maintainable code clearly marked in project index file? Can a maintainer tell which code is generated or vendored?

<grep-hints>
Pattern indicators (starting points, not definitive):
`_generated`, `_pb`, `.pb.go`, `vendor/`, `third_party/`, `node_modules/`
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Missing provenance

- Generated files missing regeneration command in project index file
- Vendored directories missing upstream source in project index file
- Any generated/vendored code without documentation of origin

[medium] Unclear ownership

- External libraries copied into repo without provenance documentation
  </violations>

<exceptions>
Generated files with regeneration command documented. Vendored code with clear upstream reference.
</exceptions>

<threshold>
Flag when file/directory matches generation patterns (e.g., *.pb.go, *_generated.*, vendor/, third_party/) AND project index file lacks corresponding entry explaining provenance.
</threshold>

## 4. Schema-Code Coherence

<principle>
Schema and code must stay synchronized. Fields referenced in code but absent from schema (or vice versa) indicate drift that causes runtime errors.
</principle>

Detect: Does code reference schema fields that don't exist? Are there schema fields unused in any code path?

<grep-hints>
Pattern indicators (starting points, not definitive):
Schema file extensions (.proto, .graphql, .json schema), field access patterns
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Schema drift

- Code references field not in schema definition
- Schema field unused in any code path (dead field)
- Any mismatch between schema definition and code usage

[medium] Type drift

- Type mismatch between schema and code representation
  </violations>

<exceptions>
Intentional divergence documented with :SCHEMA: marker. Fields used only in specific deployment configs.
</exceptions>

<threshold>
Flag when field name in code has 0 matches in corresponding schema file, or schema field has 0 references in codebase.
</threshold>

Intent marker: Use `:SCHEMA:` to suppress for intentional divergence (e.g., `:SCHEMA: field 'legacy_id' unused; migration pending`).
