"""The true state of a small private-markets business, before anyone reports on it.

Clients commit to feeder funds; each feeder commits to target funds; target funds call capital, grow or shrink
and distribute; the feeder calls its clients to pay the target funds and passes distributions on; clients pay,
mostly correctly. Everything the platform later receives (statements, bank files, CRM exports, payment events)
is written from this world, with the mistakes real sources make. The answer key stays beside it.
"""

from __future__ import annotations

import datetime as dt
import math
import random
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

FIRST_NAMES = [
    "Anna",
    "Lena",
    "Marie",
    "Sophie",
    "Laura",
    "Julia",
    "Hannah",
    "Lea",
    "Sarah",
    "Katharina",
    "Johanna",
    "Clara",
    "Paula",
    "Emma",
    "Mia",
    "Leonie",
    "Nina",
    "Eva",
    "Jonas",
    "Lukas",
    "Leon",
    "Felix",
    "Maximilian",
    "Paul",
    "Elias",
    "Noah",
    "Ben",
    "Finn",
    "Moritz",
    "Julian",
    "Tim",
    "David",
    "Jan",
    "Philipp",
    "Niklas",
    "Alexander",
    "Sebastian",
    "Tobias",
    "Florian",
    "Christian",
    "Matthias",
    "Stefan",
    "Andreas",
    "Thomas",
    "Michael",
    "Markus",
    "Daniel",
    "Ayse",
    "Mehmet",
    "Elif",
    "Can",
    "Sofia",
    "Luca",
    "Marco",
    "Giulia",
    "Pierre",
    "Camille",
    "Olga",
    "Piotr",
    "Agnieszka",
    "Lars",
    "Ingrid",
    "Henrik",
    "Priya",
    "Arjun",
]
LAST_NAMES = [
    "Müller",
    "Schmidt",
    "Schneider",
    "Fischer",
    "Weber",
    "Meyer",
    "Wagner",
    "Becker",
    "Schulz",
    "Hoffmann",
    "Koch",
    "Richter",
    "Klein",
    "Wolf",
    "Schröder",
    "Neumann",
    "Schwarz",
    "Braun",
    "Zimmermann",
    "Hofmann",
    "Hartmann",
    "Krüger",
    "Lange",
    "Werner",
    "Krause",
    "Lehmann",
    "Köhler",
    "Maier",
    "Herrmann",
    "König",
    "Walter",
    "Mayer",
    "Huber",
    "Kaiser",
    "Fuchs",
    "Peters",
    "Lang",
    "Scholz",
    "Möller",
    "Weiß",
    "Jung",
    "Hahn",
    "Vogel",
    "Friedrich",
    "Keller",
    "Günther",
    "Frank",
    "Berger",
    "Winkler",
    "Roth",
    "Beck",
    "Lorenz",
    "Baumann",
    "Franke",
    "Albrecht",
    "Yilmaz",
    "Kaya",
    "Rossi",
    "Dubois",
    "Nowak",
    "Larsen",
    "Sharma",
]
CITIES = [
    ("10115", "Berlin"),
    ("20095", "Hamburg"),
    ("80331", "München"),
    ("50667", "Köln"),
    ("60311", "Frankfurt am Main"),
    ("70173", "Stuttgart"),
    ("40213", "Düsseldorf"),
    ("04109", "Leipzig"),
    ("01067", "Dresden"),
    ("30159", "Hannover"),
    ("90402", "Nürnberg"),
    ("28195", "Bremen"),
    ("8001", "Zürich"),
    ("1010", "Wien"),
]
STREETS = [
    "Hauptstraße",
    "Bahnhofstraße",
    "Gartenstraße",
    "Lindenallee",
    "Schillerstraße",
    "Goethestraße",
    "Parkweg",
    "Bergstraße",
    "Ringstraße",
    "Kastanienallee",
]

# How each strategy behaves per quarter: mean and spread of the return, how fast capital is called
# (quarters for the call rate to fall by e), when distributions start (quarters) and how much NAV they return.
STRATEGY = {
    "Buyout": {"mu": 0.024, "sigma": 0.035, "tau": 5.0, "dist_from": 7, "dist_rate": 0.05},
    "Secondaries": {"mu": 0.022, "sigma": 0.025, "tau": 3.0, "dist_from": 3, "dist_rate": 0.07},
    "Venture": {"mu": 0.028, "sigma": 0.085, "tau": 7.0, "dist_from": 11, "dist_rate": 0.03},
    "Seed": {"mu": 0.030, "sigma": 0.11, "tau": 6.0, "dist_from": 13, "dist_rate": 0.02},
    "Growth": {"mu": 0.026, "sigma": 0.06, "tau": 6.0, "dist_from": 9, "dist_rate": 0.04},
    "Direct lending": {"mu": 0.019, "sigma": 0.006, "tau": 2.0, "dist_from": 1, "dist_rate": 0.045},
    "Senior debt": {"mu": 0.016, "sigma": 0.004, "tau": 2.0, "dist_from": 1, "dist_rate": 0.04},
    "Infrastructure debt": {"mu": 0.017, "sigma": 0.005, "tau": 3.0, "dist_from": 1, "dist_rate": 0.04},
}

CENT = Decimal("0.01")


def money(x: float | Decimal) -> Decimal:
    return Decimal(str(x)).quantize(CENT, rounding=ROUND_HALF_UP)


def quarter_end(d: dt.date) -> dt.date:
    q_month = ((d.month - 1) // 3 + 1) * 3
    nxt = dt.date(d.year + (q_month == 12), q_month % 12 + 1, 1)
    return nxt - dt.timedelta(days=1)


def quarter_start(qe: dt.date) -> dt.date:
    return dt.date(qe.year, qe.month - 2, 1)


def quarter_ends(start: dt.date, end: dt.date) -> list[dt.date]:
    out, q = [], quarter_end(start)
    while q <= end:
        out.append(q)
        q = quarter_end(q + dt.timedelta(days=1))
    return out


def business_day(d: dt.date) -> dt.date:
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d


def iban_de(rnd: random.Random) -> str:
    """A German IBAN with a valid check number (mod 97), bank code and account invented."""
    bban = f"{rnd.randint(10000000, 99999999)}{rnd.randint(0, 9999999999):010d}"
    numeric = bban + "131400"  # D=13 E=14 + "00"
    check = 98 - int(numeric) % 97
    return f"DE{check:02d}{bban}"


@dataclass
class Client:
    id: str
    first_name: str
    last_name: str
    email: str
    phone: str
    birth_date: dt.date
    street: str
    postal_code: str
    city: str
    country: str
    iban: str
    tax_id: str
    segment: str
    risk_profile: str
    onboarded_at: dt.date
    advisor: str


@dataclass
class Commitment:
    id: str
    client: str
    feeder: str
    amount: Decimal
    signed_at: dt.date


@dataclass
class TargetQuarter:
    fund: str
    period_end: dt.date
    currency: str
    commitment: Decimal
    called: Decimal  # in this quarter
    distributed: Decimal  # in this quarter
    paid_in: Decimal  # cumulative
    distributions: Decimal  # cumulative
    nav: Decimal
    call_date: dt.date | None
    dist_date: dt.date | None


@dataclass
class FeederCall:
    id: str
    feeder: str
    notice_date: dt.date
    due_date: dt.date
    percent: Decimal  # of commitment, e.g. 4.25


@dataclass
class FeederDistribution:
    id: str
    feeder: str
    pay_date: dt.date
    percent: Decimal


@dataclass
class Payment:
    """Money on a feeder's account: a client paying a call, the feeder paying a target fund, and so on."""

    id: str
    feeder: str
    booked: dt.date
    amount: Decimal  # positive credit, negative debit, EUR
    counterparty_name: str
    counterparty_iban: str
    remittance: str
    kind: str  # client_call | client_distribution | target_call | target_distribution | unknown
    client: str | None = None
    call: str | None = None
    fund: str | None = None
    anomaly: str | None = None
    received_at: dt.datetime | None = None


@dataclass
class World:
    today: dt.date
    funds: dict[str, Any]
    clients: list[Client] = field(default_factory=list)
    prospects: list[Client] = field(default_factory=list)
    commitments: list[Commitment] = field(default_factory=list)
    target_quarters: list[TargetQuarter] = field(default_factory=list)
    target_commitments: dict[str, Decimal] = field(default_factory=dict)
    feeder_calls: list[FeederCall] = field(default_factory=list)
    feeder_distributions: list[FeederDistribution] = field(default_factory=list)
    payments: list[Payment] = field(default_factory=list)
    fx: dict[dt.date, Decimal] = field(default_factory=dict)  # USD per EUR
    erasure_requests: list[tuple[str, dt.date]] = field(default_factory=list)
    planted: list[dict[str, Any]] = field(default_factory=list)

    def target(self, fund: str) -> tuple[str, dict[str, Any]]:
        for fid, f in self.funds["feeders"].items():
            if fund in f["targets"]:
                return fid, f["targets"][fund]
        raise KeyError(fund)

    def usd_per_eur(self, d: dt.date) -> Decimal:
        while d not in self.fx:
            d -= dt.timedelta(days=1)
        return self.fx[d]


def _person(rnd: random.Random, i: int, start: dt.date, end: dt.date) -> Client:
    first, last = rnd.choice(FIRST_NAMES), rnd.choice(LAST_NAMES)
    plz, city = rnd.choice(CITIES)
    country = "CH" if city == "Zürich" else "AT" if city == "Wien" else "DE"
    ascii_last = last.replace("ü", "ue").replace("ö", "oe").replace("ä", "ae").replace("ß", "ss").lower()
    span = max(1, (end - start).days)
    return Client(
        id=f"C-{i:06d}",
        first_name=first,
        last_name=last,
        email=f"{first.lower()}.{ascii_last}{rnd.randint(1, 99)}@example.com",
        phone=f"+49 1{rnd.randint(50, 79)} {rnd.randint(1000000, 9999999)}",
        birth_date=dt.date(rnd.randint(1948, 1994), rnd.randint(1, 12), rnd.randint(1, 28)),
        street=f"{rnd.choice(STREETS)} {rnd.randint(1, 140)}",
        postal_code=plz,
        city=city,
        country=country,
        iban=iban_de(rnd),
        tax_id=f"{rnd.randint(10, 99)}{rnd.randint(100000000, 999999999)}",
        segment=rnd.choices(["Private", "Entrepreneur", "Family office"], [0.62, 0.3, 0.08])[0],
        risk_profile=rnd.choice(["balanced", "growth", "growth", "dynamic"]),
        onboarded_at=start + dt.timedelta(days=rnd.randrange(span)),
        advisor=rnd.choice(["Team Nord", "Team Süd", "Team West", "Team Ost"]),
    )


def build_world(funds: dict[str, Any], today: dt.date, seed: int = 2026, n_clients: int = 420) -> World:
    rnd = random.Random(seed)
    w = World(today=today, funds=funds)

    # FX: EUR/USD as a mild random walk, one rate per business day.
    d, rate = dt.date(2023, 1, 2), 1.07
    while d <= today + dt.timedelta(days=120):
        if d.weekday() < 5:
            rate = min(1.22, max(0.98, rate * math.exp(rnd.gauss(0, 0.0045))))
            w.fx[d] = Decimal(str(round(rate, 4)))
        d += dt.timedelta(days=1)

    # Clients and their commitments; prospects are in the CRM but never committed.
    earliest = min(f["first_close"] for f in funds["feeders"].values())
    for i in range(1, n_clients + 1):
        w.clients.append(_person(rnd, i, earliest - dt.timedelta(days=365), today - dt.timedelta(days=120)))
    for j in range(n_clients + 1, n_clients + 1 + max(4, n_clients // 20)):
        w.prospects.append(_person(rnd, j, today - dt.timedelta(days=300), today - dt.timedelta(days=10)))

    n = 0
    for c in w.clients:
        chosen = [
            fid for fid in funds["feeders"] if rnd.random() < {"PE5": 0.62, "VC3": 0.48, "PD1": 0.4}.get(fid, 0.5)
        ]
        if not chosen:
            chosen = [rnd.choice(list(funds["feeders"]))]
        for fid in chosen:
            f = funds["feeders"][fid]
            if f["first_close"] > today:
                continue
            steps = [1, 1, 1, 1.5, 2, 2, 2.5, 3, 4, 5, 10] if f["min_ticket"] >= 100000 else [1, 1, 2, 2.5, 5, 10, 25]
            amount = money(f["min_ticket"] * rnd.choice(steps))
            n += 1
            # subscriptions are signed in the offering period before the close; the close fixes the fund size
            signed = f["first_close"] - dt.timedelta(days=rnd.randint(5, 150))
            w.commitments.append(Commitment(f"S-{n:06d}", c.id, fid, amount, min(signed, today)))

    # Target funds: commitments sized from the feeder's final close, quarterly capital accounts.
    for fid, f in funds["feeders"].items():
        total = sum((c.amount for c in w.commitments if c.feeder == fid), Decimal(0))
        for tid, t in f["targets"].items():
            commit_eur = total * Decimal(str(t["weight"])) * Decimal("0.97")  # a small cash reserve stays in the feeder
            fx0 = w.usd_per_eur(f["first_close"])
            commitment = money(commit_eur * fx0) if t["currency"] == "USD" else money(commit_eur)
            # round to what a fund would accept: whole thousands
            commitment = (commitment / 1000).quantize(Decimal(1)) * 1000
            w.target_commitments[tid] = commitment
            # target funds call from the quarter after the feeder's close, when every client is in
            _simulate_target(w, rnd, fid, tid, t, commitment, quarter_end(f["first_close"]) + dt.timedelta(days=1))

    _feeder_cash(w, rnd)
    _client_payments(w, rnd)
    w.erasure_requests = [
        (w.prospects[0].id, today - dt.timedelta(days=6)),
        (w.clients[3].id, today - dt.timedelta(days=4)),  # still invested: retention applies
    ]
    w.planted.append({"kind": "erasure_prospect", "client": w.prospects[0].id})
    w.planted.append({"kind": "erasure_on_hold", "client": w.clients[3].id})
    return w


def _simulate_target(
    w: World, rnd: random.Random, fid: str, tid: str, t: dict[str, Any], commitment: Decimal, start: dt.date
) -> None:
    s = STRATEGY[t["strategy"]]
    horizon = quarter_end(w.today)  # through the current quarter: its capital call is open today
    paid_in = dists = nav = Decimal(0)
    raw = [math.exp(-k / s["tau"]) for k in range(24)]
    scale = 0.92 / sum(raw[:16])
    for k, qe in enumerate(quarter_ends(start, horizon)):
        frac = raw[k] * scale if k < 24 else 0.0
        call = money(min(commitment - paid_in, commitment * Decimal(str(round(frac * rnd.uniform(0.75, 1.25), 5)))))
        ret = rnd.gauss(s["mu"], s["sigma"])
        dist = Decimal(0)
        if k >= s["dist_from"] and nav > 0:
            dist = money(nav * Decimal(str(max(0.0, s["dist_rate"] * rnd.uniform(0.3, 1.8)))))
        nav = money(max(Decimal(0), nav * Decimal(str(1 + ret)) + call - dist))
        paid_in += call
        dists += dist
        q_start = quarter_start(qe)
        call_date = business_day(q_start + dt.timedelta(days=rnd.randint(25, 40))) if call > 0 else None
        dist_date = business_day(qe - dt.timedelta(days=rnd.randint(5, 25))) if dist > 0 else None
        w.target_quarters.append(
            TargetQuarter(tid, qe, t["currency"], commitment, call, dist, paid_in, dists, nav, call_date, dist_date)
        )


def _feeder_cash(w: World, rnd: random.Random) -> None:
    """The feeder calls its clients ahead of the target funds' calls and passes distributions on."""
    for fid in w.funds["feeders"]:
        total = sum((c.amount for c in w.commitments if c.feeder == fid), Decimal(0))
        if total == 0:
            continue
        by_q: dict[dt.date, list[TargetQuarter]] = {}
        for tq in w.target_quarters:
            if w.target(tq.fund)[0] == fid:
                by_q.setdefault(tq.period_end, []).append(tq)
        seq_dist = 0
        for qe in sorted(by_q):
            rows = by_q[qe]
            need = Decimal(0)
            got = Decimal(0)
            for tq in rows:
                rate = w.usd_per_eur(tq.call_date or qe) if tq.currency == "USD" else Decimal(1)
                if tq.called > 0:
                    eur = money(tq.called / rate)
                    need += eur
                    gp = w.funds["feeders"][fid]["targets"][tq.fund]["gp"]
                    w.payments.append(
                        Payment(
                            f"P-{len(w.payments) + 1:07d}",
                            fid,
                            tq.call_date or qe,
                            -eur,
                            gp,
                            _gp_iban(tq.fund),
                            f"Capital call {tq.fund} {qe:%Y}Q{(qe.month - 1) // 3 + 1}",
                            "target_call",
                            fund=tq.fund,
                        )
                    )
                if tq.distributed > 0:
                    rate_d = w.usd_per_eur(tq.dist_date or qe) if tq.currency == "USD" else Decimal(1)
                    eur = money(tq.distributed / rate_d)
                    got += eur
                    gp = w.funds["feeders"][fid]["targets"][tq.fund]["gp"]
                    w.payments.append(
                        Payment(
                            f"P-{len(w.payments) + 1:07d}",
                            fid,
                            tq.dist_date or qe,
                            eur,
                            gp,
                            _gp_iban(tq.fund),
                            f"Distribution {tq.fund} {qe:%Y}Q{(qe.month - 1) // 3 + 1}",
                            "target_distribution",
                            fund=tq.fund,
                        )
                    )
            if need > 0:
                pct = (need / total * 100 / Decimal("0.25")).to_integral_value(rounding="ROUND_CEILING") * Decimal(
                    "0.25"
                )
                notice = business_day(quarter_start(qe) + dt.timedelta(days=11))
                due = business_day(notice + dt.timedelta(days=14))
                w.feeder_calls.append(FeederCall(f"{fid}-{qe:%Y}Q{(qe.month - 1) // 3 + 1}", fid, notice, due, pct))
            if got > 0:
                pct = (got / total * 100 / Decimal("0.25")).to_integral_value(rounding="ROUND_FLOOR") * Decimal("0.25")
                if pct > 0:
                    seq_dist += 1
                    pay = business_day(qe + dt.timedelta(days=rnd.randint(20, 35)))
                    w.feeder_distributions.append(FeederDistribution(f"{fid}-D{seq_dist:02d}", fid, pay, pct))


def _gp_iban(fund: str) -> str:
    rnd = random.Random(f"gp-{fund}")
    return iban_de(rnd)


ANOMALIES = [
    ("late", 0.02),
    ("short", 0.008),
    ("over", 0.005),
    ("no_reference", 0.012),
    ("wrong_reference", 0.006),
    ("duplicate", 0.004),
    ("unpaid", 0.004),
]


def _client_payments(w: World, rnd: random.Random) -> None:
    clients = {c.id: c for c in w.clients}
    for call in w.feeder_calls:
        if call.notice_date > w.today:
            continue
        for cm in (c for c in w.commitments if c.feeder == call.feeder and c.signed_at <= call.notice_date):
            client = clients[cm.client]
            expected = money(cm.amount * call.percent / 100)
            ref = f"{call.id} {client.id}"
            anomaly = None
            r = rnd.random()
            acc = 0.0
            for name, prob in ANOMALIES:
                acc += prob
                if r < acc:
                    anomaly = name
                    break
            open_call = call.due_date + dt.timedelta(days=10) >= w.today
            if open_call and anomaly == "unpaid":
                anomaly = None  # nobody is overdue on a call that is not due yet
            pay_day = business_day(call.notice_date + dt.timedelta(days=rnd.randint(2, 15)))
            if anomaly == "late":
                pay_day = business_day(call.due_date + dt.timedelta(days=rnd.randint(9, 30)))
            if anomaly == "unpaid" or (open_call and pay_day > w.today):
                if anomaly == "unpaid":
                    w.planted.append(
                        {"kind": "unpaid", "client": client.id, "call": call.id, "expected": str(expected)}
                    )
                continue
            amount = expected
            remittance = ref
            if anomaly == "short":
                amount = money(expected * Decimal("0.9"))
            elif anomaly == "over":
                amount = money(expected * Decimal("1.1"))
            elif anomaly == "no_reference":
                remittance = rnd.choice(["Kapitalabruf", "Einzahlung Fonds", "Private Equity", ""])
            elif anomaly == "wrong_reference":
                remittance = f"{call.id} {client.id[:-1]}{(int(client.id[-1]) + 3) % 10}"  # a typo in the client number
            name = f"{client.first_name} {client.last_name}"
            hour = rnd.randint(7, 19)
            received = dt.datetime.combine(pay_day, dt.time(hour, rnd.randint(0, 59), rnd.randint(0, 59)))
            p = Payment(
                f"P-{len(w.payments) + 1:07d}",
                call.feeder,
                pay_day,
                amount,
                name,
                client.iban,
                remittance,
                "client_call",
                client=client.id,
                call=call.id,
                anomaly=anomaly,
                received_at=received,
            )
            w.payments.append(p)
            if anomaly:
                w.planted.append(
                    {
                        "kind": anomaly,
                        "client": client.id,
                        "call": call.id,
                        "expected": str(expected),
                        "paid": str(amount),
                        "booked": pay_day.isoformat(),
                        "payment": p.id,
                    }
                )
            if anomaly == "duplicate":
                again = business_day(pay_day + dt.timedelta(days=rnd.randint(1, 4)))
                w.payments.append(
                    Payment(
                        f"P-{len(w.payments) + 1:07d}",
                        call.feeder,
                        again,
                        amount,
                        name,
                        client.iban,
                        remittance,
                        "client_call",
                        client=client.id,
                        call=call.id,
                        anomaly="duplicate_second",
                        received_at=dt.datetime.combine(again, dt.time(10, 5)),
                    )
                )
    # money nobody can place: a payer the CRM does not know, no usable reference
    for fid in w.funds["feeders"]:
        calls = [c for c in w.feeder_calls if c.feeder == fid and c.notice_date <= w.today - dt.timedelta(days=30)]
        if not calls:
            continue
        c = calls[-1]
        day = business_day(c.due_date - dt.timedelta(days=2))
        p = Payment(
            f"P-{len(w.payments) + 1:07d}",
            fid,
            day,
            money(rnd.choice([25000, 50000, 12500])),
            "M. Unbekannt",
            iban_de(rnd),
            "Zahlung",
            "unknown",
            received_at=dt.datetime.combine(day, dt.time(11, 0)),
        )
        w.payments.append(p)
        w.planted.append(
            {"kind": "unknown_payer", "feeder": fid, "payment": p.id, "paid": str(p.amount), "booked": day.isoformat()}
        )
    # distributions out to clients
    for dist in w.feeder_distributions:
        if dist.pay_date > w.today:
            continue
        for cm in (c for c in w.commitments if c.feeder == dist.feeder and c.signed_at <= dist.pay_date):
            client = clients[cm.client]
            amount = money(cm.amount * dist.percent / 100)
            w.payments.append(
                Payment(
                    f"P-{len(w.payments) + 1:07d}",
                    dist.feeder,
                    dist.pay_date,
                    -amount,
                    f"{client.first_name} {client.last_name}",
                    client.iban,
                    f"Ausschüttung {dist.id} {client.id}",
                    "client_distribution",
                    client=client.id,
                    call=dist.id,
                )
            )
    w.payments.sort(key=lambda p: (p.booked, p.id))
