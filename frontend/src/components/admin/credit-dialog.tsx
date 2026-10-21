"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field, FormError } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { splitErrors } from "@/lib/forms";
import type { AdminUser } from "@/lib/types";

/** Grant (positive) or remove (negative) credits, with a required reason. */
export function CreditDialog({ user, onClose, onDone }: { user: AdminUser; onClose: () => void; onDone: () => void }) {
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const n = Number(amount);
    const local: Record<string, string> = {};
    if (!Number.isInteger(n) || n === 0) local.amount = "Enter a whole number other than 0 (negative removes credits).";
    if (reason.trim().length < 3) local.reason = "Give a reason of at least 3 characters.";
    if (Object.keys(local).length) return setErrors(local);
    setBusy(true);
    setErrors({});
    setFormError(null);
    try {
      await api.admin.adjustCredits(user.id, n, reason.trim());
      onDone();
      onClose();
    } catch (error) {
      const split = splitErrors(error, ["amount", "reason"]);
      setErrors(split.fieldErrors);
      setFormError(split.formError);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()} title="Adjust credits" size="sm"
      description={`${user.email} · current balance ${user.credit_balance}`}>
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <FormError message={formError} />
        <Field label="Amount" required error={errors.amount} help="Positive grants credits; negative removes them.">
          {(p) => <Input {...p} type="number" step={1} value={amount} onChange={(e) => setAmount(e.target.value)} autoFocus />}
        </Field>
        <Field label="Reason" required error={errors.reason} help="Recorded in the ledger and audit log.">
          {(p) => <Input {...p} maxLength={255} value={reason} onChange={(e) => setReason(e.target.value)} />}
        </Field>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={busy}>Apply</Button>
        </div>
      </form>
    </Dialog>
  );
}
