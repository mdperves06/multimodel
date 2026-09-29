"use client";

import { CheckIcon, Loader2Icon, LockIcon } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { apiPost } from "@/lib/api";
import { useProviders } from "@/lib/hooks";
import type { Account } from "@/lib/types";
import { cn } from "@/lib/utils";
import { refreshAccounts } from "./account-actions";

const HELP: Record<string, string> = {
  openai:
    "Create an API key at platform.openai.com/api-keys. Never enter your ChatGPT password or session tokens.",
  mock: "Development-only provider. Use any key (e.g. mock-abc12345); mock-ratelimit simulates HTTP 429.",
};

export function ConnectProviderDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { data: providers, isLoading } = useProviders();
  const [provider, setProvider] = useState<string | null>(null);
  const [label, setLabel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function close(next: boolean) {
    onOpenChange(next);
    if (!next) {
      setProvider(null);
      setLabel("");
      setApiKey("");
      setError(null);
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!provider) return;
    setBusy(true);
    setError(null);
    try {
      const account = await apiPost<Account>("/accounts", {
        provider,
        label: label.trim(),
        api_key: apiKey.trim(),
      });
      setApiKey(""); // the key is never kept in the UI after submission
      toast.success(`${account.label} connected`);
      await refreshAccounts();
      close(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not connect this account");
    } finally {
      setBusy(false);
    }
  }

  const selected = providers?.find((p) => p.slug === provider);

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Connect provider</DialogTitle>
          <DialogDescription>
            {selected
              ? `Add ${selected.name} credentials.`
              : "Choose which provider you want to connect."}
          </DialogDescription>
        </DialogHeader>

        {!selected ? (
          <div className="space-y-2">
            {isLoading && <Skeleton className="h-16 w-full" />}
            {providers?.map((p) => (
              <button
                key={p.slug}
                type="button"
                onClick={() => setProvider(p.slug)}
                className="flex w-full items-center justify-between rounded-lg border p-3 text-left transition-colors hover:bg-muted"
              >
                <span>
                  <span className="block font-medium">{p.name}</span>
                  <span className="text-xs text-muted-foreground">
                    Image generation · {p.models.length} models
                  </span>
                </span>
              </button>
            ))}
            <div
              className={cn(
                "flex w-full items-center justify-between rounded-lg border border-dashed p-3 opacity-60",
              )}
            >
              <span>
                <span className="block font-medium">Other provider</span>
                <span className="text-xs text-muted-foreground">Coming soon</span>
              </span>
            </div>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            {error && (
              <Alert variant="destructive" role="alert">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-2">
              <Label htmlFor="label">Account label</Label>
              <Input
                id="label"
                required
                maxLength={100}
                placeholder="e.g. OpenAI Account 1"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="api-key">API key</Label>
              <Input
                id="api-key"
                type="password"
                required
                minLength={8}
                maxLength={500}
                autoComplete="off"
                spellCheck={false}
                placeholder="sk-…"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">{HELP[selected.slug]}</p>
            </div>
            <p className="flex items-start gap-2 rounded-lg bg-muted p-3 text-xs text-muted-foreground">
              <LockIcon className="mt-0.5 size-3.5 shrink-0" />
              The key is verified with the provider, encrypted before it is stored, and never sent
              back to your browser.
            </p>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setProvider(null)} disabled={busy}>
                Back
              </Button>
              <Button type="submit" disabled={busy}>
                {busy ? <Loader2Icon className="animate-spin" /> : <CheckIcon />}
                Verify and connect
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
