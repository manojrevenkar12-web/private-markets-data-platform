import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { session } from "../src/shared/api/client";
import { fx, routes } from "./fixtures";
import { clone, json, problem, renderAt, stubApi } from "./harness";

beforeEach(() => {
  sessionStorage.clear();
  session.reset();
});

const actAs = (role: "analyst" | "operations" | "fund_accounting", name = "Test Person") =>
  act(() => {
    session.setRole(role);
    session.setActor(name);
  });

describe("today", () => {
  it("shows what clients see, with estimates marked", async () => {
    stubApi(routes());
    renderAt("/");
    expect(
      await screen.findByRole("heading", { level: 1, name: "What clients see on 26 Oct 2026" }),
    ).toBeInTheDocument();
    const feeder = screen.getByRole("article", { name: "Northlake Private Debt I" });
    expect(within(feeder).getByText("est.")).toBeInTheDocument();
    expect(within(feeder).getByText("24.9 m EUR")).toBeInTheDocument();
    expect(screen.getByText("420 clients have committed 170.9 m EUR.")).toBeInTheDocument();
  });

  it("draws every run as a column of gates and marks the one clients see", async () => {
    stubApi(routes());
    renderAt("/");
    const ribbon = await screen.findByRole("region", { name: "Gates of the last runs" });
    const table = within(ribbon).getByRole("table");
    const runLinks = within(table).getAllByRole("link");
    expect(runLinks).toHaveLength(fx.runs.length);
    expect(runLinks[runLinks.length - 1]).toHaveAttribute("href", `/runs/${fx.runs[0]!.run_id}`);
    const unplaced = within(table).getByRole("row", { name: /Unplaced money/ });
    expect(within(unplaced).getAllByText("warned")).toHaveLength(fx.runs.length);
    const drift = within(table).getByRole("row", { name: /NAV drift/ });
    expect(within(drift).getByText("did not run")).toBeInTheDocument(); // the first run had nothing to compare with
    expect(within(table).getAllByText("this run")).toHaveLength(1);
  });

  it("separates booked money from money the bank has not booked yet", async () => {
    stubApi(routes());
    renderAt("/");
    const meter = await screen.findByRole("img", {
      name: /529,620 EUR booked, 158,040 EUR arrived but not yet booked/,
    });
    expect(meter).toBeInTheDocument();
    expect(screen.getAllByText("not booked").length).toBe(fx.overview.cash_now.length);
  });

  it("links each kind of break to the filtered queue", async () => {
    stubApi(routes());
    renderAt("/");
    const table = await screen.findByRole("region", { name: "Open breaks by kind" });
    expect(within(table).getByRole("link", { name: "Paid twice" })).toHaveAttribute(
      "href",
      "/breaks?kind=payment_duplicate",
    );
    expect(within(table).getByText("174")).toBeInTheDocument();
  });

  it("says when the newest run did not publish", async () => {
    const o = clone(fx.overview);
    o.latest_run = { ...o.latest_run, run_id: "20261026_200000000000", status: "blocked" };
    stubApi({ ...routes(), "GET /api/overview": o });
    renderAt("/");
    expect(await screen.findByText(/is blocked; clients keep seeing the published one/)).toBeInTheDocument();
  });

  it("shows a skeleton while loading", async () => {
    let release: (v: Response) => void = () => {};
    stubApi({ ...routes(), "GET /api/overview": () => new Promise<Response>((r) => (release = r)) });
    renderAt("/");
    expect(await screen.findByRole("status", { name: "Loading today's numbers" })).toBeInTheDocument();
    release(json(fx.overview));
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("What clients see");
  });

  it("says what failed and retries", async () => {
    let fail = true;
    stubApi({
      ...routes(),
      "GET /api/overview": () =>
        fail ? problem(503, "Nothing published yet", "Run `pmd run` first.") : json(fx.overview),
    });
    renderAt("/");
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Nothing published yet");
    expect(alert).toHaveTextContent("Run `pmd run` first.");
    fail = false;
    await userEvent.click(within(alert).getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("What clients see");
  });

  it("explains an unreachable API", async () => {
    stubApi(routes());
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))),
    );
    renderAt("/");
    expect(await screen.findByRole("alert")).toHaveTextContent("The platform API cannot be reached");
  });

  it("asks for the API token when the API wants one and sends it from then on", async () => {
    const calls = stubApi({
      ...routes(),
      "GET /api/overview": (_u: string, init?: RequestInit) =>
        (init?.headers as Record<string, string>)["authorization"] === "Bearer s3cret"
          ? json(fx.overview)
          : problem(401, "a valid bearer token is required"),
    });
    renderAt("/");
    await userEvent.type(await screen.findByLabelText("API token"), "s3cret");
    await userEvent.click(screen.getByRole("button", { name: "Use token" }));
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("What clients see");
    expect(sessionStorage.getItem("pmd.token")).toBe("s3cret");
    expect(calls.at(-1)!.headers["authorization"]).toBe("Bearer s3cret");
  });
});

describe("the role the console acts as", () => {
  it("sends the chosen role and name with every request", async () => {
    const calls = stubApi(routes());
    renderAt("/");
    await screen.findByRole("heading", { level: 1 });
    expect(calls[0]!.headers["x-pmd-role"]).toBe("analyst");
    await userEvent.selectOptions(screen.getByLabelText("Acting as"), "operations");
    await userEvent.type(screen.getByLabelText("Your name"), "Mia Ops");
    await waitFor(() => expect(sessionStorage.getItem("pmd.actor")).toBe("Mia Ops"));
    expect(sessionStorage.getItem("pmd.role")).toBe("operations");
    await waitFor(() => expect(calls.at(-1)!.headers["x-pmd-role"]).toBe("operations"));
  });
});

describe("breaks", () => {
  it("lists the queue and filters it through the address", async () => {
    const calls = stubApi(routes());
    renderAt("/breaks");
    const table = await screen.findByRole("region", { name: "Breaks" });
    expect(within(table).getAllByRole("row")).toHaveLength(Math.min(fx.breaks.length, 50) + 1);
    await userEvent.click(screen.getByRole("radio", { name: "Fund accounting" }));
    await waitFor(() => expect(calls.at(-1)!.path).toBe("/api/breaks?owner=fund_accounting&status=open"));
    await userEvent.selectOptions(screen.getByLabelText("Kind"), "statement_late");
    await waitFor(() =>
      expect(calls.at(-1)!.path).toBe("/api/breaks?kind=statement_late&owner=fund_accounting&status=open"),
    );
  });

  it("explains an empty filter and offers the way back", async () => {
    stubApi({ ...routes(), "GET /api/breaks?kind=payment_over&status=open": [] });
    renderAt("/breaks?kind=payment_over");
    expect(await screen.findByRole("heading", { name: "Nothing open here" })).toBeInTheDocument();
    expect(screen.getByText("No paid too much break matches these filters.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show every open break" }));
    expect(await screen.findByRole("region", { name: "Breaks" })).toBeInTheDocument();
  });

  it("lets an analyst read a break but not act on it", async () => {
    const calls = stubApi(routes());
    renderAt("/breaks");
    const table = await screen.findByRole("region", { name: "Breaks" });
    await userEvent.click(within(table).getAllByRole("button", { name: /^Act on/ })[0]!);
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(/Analysts read the queue/)).toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: "Resolve" })).not.toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(0);
  });

  it("lets operations resolve a break with a note", async () => {
    const target = fx.breaks[0]!;
    const calls = stubApi({
      ...routes(),
      [`POST /api/breaks/${target.break_id}/actions`]: {
        ...target,
        last_action: "resolve",
        last_actor: "Mia Ops",
        status: "resolved",
      },
    });
    actAs("operations", "Mia Ops");
    renderAt("/breaks");
    const table = await screen.findByRole("region", { name: "Breaks" });
    await userEvent.click(within(table).getAllByRole("button", { name: /^Act on/ })[0]!);
    const dialog = screen.getByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Resolve" }));
    expect(within(dialog).getByText("Write at least 3 characters.")).toBeInTheDocument();
    await userEvent.type(within(dialog).getByLabelText("Note"), "Client topped up on 27 Oct");
    await userEvent.click(within(dialog).getByRole("button", { name: "Resolve" }));
    expect(await within(dialog).findByText(/Resolved by Mia Ops/)).toBeInTheDocument();
    const post = calls.find((c) => c.method === "POST")!;
    expect(post.body).toEqual({ action: "resolve", note: "Client topped up on 27 Oct" });
    expect(post.headers["x-pmd-actor"]).toBe("Mia Ops");
  });

  it("shows the API's refusal in the dialog", async () => {
    const target = fx.breaks[0]!;
    stubApi({
      ...routes(),
      [`POST /api/breaks/${target.break_id}/actions`]: problem(
        403,
        "only operations and fund accounting act on breaks",
      ),
    });
    actAs("operations");
    renderAt("/breaks");
    const table = await screen.findByRole("region", { name: "Breaks" });
    await userEvent.click(within(table).getAllByRole("button", { name: /^Act on/ })[0]!);
    const dialog = screen.getByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("Note"), "checked");
    await userEvent.click(within(dialog).getByRole("button", { name: "Resolve" }));
    expect(await within(dialog).findByText(/only operations and fund accounting/)).toBeInTheDocument();
  });

  it("closes the dialog with Escape and returns focus", async () => {
    stubApi(routes());
    renderAt("/breaks");
    const table = await screen.findByRole("region", { name: "Breaks" });
    const button = within(table).getAllByRole("button", { name: /^Act on/ })[0]!;
    await userEvent.click(button);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(button).toHaveFocus();
  });
});

describe("funds", () => {
  it("groups the target funds by feeder and marks estimates", async () => {
    stubApi(routes());
    renderAt("/funds");
    const pe = await screen.findByRole("region", { name: "Target funds of Private Equity V" });
    expect(within(pe).getByRole("link", { name: "Kestrel European Buyout IV" })).toHaveAttribute(
      "href",
      "/funds/KES4",
    );
    expect(within(pe).getByText("restated 1 time")).toBeInTheDocument();
    expect(screen.getAllByText("statement not yet due").length).toBeGreaterThan(0);
  });

  it("filters by feeder", async () => {
    stubApi(routes());
    renderAt("/funds?feeder=PD1");
    expect(await screen.findByRole("region", { name: "Target funds of Private Debt I" })).toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: "Target funds of Private Equity V" }),
    ).not.toBeInTheDocument();
  });

  it("shows a fund's quarters, its restatement and every statement version", async () => {
    stubApi(routes());
    renderAt("/funds/KES4");
    expect(
      await screen.findByRole("heading", { level: 1, name: "Kestrel European Buyout IV" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "NAV by quarter today, 1 estimated, 1 restated." }),
    ).toBeInTheDocument();
    const restated = screen.getByRole("region", { name: "Restated quarters" });
    expect(within(restated).getByText("-6.1 %")).toBeInTheDocument();
    const versions = screen.getByRole("region", { name: "Statement versions received" });
    expect(within(versions).getByText("2 of 2")).toBeInTheDocument();
    expect(within(versions).getAllByText("15 Jan 2026")).toHaveLength(2); // v1 replaced, v2 known from
  });

  it("shows what the platform knew on an earlier day", async () => {
    const calls = stubApi(routes());
    renderAt("/funds/KES4");
    await screen.findByRole("heading", { level: 1, name: "Kestrel European Buyout IV" });
    await userEvent.click(screen.getByRole("radio", { name: "As known on" }));
    // the default is the day before the restatement arrived
    expect(
      await screen.findByRole("img", { name: /as known on 14 Jan 2026: 6 of 10 quarters/ }),
    ).toBeInTheDocument();
    expect(calls.at(-1)!.path).toBe("/api/funds/KES4?known_at=2026-01-14");
    fireEvent.change(screen.getByLabelText("Known on"), { target: { value: "2026-02-01" } });
    expect(
      await screen.findByRole("img", { name: /as known on 1 Feb 2026: 6 of 10 quarters/ }),
    ).toBeInTheDocument();
  });

  it("says when a fund does not exist", async () => {
    stubApi({ ...routes(), "GET /api/funds/NOPE": problem(404, "no fund NOPE") });
    renderAt("/funds/NOPE");
    expect(await screen.findByRole("alert")).toHaveTextContent("no fund NOPE");
  });
});

describe("clients", () => {
  it("lists clients by key and pages through them", async () => {
    const calls = stubApi(routes());
    renderAt("/clients");
    const table = await screen.findByRole("region", { name: "Clients" });
    expect(within(table).getAllByRole("row")).toHaveLength(fx.clients.rows.length + 1);
    expect(screen.getByText(`1 to 25 of ${fx.clients.total}`)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(calls.at(-1)!.path).toBe("/api/clients?limit=25&offset=25"));
  });

  it("searches by key after typing pauses", async () => {
    const calls = stubApi(routes());
    renderAt("/clients");
    await screen.findByRole("region", { name: "Clients" });
    await userEvent.type(screen.getByLabelText("Find a client key"), "BD61");
    await waitFor(() => expect(calls.at(-1)!.path).toBe("/api/clients?q=bd61&limit=25&offset=0"));
    expect(calls.filter((c) => c.path.includes("q=b&") || c.path.includes("q=bd&"))).toHaveLength(0);
  });

  it("says when no client matches", async () => {
    stubApi({ ...routes(), "GET /api/clients": { total: 0, rows: [] } });
    renderAt("/clients?q=zzz");
    expect(await screen.findByRole("heading", { name: "No client matches" })).toBeInTheDocument();
    expect(screen.getByText("No client key contains “zzz”.")).toBeInTheDocument();
  });

  it("shows a client's performance and what they own underneath", async () => {
    stubApi(routes());
    renderAt(`/clients/${fx.client.client.client_key}`);
    expect(await screen.findByRole("heading", { level: 1, name: "ck_bd61…2b6c4b" })).toBeInTheDocument();
    const perf = screen.getByRole("region", { name: "Performance by feeder" });
    expect(within(perf).getByRole("rowheader", { name: /Private Debt I/ })).toBeInTheDocument();
    expect(within(perf).getByText("3.6 %")).toBeInTheDocument();
    const look = screen.getByRole("region", { name: "Look-through to target funds" });
    expect(within(look).getByRole("link", { name: "Crestline Direct Lending IV" })).toHaveAttribute(
      "href",
      "/funds/CRE4",
    );
    expect(screen.getByText("The latest 12 of 31.")).toBeInTheDocument();
  });

  it("does not let an analyst see who a client is", async () => {
    const calls = stubApi(routes());
    renderAt(`/clients/${fx.client.client.client_key}`);
    await userEvent.click(await screen.findByRole("button", { name: "See who this is" }));
    expect(
      within(screen.getByRole("dialog")).getByText(/Only operations can see who a client is/),
    ).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(0);
  });

  it("lets operations see who a client is with a reason", async () => {
    const key = fx.client.client.client_key;
    const calls = stubApi({
      ...routes(),
      [`POST /api/clients/${key}/reveal`]: {
        client_key: key,
        client_id: "C-000123",
        first_name: "Erika",
        last_name: "Beispiel",
        email: "erika@example.org",
        phone: "+49 30 000000",
        city: "Berlin",
        logged: true,
      },
    });
    actAs("operations", "Mia Ops");
    renderAt(`/clients/${key}`);
    await userEvent.click(await screen.findByRole("button", { name: "See who this is" }));
    const dialog = screen.getByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("Reason"), "Ticket 4711: address change");
    await userEvent.click(within(dialog).getByRole("button", { name: "Show identity" }));
    expect(await within(dialog).findByText("Erika Beispiel")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({ reason: "Ticket 4711: address change" });
    await userEvent.click(within(dialog).getByRole("button", { name: "Close" }));
    await waitFor(() => expect(screen.queryByText("Erika Beispiel")).not.toBeInTheDocument());
  });
});

describe("data health", () => {
  it("shows feeds, quarantine, duplicates, holds and erasures", async () => {
    stubApi(routes());
    renderAt("/health");
    const gp = await screen.findByRole("region", { name: "GP statements" });
    expect(within(gp).getByRole("row", { name: /Halvard Mid-Market II/ })).toHaveTextContent("Late");
    expect(screen.getByText("gp_statements/20251209_lumen-ventures_4e5307.pdf")).toBeInTheDocument();
    expect(screen.getByText("Duplicate, ignored")).toBeInTheDocument();
    expect(
      screen.getByRole("article", { name: "Orion Global Partners IX, 30 Jun 2026" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Kept for retention")).toBeInTheDocument();
  });

  it("lets fund accounting release a held statement", async () => {
    const hold = fx.freshness.holds[0]!;
    const calls = stubApi({
      ...routes(),
      [`POST /api/statements/${hold.file_id}/release`]: {
        file_id: hold.file_id,
        released_by: "Fia Accounting",
        takes_effect: "next run",
      },
    });
    actAs("fund_accounting", "Fia Accounting");
    renderAt("/health");
    await userEvent.click(await screen.findByRole("button", { name: "Review the hold" }));
    const dialog = screen.getByRole("dialog");
    await userEvent.type(
      within(dialog).getByLabelText("Why the statement is right"),
      "GP confirmed by email",
    );
    await userEvent.click(within(dialog).getByRole("button", { name: "Release statement" }));
    expect(await within(dialog).findByText(/Released by Fia Accounting/)).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({ note: "GP confirmed by email" });
  });

  it("says when nothing was rejected or held", async () => {
    const f = clone(fx.freshness);
    f.quarantine = [];
    f.duplicates = [];
    f.holds = [];
    f.erasures = [];
    stubApi({ ...routes(), "GET /api/freshness": f });
    renderAt("/health");
    expect(await screen.findByRole("heading", { name: "Nothing rejected" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "No statement is held" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "No erasure requests" })).toBeInTheDocument();
  });
});

describe("runs", () => {
  it("lists runs and opens one with its gates", async () => {
    stubApi(routes());
    renderAt("/runs");
    const table = await screen.findByRole("region", { name: "Runs" });
    await userEvent.click(within(table).getByRole("link", { name: fx.run.run_id }));
    expect(
      await screen.findByRole("heading", { level: 1, name: `Run ${fx.run.run_id}` }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Warned").length).toBe(fx.run.gates.filter((g) => !g.passed).length);
    expect(screen.getByRole("heading", { name: "Identical to what clients saw" })).toBeInTheDocument();
  });

  it("shows what changed and how a drift-only block is approved", async () => {
    const r = clone(fx.run);
    r.status = "blocked";
    r.gates = r.gates.map((g) =>
      g.name === "nav_drift" ? { ...g, passed: false, detail: "ORI9 2026-06-30: 11024022 -> 10691 EUR" } : g,
    );
    r.diff!["fct_fund_nav"] = {
      ...r.diff!["fct_fund_nav"],
      changed: 1,
      totals_changed: { nav_eur: { old: 100, new: 90 } },
    };
    stubApi({ ...routes(), [`GET /api/runs/${r.run_id}`]: r });
    renderAt(`/runs/${r.run_id}`);
    expect(await screen.findByText(/Only the drift gate stopped this build/)).toBeInTheDocument();
    expect(screen.getByText("ORI9 2026-06-30: 11024022 -> 10691 EUR")).toBeInTheDocument();
    const diff = screen.getByRole("region", { name: "What changed against the published build" });
    expect(within(diff).getByRole("rowheader", { name: "fct_fund_nav" })).toBeInTheDocument();
    expect(within(diff).getByText("nav_eur: 100 to 90")).toBeInTheDocument();
  });
});

describe("lineage", () => {
  it("lights up what a model is built from and what it feeds", async () => {
    stubApi(routes());
    renderAt("/lineage");
    const node = await screen.findByRole("button", { name: "int_statement_versions" });
    await userEvent.click(node);
    expect(node).toHaveAttribute("aria-pressed", "true");
    expect(
      screen.getByRole("button", { name: /stg_statements, feeds the selected model/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /fct_fund_nav, built from the selected model/ }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "int_statement_versions" })).toBeInTheDocument();
  });
});

describe("addresses", () => {
  it("explains an address that does not exist", async () => {
    stubApi(routes());
    renderAt("/nowhere");
    expect(
      await screen.findByRole("heading", { name: "There is nothing at this address" }),
    ).toBeInTheDocument();
  });
});
