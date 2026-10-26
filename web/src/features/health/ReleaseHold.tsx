import { type FormEvent, useState } from "react";

import type { Hold } from "../../shared/api/types";
import { date, pct } from "../../shared/lib/format";
import { canRelease, useSession } from "../../shared/lib/useSession";
import { Amount, Button, Notice } from "../../shared/ui";
import { Dialog } from "../../shared/ui/Dialog";
import { Field } from "../../shared/ui/Field";
import { useRelease } from "./api";
import styles from "./Health.module.css";

const MIN_NOTE = 5;

/** A held statement, what its checks found, and (for fund accounting) the release that lets the next run use it. */
export function HoldCard({ hold }: { hold: Hold }) {
  const { role } = useSession();
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [tried, setTried] = useState(false);
  const release = useRelease();
  const tooShort = note.trim().length < MIN_NOTE;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setTried(true);
    if (!tooShort) release.mutate({ fileId: hold.file_id, note: note.trim() });
  };
  const close = () => {
    setOpen(false);
    setTried(false);
  };

  return (
    <article className={styles.hold} aria-labelledby={`hold-${hold.file_id}`}>
      <h3 id={`hold-${hold.file_id}`}>
        {hold.fund_name}, {date(hold.period_end)}
      </h3>
      <p className={styles.reason}>{hold.hold_reason}</p>
      <dl className={styles.holdFacts}>
        <div>
          <dt>NAV in the statement</dt>
          <dd>
            <Amount value={hold.nav} currency={hold.currency} digits={2} />
          </dd>
        </div>
        <div>
          <dt>Previous quarter</dt>
          <dd>
            {hold.prev_nav ? <Amount value={hold.prev_nav} currency={hold.currency} digits={2} /> : "none"}
          </dd>
        </div>
        <div>
          <dt>Move not explained by cash flows</dt>
          <dd>{hold.unexplained_move ? pct(hold.unexplained_move) : "n/a"}</dd>
        </div>
        <div>
          <dt>Received</dt>
          <dd>
            {date(hold.received_on)}, version {hold.version}
          </dd>
        </div>
      </dl>
      {release.isSuccess ? (
        <Notice>Released by {release.data.released_by}. The next run uses this statement.</Notice>
      ) : (
        <Button onClick={() => setOpen(true)}>Review the hold</Button>
      )}
      <Dialog open={open} title={`Release ${hold.fund} ${date(hold.period_end)}?`} onClose={close}>
        <p>
          Releasing tells the next run to use this statement as it is. Until then the quarter is estimated
          from bank flows. Ask the manager for a corrected statement if the figures are wrong; a new version
          replaces this one on its own.
        </p>
        {release.isSuccess ? (
          <>
            <Notice>Released by {release.data.released_by}. The next run uses this statement.</Notice>
            <Button variant="primary" onClick={close}>
              Close
            </Button>
          </>
        ) : canRelease(role) ? (
          <form className={styles.form} onSubmit={submit} noValidate>
            <Field
              label="Why the statement is right"
              hint="For example who at the manager confirmed the figures."
              error={
                tried && tooShort
                  ? `Write at least ${MIN_NOTE} characters.`
                  : release.error
                    ? String(release.error.message)
                    : undefined
              }
            >
              {(p) => (
                <textarea {...p} value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} />
              )}
            </Field>
            <div className={styles.buttons}>
              <Button type="submit" variant="primary" busy={release.isPending}>
                Release statement
              </Button>
              <Button variant="quiet" onClick={close}>
                Keep it held
              </Button>
            </div>
          </form>
        ) : (
          <>
            <Notice>
              Only fund accounting releases a held statement. Switch the role at the top of the page.
            </Notice>
            <Button onClick={close}>Close</Button>
          </>
        )}
      </Dialog>
    </article>
  );
}
