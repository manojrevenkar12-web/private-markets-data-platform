# Held-out set v1: capital account statements

30 statements in `statements/`, one answer key per file in `answers/` (same stem, `.json`). Written from
`heldout/WRITING_STATEMENTS.md` only, without seeing the parser, its config or its tests. File names
are neutral (`s01` to `s30`) so they give away neither the fund nor whether a file should be rejected.

## Files

| File | Lang | Fund | Period end | Expect | What it looks like |
|---|---|---|---|---|---|
| s01.txt | EN | AUR7 | 2026-06-30 | accept | GP letter, label: value lines, `$` before, US long date, quarter figures beside cumulative |
| s02.xlsx | DE | KES4 | 2026-06-30 | accept | TEUR, numeric cells, Q2 and "seit Auflegung" columns, "davon Verwaltungsvergütung" row |
| s03.md | EN | FJD3 | 2026-03-31 | accept | Quarter roll-forward (negatives in parentheses) plus a separate cumulative table |
| s04.txt | DE | HAL2 | 2026-06-30 | accept | Dotted label/value lines, `1.234,56 EUR`, "davon im Berichtsquartal" rows |
| s05.txt | EN | - | 2026-06-30 | **reject** | Fund not in the table (Granite Peak Capital Partners VI, L.P.) |
| s06.csv | EN | ORI9 | 2026-09-30 | accept | One-row GP export, own column names (`contributions_itd`, `ending_capital_balance`), ISO dates |
| s07.md | EN | LUM5 | 2026-06-30 | accept | USD '000, QTD/ITD roll-forward, `06/30/2026` |
| s08.txt | DE | SPR2 | 2025-12-31 | accept | Annual roll-forward 2025 plus a separate cumulative block |
| s09.pdf | EN | NOV3 | 2026-06-30 | accept | EUR m with two decimals, TVPI row, footnote |
| s10.csv | DE | TID1 | 2026-06-30 | accept | Semicolon CSV `Position;Betrag;Währung`, decimal comma, a negative fee row |
| s11.csv | EN | - | 2026-06-30 | **reject** | Three statements (SPR2, NOV3, TID1) in one CSV |
| s12.txt | EN | CRE4 | 2026-06-30 | accept | Space thousands separator, `30/06/2026`, distributions split into interest and return of capital |
| s13.md | EN | BAS2 | 2026-09-30 | accept | Letter with a table, "EUR in thousands", no decimals |
| s14.pdf | DE | MER3 | 2026-06-30 | accept | TEUR with one decimal, "30. Juni 2026" |
| s15.csv | EN | AUR7 | 2026-09-30 | accept | Two-column `Field,Value` CSV, values like `"USD 1,234.56"` |
| s16.txt | EN | KES4 | 2026-09-30 | accept | Q3 and since-inception columns, code after the amount, "of which management fees" row |
| s17.md | DE | KES4 | 2026-05-15 | **reject** | Interim statement at final closing, Stichtag 15.05.2026 (30.06.2026 appears only in prose) |
| s18.xlsx | EN | ORI9 | 2026-06-30 | accept | Quarter and ITD columns, numeric cells, commitment block underneath |
| s19.txt | DE | LUM5 | 2026-09-30 | accept | German text for a USD fund, `1.234,56 USD` |
| s20.md | EN | HAL2 | 2026-09-30 | accept | `€` before the amount, quarter and since-inception columns |
| s21.md | DE | FJD3 | 2026-06-30 | accept | "Angaben in Mio. EUR", three decimals with a decimal comma (`12,465` = EUR 12.465 m) |
| s22.txt | EN | HAL2 | 2026-06-30 | **reject** | Paid-in EUR 48,750,000.00 against a commitment of EUR 5,000,000.00 |
| s23.csv | EN | CRE4 | 2026-09-30 | accept | Quoted `1,234.56` values, distributions shown as `(4,512,330.88)` |
| s24.txt | EN | SPR2 | 2026-06-30 | accept | `€ 1,234.56`, dotted leaders, a "thereof in H1 2026" row |
| s25.txt | EN | TID1 | 2026-09-30 | accept | ISO dates, period cash flows, a recallable distribution footnote |
| s26.txt | DE | BAS2 | 2026-06-30 | accept | Letter with an ASCII table, `EUR 1.234,56`, "davon Zinserträge" row |
| s27.csv | EN | NOV3 | 2026-09-30 | accept | US dates `09/30/2026`, plain numbers, all fields quoted |
| s28.md | DE | CRE4 | 2026-03-31 | **reject** | No NAV ("wird ... gesondert mitgeteilt") |
| s29.xlsx | EN | MER3 | 2026-09-30 | accept | Labels in column A and values in column D, EUR '000, period end as a real Excel date cell |
| s30.md | EN | AUR7 | 2025-12-31 | accept | USD m with two decimals, Q4, FY and ITD columns, IRR/TVPI/DPI line |

Totals: 11 txt, 8 md, 6 csv, 3 xlsx, 2 pdf; 20 English and 10 German; 25 accept and 5 reject.

## Conventions a scorer should know

- **Scaled amounts:** the key is the displayed figure times the unit (thousands or millions), with no
  attempt to recover precision the document does not give. 8 statements are scaled: s02, s07, s13, s14
  and s29 in thousands; s09, s21 and s30 in millions.
- **Sign:** `distributed` is always positive, even where the document shows it as negative or in
  parentheses (s03 for the period, s07, s23).
- **Cumulative, not period:** paid-in and distributions are inception-to-date. Several files put quarter,
  half-year or full-year figures next to them (s01, s02, s07, s14, s16, s18, s20, s21, s24, s25, s30).
- **Roll-forwards:** in s03 and s08 the NAV is the closing balance of the roll-forward, while paid-in and
  distributions come from the separate cumulative block. s08's roll-forward covers the full year 2025.
- **Fees:** where a fee row is "of which" or "included in contributions", paid-in is the stated total
  including fees (s01, s02, s16, s25). In s03, s08 and s18, fees are charged outside the commitment, so
  they are not in paid-in.
- **Distribution components:** in s12 and s26 the answer is the stated total. Interest and return of
  capital are sub-rows.
- **Recallable distribution (s25):** the remaining commitment printed in the statement (3,330,000.00) is
  not commitment minus paid-in, because the recallable EUR 210,000 was added back. The keys do not include
  unfunded, but a parser that cross-checks unfunded against commitment minus paid-in should not reject
  this file.
- **Rounding (s14):** TEUR figures with one decimal; commitment minus paid-in equals unfunded exactly, so
  there are no rounding differences to tolerate in the keys.
- **Upper-case fund names** in s12 and s24 (`CRESTLINE DIRECT LENDING IV SCSp`, `SPREE SEED II`): fund
  matching should be case-insensitive. Legal-form suffixes vary (L.P., SCSp, GmbH & Co. KG,
  S.C.A. SICAV-RAIF).
- **s11:** each row on its own is valid, and the rows repeat figures from other files in this set. The
  file is rejected only because it contains several statements.
- **s17:** the only quarter-end date in the document is in the closing sentence. The statement date is
  15.05.2026.
- **s22:** the fund is valid and the numbers are internally consistent apart from paid-in versus
  commitment.
- **Same fund across quarters:** AUR7 (Q4 2025, Q2 and Q3 2026), KES4, ORI9, LUM5, HAL2, FJD3, SPR2, TID1,
  CRE4, BAS2, NOV3 and MER3 each appear more than once. Figures are consistent across periods (including
  s11, s17 and s28), so they can also be used for roll-over checks. The exception is s22, which uses a
  different commitment for HAL2.
- Amounts in the keys are JSON numbers (for example `12465000.0`). Compare them numerically to the cent.
