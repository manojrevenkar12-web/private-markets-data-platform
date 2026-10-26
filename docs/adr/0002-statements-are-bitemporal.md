# 2. Statements are versions, never overwritten

Status: accepted

Managers restate quarters. Overwriting the old figure would change what a client was told without a record.
Every statement is a version of (fund, period end) with the day it became known and the day a newer one
replaced it. Marts use the current version; `nav_restatements` lists every change with its size; the API
answers "what did we know on day D" from the same table.
