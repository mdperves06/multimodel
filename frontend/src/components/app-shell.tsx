"use client";

import {
  ImagesIcon,
  KeyRoundIcon,
  LayoutDashboardIcon,
  ListChecksIcon,
  LogOutIcon,
  MenuIcon,
  SettingsIcon,
  BarChart3Icon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import { toast } from "sonner";
import { mutate } from "swr";
import { Brand } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { apiPost } from "@/lib/api";
import { useUser } from "@/lib/hooks";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboardIcon },
  { href: "/accounts", label: "Accounts", icon: KeyRoundIcon },
  { href: "/jobs", label: "Jobs", icon: ListChecksIcon },
  { href: "/gallery", label: "Gallery", icon: ImagesIcon },
  { href: "/usage", label: "Usage", icon: BarChart3Icon },
  { href: "/settings", label: "Settings", icon: SettingsIcon },
];

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="flex flex-col gap-1 px-3">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              active
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            <Icon className="size-4" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

function UserMenu() {
  const { data: user } = useUser();
  const router = useRouter();

  async function logout() {
    try {
      await apiPost("/auth/logout");
    } finally {
      await mutate(() => true, undefined, { revalidate: false });
      toast.success("Signed out");
      router.push("/login");
      router.refresh();
    }
  }

  const initial = (user?.display_name || user?.email || "?").slice(0, 1).toUpperCase();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={<Button variant="ghost" className="h-9 gap-2 px-1.5" aria-label="Account menu" />}
      >
        <Avatar className="size-7">
          <AvatarFallback>{initial}</AvatarFallback>
        </Avatar>
        <span className="hidden max-w-40 truncate text-sm sm:inline">
          {user?.display_name || user?.email}
        </span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="truncate">{user?.email}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => router.push("/settings")}>
          <SettingsIcon /> Settings
        </DropdownMenuItem>
        <DropdownMenuItem onClick={logout}>
          <LogOutIcon /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const { isLoading, error } = useUser();

  return (
    <div className="min-h-screen bg-muted/30">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r bg-background lg:flex">
        <div className="flex h-14 items-center border-b px-4">
          <Brand href="/dashboard" />
        </div>
        <div className="flex-1 overflow-y-auto py-4">
          <NavLinks />
        </div>
        <p className="border-t p-4 text-xs text-muted-foreground">
          Official provider APIs only. Credentials are encrypted at rest.
        </p>
      </aside>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="left" className="w-64 p-0">
          <SheetHeader className="border-b">
            <SheetTitle>
              <Brand href="/dashboard" />
            </SheetTitle>
          </SheetHeader>
          <div className="py-2">
            <NavLinks onNavigate={() => setOpen(false)} />
          </div>
        </SheetContent>
      </Sheet>

      <div className="lg:pl-60">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-2 border-b bg-background/80 px-4 backdrop-blur sm:px-6">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            aria-label="Open navigation"
            onClick={() => setOpen(true)}
          >
            <MenuIcon />
          </Button>
          <div className="lg:hidden">
            <Brand href="/dashboard" className="text-sm" />
          </div>
          <div className="ml-auto flex items-center gap-1">
            <ThemeToggle />
            {isLoading ? <Skeleton className="size-8 rounded-full" /> : !error && <UserMenu />}
          </div>
        </header>
        <main className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}
