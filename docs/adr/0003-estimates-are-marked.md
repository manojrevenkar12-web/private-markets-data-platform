# 3. A missing quarter is estimated from booked cash and marked as an estimate everywhere

Status: accepted

A statement arrives up to 90 days after quarter end, or is held by its checks. Leaving the quarter empty
breaks every client NAV; using last quarter silently is wrong. The quarter is the last statement's NAV plus
calls minus distributions the bank has booked since, with `nav_source = 'estimated'` and the reason. The flag
travels to feeder and client figures (`nav_has_estimates`), the API and the console, which marks estimates
with their own style. Measured against the truth: median error 2.3 % on the simulated firm.
