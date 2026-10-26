import { type FormEvent, useState } from "react";

import { ApiError } from "../../shared/api/client";
import type { Break } from "../../shared/api/types";
import { eur, humanise, time } from "../../shared/lib/format";
import { canActOnBreaks, useSession } from "../../shared/lib/useSession";
import { Button, Notice } from "../../shared/ui";
import { Dialog } from "../../shared/ui/Dialog";
import { Field } from "../../shared/ui/Field";
import { Segmented } from "../../shared/ui/Segmented";
import { BREAK_KIND, OWNER } from "../../shared/theme/tokens";
import { type BreakActionKind, useBreakAction } from "./api";
import styles from "./Breaks.module.css";

const VERB: Record<BreakActionKind, string> = { resolve: "Resolve", reopen: "Reopen", note: "Add note" };
const DONE: Record<BreakActionKind, string> = { resolve: "Resolved", reopen: "Reopened", note: "Note added" };
const MIN_NOTE = 3;

/** Resolve, reopen or annotate one break. The action is kept across runs: the same break keeps its id. */
export function ActOnBreak({ item, onClose }: { item: Break | null; onClose: () => void }) {
  const { role, actor } = useSession();
  const mutation = useBreakAction();
  const [action, setAction] = useState<BreakActionKind>("resolve");
  const [note, setNote] = useState("");
  const [tried, setTried] = useState(false);
  const allowed = canActOnBreaks(role);
  const tooShort = note.trim().length < MIN_NOTE;

  const options: { value: BreakActionKind; label: string }[] =
    item?.status === "resolved"
      ? [
          { value: "reopen", label: VERB.reopen },
          { value: "note", label: VERB.note },
        ]
      : [
          { value: "resolve", label: VERB.resolve },
          { value: "note", label: VERB.note },
        ];
  const chosen = options.some((o) => o.value === action) ? action : options[0]!.value;

  const close = () => {
    mutation.reset();
    setNote("");
    setTried(false);
    onClose();
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setTried(true);
    if (tooShort || !item) return;
    mutation.mutate({ id: item.break_id, action: chosen, note: note.trim() });
  };

  const error =
    mutation.error instanceof ApiError
      ? mutation.error.message
      : mutation.error
        ? String(mutation.error)
        : null;

  return (
    <Dialog
      open={item !== null}
      title={item ? (BREAK_KIND[item.kind]?.label ?? humanise(item.kind)) : ""}
      onClose={close}
    >
      {item && (
        <>
          <dl className={styles.facts}>
            <div>
              <dt>Reference</dt>
              <dd>{item.reference ?? item.fund ?? "none"}</dd>
            </div>
            {item.expected_eur != null && (
              <div>
                <dt>Expected</dt>
                <dd>{eur(item.expected_eur, 2)}</dd>
              </div>
            )}
            {item.actual_eur != null && (
              <div>
                <dt>Received</dt>
                <dd>{eur(item.actual_eur, 2)}</dd>
              </div>
            )}
            <div>
              <dt>Owner</dt>
              <dd>{OWNER[item.owner] ?? item.owner}</dd>
            </div>
            <div>
              <dt>What the rule saw</dt>
              <dd>{item.detail}</dd>
            </div>
            {item.last_action_at && (
              <div>
                <dt>Last action</dt>
                <dd>
                  {humanise(item.last_action)} by {item.last_actor} on {time(item.last_action_at)}
                  {item.last_note ? `: ${item.last_note}` : ""}
                </dd>
              </div>
            )}
          </dl>
          {mutation.isSuccess ? (
            <>
              <Notice>
                {DONE[mutation.variables.action]} by {mutation.data.last_actor ?? actor}. The next run keeps
                it.
              </Notice>
              <Button variant="primary" onClick={close}>
                Close
              </Button>
            </>
          ) : !allowed ? (
            <>
              <Notice>
                Analysts read the queue. Switch to Operations or Fund accounting at the top of the page to act
                on a break.
              </Notice>
              <Button onClick={close}>Close</Button>
            </>
          ) : (
            <form className={styles.form} onSubmit={submit} noValidate>
              <Segmented label="What to do" options={options} value={chosen} onChange={setAction} />
              <Field
                label="Note"
                hint="What you did or found, for whoever looks next. It is kept with the break."
                error={tried && tooShort ? `Write at least ${MIN_NOTE} characters.` : error}
              >
                {(p) => (
                  <textarea {...p} value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} />
                )}
              </Field>
              <div className={styles.buttons}>
                <Button type="submit" variant="primary" busy={mutation.isPending}>
                  {VERB[chosen]}
                </Button>
                <Button variant="quiet" onClick={close}>
                  Cancel
                </Button>
              </div>
            </form>
          )}
        </>
      )}
    </Dialog>
  );
}
