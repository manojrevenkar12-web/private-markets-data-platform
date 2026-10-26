import { motion } from "framer-motion";

import type { CashCall } from "../../shared/api/types";
import { eur, num } from "../../shared/lib/format";
import { MOTION } from "../../shared/theme/tokens";
import styles from "./Today.module.css";

/**
 * One capital call: what the custodian has booked, what the instant feed says arrived since the last bank
 * statement (provisional until booked), and what is still outstanding.
 */
export function CallMeter({ call }: { call: CashCall }) {
  const booked = Math.max(num(call.booked_eur), 0);
  const arrived = Math.max(num(call.arrived_since_statement_eur), 0);
  const outstanding = Math.max(num(call.outstanding_eur), 0);
  const whole = Math.max(num(call.expected_eur), booked + arrived + outstanding, 1);
  const share = (x: number) => `${(x / whole) * 100}%`;
  const label = `${eur(booked)} booked, ${eur(arrived)} arrived but not yet booked, ${eur(outstanding)} outstanding of ${eur(call.expected_eur)}`;
  return (
    <div className={styles.meter} role="img" aria-label={label}>
      <motion.span
        className={styles.booked}
        initial={{ width: 0 }}
        animate={{ width: share(booked) }}
        transition={{ duration: MOTION.draw, ease: MOTION.ease }}
      />
      <motion.span
        className={styles.arrived}
        initial={{ width: 0 }}
        animate={{ width: share(arrived) }}
        transition={{ duration: MOTION.draw, ease: MOTION.ease, delay: MOTION.quick }}
      />
    </div>
  );
}
