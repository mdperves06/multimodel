"use client";

import { ArrowLeftIcon, Loader2Icon, PlugZapIcon } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { DisconnectDialog, useTestAccount } from "@/components/accounts/account-actions";
import { imageGenerationStatus } from "@/components/accounts/account-card";
import { ErrorState, PageHeader } from "@/components/states";
import { AccountStatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate, formatNumber, timeAgo } from "@/lib/format";
import { useAccount, useUsage } from "@/lib/hooks";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-2 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right break-words">{children}</dd>
    </div>
  );
}

export default function AccountDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: account, error, isLoading, mutate } = useAccount(id);
  const { data: usage } = useUsage(id);
  const { testingId, test } = useTestAccount();
  const [disconnectOpen, setDisconnectOpen] = useState(false);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (error || !account) {
    return <ErrorState message={error?.message ?? "Account not found"} onRetry={() => mutate()} />;
  }

  const img = imageGenerationStatus(account);
  const stats = usage?.accounts[0];
  const limits = account.limits ?? stats?.rate_limits ?? null;

  return (
    <>
      <Link href="/accounts" className={buttonVariants({ variant: "ghost", size: "sm" })}>
        <ArrowLeftIcon /> All accounts
      </Link>
      <PageHeader
        title={account.label}
        description={`${account.provider_name} connection`}
        actions={
          <>
            <AccountStatusBadge account={account} />
            <Button variant="outline" onClick={() => test(account)} disabled={testingId === account.id}>
              {testingId === account.id ? <Loader2Icon className="animate-spin" /> : <PlugZapIcon />}
              Test connection
            </Button>
            <Button variant="destructive" onClick={() => setDisconnectOpen(true)}>
              Disconnect
            </Button>
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Connection</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="divide-y">
              <Row label="Image generation">
                <span className={img.tone}>{img.text}</span>
              </Row>
              <Row label="API key">
                <span className="font-mono text-xs">••••{account.credential_hint}</span>
              </Row>
              <Row label="Connected">{formatDate(account.created_at)}</Row>
              <Row label="Last validated">{formatDate(account.last_validated_at)}</Row>
              <Row label="Last request">
                {account.last_request_at ? timeAgo(account.last_request_at) : "Never"}
              </Row>
              <Row label="Last error">
                {account.last_error ? (
                  <span className="text-red-600 dark:text-red-400">
                    {account.last_error}
                    <span className="block text-xs text-muted-foreground">
                      {timeAgo(account.last_error_at)}
                    </span>
                  </span>
                ) : (
                  "None"
                )}
              </Row>
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Usage on this connection</CardTitle>
            <CardDescription>Counted from requests sent through this app.</CardDescription>
          </CardHeader>
          <CardContent>
            {!stats ? (
              <Skeleton className="h-32 w-full" />
            ) : (
              <>
                <dl className="divide-y">
                  <Row label="Requests">{formatNumber(stats.requests)}</Row>
                  <Row label="Images generated">{formatNumber(stats.images)}</Row>
                  <Row label="Input tokens">{formatNumber(stats.input_tokens)}</Row>
                  <Row label="Output tokens">{formatNumber(stats.output_tokens)}</Row>
                </dl>
                <p className="mt-3 text-xs text-muted-foreground">
                  {stats.provider_usage.message}
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Capabilities and models</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {account.capabilities.map((c) => (
                <Badge key={c} variant="secondary">
                  {c.replaceAll("_", " ")}
                </Badge>
              ))}
            </div>
            <ul className="space-y-2 text-sm">
              {account.models.map((m) => (
                <li key={m.id} className="flex items-center justify-between rounded-lg border p-2.5">
                  <span>
                    <span className="font-medium">{m.name}</span>
                    <span className="ml-2 font-mono text-xs text-muted-foreground">{m.id}</span>
                  </span>
                  <span className="text-xs text-muted-foreground">
                    up to {m.max_outputs_per_request}/request
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Provider rate limits</CardTitle>
            <CardDescription>As last reported by the provider.</CardDescription>
          </CardHeader>
          <CardContent>
            {limits && Object.keys(limits).length > 0 ? (
              <dl className="divide-y">
                {Object.entries(limits).map(([k, v]) => (
                  <Row key={k} label={k.replaceAll("_", " ")}>
                    {typeof v === "number" ? formatNumber(v) : String(v)}
                  </Row>
                ))}
              </dl>
            ) : (
              <p className="text-sm text-muted-foreground">
                The provider has not reported rate limit information for this connection yet.
              </p>
            )}
            {account.rate_limited_until && !account.available && (
              <p className="mt-3 text-sm text-amber-600 dark:text-amber-400">
                Paused until {new Date(account.rate_limited_until).toLocaleTimeString()} as
                instructed by the provider.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <DisconnectDialog
        account={account}
        open={disconnectOpen}
        onOpenChange={setDisconnectOpen}
        onDone={() => router.push("/accounts")}
      />
    </>
  );
}
