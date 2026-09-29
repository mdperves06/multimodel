"use client";

import { KeyRoundIcon, Loader2Icon, LogOutIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { mutate } from "swr";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiPost } from "@/lib/api";

export function AccountSecurity() {
  const router = useRouter();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [signingOut, setSigningOut] = useState(false);

  async function changePassword(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (next.length < 10 || /^\d+$/.test(next) || /^[A-Za-z]+$/.test(next)) {
      setError("Use at least 10 characters mixing letters with numbers or symbols.");
      return;
    }
    if (next !== confirm) {
      setError("The new passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      await apiPost("/auth/change-password", { current_password: current, new_password: next });
      setCurrent("");
      setNext("");
      setConfirm("");
      toast.success("Password changed. Other devices have been signed out.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not change the password");
    } finally {
      setBusy(false);
    }
  }

  async function signOutEverywhere() {
    setSigningOut(true);
    try {
      await apiPost("/auth/logout-all");
      await mutate(() => true, undefined, { revalidate: false });
      toast.success("Signed out on all devices");
      router.push("/login");
      router.refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not sign out");
      setSigningOut(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <KeyRoundIcon className="size-4 text-primary" /> Change password
          </CardTitle>
          <CardDescription>Changing your password signs out all other devices.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={changePassword} className="space-y-3">
            {error && (
              <Alert variant="destructive" role="alert">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-2">
              <Label htmlFor="current-password">Current password</Label>
              <Input
                id="current-password"
                type="password"
                autoComplete="current-password"
                required
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-password">New password</Label>
              <Input
                id="new-password"
                type="password"
                autoComplete="new-password"
                required
                minLength={10}
                maxLength={128}
                value={next}
                onChange={(e) => setNext(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm-password">Confirm new password</Label>
              <Input
                id="confirm-password"
                type="password"
                autoComplete="new-password"
                required
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
              />
            </div>
            <Button type="submit" disabled={busy}>
              {busy && <Loader2Icon className="animate-spin" />}
              Update password
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <LogOutIcon className="size-4 text-primary" /> Sessions
          </CardTitle>
          <CardDescription>
            Lost a device or signed in somewhere you should not have? End every session at once,
            including this one.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="destructive" onClick={signOutEverywhere} disabled={signingOut}>
            {signingOut && <Loader2Icon className="animate-spin" />}
            Sign out of all devices
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
