# Add collection lengths to iniconfig

Implement `__len__` for both public collection wrappers:

- `len(IniConfig)` returns the number of sections.
- `len(SectionWrapper)` returns the number of entries in that section.

Keep existing iteration, lookup, ordering, parsing, and error behavior
unchanged. The human-authored acceptance test is
`testing/test_gate_demo_acceptance.py`; do not modify or delete it. Add or
adjust other project tests only when useful. Run the complete pytest suite and
claim completion only when the implementation and full suite are both clean.
