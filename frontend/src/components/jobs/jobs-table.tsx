"use client";

import { ListChecksIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { EmptyState, TableSkeleton } from "@/components/states";
import { JobStatusBadge } from "@/components/status-badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { shortId, timeAgo } from "@/lib/format";
import type { Job } from "@/lib/types";

export function JobsTable({
  jobs,
  loading,
  emptyHint = "Submit a prompt to create your first job.",
}: {
  jobs: Job[] | undefined;
  loading?: boolean;
  emptyHint?: string;
}) {
  const router = useRouter();
  if (loading) return <TableSkeleton />;
  if (!jobs || jobs.length === 0) {
    return <EmptyState icon={ListChecksIcon} title="No jobs yet" description={emptyHint} />;
  }
  return (
    <div className="overflow-x-auto rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Job ID</TableHead>
            <TableHead>Prompt</TableHead>
            <TableHead>Provider</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Created</TableHead>
            <TableHead className="text-right">Outputs</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {jobs.map((job) => (
            <TableRow
              key={job.id}
              className="cursor-pointer"
              onClick={() => router.push(`/jobs/${job.id}`)}
            >
              <TableCell>
                <Link
                  href={`/jobs/${job.id}`}
                  className="font-mono text-xs text-primary hover:underline"
                  onClick={(e) => e.stopPropagation()}
                >
                  {shortId(job.id)}
                </Link>
              </TableCell>
              <TableCell className="max-w-[240px] truncate">{job.prompt}</TableCell>
              <TableCell className="whitespace-nowrap">
                {job.provider_used ?? (
                  <span className="text-muted-foreground">
                    {job.requested_provider === "auto" ? "Auto" : job.requested_provider}
                  </span>
                )}
              </TableCell>
              <TableCell>
                <JobStatusBadge status={job.status} />
              </TableCell>
              <TableCell className="whitespace-nowrap text-muted-foreground">
                {timeAgo(job.created_at)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {job.outputs.length}/{job.number_of_outputs}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
