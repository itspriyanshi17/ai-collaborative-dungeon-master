"use client";

import Link from "next/link";
import { AlertCircle, CheckCircle2, Loader2, LogIn, LogOut, Plus, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/services/api";
import { createRoom } from "@/services/rooms";

export function Dashboard() {
  const router = useRouter();
  const { user, accessToken, logout } = useAuth();
  const [isCreating, setIsCreating] = useState(false);
  const [notice, setNotice] = useState<{ type: "success" | "error"; message: string } | null>(null);

  async function handleCreateRoom() {
    if (!accessToken) {
      setNotice({ type: "error", message: "Please sign in before creating a room." });
      return;
    }

    setIsCreating(true);
    setNotice(null);

    try {
      const room = await createRoom(accessToken);
      setNotice({ type: "success", message: `Room ${room.code} created.` });
      window.sessionStorage.setItem("room-create-success", room.code);
      router.push(`/rooms/${room.code}`);
    } catch (error) {
      setNotice({
        type: "error",
        message: error instanceof ApiError ? error.message : "Could not create the room. Please try again."
      });
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-6 px-4 py-5 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-4 border-b border-border pb-5 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-primary">
            Signed in as {user?.username}
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-normal text-foreground md:text-4xl">
            AI Collaborative Dungeon Master
          </h1>
        </div>
        <div className="flex gap-2">
          <Link
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md border border-border bg-muted px-4 text-sm font-semibold text-foreground transition hover:bg-muted/80 focus:outline-none focus:ring-2 focus:ring-primary"
            href="/rooms/join"
          >
            <LogIn className="h-4 w-4" />
            Join Room
          </Link>
          <Button variant="secondary" onClick={logout}>
            <LogOut className="h-4 w-4" />
            Logout
          </Button>
        </div>
      </header>

      <section className="flex flex-1 items-center justify-center">
        <div className="w-full rounded-lg border border-border bg-card/80 p-6 shadow-glow sm:p-8">
          <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div className="max-w-2xl">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-md border border-border bg-background/70">
                <Users className="h-6 w-6 text-accent" />
              </div>
              <h2 className="text-2xl font-semibold tracking-normal text-foreground">Create a waiting room</h2>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                Start a real room backed by PostgreSQL, then invite players with the generated code.
              </p>
            </div>
            <Button onClick={handleCreateRoom} disabled={isCreating} className="w-full md:w-auto">
              {isCreating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              {isCreating ? "Creating..." : "Create Room"}
            </Button>
          </div>

          {notice && (
            <div
              className={`mt-6 flex items-center gap-3 rounded-md border px-4 py-3 text-sm ${
                notice.type === "success"
                  ? "border-accent/40 bg-accent/10 text-foreground"
                  : "border-red-400/40 bg-red-500/10 text-red-100"
              }`}
            >
              {notice.type === "success" ? (
                <CheckCircle2 className="h-4 w-4 text-accent" />
              ) : (
                <AlertCircle className="h-4 w-4 text-red-300" />
              )}
              <span>{notice.message}</span>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
