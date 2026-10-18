import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

function navClass({ isActive }: { isActive: boolean }) {
  return `rounded-md px-3 py-1.5 text-sm font-medium ${isActive ? "bg-ink text-panel" : "text-muted hover:text-ink"}`;
}

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-panel">
        <div className="mx-auto flex max-w-7xl items-center gap-6 px-4 py-3">
          <NavLink to="/" className="flex items-center gap-2 font-bold tracking-tight">
            <svg aria-hidden viewBox="0 0 32 32" className="size-6">
              <rect width="32" height="32" rx="7" fill="var(--ink)" />
              <rect x="6" y="8" width="14" height="4" rx="2" fill="var(--ok)" />
              <rect x="10" y="14" width="10" height="4" rx="2" fill="var(--ok)" />
              <rect x="14" y="20" width="12" height="4" rx="2" fill="var(--fault)" />
              <rect x="21" y="5" width="2" height="22" fill="var(--cursor)" />
            </svg>
            ReplayLab
          </NavLink>
          <nav className="flex gap-1" aria-label="Main">
            <NavLink to="/" end className={navClass}>
              Runs
            </NavLink>
            <NavLink to="/compare" className={navClass}>
              Compare
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
    </div>
  );
}
