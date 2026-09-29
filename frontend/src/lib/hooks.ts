"use client";

import useSWR from "swr";
import { apiGet } from "@/lib/api";
import type {
  Account,
  AuditEntry,
  GalleryItem,
  Job,
  Page,
  Provider,
  UsageSummary,
  User,
} from "@/lib/types";

const ACTIVE = new Set(["queued", "processing", "retrying"]);

export function useUser() {
  return useSWR<User>("/auth/me", apiGet, { shouldRetryOnError: false });
}

export function useProviders() {
  return useSWR<Provider[]>("/providers", apiGet);
}

export function useAccounts() {
  return useSWR<Account[]>("/accounts", apiGet, { refreshInterval: 30_000 });
}

export function useAccount(id: string) {
  return useSWR<Account>(`/accounts/${id}`, apiGet);
}

export function useJobs(params: { status?: string; limit?: number; offset?: number } = {}) {
  const q = new URLSearchParams();
  if (params.status && params.status !== "all") q.set("status", params.status);
  q.set("limit", String(params.limit ?? 20));
  q.set("offset", String(params.offset ?? 0));
  return useSWR<Page<Job>>(`/jobs?${q}`, apiGet, {
    refreshInterval: (data) => (data?.items.some((j) => ACTIVE.has(j.status)) ? 2000 : 15_000),
  });
}

export function useJob(id: string) {
  return useSWR<Job>(`/jobs/${id}`, apiGet, {
    refreshInterval: (job) => (job && !ACTIVE.has(job.status) ? 0 : 1500),
  });
}

export function useGallery(params: { q?: string; limit?: number; offset?: number }) {
  const q = new URLSearchParams();
  if (params.q) q.set("q", params.q);
  q.set("limit", String(params.limit ?? 24));
  q.set("offset", String(params.offset ?? 0));
  return useSWR<Page<GalleryItem>>(`/gallery?${q}`, apiGet, { keepPreviousData: true });
}

export function useUsage(accountId?: string) {
  return useSWR<UsageSummary>(accountId ? `/accounts/${accountId}/usage` : "/usage", apiGet);
}

export function useAuditLogs(limit = 20) {
  return useSWR<AuditEntry[]>(`/audit-logs?limit=${limit}`, apiGet);
}

export function isActiveStatus(status: string): boolean {
  return ACTIVE.has(status);
}
