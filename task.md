Bug ticket #4127

parse_duration('90m') raises ValueError, but 90 minutes is a valid
duration — it should return 5400 seconds. Customers hit this constantly
when typing durations by hand.

Fix app/parser.py. The parser tests are in tests/test_parser.py.
