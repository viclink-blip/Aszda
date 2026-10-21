"use client";

import { Search } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/dialog";
import { ErrorState } from "@/components/ui/error-state";
import { Input } from "@/components/ui/input";
import { Pagination } from "@/components/ui/pagination";
import { LoadingRows } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/use-api";
import { useDebounced } from "@/hooks/use-debounced";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDate, formatNumber } from "@/lib/format";
import type { AdminUser } from "@/lib/types";
import { CreditDialog } from "./credit-dialog";

const PAGE_SIZE = 25;

type PendingChange = { user: AdminUser; change: { is_active?: boolean; role?: "user" | "admin" }; label: string };

export function AdminUsers() {
  const { user: me } = useAuth();
  const toast = useToast();
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [pending, setPending] = useState<PendingChange | null>(null);
  const [crediting, setCrediting] = useState<AdminUser | null>(null);
  const q = useDebounced(query.trim());
  const { data, error, reload } = useApi(() => api.admin.users({ q, limit: PAGE_SIZE, offset }), [q, offset]);

  const apply = async () => {
    if (!pending) return;
    try {
      await api.admin.updateUser(pending.user.id, pending.change);
    } catch (err) {
      throw new Error(errorMessage(err));
    }
    toast.success("User updated");
    await reload();
  };

  return (
    <>
      <div className="relative mb-4 max-w-md">
        <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-subtle" aria-hidden />
        <Input type="search" className="pl-9" aria-label="Search users by email or name" placeholder="Search by email or name"
          value={query} onChange={(e) => { setQuery(e.target.value); setOffset(0); }} />
      </div>
      {error && !data ? <ErrorState error={error} onRetry={reload} /> : !data ? <LoadingRows rows={5} /> : (
        <>
          <div className="overflow-x-auto rounded-xl border border-line bg-surface">
            <table className="w-full min-w-[48rem] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-subtle uppercase">
                  <th scope="col" className="px-4 py-2.5 font-medium">User</th>
                  <th scope="col" className="px-3 py-2.5 font-medium">Status</th>
                  <th scope="col" className="px-3 py-2.5 text-right font-medium">Credits</th>
                  <th scope="col" className="px-3 py-2.5 font-medium">Joined</th>
                  <th scope="col" className="px-4 py-2.5 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {data.items.map((u) => {
                  const self = u.id === me?.id;
                  return (
                    <tr key={u.id}>
                      <td className="px-4 py-3">
                        <p className="font-medium text-fg">{u.display_name || "—"}</p>
                        <p className="text-xs text-subtle">{u.email}</p>
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex flex-wrap gap-1">
                          {u.role === "admin" && <Badge tone="accent">Admin</Badge>}
                          <Badge tone={u.is_active ? "success" : "danger"}>{u.is_active ? "Active" : "Deactivated"}</Badge>
                          {!u.email_verified && <Badge tone="warning">Unverified</Badge>}
                        </div>
                      </td>
                      <td className="px-3 py-3 text-right font-mono tabular-nums">{formatNumber(u.credit_balance)}</td>
                      <td className="px-3 py-3 text-muted">{formatDate(u.created_at)}</td>
                      <td className="px-4 py-3">
                        <div className="flex justify-end gap-1.5">
                          <Button size="sm" variant="outline" onClick={() => setCrediting(u)}>Credits</Button>
                          <Button size="sm" variant="ghost" disabled={self}
                            onClick={() => setPending({ user: u, change: { role: u.role === "admin" ? "user" : "admin" }, label: u.role === "admin" ? "Remove admin role" : "Make admin" })}>
                            {u.role === "admin" ? "Remove admin" : "Make admin"}
                          </Button>
                          <Button size="sm" variant="ghost" disabled={self} className={u.is_active ? "text-danger" : ""}
                            onClick={() => setPending({ user: u, change: { is_active: !u.is_active }, label: u.is_active ? "Deactivate" : "Activate" })}>
                            {u.is_active ? "Deactivate" : "Activate"}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {data.items.length === 0 && <p className="p-6 text-center text-sm text-muted">No users found.</p>}
          </div>
          <Pagination offset={offset} limit={PAGE_SIZE} total={data.total} onChange={setOffset} />
        </>
      )}
      <ConfirmDialog
        open={pending !== null}
        onOpenChange={(o) => !o && setPending(null)}
        title={`${pending?.label ?? ""}?`}
        description={<>This applies to <strong className="text-fg">{pending?.user.email}</strong> and signs them out of all sessions.</>}
        confirmLabel={pending?.label}
        destructive={pending?.change.is_active === false}
        onConfirm={apply}
      />
      {crediting && <CreditDialog user={crediting} onClose={() => setCrediting(null)} onDone={() => { toast.success("Credits adjusted"); void reload(); }} />}
    </>
  );
}
