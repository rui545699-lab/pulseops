import Link from "next/link";
import type { ReactNode } from "react";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[#f7f7f5] text-[#191918]">
      <header className="sticky top-0 z-40 border-b border-[#e5e5e1] bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[1400px] items-center justify-between px-5 sm:px-8 lg:px-12">
          <div className="flex items-center gap-9">
            <Link href="/" className="flex items-center gap-2.5" aria-label="PulseOps overview">
              <span className="grid size-7 place-items-center rounded-[8px] bg-[#181817] text-[11px] font-semibold text-white">
                P
              </span>
              <span className="text-[15px] font-semibold tracking-[-0.02em]">PulseOps</span>
            </Link>
            <nav className="hidden items-center gap-6 text-[13px] text-[#666660] sm:flex" aria-label="Primary navigation">
              <Link className="transition-colors hover:text-[#181817]" href="/">Overview</Link>
              <Link className="transition-colors hover:text-[#181817]" href="/#opportunities">Opportunities</Link>
              <Link className="transition-colors hover:text-[#181817]" href="/#runs">Runs</Link>
            </nav>
          </div>
          <div className="flex items-center gap-2 text-[12px] text-[#666660]">
            <span className="size-1.5 rounded-full bg-[#16836f]" />
            <span className="hidden sm:inline">Agent ready</span>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1400px] px-5 py-9 sm:px-8 sm:py-12 lg:px-12 lg:py-14">
        {children}
      </main>
    </div>
  );
}
