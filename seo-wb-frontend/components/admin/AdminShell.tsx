"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, Bot, CreditCard, FolderKanban, Image, LogOut, Users } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/admin", label: "Dashboard", icon: BarChart3 },
  { href: "/admin/users", label: "Users", icon: Users },
  { href: "/admin/plans", label: "Plans", icon: CreditCard },
  { href: "/admin/models", label: "Models", icon: Image },
  { href: "/admin/jobs", label: "Jobs", icon: FolderKanban },
  { href: "/admin/usage", label: "Usage", icon: BarChart3 },
  { href: "/admin/settings/ai", label: "AI Settings", icon: Bot },
];

export function AdminShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#f4efe7_0%,#f7f5f0_42%,#fcfbf7_100%)] text-zinc-900">
      <div className="mx-auto grid min-h-screen max-w-[1600px] gap-6 px-4 py-4 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="rounded-[28px] border border-stone-200/80 bg-[#1f2937] p-5 text-stone-100 shadow-2xl shadow-stone-300/20">
          <div className="mb-8 rounded-2xl border border-white/10 bg-white/5 p-4">
            <p className="text-xs uppercase tracking-[0.24em] text-stone-300">Admin Panel</p>
            <h1 className="mt-2 text-xl font-semibold">{user?.name || "Admin"}</h1>
            <p className="mt-1 text-sm text-stone-300">{user?.email}</p>
          </div>
          <nav className="space-y-2">
            {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-3 rounded-2xl px-4 py-3 text-sm transition-colors",
                  pathname === href || (href !== "/admin" && pathname.startsWith(href))
                    ? "bg-amber-200 text-stone-950"
                    : "text-stone-200 hover:bg-white/8 hover:text-white"
                )}
              >
                <Icon size={16} />
                {label}
              </Link>
            ))}
          </nav>
          <button
            onClick={() => logout({ endpoint: "/admin/logout", redirectTo: "/admin/login" })}
            className="mt-8 flex w-full items-center gap-3 rounded-2xl border border-white/10 px-4 py-3 text-sm text-stone-200 transition-colors hover:bg-white/8 hover:text-white"
          >
            <LogOut size={16} />
            Logout
          </button>
        </aside>

        <main className="rounded-[32px] border border-stone-200 bg-white/90 p-6 shadow-xl shadow-stone-200/60 backdrop-blur">
          <header className="mb-6 flex flex-wrap items-end justify-between gap-3 border-b border-stone-200 pb-5">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-stone-400">Control Center</p>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight text-stone-950">{title}</h2>
              {subtitle ? <p className="mt-2 max-w-3xl text-sm text-stone-500">{subtitle}</p> : null}
            </div>
          </header>
          {children}
        </main>
      </div>
    </div>
  );
}
