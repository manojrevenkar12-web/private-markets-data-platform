# Writing a held-out set of capital account statements

You are writing test documents for a parser you have never seen. **Read only this file.** Do not open, list,
search or run anything else in the repository, and do not look at other held-out sets. The point is that the
statements are written by someone who does not know how the parser works, so its score on them is honest.

## What a capital account statement is

Each quarter, the manager (GP) of a private equity, venture or private debt fund sends each investor (LP) a
statement of that investor's capital account in the fund. The investor here is always one of three feeder
funds of a German wealth manager, for example "Northlake Private Equity V GmbH & Co. KG",
"Northlake Venture III GmbH & Co. KG" or "Northlake Private Debt I GmbH & Co. KG".

A statement states, at least:

- the fund it is about (by name),
- the period end (a quarter end: 31 March, 30 June, 30 September or 31 December),
- the currency,
- the investor's total **commitment**,
- the cumulative **paid-in** capital (also called contributions, called capital, drawn capital),
- the cumulative **distributions**,
- the **NAV** of the investor's capital account at the period end,
- usually also the unfunded (remaining) commitment and the date the statement was issued.

## The funds

| Code | Fund name | Currency |
| --- | --- | --- |
| AUR7 | Aurora Buyout Fund VII | USD |
| KES4 | Kestrel European Buyout IV | EUR |
| FJD3 | Fjord Secondaries III | EUR |
| HAL2 | Halvard Mid-Market II | EUR |
| ORI9 | Orion Global Partners IX | USD |
| LUM5 | Lumen Ventures V | USD |
| SPR2 | Spree Seed II | EUR |
| NOV3 | Novara Growth III | EUR |
| TID1 | Tidewater Climate Tech I | EUR |
| CRE4 | Crestline Direct Lending IV | EUR |
| BAS2 | Bastion Senior Debt II | EUR |
| MER3 | Meridian Infrastructure Debt III | EUR |

## What to write

Write **30 statements** into `heldout/v1/statements/`, one statement per file, and one answer key per file
in `heldout/v1/answers/` with the same file stem and `.json`.

Vary them the way real managers do. Use your own wording and layouts; do not copy one template thirty times.

- **Formats:** `.txt`, `.md` and `.csv` for most; you may also write some `.xlsx` (Excel) or `.pdf` files
  with a short Python script using openpyxl or reportlab (keep the script outside the repository).
- **Languages:** English and German, roughly two to one. Use the wording a fund administrator would use.
- **Numbers:** `1,234,567.89`, `1.234.567,89`, `1 234 567.89`, plain `1234567.89`; currency codes or
  symbols before or after; negative numbers in parentheses where it is natural.
- **Units:** some statements in thousands or millions, saying so the way documents do ("in thousands",
  "USD '000", "in TEUR", "EUR m").
- **Dates:** "30 June 2026", "June 30, 2026", "30.06.2026", "2026-06-30", "06/30/2026" (US), "30/06/2026".
- **Layouts:** label and value on one line, a table, label and value in separate columns, a letter with the
  figures in a table, a CSV export with its own column names, a capital account roll-forward (opening
  balance, contributions in the period, distributions in the period, gains and losses, closing balance)
  where the cumulative figures are stated separately.
- **Noise:** add what real statements have: addresses, a fund's legal form ("SCSp", "L.P.", "GmbH & Co. KG"),
  a footnote, management fees, period figures next to cumulative ones. The answer is always the cumulative
  figure and the closing NAV.

About **five** of the 30 should be statements a careful platform must **reject**, each for one clear reason:
a fund that is not in the table above, a period end that is not a quarter end, paid-in capital far above the
commitment, a CSV with several statements in one file, or a document missing the NAV entirely.

Keep the numbers plausible: paid-in between 10 % and 100 % of the commitment, distributions below paid-in
for young funds, NAV of the same order as paid-in.

## Answer key format

```json
{
  "expect": "accept",
  "fund": "KES4",
  "period_end": "2026-06-30",
  "currency": "EUR",
  "commitment": 18240000.00,
  "paid_in": 13412601.60,
  "distributed": 0.00,
  "nav": 14481028.86,
  "note": "German xlsx, amounts in TEUR"
}
```

All amounts in full units of the currency (a statement in thousands showing 13,412.6 has paid_in
13412600.00). For a statement to reject:

```json
{ "expect": "reject", "reason": "period end 15 May 2026 is not a quarter end", "note": "..." }
```

When you are done, write `heldout/v1/README.md` listing the files and anything a scorer should know, and
report back how many files you wrote in each format and language and which ones should be rejected.
