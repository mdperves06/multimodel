"use client";

import { ArrowRightIcon, ImagesIcon, KeyRoundIcon, ListChecksIcon, ZapIcon } from "lucide-react";
import Link from "next/link";
import { AccountsPanel } from "@/components/accounts/accounts-panel";
import { CreateJobForm } from "@/components/jobs/create-job-form";
import { JobsTable } from "@/components/jobs/jobs-table";
import { PageHeader } from "@/components/states";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatNumber } from "@/lib/format";
import { useAccounts, useJobs, useUsage, useUser } from "@/lib/hooks";
import type { LucideIcon } from "lucide-react";

function Stat({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: LucideIcon;
  label: string;
  value: string | undefined;
  hint?: string;
}) {
  return (
    <Card size="sm">
      <CardContent className="flex items-center gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Icon className="size-5" />
        </span>
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">{label}</p>
          {value === undefined ? (
            <Skeleton className="mt-1 h-6 w-12" />
          ) : (
            <p className="text-xl font-semibold tabular-nums">{value}</p>
          )}
          {hint && <p className="truncate text-xs text-muted-foreground">{hint}</p>}
        </div>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const { data: user } = useUser();
  const { data: accounts } = useAccounts();
  const { data: usage } = useUsage();
  const { data: jobs, isLoading: jobsLoading } = useJobs({ limit: 8 });
  const active = jobs?.items.filter((j) => ["queued", "processing", "retrying"].includes(j.status)).length;

  return (
    <>
      <PageHeader
        title={user?.display_name ? `Welcome back, ${user.display_name}` : "Dashboard"}
        description="Your connected providers, active jobs and recent results at a glance."
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          icon={KeyRoundIcon}
          label="Connected accounts"
          value={accounts ? String(accounts.length) : undefined}
          hint={accounts ? `${accounts.filter((a) => a.available).length} available now` : undefined}
        />
        <Stat icon={ZapIcon} label="Active jobs" value={active === undefined ? undefined : String(active)} />
        <Stat icon={ListChecksIcon} label="Total jobs" value={jobs ? formatNumber(jobs.total) : undefined} />
        <Stat icon={ImagesIcon} label="Images generated" value={usage ? formatNumber(usage.images) : undefined} />
      </div>

      <AccountsPanel title="Connected accounts" />

      <div className="grid gap-6 xl:grid-cols-5">
        <div className="xl:col-span-2">
          <CreateJobForm />
        </div>
        <Card className="xl:col-span-3">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Recent jobs</CardTitle>
            <Link href="/jobs" className={buttonVariants({ variant: "ghost", size: "sm" })}>
              View all <ArrowRightIcon />
            </Link>
          </CardHeader>
          <CardContent>
            <JobsTable jobs={jobs?.items} loading={jobsLoading} />
          </CardContent>
        </Card>
      </div>
    </>
  );
}
