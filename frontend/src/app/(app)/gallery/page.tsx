"use client";

import {
  ChevronLeftIcon,
  ChevronRightIcon,
  CopyIcon,
  DownloadIcon,
  EyeIcon,
  ImagesIcon,
  Loader2Icon,
  SearchIcon,
  Trash2Icon,
  XIcon,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { mutate as globalMutate } from "swr";
import { CardGridSkeleton, EmptyState, ErrorState, PageHeader } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { apiPost, apiPostBlob, downloadBlob } from "@/lib/api";
import { formatBytes, formatDate } from "@/lib/format";
import { useGallery } from "@/lib/hooks";
import type { GalleryItem } from "@/lib/types";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 24;

function copyPrompt(prompt: string) {
  void navigator.clipboard.writeText(prompt);
  toast.success("Prompt copied");
}

export default function GalleryPage() {
  const [input, setInput] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [viewing, setViewing] = useState<GalleryItem | null>(null);
  const [toDelete, setToDelete] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);

  const { data, error, isLoading, mutate } = useGallery({
    q,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  });

  useEffect(() => {
    const t = setTimeout(() => {
      setQ(input.trim());
      setPage(0);
    }, 300);
    return () => clearTimeout(t);
  }, [input]);

  const items = data?.items ?? [];
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
  const allSelected = items.length > 0 && items.every((i) => selected.has(i.id));

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function downloadSelected() {
    setBusy(true);
    try {
      const blob = await apiPostBlob("/outputs/download", { ids: [...selected] });
      downloadBlob(blob, "images.zip");
      toast.success(`Downloaded ${selected.size} image${selected.size === 1 ? "" : "s"}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Download failed");
    } finally {
      setBusy(false);
    }
  }

  async function confirmDelete() {
    if (!toDelete) return;
    setBusy(true);
    try {
      const res = await apiPost<{ deleted: number }>("/outputs/delete", { ids: toDelete });
      toast.success(`Deleted ${res.deleted} image${res.deleted === 1 ? "" : "s"}`);
      setSelected((prev) => {
        const next = new Set(prev);
        toDelete.forEach((id) => next.delete(id));
        return next;
      });
      if (viewing && toDelete.includes(viewing.id)) setViewing(null);
      setToDelete(null);
      await mutate();
      await globalMutate((k) => typeof k === "string" && k.startsWith("/jobs"));
      if (items.length === toDelete.length && page > 0) setPage(page - 1);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Gallery"
        description="Every image generated across all of your connected accounts."
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative max-w-sm flex-1">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            aria-label="Search prompts"
            placeholder="Search prompts…"
            className="pl-8"
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
        </div>
        <div className="flex flex-wrap items-center gap-2 sm:ml-auto">
          {items.length > 0 && (
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={allSelected}
                onCheckedChange={(checked) =>
                  setSelected((prev) => {
                    const next = new Set(prev);
                    items.forEach((i) => (checked ? next.add(i.id) : next.delete(i.id)));
                    return next;
                  })
                }
                aria-label="Select all on this page"
              />
              Select page
            </label>
          )}
          {selected.size > 0 && (
            <>
              <Badge variant="secondary">{selected.size} selected</Badge>
              <Button variant="outline" size="sm" onClick={downloadSelected} disabled={busy}>
                {busy ? <Loader2Icon className="animate-spin" /> : <DownloadIcon />}
                Download selected
              </Button>
              <Button variant="destructive" size="sm" onClick={() => setToDelete([...selected])} disabled={busy}>
                <Trash2Icon /> Delete selected
              </Button>
              <Button variant="ghost" size="icon-sm" aria-label="Clear selection" onClick={() => setSelected(new Set())}>
                <XIcon />
              </Button>
            </>
          )}
        </div>
      </div>

      {isLoading ? (
        <CardGridSkeleton count={6} />
      ) : error ? (
        <ErrorState message={error.message} onRetry={() => mutate()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={ImagesIcon}
          title={q ? "No images match your search" : "No images yet"}
          description={q ? "Try a different search term." : "Generated images will appear here."}
          action={
            !q && (
              <Link href="/dashboard" className={buttonVariants()}>
                Create a job
              </Link>
            )
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {items.map((item) => {
            const isSelected = selected.has(item.id);
            return (
              <Card key={item.id} size="sm" className={cn("gap-0 overflow-hidden p-0", isSelected && "ring-2 ring-primary")}>
                <div className="group relative aspect-square bg-muted">
                  <button
                    type="button"
                    onClick={() => setViewing(item)}
                    className="block size-full"
                    aria-label="View image"
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={item.url} alt={item.prompt} loading="lazy" className="size-full object-cover" />
                  </button>
                  <div
                    className={cn(
                      "absolute top-2 left-2 rounded-md bg-background/90 p-1 shadow-sm transition-opacity",
                      isSelected ? "opacity-100" : "opacity-100 sm:opacity-0 sm:group-hover:opacity-100 sm:focus-within:opacity-100",
                    )}
                  >
                    <Checkbox
                      checked={isSelected}
                      onCheckedChange={() => toggle(item.id)}
                      aria-label="Select image"
                    />
                  </div>
                </div>
                <div className="space-y-2 p-3">
                  <div className="flex flex-wrap gap-1.5">
                    {item.provider && <Badge variant="secondary">{item.provider}</Badge>}
                    {item.model && (
                      <Badge variant="outline" className="font-mono text-[10px]">
                        {item.model}
                      </Badge>
                    )}
                  </div>
                  <p className="line-clamp-2 text-sm" title={item.prompt}>
                    {item.prompt}
                  </p>
                  <p className="text-xs text-muted-foreground">{formatDate(item.created_at)}</p>
                  <div className="flex gap-1 pt-1">
                    <Button variant="ghost" size="icon-sm" aria-label="View" onClick={() => setViewing(item)}>
                      <EyeIcon />
                    </Button>
                    <a
                      href={`${item.url}?download=true`}
                      className={buttonVariants({ variant: "ghost", size: "icon-sm" })}
                      aria-label="Download"
                    >
                      <DownloadIcon />
                    </a>
                    <Button variant="ghost" size="icon-sm" aria-label="Copy prompt" onClick={() => copyPrompt(item.prompt)}>
                      <CopyIcon />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      className="ml-auto text-destructive hover:text-destructive"
                      aria-label="Delete"
                      onClick={() => setToDelete([item.id])}
                    >
                      <Trash2Icon />
                    </Button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {data && data.total > PAGE_SIZE && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Page {page + 1} of {pages} · {data.total} images
          </p>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage(page - 1)}>
              <ChevronLeftIcon /> Previous
            </Button>
            <Button variant="outline" size="sm" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>
              Next <ChevronRightIcon />
            </Button>
          </div>
        </div>
      )}

      <Dialog open={viewing !== null} onOpenChange={(o) => !o && setViewing(null)}>
        <DialogContent className="sm:max-w-3xl">
          {viewing && (
            <>
              <DialogHeader>
                <DialogTitle className="line-clamp-2">{viewing.prompt}</DialogTitle>
                <DialogDescription>
                  {viewing.provider} · {viewing.model} · {formatDate(viewing.created_at)} ·{" "}
                  {formatBytes(viewing.size_bytes)}
                </DialogDescription>
              </DialogHeader>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={viewing.url}
                alt={viewing.prompt}
                className="max-h-[65vh] w-full rounded-lg bg-muted object-contain"
              />
              <div className="flex flex-wrap gap-2">
                <a href={`${viewing.url}?download=true`} className={buttonVariants({ variant: "outline", size: "sm" })}>
                  <DownloadIcon /> Download
                </a>
                <Button variant="outline" size="sm" onClick={() => copyPrompt(viewing.prompt)}>
                  <CopyIcon /> Copy prompt
                </Button>
                <Link href={`/jobs/${viewing.job_id}`} className={buttonVariants({ variant: "outline", size: "sm" })}>
                  View job
                </Link>
                <Button variant="destructive" size="sm" className="ml-auto" onClick={() => setToDelete([viewing.id])}>
                  <Trash2Icon /> Delete
                </Button>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      <AlertDialog open={toDelete !== null} onOpenChange={(o) => !o && setToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete {toDelete?.length} image{toDelete?.length === 1 ? "" : "s"}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              The files are permanently removed from storage. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>Cancel</AlertDialogCancel>
            <Button variant="destructive" onClick={confirmDelete} disabled={busy}>
              {busy && <Loader2Icon className="animate-spin" />}
              Delete
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
