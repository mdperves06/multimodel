"use client";

import { Loader2Icon, PlugZapIcon } from "lucide-react";
import Link from "next/link";
import { AccountStatusBadge } from "@/components/status-badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate, timeAgo } from "@/lib/format";
import type { Account } from "@/lib/types";

export function imageGenerationStatus(account: Account): { text: string; tone: string } {
  if (!account.capabilities.includes("image_generation")) {
    return { text: "Not supported", tone: "text-muted-foreground" };
  }
  if (account.status === "invalid") {
    return { text: "Unavailable — credentials rejected", tone: "text-red-600 dark:text-red-400" };
  }
  if (account.status === "disabled") {
    return { text: "Unavailable — disabled", tone: "text-muted-foreground" };
  }
  if (!account.available && account.rate_limited_until) {
    return {
      text: `Paused by provider limit until ${new Date(account.rate_limited_until).toLocaleTimeString()}`,
      tone: "text-amber-600 dark:text-amber-400",
    };
  }
  return { text: "Available", tone: "text-emerald-600 dark:text-emerald-400" };
}

export function AccountCard({
  account,
  detailed = false,
  testing,
  onTest,
  onDisconnect,
}: {
  account: Account;
  detailed?: boolean;
  testing?: boolean;
  onTest: () => void;
  onDisconnect?: () => void;
}) {
  const img = imageGenerationStatus(account);
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">{account.provider_name}</p>
          <CardTitle className="mt-0.5 truncate text-base">{account.label}</CardTitle>
        </div>
        <AccountStatusBadge account={account} />
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="flex items-center justify-between gap-3">
          <span className="text-muted-foreground">Image generation</span>
          <span className={`text-right font-medium ${img.tone}`}>{img.text}</span>
        </div>
        {detailed && (
          <>
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">Key</span>
              <span className="font-mono text-xs">••••{account.credential_hint}</span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">Last request</span>
              <span>{account.last_request_at ? timeAgo(account.last_request_at) : "Never"}</span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">Connected</span>
              <span>{formatDate(account.created_at)}</span>
            </div>
            <div className="flex items-start justify-between gap-3">
              <span className="text-muted-foreground">Last error</span>
              <span className="max-w-[60%] text-right text-xs break-words">
                {account.last_error ?? "None"}
              </span>
            </div>
          </>
        )}
      </CardContent>
      <CardFooter className="gap-2">
        <Link
          href={`/accounts/${account.id}`}
          className={buttonVariants({ variant: "outline", size: "sm" })}
        >
          Manage
        </Link>
        <Button variant="outline" size="sm" onClick={onTest} disabled={testing}>
          {testing ? <Loader2Icon className="animate-spin" /> : <PlugZapIcon />}
          Test{detailed ? "" : " Connection"}
        </Button>
        {onDisconnect && (
          <Button variant="destructive" size="sm" className="ml-auto" onClick={onDisconnect}>
            Disconnect
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
