import { motion } from "framer-motion";
import { useId } from "react";

import { eurM, num, quarter } from "../../shared/lib/format";
import { MOTION } from "../../shared/theme/tokens";
import styles from "./Funds.module.css";

export interface Bar {
  quarter_end: string;
  value: number | null; // EUR; null: nothing known for this quarter
  source: "statement" | "estimated" | "unknown";
  ghost?: number | null; // EUR the first version said, when the quarter was restated
}

const W = 64;
const H = 220;
const TOP = 16;
const BOTTOM = 28;
const LEFT = 56;
const BAR = 36;

function niceStep(max: number) {
  const raw = max / 4;
  const mag = 10 ** Math.floor(Math.log10(raw || 1));
  const n = raw / mag;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * mag;
}

/**
 * NAV per quarter in EUR. Statement figures are solid, carried-forward estimates hatched, a restated quarter
 * shows the first version as a dashed outline, and a quarter nothing was known for yet is an empty slot.
 */
export function NavChart({ bars, label }: { bars: Bar[]; label: string }) {
  const hatch = `hatch-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const max = Math.max(...bars.map((b) => Math.max(b.value ?? 0, b.ghost ?? 0)), 1);
  const step = niceStep(max);
  const top = Math.ceil(max / step) * step;
  const plot = H - TOP - BOTTOM;
  const y = (v: number) => TOP + plot - (v / top) * plot;
  const width = LEFT + bars.length * W;
  const ticks = Array.from({ length: Math.round(top / step) + 1 }, (_, i) => i * step);

  return (
    <figure className={styles.chart}>
      <svg
        viewBox={`0 0 ${width} ${H}`}
        role="img"
        aria-label={label}
        className={styles.svg}
        style={{ minWidth: `${width * 0.6}px`, maxWidth: `${width * 1.25}px` }}
      >
        <defs>
          <pattern
            id={hatch}
            width="6"
            height="6"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(45)"
          >
            <rect width="6" height="6" className={styles.hatchBack} />
            <line x1="0" y1="0" x2="0" y2="6" className={styles.hatchLine} />
          </pattern>
        </defs>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={LEFT} x2={width} y1={y(t)} y2={y(t)} className={styles.grid} />
            <text x={LEFT - 8} y={y(t)} className={styles.tick} textAnchor="end" dominantBaseline="middle">
              {t === 0 ? "0" : eurM(t).replace(" EUR", "")}
            </text>
          </g>
        ))}
        {bars.map((b, i) => {
          const x = LEFT + i * W + (W - BAR) / 2;
          const v = b.value ?? 0;
          return (
            <g key={b.quarter_end}>
              <title>
                {quarter(b.quarter_end)}:{" "}
                {b.value == null
                  ? "nothing known yet"
                  : `${eurM(b.value)}${b.source === "estimated" ? ", estimated" : ""}`}
                {b.ghost != null ? `; first reported ${eurM(b.ghost)}` : ""}
              </title>
              {b.value == null ? (
                <rect x={x} y={y(0) - 4} width={BAR} height={4} className={styles.unknown} />
              ) : (
                <motion.rect
                  x={x}
                  width={BAR}
                  initial={{ y: y(0), height: 0 }}
                  animate={{ y: y(v), height: y(0) - y(v) }}
                  transition={{ duration: MOTION.move, ease: MOTION.ease, delay: i * MOTION.stagger }}
                  className={b.source === "estimated" ? styles.estimatedBar : styles.statementBar}
                  fill={b.source === "estimated" ? `url(#${hatch})` : undefined}
                />
              )}
              {b.ghost != null && (
                <rect
                  x={x - 3}
                  y={y(b.ghost)}
                  width={BAR + 6}
                  height={y(0) - y(b.ghost)}
                  className={styles.ghost}
                />
              )}
              <text x={x + BAR / 2} y={H - 8} className={styles.tick} textAnchor="middle">
                {quarter(b.quarter_end).replace(" 20", " ")}
              </text>
            </g>
          );
        })}
      </svg>
      <figcaption className={styles.key}>
        <span>
          <i className={styles.keyStatement} aria-hidden /> From a statement
        </span>
        <span>
          <i className={styles.keyEstimated} aria-hidden /> Estimated, carried forward from bank flows
        </span>
        <span>
          <i className={styles.keyGhost} aria-hidden /> What the first version said
        </span>
      </figcaption>
    </figure>
  );
}

export const toEur = (ccy: unknown, navCcy: unknown, navEur: unknown) => {
  const rate = num(navCcy) ? num(navEur) / num(navCcy) : 1;
  return num(ccy) * rate;
};
