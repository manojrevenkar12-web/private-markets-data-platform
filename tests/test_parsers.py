from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path

import pytest

from pmd.parsers.camt import CamtError, parse_camt053
from pmd.parsers.statements import ParseError, parse_cells, parse_date, parse_number, parse_statement, violations
from pmd_sim import writers
from pmd_sim.world import TargetQuarter


@pytest.mark.parametrize(
    ("raw", "german", "want"),
    [
        ("19,616,000.00", False, "19616000.00"),
        ("11.400.000,00 EUR", True, "11400000.00"),
        ("USD 3,526,368.32", False, "3526368.32"),
        ("(1,234.50)", False, "-1234.50"),
        ("1 234 567.89", False, "1234567.89"),
        ("1'234'567.89", False, "1234567.89"),
        ("12345.678000", True, "12345.678"),
        ("1.234", True, "1234"),
        ("1,5", True, "1.5"),
        ("€ 2.500,00", True, "2500.00"),
    ],
)
def test_numbers_either_way(raw: str, german: bool, want: str) -> None:
    assert parse_number(raw, german) == Decimal(want)


@pytest.mark.parametrize(
    ("raw", "us", "want"),
    [
        ("June 30, 2026", None, "2026-06-30"),
        ("30 June 2026", None, "2026-06-30"),
        ("30.06.2026", None, "2026-06-30"),
        ("2026-06-30", None, "2026-06-30"),
        ("06/30/2026", True, "2026-06-30"),
        ("30/06/2026", False, "2026-06-30"),
        ("31. Dezember 2025", None, "2025-12-31"),
        ("Stichtag: 31.03.2026", None, "2026-03-31"),
    ],
)
def test_dates_in_the_usual_formats(raw: str, us: bool | None, want: str) -> None:
    assert parse_date(raw, us) == dt.date.fromisoformat(want)


FUND = {"name": "Kestrel European Buyout IV", "gp": "Kestrel Partners", "currency": "EUR"}


def _tq(**kw: object) -> TargetQuarter:
    base = dict(
        fund="KES4",
        period_end=dt.date(2026, 6, 30),
        currency="EUR",
        commitment=Decimal("18240000.00"),
        called=Decimal(0),
        distributed=Decimal(0),
        paid_in=Decimal("13412601.60"),
        distributions=Decimal("250000.00"),
        nav=Decimal("14481028.86"),
        call_date=None,
        dist_date=None,
    )
    base.update(kw)
    return TargetQuarter(**base)  # type: ignore[arg-type]


def _check(st, tq: TargetQuarter) -> None:  # type: ignore[no-untyped-def]
    assert st.fund == tq.fund
    assert st.period_end == tq.period_end
    assert st.currency == tq.currency
    assert (st.commitment, st.paid_in, st.distributed, st.nav) == (tq.commitment, tq.paid_in, tq.distributions, tq.nav)
    assert violations(st) == []


def test_every_generated_format_reads_back(tmp_path: Path) -> None:
    issued = dt.date(2026, 8, 14)
    investor = "Northlake Private Equity V GmbH & Co. KG"
    aurora = {"name": "Aurora Buyout Fund VII", "gp": "Aurora Capital Partners"}
    halvard = {"name": "Halvard Mid-Market II", "gp": "Halvard Beteiligungen"}
    cases = {
        "a.pdf": (
            writers.statement_pdf_en(investor, aurora, _tq(fund="AUR7", currency="USD"), issued),
            _tq(fund="AUR7", currency="USD"),
        ),
        "b.pdf": (writers.statement_pdf_de(investor, halvard, _tq(fund="HAL2"), issued), _tq(fund="HAL2")),
        "c.xlsx": (writers.statement_xlsx_de(investor, FUND, _tq(), issued, teur=False), _tq()),
    }
    for fid, name in (
        ("FJD3", "Fjord Secondaries III"),
        ("ORI9", "Orion Global Partners IX"),
        ("TID1", "Tidewater Climate Tech I"),
        ("CRE4", "Crestline Direct Lending IV"),
    ):
        tq = _tq(fund=fid, currency="USD" if fid == "ORI9" else "EUR")
        cases[f"{fid}.csv"] = (writers.statement_csv(fid, investor, {"name": name}, tq, issued), tq)
    for name, (data, tq) in cases.items():
        p = tmp_path / name
        p.write_bytes(data)
        _check(parse_statement(p), tq)


def test_amounts_in_teur_are_scaled(tmp_path: Path) -> None:
    p = tmp_path / "teur.xlsx"
    tq = _tq(
        fund="SPR2",
        commitment=Decimal("12736000.00"),
        paid_in=Decimal("3445597.00"),
        nav=Decimal("3577199.00"),
        distributions=Decimal(0),
    )
    p.write_bytes(writers.statement_xlsx_de("x", {"name": "Spree Seed II"}, tq, dt.date(2026, 8, 1), teur=True))
    st = parse_statement(p)
    assert st.unit_scale == 1000
    assert st.nav == Decimal("3577199.00")
    assert any("scaled" in n for n in st.notes)


def test_a_scan_is_quarantined_not_guessed(tmp_path: Path) -> None:
    p = tmp_path / "scan.pdf"
    p.write_bytes(
        writers.statement_pdf_en(
            "x", {"name": "Aurora Buyout Fund VII", "gp": "Aurora"}, _tq(fund="AUR7"), dt.date(2026, 8, 1), scan=True
        )
    )
    with pytest.raises(ParseError) as e:
        parse_statement(p)
    assert e.value.rule == "no_text_layer"


def test_contract_rules() -> None:
    cells = [
        "Fonds",
        "Kestrel European Buyout IV",
        "Stichtag",
        "15.05.2026",
        "Währung",
        "EUR",
        "Zeichnungsbetrag",
        "1.000.000,00",
        "Eingezahltes Kapital",
        "1.500.000,00",
        "Ausschüttungen",
        "0,00",
        "Nettoinventarwert",
        "900.000,00",
        "Offene Einzahlungsverpflichtung",
        "100,00",
    ]
    rules = {r for r, _ in violations(parse_cells(cells, "test"))}
    assert {"quarter_end", "paid_in_within_commitment"} <= rules


def test_unknown_fund_and_missing_nav_are_rejected() -> None:
    st = parse_cells(["Fund", "Some Other Fund LP", "As of", "2026-06-30", "Currency", "EUR", "Commitment", "100"], "t")
    assert violations(st)[0][0] == "required_fields"


def test_one_statement_per_csv(tmp_path: Path) -> None:
    p = tmp_path / "two.csv"
    p.write_text("fund,period_end,commitment,nav\nA,2026-06-30,1,1\nB,2026-06-30,2,2\n", encoding="utf-8")
    with pytest.raises(ParseError) as e:
        parse_statement(p)
    assert e.value.rule == "several_statements"


def test_camt_balances_must_add_up(tmp_path: Path) -> None:
    from types import SimpleNamespace

    entry = SimpleNamespace(
        id="R1",
        booked=dt.date(2026, 10, 1),
        amount=Decimal("100.00"),
        counterparty_name="A B",
        counterparty_iban="DE89370400440532013000",
        remittance="PE5-2026Q4 C-000001",
    )
    good = writers.camt053("DE89370400440532013000", dt.date(2026, 10, 1), Decimal("50.00"), [entry], 7)
    p = tmp_path / "s.xml"
    p.write_bytes(good)
    st = parse_camt053(p)
    assert st.closing == Decimal("150.00") and st.sequence == 7 and st.entries[0].amount == Decimal("100.00")
    p.write_bytes(good.replace(b'<Amt Ccy="EUR">150.00</Amt>', b'<Amt Ccy="EUR">151.00</Amt>'))
    with pytest.raises(CamtError) as e:
        parse_camt053(p)
    assert e.value.rule == "balances_add_up"
