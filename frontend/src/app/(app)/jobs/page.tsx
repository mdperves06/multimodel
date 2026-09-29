"use client";

import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react";
import { useState } from "react";
import { JobsTable } from "@/components/jobs/jobs-table";
import { ErrorState, PageHeader } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useJobs } from "@/lib/hooks";

const PAGE_SIZE = 15;
const FILTERS = [
  ["all", "All"],
  ["queued", "Queued"],
  ["processing", "Processing"],
  ["retrying", "Retrying"],
  ["completed", "Completed"],
  ["failed", "Failed"],
  ["cancelled", "Cancelled"],
] as const;

export default function JobsPage() {
  const [status, setStatus] = useState<string>("all");
  const [page, setPage] = useState(0);
  const { data, error, isLoading, mutate } = useJobs({
    status,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  });
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <>
      <PageHeader title="Jobs" description="Every generation request and its current state." />
      <Tabs
        value={status}
        onValueChange={(v) => {
          setStatus(String(v));
          setPage(0);
        }}
      >
        <div className="overflow-x-auto pb-1">
          <TabsList>
            {FILTERS.map(([value, label]) => (
              <TabsTrigger key={value} value={value}>
                {label}
              </TabsTrigger>
            ))}
          </TabsList>
        </div>
      </Tabs>

      {error ? (
        <ErrorState message={error.message} onRetry={() => mutate()} />
      ) : (
        <JobsTable
          jobs={data?.items}
          loading={isLoading}
          emptyHint={
            status === "all"
              ? "Create a job from the dashboard to see it here."
              : `No ${status} jobs.`
          }
        />
      )}

      {data && data.total > PAGE_SIZE && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Page {page + 1} of {pages} · {data.total} jobs
          </p>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage(page - 1)}>
              <ChevronLeftIcon /> Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page + 1 >= pages}
              onClick={() => setPage(page + 1)}
            >
              Next <ChevronRightIcon />
            </Button>
          </div>
        </div>
      )}
    </>
  );
}
