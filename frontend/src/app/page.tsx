import {
  ImagesIcon,
  LayersIcon,
  ShieldCheckIcon,
  ZapIcon,
  GaugeIcon,
  PlugIcon,
} from "lucide-react";
import Link from "next/link";
import { Brand } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const FEATURES = [
  {
    icon: PlugIcon,
    title: "Connect authorized accounts",
    text: "Bring your own official API credentials. Keys are encrypted before storage and never shown again.",
  },
  {
    icon: LayersIcon,
    title: "One central job queue",
    text: "Submit a prompt once. Jobs are queued, retried and routed to an eligible connection automatically.",
  },
  {
    icon: GaugeIcon,
    title: "Limit-aware routing",
    text: "Provider rate limits are respected, never bypassed. Throttled accounts rest until the provider says go.",
  },
  {
    icon: ImagesIcon,
    title: "Unified results gallery",
    text: "Every image from every connection in a single searchable gallery, with bulk download and delete.",
  },
  {
    icon: ShieldCheckIcon,
    title: "Security first",
    text: "Argon2 password hashing, encrypted credentials, audit logs, strict headers and full request validation.",
  },
  {
    icon: ZapIcon,
    title: "Provider-agnostic",
    text: "OpenAI today. A clean adapter interface makes adding another official API a single-file change.",
  },
];

export default function Landing() {
  return (
    <div className="min-h-screen">
      <header className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Brand />
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Link href="/login" className={buttonVariants({ variant: "ghost" })}>
            Sign in
          </Link>
          <Link href="/register" className={buttonVariants()}>
            Get started
          </Link>
        </div>
      </header>

      <main>
        <section className="relative overflow-hidden">
          <div
            aria-hidden
            className="absolute inset-x-0 top-0 -z-10 h-[420px] bg-gradient-to-b from-primary/15 via-primary/5 to-transparent"
          />
          <div className="mx-auto max-w-3xl px-4 py-20 text-center sm:py-28">
            <span className="inline-flex items-center gap-2 rounded-full border bg-background px-3 py-1 text-xs text-muted-foreground">
              <ShieldCheckIcon className="size-3.5 text-primary" /> Official APIs and OAuth only
            </span>
            <h1 className="mt-6 text-4xl font-semibold tracking-tight sm:text-6xl">
              One dashboard for all your AI provider connections
            </h1>
            <p className="mx-auto mt-5 max-w-xl text-lg text-muted-foreground">
              Connect your authorized accounts, queue image generation jobs centrally, and manage
              results and usage from a single place.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Link href="/register" className={cn(buttonVariants({ size: "lg" }), "h-10 px-5")}>
                Create your workspace
              </Link>
              <Link
                href="/login"
                className={cn(buttonVariants({ variant: "outline", size: "lg" }), "h-10 px-5")}
              >
                Sign in
              </Link>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 pb-24 sm:px-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(({ icon: Icon, title, text }) => (
              <div key={title} className="rounded-xl border bg-card p-5">
                <div className="mb-3 flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Icon className="size-4.5" />
                </div>
                <h3 className="font-medium">{title}</h3>
                <p className="mt-1.5 text-sm text-muted-foreground">{text}</p>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
