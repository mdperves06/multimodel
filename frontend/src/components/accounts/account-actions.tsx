"use client";

import { Loader2Icon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { mutate } from "swr";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { apiDelete, apiPost } from "@/lib/api";
import type { Account, AccountTestResult } from "@/lib/types";

export async function refreshAccounts(id?: string) {
  await mutate((key) => typeof key === "string" && key.startsWith("/accounts"));
  if (id) await mutate(`/accounts/${id}`);
}

export function useTestAccount() {
  const [testingId, setTestingId] = useState<string | null>(null);
  async function test(account: Pick<Account, "id" | "label">) {
    setTestingId(account.id);
    try {
      const res = await apiPost<AccountTestResult>(`/accounts/${account.id}/test`);
      if (res.ok) toast.success(`${account.label}: ${res.message}`);
      else toast.error(`${account.label}: ${res.message}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Test failed");
    } finally {
      setTestingId(null);
      await refreshAccounts(account.id);
    }
  }
  return { testingId, test };
}

export function DisconnectDialog({
  account,
  open,
  onOpenChange,
  onDone,
}: {
  account: Pick<Account, "id" | "label" | "provider_name"> | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDone?: () => void;
}) {
  const [busy, setBusy] = useState(false);

  async function confirm() {
    if (!account) return;
    setBusy(true);
    try {
      await apiDelete(`/accounts/${account.id}`);
      toast.success(`${account.label} disconnected`);
      onOpenChange(false);
      await refreshAccounts();
      onDone?.();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not disconnect");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Disconnect {account?.label}?</AlertDialogTitle>
          <AlertDialogDescription>
            The stored {account?.provider_name} credentials and usage records for this connection
            will be permanently deleted. Existing jobs and generated images are kept.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={busy}>Cancel</AlertDialogCancel>
          <Button variant="destructive" onClick={confirm} disabled={busy}>
            {busy && <Loader2Icon className="animate-spin" />}
            Disconnect
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
