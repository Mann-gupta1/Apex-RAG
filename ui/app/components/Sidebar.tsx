"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Search, MessageCircle, BarChart2, Settings, Sparkles } from "lucide-react";
import clsx from "clsx";

const items = [
  { href: "/search", label: "Search", icon: Search },
  { href: "/chat", label: "Chat", icon: MessageCircle },
  { href: "/eval", label: "Eval", icon: BarChart2 },
  { href: "/admin", label: "Admin", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="bg-white dark:bg-ink-900 border-r border-ink-200 dark:border-ink-800">
      <div className="p-4 flex items-center gap-2 border-b border-ink-200 dark:border-ink-800">
        <Sparkles className="w-5 h-5 text-brand" />
        <Link href="/" className="font-semibold">
          Apex RAG
        </Link>
      </div>
      <nav className="p-2 space-y-1">
        {items.map(({ href, label, icon: Icon }) => {
          const active = pathname?.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                "flex items-center gap-2 rounded-md px-3 py-2 text-sm",
                active
                  ? "bg-brand/10 text-brand-700 dark:text-brand"
                  : "text-ink-700 dark:text-ink-300 hover:bg-ink-100 dark:hover:bg-ink-800"
              )}
            >
              <Icon className="w-4 h-4" />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
