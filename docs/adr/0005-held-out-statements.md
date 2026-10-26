# 5. The parser is measured on statements written blind, and their first run is never rewritten

Status: accepted

The simulator and parser share an author, so dev accuracy flatters. Held-out sets are written by an agent that
reads only `heldout/WRITING_STATEMENTS.md`. `pmd heldout <set>` writes `first_run.json` once; later runs write
`latest.json`; CI fails if a first run changes. A set whose failures were studied to change the parser is
marked `regression` and no longer quoted as a measure; the next one is written blind again. v1: 2 of 25 on the
first run, studied. v2: 14 of 25, parser frozen.
