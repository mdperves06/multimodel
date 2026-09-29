"use client";

import { BarChart3Icon } from "lucide-react";
import Link from "next/link";
import { EmptyState, ErrorState, PageHeader } from "@/components/states";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatNumber, timeAgo } from "@/lib/format";
import { useUsage } from "@/lib/hooks";
import type { AccountUsage } from "@/lib/types";

function Metric({ label, value, note }: { label: string; value: number | null; note?: string }) {
  return (
    <Card size="sm">
      <CardContent>
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="mt-1 text-2xl font-semibold tabular-nums">{formatNumber(value)}</p>
        {value === null && (
          <p className="mt-0.5 text-xs text-muted-foreground">{note ?? "Not reported by provider"}</p>
        )}
      </CardContent>
    </Card>
  );
}

function DailyChart({ daily }: { daily: { date: string; requests: number; images: number }[] }) {
  const max = Math.max(1, ...daily.map((d) => d.images));
  const total = daily.reduce((n, d) => n + d.images, 0);
  return (
    <div>
      <div
        role="img"
        aria-label={`Images generated per day over the last ${daily.length} days: ${total} total`}
        className="flex h-40 items-end gap-1.5"
      >
        {daily.map((d) => (
          <div key={d.date} className="group flex h-full flex-1 flex-col justify-end" title={`${d.date}: ${d.images} images, ${d.requests} requests`}>
            <div
              className="min-h-px w-full rounded-t bg-primary/80 transition-colors group-hover:bg-primary"
              style={{ height: `${(d.images / max) * 100}%` }}
            />
          </div>
        ))}
      </div>
      <div className="mt-2 flex justify-between text-xs text-muted-foreground">
        <span>{daily[0]?.date}</span>
        <span>{daily[daily.length - 1]?.date}</span>
      </div>
    </div>
  );
}

function AccountUsageCard({ a }: { a: AccountUsage }) {
  const limits = a.rate_limits && Object.keys(a.rate_limits).length > 0 ? a.rate_limits : null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-2 text-base">
          <Link href={`/accounts/${a.account_id}`} className="truncate hover:underline">
            {a.label}
          </Link>
          <span className="text-xs font-normal text-muted-foreground">{a.provider_name}</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-xs text-muted-foreground">Requests</dt>
            <dd className="font-medium tabular-nums">{formatNumber(a.requests)}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Images</dt>
            <dd className="font-medium tabular-nums">{formatNumber(a.images)}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Input tokens</dt>
            <dd className="font-medium tabular-nums">{formatNumber(a.input_tokens)}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Output tokens</dt>
            <dd className="font-medium tabular-nums">{formatNumber(a.output_tokens)}</dd>
          </div>
        </dl>
        <div className="rounded-lg bg-muted p-3 text-sm">
          <p className="mb-1 text-xs font-medium text-muted-foreground">Provider-reported usage</p>
          {a.provider_usage.available ? (
            <pre className="text-xs">{JSON.stringify(a.provider_usage.data, null, 2)}</pre>
          ) : (
            <p>{a.provider_usage.message ?? "Usage information unavailable for this provider."}</p>
          )}
        </div>
        <div className="rounded-lg bg-muted p-3 text-sm">
          <p className="mb-1 text-xs font-medium text-muted-foreground">
            Rate limits {a.rate_limits_updated_at && `· updated ${timeAgo(a.rate_limits_updated_at)}`}
          </p>
          {limits ? (
            <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
              {Object.entries(limits).map(([k, v]) => (
                <div key={k} className="contents">
                  <dt className="text-muted-foreground">{k.replaceAll("_", " ")}</dt>
                  <dd className="text-right tabular-nums">{String(v)}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-muted-foreground">Not reported by this provider.</p>
          )}
        </div>
        <p className="text-xs text-muted-foreground">Last request: {timeAgo(a.last_request_at)}</p>
      </CardContent>
    </Card>
  );
}

export default function UsagePage() {
  const { data, error, isLoading, mutate } = useUsage();

  return (
    <>
      <PageHeader
        title="Usage"
        description="Requests sent through this app, plus whatever each provider reports about its own limits."
      />
      {isLoading ? (
        <Skeleton className="h-96 w-full" />
      ) : error ? (
        <ErrorState message={error.message} onRetry={() => mutate()} />
      ) : !data || data.accounts.length === 0 ? (
        <EmptyState
          icon={BarChart3Icon}
          title="No usage to show"
          description="Connect a provider and run a job to see usage here."
          action={
            <Link href="/accounts" className={buttonVariants()}>
              Connect a provider
            </Link>
          }
        />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Metric label="Requests" value={data.requests} />
            <Metric label="Images generated" value={data.images} />
            <Metric label="Input tokens" value={data.input_tokens} />
            <Metric label="Output tokens" value={data.output_tokens} />
          </div>
          <Card>
            <CardHeader>
              <CardTitle>Images per day</CardTitle>
              <CardDescription>Last {data.daily.length} days across all connections.</CardDescription>
            </CardHeader>
            <CardContent>
              <DailyChart daily={data.daily} />
            </CardContent>
          </Card>
          <div className="grid gap-4 lg:grid-cols-2">
            {data.accounts.map((a) => (
              <AccountUsageCard key={a.account_id} a={a} />
            ))}
          </div>
        </>
      )}
    </>
  );
}
