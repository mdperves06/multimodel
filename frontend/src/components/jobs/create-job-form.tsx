"use client";

import { Loader2Icon, SparklesIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { mutate } from "swr";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { apiPost } from "@/lib/api";
import { useAccounts, useProviders } from "@/lib/hooks";
import type { JobCreateInput } from "@/lib/types";

const TASKS = { image_generation: "Image Generation" };

export function CreateJobForm() {
  const router = useRouter();
  const { data: providers } = useProviders();
  const { data: accounts } = useAccounts();
  const [prompt, setPrompt] = useState("");
  const [count, setCount] = useState(4);
  const [provider, setProvider] = useState("auto");
  const [model, setModel] = useState("auto");
  const [size, setSize] = useState("default");
  const [quality, setQuality] = useState("default");
  const [busy, setBusy] = useState(false);

  const connected = useMemo(
    () => providers?.filter((p) => accounts?.some((a) => a.provider === p.slug)) ?? [],
    [providers, accounts],
  );
  const providerItems: Record<string, string> = { auto: "Auto" };
  for (const p of connected) providerItems[p.slug] = p.name;

  const candidates = provider === "auto" ? connected : connected.filter((p) => p.slug === provider);
  const models = candidates.flatMap((p) =>
    p.models.filter((m) => m.capability === "image_generation").map((m) => ({ ...m, provider: p })),
  );
  const modelItems: Record<string, string> = { auto: "Auto" };
  for (const m of models) modelItems[m.id] = candidates.length > 1 ? `${m.name} (${m.provider.name})` : m.name;
  const chosen = models.find((m) => m.id === model);

  const sizeItems: Record<string, string> = { default: "Default" };
  for (const s of chosen?.sizes ?? []) sizeItems[s] = s;
  const qualityItems: Record<string, string> = { default: "Default" };
  for (const q of chosen?.qualities ?? []) qualityItems[q] = q;

  const noAccounts = accounts !== undefined && accounts.length === 0;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!prompt.trim()) return;
    setBusy(true);
    const body: JobCreateInput = {
      type: "image_generation",
      prompt: prompt.trim(),
      number_of_outputs: count,
      provider,
      model,
      size: chosen && size !== "default" ? size : null,
      quality: chosen && quality !== "default" ? quality : null,
    };
    try {
      const res = await apiPost<{ job_id: string; status: string }>("/jobs", body);
      toast.success("Job queued", {
        description: `Job ${res.job_id.slice(0, 8)} is ${res.status}.`,
        action: { label: "View", onClick: () => router.push(`/jobs/${res.job_id}`) },
      });
      await mutate((k) => typeof k === "string" && k.startsWith("/jobs"));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create the job");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Create new job</CardTitle>
        <CardDescription>
          Jobs are queued and routed to an eligible connected account.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Task</Label>
              <Select value="image_generation" items={TASKS}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="image_generation">Image Generation</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="count">Number of outputs</Label>
              <Input
                id="count"
                type="number"
                min={1}
                max={10}
                value={count}
                onChange={(e) => setCount(Math.min(10, Math.max(1, Number(e.target.value) || 1)))}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="prompt">Prompt</Label>
            <Textarea
              id="prompt"
              required
              rows={4}
              maxLength={4000}
              placeholder="A futuristic city at night"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Provider</Label>
              <Select
                value={provider}
                items={providerItems}
                onValueChange={(v) => {
                  setProvider(v ?? "auto");
                  setModel("auto");
                }}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(providerItems).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Model</Label>
              <Select
                value={model}
                items={modelItems}
                onValueChange={(v) => {
                  setModel(v ?? "auto");
                  setSize("default");
                  setQuality("default");
                }}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(modelItems).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {chosen && (
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Size</Label>
                <Select value={size} items={sizeItems} onValueChange={(v) => setSize(v ?? "default")}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(sizeItems).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {chosen.qualities.length > 0 && (
                <div className="space-y-2">
                  <Label>Quality</Label>
                  <Select
                    value={quality}
                    items={qualityItems}
                    onValueChange={(v) => setQuality(v ?? "default")}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.entries(qualityItems).map(([value, label]) => (
                        <SelectItem key={value} value={value}>
                          {label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
          )}

          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground">
              {noAccounts ? "Connect a provider before generating." : "Provider limits are always respected."}
            </p>
            <Button type="submit" disabled={busy || noAccounts || !prompt.trim()}>
              {busy ? <Loader2Icon className="animate-spin" /> : <SparklesIcon />}
              Generate
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
