import { type FormEvent, useState } from "react";

import { canReveal, useSession } from "../../shared/lib/useSession";
import { Button, Notice } from "../../shared/ui";
import { Dialog } from "../../shared/ui/Dialog";
import { Field } from "../../shared/ui/Field";
import { useReveal } from "./api";
import styles from "./Clients.module.css";

const MIN_REASON = 5;

/**
 * Seeing who a client is. The API checks the role in the database, needs a reason and logs the attempt either
 * way; the identity is shown once, in this panel, and is gone when it closes.
 */
export function Reveal({ clientKey }: { clientKey: string }) {
  const { role } = useSession();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const reveal = useReveal(clientKey);
  const tooShort = reason.trim().length < MIN_REASON;

  const close = () => {
    setOpen(false);
    setReason("");
    setTried(false);
    reveal.reset();
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setTried(true);
    if (!tooShort) reveal.mutate(reason.trim());
  };

  return (
    <>
      <Button onClick={() => setOpen(true)}>See who this is</Button>
      <Dialog open={open} title="See who this client is" onClose={close}>
        {reveal.isSuccess ? (
          <>
            <dl className={styles.identity}>
              <div>
                <dt>Name</dt>
                <dd>
                  {reveal.data.first_name} {reveal.data.last_name}
                </dd>
              </div>
              <div>
                <dt>Client id</dt>
                <dd>{reveal.data.client_id}</dd>
              </div>
              <div>
                <dt>Email</dt>
                <dd>{reveal.data.email}</dd>
              </div>
              <div>
                <dt>Phone</dt>
                <dd>{reveal.data.phone}</dd>
              </div>
              <div>
                <dt>City</dt>
                <dd>{reveal.data.city}</dd>
              </div>
            </dl>
            <Notice>Logged with your reason. Closing this panel clears it from the screen.</Notice>
            <Button variant="primary" onClick={close}>
              Close
            </Button>
          </>
        ) : !canReveal(role) ? (
          <>
            <p>
              Only operations can see who a client is. Analysts and fund accounting work with the key; the
              numbers are the same.
            </p>
            <Button onClick={close}>Close</Button>
          </>
        ) : (
          <form className={styles.form} onSubmit={submit} noValidate>
            <p>Your name, your reason and the time are logged. Data protection reviews the log.</p>
            <Field
              label="Reason"
              hint="For example the ticket you are answering."
              error={tried && tooShort ? `Write at least ${MIN_REASON} characters.` : reveal.error?.message}
            >
              {(p) => (
                <input {...p} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} />
              )}
            </Field>
            <div className={styles.buttons}>
              <Button type="submit" variant="primary" busy={reveal.isPending}>
                Show identity
              </Button>
              <Button variant="quiet" onClick={close}>
                Cancel
              </Button>
            </div>
          </form>
        )}
      </Dialog>
    </>
  );
}
