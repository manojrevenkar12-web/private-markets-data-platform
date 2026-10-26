# Held-out set v2: capital account statements

Written from `heldout/WRITING_STATEMENTS.md` alone, by someone who has not seen the parser, its
configuration, its tests, its reports or any other held-out set. 30 statements in `statements/`, one
answer key per statement in `answers/` (same stem, `.json`).

The `.xlsx` and `.pdf` files were made with a small openpyxl/reportlab script kept outside the
repository. Every accepted key was checked by script: each printed figure occurs in the statement
text (pdftotext for PDFs, cell values for xlsx), it equals the key once the stated unit is applied,
and paid-in is between 10 % and 100 % of commitment.

## Counts

| Format | English | German | Total |
|---|---:|---:|---:|
| .txt | 4 | 4 | 8 |
| .md | 5 | 2 | 7 |
| .csv | 4 | 1 | 5 |
| .xlsx | 2 | 3 | 5 |
| .pdf | 4 | 1 | 5 |
| **Total** | **19** | **11** | **30** |

25 to accept, 5 to reject.

## Files

| File | Fund | Period end | Lang | Expect | What makes it hard |
|---|---|---|---|---|---|
| aurora_q2-2026_capital_statement.txt | AUR7 | 2026-06-30 | EN | accept | letter; $ prefix; paid-in = investment + fee contributions; distributions in parentheses |
| aurora_vii_q1_2026_portal.csv | AUR7 | 2026-03-31 | EN | accept | portal CSV with metadata lines; QTD/YTD/ITD columns; 03/31/2026; negative distributions |
| aurora_vii_q3_2026.md | AUR7 | 2026-09-30 | EN | accept | US$; roll-forward first, cumulative table after |
| KES4_Kapitalkonto_2026Q2.xlsx | KES4 | 2026-06-30 | DE | accept | TEUR, numeric cells |
| kestrel_iv_q1_2026.txt | KES4 | 2026-03-31 | EN | accept | € prefix; period "1 Jan 2026 - 31 Mar 2026"; prior and current NAV both shown |
| fjord-sec-iii-2026-03-31.md | FJD3 | 2026-03-31 | EN | accept | space thousands separator; "of which recallable" sub-line |
| fjord_iii_2026-09-30.txt | FJD3 | 2026-09-30 | DE | accept | Mio. EUR with three decimals: "13,652" = 13,652,000 |
| halvard_mid_market_ii_2026-06-30.pdf | HAL2 | 2026-06-30 | EN | accept | letter with table; second date in a note |
| halvard_mm2_q3_2026.txt | HAL2 | 2026-09-30 | DE | accept | quarter figures next to cumulative ones |
| orion_ix_export_20260630.csv | ORI9 | 2026-06-30 | EN | accept | single-row export, own column names |
| orion_ix_q4_2025.md | ORI9 | 2025-12-31 | EN | accept | USD thousands with one decimal |
| lumen_v_2025q4.pdf | LUM5 | 2025-12-31 | EN | accept | USD '000; 12/31/2025; roll-forward |
| lumen_v_kapitalkonto_2026-06-30.txt | LUM5 | 2026-06-30 | DE | accept | USD fund in German; informational EUR conversion of the NAV |
| spree_seed_ii_2025-09-30.csv | SPR2 | 2025-09-30 | DE | accept | semicolon CSV, decimal comma, no thousands separator |
| spree_seed_ii_q1_2026.md | SPR2 | 2026-03-31 | DE | accept | Q1 and since-inception columns |
| novara_growth_iii_h1_2026.txt | NOV3 | 2026-06-30 | EN | accept | EUR m; 30/06/2026; H1 column |
| novara_g3_q3_2026.xlsx | NOV3 | 2026-09-30 | EN | accept | QTD/YTD/ITD roll-forward; commitment only in a text line |
| tidewater_climate_i_31032026.md | TID1 | 2026-03-31 | DE | accept | letter; € after the number; "31. März 2026" |
| tidewater_cti_q3_2026.xlsx | TID1 | 2026-09-30 | EN | accept | real Excel date cell; values in column C, notes in column B |
| crestline_dl_iv_2026-06-30.md | CRE4 | 2026-06-30 | EN | accept | distributions split by type (answer is the total); NAV roll-forward |
| crestline_iv_q4_2025.pdf | CRE4 | 2025-12-31 | EN | accept | EUR thousands |
| bastion_sd_ii_31122025.pdf | BAS2 | 2025-12-31 | DE | accept | German PDF letter; distribution breakdown rows |
| bastion_ii_q2_2026.csv | BAS2 | 2026-06-30 | EN | accept | long format: one statement across many rows (measure x basis) |
| meridian_iii_2026q2.xlsx | MER3 | 2026-06-30 | DE | accept | period and cumulative columns |
| meridian_infra_debt_iii_q3_2026.txt | MER3 | 2026-09-30 | EN | accept | quarterly roll-forward, cumulative block separate |
| aurora_buyout_viii_q2_2026.pdf | — | 2026-06-30 | EN | **reject** | fund not in the table (Fund VIII, not VII) |
| halvard_mm2_monatsbericht_2026-05.txt | HAL2 | 2026-05-31 | DE | **reject** | period end 31.05.2026 is not a quarter end |
| orion_ix_q2_2026_restated.md | ORI9 | 2026-06-30 | EN | **reject** | paid-in USD 118.45 m against a USD 30 m commitment |
| northlake_venture_q2_2026_all_funds.csv | 3 funds | 2026-06-30 | EN | **reject** | three statements in one CSV |
| kestrel_iv_kapitalkonto_q3_2026.xlsx | KES4 | 2026-09-30 | DE | **reject** | no NAV; the valuation "will follow" |

Each rejected file has exactly one reason. Apart from that reason it is complete and plausible.

## Notes for the scorer

- **Amounts** are in full units of the fund currency. They are JSON numbers, so `17312500.00` is
  written `17312500.0`; compare to the cent.
- **`distributed` is always positive**, also where the statement prints it as `(4,105,882.17)` or
  `-3493482.17`.
- **Cumulative, not period:** `paid_in` and `distributed` are always the inception-to-date figures,
  and `nav` is the closing NAV at the period end. Many files also print quarter, half-year or YTD
  figures and an opening NAV.
- **Units:** EUR m and Mio. EUR (`novara_growth_iii_h1_2026`, `fjord_iii_2026-09-30`), thousands
  (`KES4_Kapitalkonto_2026Q2` TEUR, `lumen_v_2025q4` USD '000, `orion_ix_q4_2025`,
  `crestline_iv_q4_2025`). The key is the printed figure times the unit, so a rounded statement gives
  a round answer (e.g. 14.35 EUR m -> 14350000.0).
- **Hardest case:** `fjord_iii_2026-09-30.txt` prints German three-decimal millions ("15,000",
  "13,652"). A parser that reads the comma as a thousands separator will be off by a factor of
  1,000.
- **Currency:** `lumen_v_kapitalkonto_2026-06-30.txt` is a USD fund reported in German. It has an
  informational EUR conversion of the NAV (8.648.959,26 EUR); the answer is USD 9,377,201.63.
- **Paid-in:** where paid-in includes fee contributions (`aurora_q2-2026_capital_statement`), the
  answer is the total paid-in line. Recallable distributions are never added back.
- **Not multi-statement:** `bastion_ii_q2_2026.csv` repeats the fund on every row but is one
  statement. Only `northlake_venture_q2_2026_all_funds.csv` is a multi-statement CSV.
- **Dates:** each file also carries an issue date or a valuation date; `period_end` is the
  statement's reporting date. `tidewater_cti_q3_2026.xlsx` stores it as a real Excel date.
- **Cross-quarter consistency:** where a fund appears more than once, the quarters agree with each
  other (e.g. AUR7 Q1 closing NAV = Q2 opening NAV). This is not needed for scoring.
