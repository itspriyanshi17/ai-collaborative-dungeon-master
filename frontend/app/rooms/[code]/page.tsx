"use client";

import {
  AlertCircle,
  ArrowLeftRight,
  Check,
  CheckCircle2,
  Copy,
  Crown,
  Loader2,
  LogOut,
  Play,
  Trash2,
  UserMinus,
  Users,
  XCircle,
} from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ProtectedRoute } from "@/components/auth/protected-route";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/services/api";
import {
  deleteRoom,
  fetchRoom,
  kickPlayer,
  leaveRoom,
  startGame,
  toggleReady,
  transferHost,
} from "@/services/rooms";
import { getSocket } from "@/socket/client";
import type { Room, RoomPresence, Character } from "@/types/game";
import CharacterCreation, { AVATARS } from "@/components/game/character-creation";

function getAvatarColor(username: string) {
  const colors = [
    "from-pink-500 to-rose-500",
    "from-purple-500 to-indigo-500",
    "from-blue-500 to-cyan-500",
    "from-green-500 to-teal-500",
    "from-yellow-500 to-amber-500",
    "from-orange-500 to-red-500",
  ];
  let hash = 0;
  for (let i = 0; i < username.length; i++) {
    hash = username.charCodeAt(i) + ((hash << 5) - hash);
  }
  const index = Math.abs(hash) % colors.length;
  return colors[index];
}

function getInitials(username: string) {
  if (!username) return "?";
  return username.slice(0, 2).toUpperCase();
}

export default function WaitingRoomPage() {
  return (
    <ProtectedRoute>
      <WaitingRoom />
    </ProtectedRoute>
  );
}

function WaitingRoom() {
  const params = useParams<{ code: string }>();
  const router = useRouter();
  const { accessToken, logout, user } = useAuth();
  const [room, setRoom] = useState<Room | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [isActionPending, setIsActionPending] = useState(false);

  // Clear notice after 5 seconds
  useEffect(() => {
    if (notice) {
      const timer = setTimeout(() => setNotice(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [notice]);

  // Fetch Room Data initially
  useEffect(() => {
    if (!accessToken || !params.code) {
      return;
    }

    let isMounted = true;
    setIsLoading(true);
    setError(null);

    fetchRoom(params.code, accessToken)
      .then((roomData) => {
        if (!isMounted) return;
        setRoom(roomData);
        const createdCode = window.sessionStorage.getItem("room-create-success");
        const joinedCode = window.sessionStorage.getItem("room-join-success");
        if (createdCode === roomData.code) {
          setNotice(`Room ${roomData.code} created successfully.`);
          window.sessionStorage.removeItem("room-create-success");
        }
        if (joinedCode === roomData.code) {
          setNotice(`Joined room ${roomData.code}.`);
          window.sessionStorage.removeItem("room-join-success");
        }
      })
      .catch((fetchError) => {
        if (!isMounted) return;
        setError(fetchError instanceof ApiError ? fetchError.message : "Could not load the room.");
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [accessToken, params.code]);

  // Setup Socket.IO Event Listeners
  useEffect(() => {
    const token = accessToken;
    if (!token || !params.code || !user) {
      return;
    }

    const socket = getSocket();
    const code = params.code.toUpperCase();

    function handlePlayersUpdated(payload: RoomPresence) {
      if (payload.code !== code) return;
      setRoom((currentRoom) => {
        if (!currentRoom) return null;
        
        // Find my current role
        const myPlayer = payload.players.find((p) => p.user.id === user?.id);
        const updatedRole = myPlayer ? myPlayer.role : "PLAYER";

        return {
          ...currentRoom,
          status: payload.status,
          host: payload.host,
          players: payload.players,
          current_user_role: updatedRole,
        };
      });
    }

    function handlePlayerJoined(payload: { code: string; username: string }) {
      if (payload.code === code) {
        setNotice(`${payload.username} joined the room.`);
      }
    }

    function handlePlayerLeft(payload: { code: string; username: string }) {
      if (payload.code === code) {
        setNotice(`${payload.username} left the room.`);
      }
    }

    function handlePlayerReady(payload: { code: string; username: string; is_ready: boolean }) {
      if (payload.code === code) {
        setNotice(`${payload.username} is now ${payload.is_ready ? "Ready" : "Not Ready"}.`);
      }
    }

    function handleHostChanged(payload: { code: string; new_host_username: string }) {
      if (payload.code === code) {
        setNotice(`${payload.new_host_username} has been promoted to Host.`);
      }
    }

    function handlePlayerKicked(payload: { code: string; username: string }) {
      if (payload.code === code) {
        if (payload.username === user?.username) {
          window.sessionStorage.setItem("room-error", "You have been kicked from the room by the host.");
          router.push("/rooms/join");
        } else {
          setNotice(`${payload.username} was kicked from the room.`);
        }
      }
    }

    function handleRoomDeleted(payload: { code: string }) {
      if (payload.code === code) {
        window.sessionStorage.setItem("room-error", "The host has deleted the room.");
        router.push("/rooms/join");
      }
    }

    function handleGameStarted(payload: { code: string }) {
      if (payload.code === code) {
        setNotice("The DM has started the game! Prepare yourself!");
        setRoom((currentRoom) => currentRoom ? { ...currentRoom, status: "playing" } : null);
      }
    }

    function handleRoomError(payload: { message?: string }) {
      setError(payload.message ?? "Real-time room updates are unavailable.");
    }

    function handleCharacterCreated(payload: { code: string; username: string; character: Character }) {
      if (payload.code === code) {
        setNotice(`${payload.username} created character "${payload.character.character_name}"!`);
        fetchRoom(params.code, token!).then((roomData) => setRoom(roomData)).catch(() => {});
      }
    }

    function handleCharacterUpdated(payload: { code: string; username: string; character: Character }) {
      if (payload.code === code) {
        setNotice(`${payload.username} updated their character!`);
        fetchRoom(params.code, token!).then((roomData) => setRoom(roomData)).catch(() => {});
      }
    }

    socket.on("room:players_updated", handlePlayersUpdated);
    socket.on("room:player_joined", handlePlayerJoined);
    socket.on("room:player_left", handlePlayerLeft);
    socket.on("room:player_ready", handlePlayerReady);
    socket.on("room:host_changed", handleHostChanged);
    socket.on("room:player_kicked", handlePlayerKicked);
    socket.on("room:room_deleted", handleRoomDeleted);
    socket.on("room:game_started", handleGameStarted);
    socket.on("room:character_created", handleCharacterCreated);
    socket.on("character_created", handleCharacterCreated);
    socket.on("room:character_updated", handleCharacterUpdated);
    socket.on("character_updated", handleCharacterUpdated);
    socket.on("room:error", handleRoomError);

    if (!socket.connected) {
      socket.connect();
    }
    socket.emit("room_subscribe", { code, token });

    return () => {
      socket.off("room:players_updated", handlePlayersUpdated);
      socket.off("room:player_joined", handlePlayerJoined);
      socket.off("room:player_left", handlePlayerLeft);
      socket.off("room:player_ready", handlePlayerReady);
      socket.off("room:host_changed", handleHostChanged);
      socket.off("room:player_kicked", handlePlayerKicked);
      socket.off("room:room_deleted", handleRoomDeleted);
      socket.off("room:game_started", handleGameStarted);
      socket.off("room:character_created", handleCharacterCreated);
      socket.off("character_created", handleCharacterCreated);
      socket.off("room:character_updated", handleCharacterUpdated);
      socket.off("character_updated", handleCharacterUpdated);
      socket.off("room:error", handleRoomError);
    };
  }, [accessToken, params.code, user, router]);

  async function copyRoomCode() {
    if (!room) return;
    await navigator.clipboard.writeText(room.code);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  }

  // Action wrappers to handle error display & loading state
  async function performAction(actionFn: () => Promise<unknown>, errorMessage: string) {
    if (isActionPending) return;
    setIsActionPending(true);
    setError(null);
    try {
      await actionFn();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : errorMessage);
    } finally {
      setIsActionPending(false);
    }
  }

  const isHost = room?.current_user_role === "HOST";
  const myPlayerInfo = room?.players.find((p) => p.user.id === user?.id);
  const isReady = myPlayerInfo?.is_ready ?? false;
  const myCharacter = myPlayerInfo?.character;
  const hasCreatedCharacter = !!myCharacter;

  const canStartGame = room && room.players.every((p) => {
    const hasChar = !!p.character;
    const isReady = p.role === "HOST" || p.is_ready;
    return hasChar && isReady;
  });

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 px-4 py-5 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-4 border-b border-border pb-5 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-primary">
            Signed in as {user?.username}
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-normal text-foreground md:text-4xl">Waiting Room</h1>
        </div>
        <Button variant="secondary" onClick={logout}>
          <LogOut className="h-4 w-4" />
          Logout
        </Button>
      </header>

      {isLoading && (
        <section className="flex flex-1 items-center justify-center rounded-lg border border-border bg-card/80 p-8">
          <div className="flex items-center gap-3 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            Loading room...
          </div>
        </section>
      )}

      {!isLoading && error && (
        <section className="rounded-lg border border-red-400/40 bg-red-500/10 p-5 text-red-100">
          <div className="flex items-center gap-3">
            <AlertCircle className="h-5 w-5 text-red-300" />
            <p>{error}</p>
          </div>
        </section>
      )}

      {!isLoading && room && (
        <section className="grid flex-1 gap-5 lg:grid-cols-[1fr_0.8fr]">
          <div className="flex flex-col gap-5">
            {notice && (
              <div className="flex items-center gap-3 rounded-md border border-accent/40 bg-accent/10 px-4 py-3 text-sm text-foreground">
                <Check className="h-4 w-4 text-accent" />
                <span>{notice}</span>
              </div>
            )}

            {!hasCreatedCharacter ? (
              <CharacterCreation
                roomCode={room.code}
                accessToken={accessToken!}
                onSuccess={() => {
                  fetchRoom(params.code, accessToken!).then((roomData) => setRoom(roomData)).catch(() => {});
                }}
              />
            ) : (
              <div className="rounded-lg border border-border bg-card/80 p-5 shadow-glow">
                <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-sm font-medium uppercase tracking-[0.18em] text-muted-foreground">Room Code</p>
                    <p className="mt-3 font-mono text-5xl font-semibold tracking-normal text-primary">{room.code}</p>
                  </div>
                  <Button variant="secondary" onClick={copyRoomCode}>
                    {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                    {copied ? "Copied" : "Copy Room Code"}
                  </Button>
                </div>

                <div className="mt-8 grid gap-4 sm:grid-cols-2">
                  <div className="rounded-md border border-border bg-background/60 p-4">
                    <div className="mb-3 flex items-center gap-2 text-sm text-muted-foreground">
                      <Crown className="h-4 w-4 text-primary" />
                      Host
                    </div>
                    <p className="text-lg font-semibold">{room.host.username}</p>
                    <p className="mt-1 text-sm text-muted-foreground">{room.host.email}</p>
                  </div>
                  <div className="rounded-md border border-border bg-background/60 p-4">
                    <div className="mb-3 flex items-center gap-2 text-sm text-muted-foreground">
                      <Users className="h-4 w-4 text-accent" />
                      Connected Players
                    </div>
                    <p className="text-lg font-semibold">{room.players.filter((player) => player.is_connected).length}</p>
                    <p className="mt-1 text-sm text-muted-foreground">Waiting for the party to gather.</p>
                  </div>
                </div>

                {room.status === "playing" && (
                  <div className="mt-8 rounded-lg border border-accent/40 bg-accent/10 p-5 text-center">
                    <h3 className="text-xl font-semibold text-accent">Game in Progress</h3>
                    <p className="mt-2 text-muted-foreground text-sm">
                      The host has started the game! Prepare to enter the dungeon.
                    </p>
                  </div>
                )}

                <div className="mt-8 flex flex-col gap-4">
                  <div className="flex flex-wrap gap-4">
                    {isHost ? (
                      <>
                        {room.status !== "playing" && (
                          <Button
                            onClick={() => performAction(() => startGame(room.code, accessToken!), "Failed to start game.")}
                            disabled={isActionPending || !canStartGame}
                            className="bg-accent hover:bg-accent/80 font-bold"
                          >
                            {isActionPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                            Start Game
                          </Button>
                        )}
                        <Button
                          variant="secondary"
                          onClick={() => performAction(() => deleteRoom(room.code, accessToken!), "Failed to delete room.")}
                          disabled={isActionPending}
                          className="border-red-900/50 text-red-400 hover:bg-red-500/10 hover:border-red-900 font-semibold"
                        >
                          <Trash2 className="h-4 w-4" />
                          Delete Room
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button
                          onClick={() => performAction(() => toggleReady(room.code, accessToken!), "Failed to toggle ready status.")}
                          disabled={isActionPending}
                          variant={isReady ? "secondary" : "primary"}
                          className="font-bold"
                        >
                          {isReady ? <XCircle className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
                          {isReady ? "Set Not Ready" : "Set Ready"}
                        </Button>
                        <Button
                          variant="secondary"
                          onClick={() => performAction(() => leaveRoom(room.code, accessToken!).then(() => router.push("/rooms/join")), "Failed to leave room.")}
                          disabled={isActionPending}
                        >
                          <LogOut className="h-4 w-4" />
                          Leave Room
                        </Button>
                      </>
                    )}
                  </div>
                  {isHost && !canStartGame && (
                    <p className="text-xs text-amber-400 font-medium animate-pulse">
                      ⚠ Start Game is disabled until all connected players have created characters and clicked Ready.
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>

          <aside className="rounded-lg border border-border bg-card/80 p-5 flex flex-col gap-5">
            <div className="flex items-center gap-2">
              <Users className="h-5 w-5 text-accent" />
              <h2 className="text-lg font-semibold">Players ({room.players.length})</h2>
            </div>
            <div className="space-y-3 overflow-y-auto max-h-[75vh]">
              {room.players.map((player) => {
                const isPlayerHost = player.role === "HOST";
                const char = player.character;
                const charAvatar = char ? AVATARS.find((av) => av.id === char.avatar) : null;
                const AvatarIcon = charAvatar ? charAvatar.Icon : null;
                const initials = getInitials(player.user.username);
                const avatarGrad = charAvatar ? charAvatar.gradient : getAvatarColor(player.user.username);

                return (
                  <div key={player.id} className="rounded-md border border-border bg-background/60 p-4">
                    <div className="flex flex-col gap-3">
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-3">
                          <div
                            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br font-semibold text-white ${avatarGrad}`}
                          >
                            {AvatarIcon ? <AvatarIcon className="h-5 w-5 text-white" /> : initials}
                          </div>
                          <div>
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="font-semibold text-sm sm:text-base text-foreground">
                                {char ? char.character_name : player.user.username}
                              </span>
                              {char && (
                                <span className="text-xs text-muted-foreground">
                                  ({player.user.username})
                                </span>
                              )}
                              {isPlayerHost && <Crown className="h-3.5 w-3.5 text-yellow-400 fill-yellow-400" />}
                            </div>
                            <div className="flex items-center gap-2 mt-0.5">
                              <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                                {player.role}
                              </p>
                              {char && (
                                <span className="rounded bg-primary/20 px-1.5 py-0.5 text-[10px] font-semibold text-primary">
                                  {char.class} (Lv.{char.level})
                                </span>
                              )}
                            </div>
                          </div>
                        </div>

                        <div className="flex flex-col items-end gap-2 text-xs">
                          <div className="flex items-center gap-2">
                            <span
                              className={`rounded-full px-2.5 py-0.5 font-semibold text-[10px] sm:text-xs ${
                                player.is_ready ? "bg-accent/15 text-accent" : "bg-muted text-muted-foreground"
                              }`}
                            >
                              {player.is_ready ? "Ready" : "Not Ready"}
                            </span>
                            <span className="flex items-center gap-1.5 text-muted-foreground">
                              <span
                                className={`h-2.5 w-2.5 rounded-full ${
                                  player.is_connected ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" : "bg-muted-foreground"
                                }`}
                                aria-hidden="true"
                              />
                              <span className="hidden sm:inline">{player.is_connected ? "Connected" : "Disconnected"}</span>
                            </span>
                          </div>

                          {isHost && player.user.id !== user?.id && (
                            <div className="flex items-center gap-2 mt-1">
                              <button
                                className="h-7 px-2 inline-flex items-center justify-center rounded-md border border-border bg-muted text-xs text-muted-foreground hover:text-amber-400 hover:bg-muted/80 disabled:opacity-50 transition font-semibold"
                                title="Transfer Host"
                                disabled={isActionPending}
                                onClick={() =>
                                  performAction(
                                    () => transferHost(room.code, player.user.username, accessToken!),
                                    "Failed to transfer host."
                                  )
                                }
                              >
                                <ArrowLeftRight className="h-3.5 w-3.5 mr-1" />
                                Host
                              </button>
                              <button
                                className="h-7 px-2 inline-flex items-center justify-center rounded-md border border-border bg-muted text-xs text-muted-foreground hover:text-red-400 hover:bg-muted/80 disabled:opacity-50 transition font-semibold"
                                title="Kick Player"
                                disabled={isActionPending}
                                onClick={() =>
                                  performAction(
                                    () => kickPlayer(room.code, player.user.username, accessToken!),
                                    "Failed to kick player."
                                  )
                                }
                              >
                                <UserMinus className="h-3.5 w-3.5 mr-1" />
                                Kick
                              </button>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Character Stats preview and status */}
                      <div className="flex items-center justify-between border-t border-border/40 pt-2 text-[11px] sm:text-xs">
                        <span className="flex items-center gap-1">
                          <span
                            className={`h-2 w-2 rounded-full ${
                              char ? "bg-emerald-500" : "bg-amber-500 animate-pulse"
                            }`}
                          />
                          <span className="text-muted-foreground">
                            {char ? "✓ Created" : "⚠ Creating..."}
                          </span>
                        </span>

                        {char && (
                          <span className="text-muted-foreground">
                            HP: <span className="text-rose-400 font-semibold">{char.health}</span> | 
                            MP: <span className="text-blue-400 font-semibold">{char.mana}</span> | 
                            Gold: <span className="text-amber-400 font-semibold">{char.gold}g</span>
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </aside>
        </section>
      )}
    </main>
  );
}

