import { ReactNode } from "react";

export function AuthCard({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <section className="w-full max-w-md rounded-lg border border-border bg-card/90 p-6 shadow-glow">
        <div className="mb-6">
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-primary">AI Dungeon Master</p>
          <h1 className="mt-2 text-2xl font-semibold">{title}</h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{subtitle}</p>
        </div>
        {children}
      </section>
    </main>
  );
}
