"use client";

import { LogOutIcon, MonitorIcon, MoonIcon, ShieldCheckIcon, SunIcon } from "lucide-react";
import { useTheme } from "next-themes";
import { useRouter } from "next/navigation";
import { useSyncExternalStore } from "react";
import { toast } from "sonner";
import { mutate } from "swr";
import { ErrorState, PageHeader, TableSkeleton } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { apiPost } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { useAuditLogs, useUser } from "@/lib/hooks";
import { cn } from "@/lib/utils";

const THEMES = [
  { value: "light", label: "Light", icon: SunIcon },
  { value: "dark", label: "Dark", icon: MoonIcon },
  { value: "system", label: "System", icon: MonitorIcon },
] as const;

export default function SettingsPage() {
  const router = useRouter();
  const { data: user, isLoading } = useUser();
  const { data: logs, error, isLoading: logsLoading, mutate: reloadLogs } = useAuditLogs(25);
  const { theme, setTheme } = useTheme();
  const mounted = useSyncExternalStore(
    () => () => undefined,
    () => true,
    () => false,
  );

  async function signOut() {
    await apiPost("/auth/logout").catch(() => undefined);
    await mutate(() => true, undefined, { revalidate: false });
    toast.success("Signed out");
    router.push("/login");
    router.refresh();
  }

  return (
    <>
      <PageHeader title="Settings" description="Your profile, appearance and account activity." />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Profile</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading || !user ? (
              <Skeleton className="h-24 w-full" />
            ) : (
              <dl className="divide-y text-sm">
                <div className="flex justify-between py-2">
                  <dt className="text-muted-foreground">Email</dt>
                  <dd>{user.email}</dd>
                </div>
                <div className="flex justify-between py-2">
                  <dt className="text-muted-foreground">Name</dt>
                  <dd>{user.display_name || "—"}</dd>
                </div>
                <div className="flex justify-between py-2">
                  <dt className="text-muted-foreground">Member since</dt>
                  <dd>{formatDate(user.created_at)}</dd>
                </div>
              </dl>
            )}
            <Button variant="outline" className="mt-4" onClick={signOut}>
              <LogOutIcon /> Sign out
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Appearance</CardTitle>
            <CardDescription>Choose how the dashboard looks.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-2" role="radiogroup" aria-label="Theme">
              {THEMES.map(({ value, label, icon: Icon }) => (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={mounted && theme === value}
                  onClick={() => setTheme(value)}
                  className={cn(
                    "flex flex-col items-center gap-2 rounded-lg border p-3 text-sm transition-colors hover:bg-muted",
                    mounted && theme === value && "border-primary bg-primary/5 text-primary",
                  )}
                >
                  <Icon className="size-5" />
                  {label}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheckIcon className="size-4 text-primary" /> Security
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-1.5 text-sm text-muted-foreground">
          <p>Provider API keys are encrypted before they are stored and are never sent back to your browser.</p>
          <p>Only official provider APIs are used. This app never asks for website passwords, cookies or session tokens.</p>
          <p>Your session is an HTTP-only cookie that is revoked when you sign out.</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent activity</CardTitle>
          <CardDescription>Audit log of important actions on your account.</CardDescription>
        </CardHeader>
        <CardContent>
          {logsLoading ? (
            <TableSkeleton rows={4} />
          ) : error ? (
            <ErrorState message={error.message} onRetry={() => reloadLogs()} />
          ) : (
            <div className="overflow-x-auto rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>When</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Details</TableHead>
                    <TableHead>IP</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {logs?.map((l) => (
                    <TableRow key={l.id}>
                      <TableCell className="whitespace-nowrap text-muted-foreground">{formatDate(l.created_at)}</TableCell>
                      <TableCell className="font-mono text-xs">{l.action}</TableCell>
                      <TableCell className="max-w-[260px] truncate text-xs text-muted-foreground">
                        {Object.keys(l.metadata).length ? JSON.stringify(l.metadata) : "—"}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">{l.ip_address ?? "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </>
  );
}
