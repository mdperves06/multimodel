"use client";

import { ArrowLeftIcon, CopyIcon, DownloadIcon, Loader2Icon, RotateCcwIcon, XIcon } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { mutate as globalMutate } from "swr";
import { JobTimeline } from "@/components/jobs/job-timeline";
import { ErrorState, PageHeader } from "@/components/states";
import { JobStatusBadge } from "@/components/status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiPost } from "@/lib/api";
import { duration, formatDate } from "@/lib/format";
import { isActiveStatus, useJob } from "@/lib/hooks";
import type { Job } from "@/lib/types";

function Field({ label, children, mono }: { label: string; children: React.ReactNode; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={`mt-0.5 text-sm break-words ${mono ? "font-mono text-xs" : ""}`}>{children}</dd>
    </div>
  );
}

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: job, error, isLoading, mutate } = useJob(id);
  const [busy, setBusy] = useState<"cancel" | "retry" | null>(null);

  async function act(kind: "cancel" | "retry") {
    setBusy(kind);
    try {
      const updated = await apiPost<Job>(`/jobs/${id}/${kind}`);
      await mutate(updated, { revalidate: false });
      await globalMutate((k) => typeof k === "string" && k.startsWith("/jobs?"));
      toast.success(kind === "cancel" ? "Job cancelled" : "Job re-queued");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy(null);
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-80 w-full" />
      </div>
    );
  }
  if (error || !job) {
    return <ErrorState message={error?.message ?? "Job not found"} onRetry={() => mutate()} />;
  }

  return (
    <>
      <Link href="/jobs" className={buttonVariants({ variant: "ghost", size: "sm" })}>
        <ArrowLeftIcon /> All jobs
      </Link>
      <PageHeader
        title={`Job ${job.id.slice(0, 8)}`}
        description={job.type.replaceAll("_", " ")}
        actions={
          <>
            <JobStatusBadge status={job.status} />
            {isActiveStatus(job.status) && (
              <Button variant="outline" onClick={() => act("cancel")} disabled={busy !== null}>
                {busy === "cancel" ? <Loader2Icon className="animate-spin" /> : <XIcon />}
                Cancel
              </Button>
            )}
            {(job.status === "failed" || job.status === "cancelled") && (
              <Button onClick={() => act("retry")} disabled={busy !== null}>
                {busy === "retry" ? <Loader2Icon className="animate-spin" /> : <RotateCcwIcon />}
                Retry
              </Button>
            )}
          </>
        }
      />

      {job.error && job.status === "failed" && (
        <Alert variant="destructive">
          <AlertTitle>This job failed</AlertTitle>
          <AlertDescription>{job.error}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <div>
              <div className="flex items-center justify-between">
                <p className="text-xs text-muted-foreground">Prompt</p>
                <Button
                  variant="ghost"
                  size="xs"
                  onClick={() => {
                    void navigator.clipboard.writeText(job.prompt);
                    toast.success("Prompt copied");
                  }}
                >
                  <CopyIcon /> Copy
                </Button>
              </div>
              <p className="mt-1 rounded-lg bg-muted p-3 text-sm whitespace-pre-wrap">{job.prompt}</p>
            </div>
            <dl className="grid gap-4 sm:grid-cols-2">
              <Field label="Job ID" mono>
                {job.id}
              </Field>
              <Field label="Status">
                <JobStatusBadge status={job.status} />
              </Field>
              <Field label="Provider">
                {job.provider_used ?? (job.requested_provider === "auto" ? "Auto (not yet assigned)" : job.requested_provider)}
                {job.account_label && (
                  <span className="text-muted-foreground"> · {job.account_label}</span>
                )}
              </Field>
              <Field label="Model">
                {job.model_used ?? (job.requested_model === "auto" ? "Auto (not yet assigned)" : job.requested_model)}
              </Field>
              <Field label="Number of outputs">
                {job.outputs.length} of {job.number_of_outputs}
              </Field>
              <Field label="Attempts">{job.attempts}</Field>
              <Field label="Created">{formatDate(job.created_at)}</Field>
              <Field label="Started">{formatDate(job.started_at)}</Field>
              <Field label="Completed">{formatDate(job.completed_at)}</Field>
              <Field label="Duration">{duration(job.started_at, job.completed_at)}</Field>
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Timeline</CardTitle>
          </CardHeader>
          <CardContent>
            <JobTimeline job={job} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Outputs</CardTitle>
        </CardHeader>
        <CardContent>
          {job.outputs.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              {isActiveStatus(job.status)
                ? "Results will appear here as soon as they are generated."
                : "This job produced no outputs."}
            </p>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {job.outputs.map((o) => (
                <div key={o.id} className="group relative overflow-hidden rounded-lg border bg-muted">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={o.url} alt={job.prompt} loading="lazy" className="aspect-square w-full object-cover" />
                  <a
                    href={`${o.url}?download=true`}
                    className={`${buttonVariants({ variant: "secondary", size: "icon-sm" })} absolute top-2 right-2 opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100`}
                    aria-label="Download image"
                  >
                    <DownloadIcon />
                  </a>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </>
  );
}
