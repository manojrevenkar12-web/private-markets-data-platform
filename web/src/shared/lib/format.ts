/** Formatting in one place, so a number reads the same on every screen. */

const LOCALE = "en-GB";

export const num = (x: unknown): number => (x == null || x === "" ? NaN : Number(x));

export function eur(x: unknown, digits = 0): string {
  const n = num(x);
  return Number.isNaN(n)
    ? "n/a"
    : `${n.toLocaleString(LOCALE, { minimumFractionDigits: digits, maximumFractionDigits: digits })} EUR`;
}

/** Large sums in millions: "61.7 m EUR". */
export function eurM(x: unknown): string {
  const n = num(x);
  if (Number.isNaN(n)) return "n/a";
  if (Math.abs(n) < 1_000_000) return eur(n);
  return `${(n / 1_000_000).toLocaleString(LOCALE, { maximumFractionDigits: 1, minimumFractionDigits: 1 })} m EUR`;
}

export function pct(x: unknown, digits = 1): string {
  const n = num(x);
  return Number.isNaN(n)
    ? "n/a"
    : `${(n * 100).toLocaleString(LOCALE, { minimumFractionDigits: digits, maximumFractionDigits: digits })} %`;
}

export function multiple(x: unknown): string {
  const n = num(x);
  return Number.isNaN(n)
    ? "n/a"
    : `${n.toLocaleString(LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}x`;
}

export const int = (x: unknown) => {
  const n = num(x);
  return Number.isNaN(n) ? "n/a" : Math.round(n).toLocaleString(LOCALE);
};

export function date(iso: string | null | undefined): string {
  if (!iso) return "not yet";
  const d = new Date(`${iso.slice(0, 10)}T12:00:00Z`);
  return d.toLocaleDateString(LOCALE, { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

export function time(iso: string | null | undefined): string {
  if (!iso) return "not yet";
  return new Date(iso).toLocaleString(LOCALE, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Berlin",
  });
}

export function quarter(iso: string | null | undefined): string {
  if (!iso) return "n/a";
  const m = Number(iso.slice(5, 7));
  return `Q${Math.ceil(m / 3)} ${iso.slice(0, 4)}`;
}

export const humanise = (s: string) => {
  const t = s.replace(/_/g, " ");
  return t.charAt(0).toUpperCase() + t.slice(1);
};

/** A client key, shortened for tables: ck_bd61…2b6c4b. */
export const shortKey = (k: string | null | undefined) => (k ? `${k.slice(0, 7)}…${k.slice(-6)}` : "");
