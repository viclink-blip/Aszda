"use client";

import { LogOut, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { PasswordInput } from "@/components/auth/password-input";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { ConfirmDialog, Dialog } from "@/components/ui/dialog";
import { Field, FormError } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, ApiError, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { focusFirstError } from "@/lib/forms";

/** Sign out everywhere, and permanent account deletion (password + typing DELETE). */
export function DangerZone() {
  const { clearSession } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const [signingOut, setSigningOut] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const signOutEverywhere = async () => {
    try {
      await api.auth.logoutAll();
    } catch (error) {
      throw new Error(errorMessage(error));
    }
    clearSession();
    toast.success("Signed out on every device");
    router.replace("/sign-in");
  };

  return (
    <Card>
      <CardHeader title="Security and account" />
      <CardBody className="flex flex-col gap-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-medium text-fg">Sign out everywhere</p>
            <p className="text-sm text-muted">Ends every session on every device, including this one.</p>
          </div>
          <Button variant="outline" onClick={() => setSigningOut(true)}><LogOut className="h-4 w-4" aria-hidden /> Sign out everywhere</Button>
        </div>
        <hr className="border-line" />
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-medium text-danger">Delete account</p>
            <p className="text-sm text-muted">Permanently deletes your account, projects, files and history.</p>
          </div>
          <Button variant="danger" onClick={() => setDeleting(true)}><Trash2 className="h-4 w-4" aria-hidden /> Delete account</Button>
        </div>
      </CardBody>
      <ConfirmDialog
        open={signingOut}
        onOpenChange={setSigningOut}
        title="Sign out on every device?"
        description="You will need to sign in again everywhere, including here."
        confirmLabel="Sign out everywhere"
        onConfirm={signOutEverywhere}
      />
      {deleting && <DeleteAccountDialog onClose={() => setDeleting(false)} />}
    </Card>
  );
}

function DeleteAccountDialog({ onClose }: { onClose: () => void }) {
  const { clearSession } = useAuth();
  const router = useRouter();
  const formRef = useRef<HTMLFormElement>(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (confirm !== "DELETE") {
      setErrors({ confirm: "Type DELETE in capital letters to confirm." });
      focusFirstError(formRef.current);
      return;
    }
    setBusy(true);
    setErrors({});
    setFormError(null);
    try {
      await api.me.deleteAccount(password, confirm);
      clearSession();
      router.replace("/");
    } catch (error) {
      if (error instanceof ApiError && error.code === "invalid_password") setErrors({ password: error.message });
      else setFormError(errorMessage(error));
      focusFirstError(formRef.current);
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()} title="Delete your account?" size="sm"
      description="This cannot be undone. All projects, characters, scenes, files and generation history are deleted.">
      <form ref={formRef} onSubmit={submit} noValidate className="flex flex-col gap-4">
        <FormError message={formError} />
        <Field label="Your password" error={errors.password}>
          {(p) => <PasswordInput {...p} autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />}
        </Field>
        <Field label={<>Type <span className="font-mono">DELETE</span> to confirm</>} error={errors.confirm}>
          {(p) => <Input {...p} autoComplete="off" value={confirm} onChange={(e) => setConfirm(e.target.value)} />}
        </Field>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="danger" loading={busy} disabled={!password || confirm !== "DELETE"}>Delete my account</Button>
        </div>
      </form>
    </Dialog>
  );
}
