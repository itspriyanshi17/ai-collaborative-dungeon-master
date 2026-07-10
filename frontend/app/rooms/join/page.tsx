"use client";

import { FormEvent, useMemo, useState } from "react";
import { AlertCircle, DoorOpen, Loader2, LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { ProtectedRoute } from "@/components/auth/protected-route";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/services/api";
import { joinRoom } from "@/services/rooms";

const ROOM_CODE_PATTERN = /^[A-Za-z0-9]{6}$/;

export default function JoinRoomPage() {
  return (
    <ProtectedRoute>
      <JoinRoomForm />
    </ProtectedRoute>
  );
}

function JoinRoomForm() {
  const router = useRouter();
  const { accessToken, logout, user } = useAuth();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isJoining, setIsJoining] = useState(false);

  useState(() => {
    if (typeof window !== "undefined") {
      const storedError = window.sessionStorage.getItem("room-error");
      if (storedError) {
        setError(storedError);
        window.sessionStorage.removeItem("room-error");
      }
    }
  });

  const normalizedCode = useMemo(() => code.trim().toUpperCase(), [code]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!ROOM_CODE_PATTERN.test(normalizedCode)) {
      setError("Enter a valid 6-character room code.");
      return;
    }

    if (!accessToken) {
      setError("Please sign in before joining a room.");
      return;
    }

    setIsJoining(true);
    try {
      const room = await joinRoom(normalizedCode, accessToken);
      window.sessionStorage.setItem("room-join-success", room.code);
      router.push(`/rooms/${room.code}`);
    } catch (joinError) {
      setError(joinError instanceof ApiError ? joinError.message : "Could not join the room. Please try again.");
    } finally {
      setIsJoining(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-6 px-4 py-5 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-4 border-b border-border pb-5 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-primary">
            Signed in as {user?.username}
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-normal text-foreground md:text-4xl">Join Room</h1>
        </div>
        <Button variant="secondary" onClick={logout}>
          <LogOut className="h-4 w-4" />
          Logout
        </Button>
      </header>

      <section className="flex flex-1 items-center justify-center">
        <form className="grid w-full max-w-md gap-5 rounded-lg border border-border bg-card/80 p-6 shadow-glow" onSubmit={onSubmit}>
          <label className="grid gap-2 text-sm font-medium" htmlFor="room-code">
            Room Code
            <input
              id="room-code"
              className="min-h-12 rounded-md border border-border bg-background px-3 font-mono text-lg uppercase tracking-[0.18em] outline-none transition placeholder:font-sans placeholder:text-sm placeholder:normal-case placeholder:tracking-normal placeholder:text-muted-foreground focus:border-primary"
              inputMode="text"
              maxLength={6}
              minLength={6}
              pattern="[A-Za-z0-9]{6}"
              placeholder="ABC123"
              value={code}
              onChange={(event) => setCode(event.target.value.toUpperCase())}
              required
            />
          </label>

          {error && (
            <div className="flex items-center gap-3 rounded-md border border-red-400/40 bg-red-500/10 px-4 py-3 text-sm text-red-100">
              <AlertCircle className="h-4 w-4 text-red-300" />
              <span>{error}</span>
            </div>
          )}

          <Button type="submit" disabled={isJoining}>
            {isJoining ? <Loader2 className="h-4 w-4 animate-spin" /> : <DoorOpen className="h-4 w-4" />}
            {isJoining ? "Joining..." : "Join Room"}
          </Button>
        </form>
      </section>
    </main>
  );
}
