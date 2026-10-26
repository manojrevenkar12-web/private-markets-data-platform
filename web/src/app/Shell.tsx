import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";

import { MOTION } from "../shared/theme/tokens";
import { SessionControls } from "./SessionControls";
import styles from "./Shell.module.css";

const NAV = [
  { to: "/", label: "Today", end: true },
  { to: "/breaks", label: "Breaks" },
  { to: "/funds", label: "Funds" },
  { to: "/clients", label: "Clients" },
  { to: "/health", label: "Data health" },
  { to: "/runs", label: "Runs" },
  { to: "/lineage", label: "Lineage" },
];

function active(pathname: string, to: string, end?: boolean) {
  return end ? pathname === to : pathname === to || pathname.startsWith(`${to}/`);
}

export function Shell({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  return (
    <div className={styles.shell}>
      <a className={styles.skip} href="#main">
        Skip to content
      </a>
      <header className={styles.top}>
        <div className={styles.bar}>
          <Link to="/" className={styles.brand}>
            <span className={styles.mark} aria-hidden />
            <span>
              <strong>Northlake fund data</strong>
              <span>Private markets operations</span>
            </span>
          </Link>
          <SessionControls />
        </div>
        <nav aria-label="Main" className={styles.nav}>
          <ul>
            {NAV.map((n) => {
              const on = active(pathname, n.to, n.end);
              return (
                <li key={n.to}>
                  <NavLink to={n.to} end={n.end} className={styles.link}>
                    {n.label}
                    {on && (
                      <motion.span
                        layoutId="nav-marker"
                        className={styles.marker}
                        transition={{ duration: MOTION.move, ease: MOTION.ease }}
                      />
                    )}
                  </NavLink>
                </li>
              );
            })}
          </ul>
        </nav>
      </header>
      <main id="main" className={styles.main}>
        {children}
      </main>
      <footer className={styles.footer}>
        Northlake Wealth is fictional; every client, fund and payment here is simulated.
      </footer>
    </div>
  );
}
