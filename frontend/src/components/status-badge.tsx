import { Badge } from "@/components/ui/badge";
import type { Account, JobStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const JOB_STYLES: Record<JobStatus, { label: string; dot: string; pulse?: boolean }> = {
  queued: { label: "Queued", dot: "bg-slate-400" },
  processing: { label: "Processing", dot: "bg-blue-500", pulse: true },
  retrying: { label: "Retrying", dot: "bg-amber-500", pulse: true },
  completed: { label: "Completed", dot: "bg-emerald-500" },
  failed: { label: "Failed", dot: "bg-red-500" },
  cancelled: { label: "Cancelled", dot: "bg-zinc-400" },
};

function Dot({ className, pulse }: { className: string; pulse?: boolean }) {
  return (
    <span className="relative flex size-2">
      {pulse && (
        <span className={cn("absolute inline-flex size-full animate-ping rounded-full opacity-60", className)} />
      )}
      <span className={cn("relative inline-flex size-2 rounded-full", className)} />
    </span>
  );
}

export function JobStatusBadge({ status }: { status: JobStatus }) {
  const s = JOB_STYLES[status] ?? JOB_STYLES.queued;
  return (
    <Badge variant="outline" className="gap-1.5 font-normal">
      <Dot className={s.dot} pulse={s.pulse} />
      {s.label}
    </Badge>
  );
}

export function AccountStatusBadge({ account }: { account: Pick<Account, "status" | "available" | "rate_limited_until"> }) {
  let label = "Connected";
  let dot = "bg-emerald-500";
  if (account.status === "invalid") {
    label = "Invalid credentials";
    dot = "bg-red-500";
  } else if (account.status === "disabled") {
    label = "Disabled";
    dot = "bg-zinc-400";
  } else if (!account.available) {
    label = "Rate limited";
    dot = "bg-amber-500";
  }
  return (
    <Badge variant="outline" className="gap-1.5 font-normal">
      <Dot className={dot} />
      {label}
    </Badge>
  );
}
