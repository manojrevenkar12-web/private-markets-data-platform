-- XIRR against values computed independently: -100 then +110 a year later is 10 %.
select * from (
  select pmd_util.xirr(array[date '2024-01-01', date '2025-01-01'], array[-100, 110]::numeric[]) as r1,
         pmd_util.xirr(array[date '2024-01-01', date '2024-07-01', date '2026-01-01'], array[-1000, -500, 1800]::numeric[]) as r2
) x
where abs(r1 - 0.10) > 0.0005 or abs(r2 - 0.1042) > 0.0005
