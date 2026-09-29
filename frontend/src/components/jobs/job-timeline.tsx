import { CheckIcon, CircleAlertIcon, CircleSlashIcon, Loader2Icon, RotateCcwIcon } from "lucide-react";
import { formatTime } from "@/lib/format";
import type { Job } from "@/lib/types";
import { cn } from "@/lib/utils";

const STAGES: { key: string; label: string }[] = [
  { key: "created", label: "Created" },
  { key: "queued", label: "Queued" },
  { key: "processing", label: "Processing" },
  { key: "generating", label: "Generating" },
  { key: "storing", label: "Storing result" },
  { key: "completed", label: "Completed" },
];

export function JobTimeline({ job }: { job: Job }) {
  const firstAt = new Map<string, string>();
  for (const e of job.events) if (!firstAt.has(e.stage)) firstAt.set(e.stage, e.at);
  const lastReached = STAGES.reduce((acc, s, i) => (firstAt.has(s.key) ? i : acc), -1);
  const active = ["queued", "processing", "retrying"].includes(job.status);
  const terminalBad = job.status === "failed" || job.status === "cancelled";

  return (
    <div className="space-y-5">
      <ol className="space-y-0">
        {STAGES.map((stage, i) => {
          const reached = firstAt.has(stage.key);
          const current = active && i === lastReached;
          const done = reached && !current;
          const failedHere = terminalBad && i === lastReached;
          return (
            <li key={stage.key} className="relative flex gap-3 pb-5 last:pb-0">
              {i < STAGES.length - 1 && (
                <span
                  aria-hidden
                  className={cn(
                    "absolute top-7 left-[13px] h-[calc(100%-1.75rem)] w-px",
                    i < lastReached ? "bg-primary" : "bg-border",
                  )}
                />
              )}
              <span
                className={cn(
                  "relative z-10 flex size-7 shrink-0 items-center justify-center rounded-full border text-xs",
                  done && "border-primary bg-primary text-primary-foreground",
                  current && "border-primary bg-background text-primary",
                  failedHere && "border-destructive bg-destructive/10 text-destructive",
                  !reached && "border-border bg-background text-muted-foreground",
                )}
              >
                {failedHere ? (
                  <CircleAlertIcon className="size-3.5" />
                ) : current ? (
                  <Loader2Icon className="size-3.5 animate-spin" />
                ) : done ? (
                  <CheckIcon className="size-3.5" />
                ) : (
                  i + 1
                )}
              </span>
              <div className="min-w-0 pt-0.5">
                <p className={cn("text-sm font-medium", !reached && "text-muted-foreground")}>
                  {stage.label}
                </p>
                <p className="text-xs text-muted-foreground">
                  {reached ? formatTime(firstAt.get(stage.key)) : "Pending"}
                </p>
              </div>
            </li>
          );
        })}
      </ol>

      {job.events.some((e) => ["retrying", "failed", "cancelled"].includes(e.stage)) && (
        <div className="space-y-2 border-t pt-4">
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            Notable events
          </p>
          {job.events
            .filter((e) => ["retrying", "failed", "cancelled"].includes(e.stage))
            .map((e, i) => (
              <div key={i} className="flex items-start gap-2 text-sm">
                {e.stage === "retrying" ? (
                  <RotateCcwIcon className="mt-0.5 size-3.5 text-amber-500" />
                ) : e.stage === "cancelled" ? (
                  <CircleSlashIcon className="mt-0.5 size-3.5 text-muted-foreground" />
                ) : (
                  <CircleAlertIcon className="mt-0.5 size-3.5 text-destructive" />
                )}
                <span>
                  <span className="text-muted-foreground">{formatTime(e.at)}</span>{" "}
                  {e.message ?? e.stage}
                </span>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
