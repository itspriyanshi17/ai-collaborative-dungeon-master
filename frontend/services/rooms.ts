import { apiFetch } from "@/services/api";
import type { Room } from "@/types/game";

export function createRoom(accessToken: string) {
  return apiFetch<Room>("/api/rooms", {
    method: "POST",
    accessToken
  });
}

export function joinRoom(code: string, accessToken: string) {
  return apiFetch<Room>("/api/rooms/join", {
    method: "POST",
    accessToken,
    body: JSON.stringify({ code })
  });
}

export function fetchRoom(code: string, accessToken: string) {
  return apiFetch<Room>(`/api/rooms/${code}`, {
    method: "GET",
    accessToken
  });
}

export function toggleReady(code: string, accessToken: string) {
  return apiFetch<Room>(`/api/rooms/${code}/ready`, {
    method: "POST",
    accessToken
  });
}

export function startGame(code: string, accessToken: string) {
  return apiFetch<Room>(`/api/rooms/${code}/start`, {
    method: "POST",
    accessToken
  });
}

export function kickPlayer(code: string, username: string, accessToken: string) {
  return apiFetch<Room>(`/api/rooms/${code}/kick`, {
    method: "POST",
    accessToken,
    body: JSON.stringify({ username })
  });
}

export function transferHost(code: string, username: string, accessToken: string) {
  return apiFetch<Room>(`/api/rooms/${code}/transfer-host`, {
    method: "POST",
    accessToken,
    body: JSON.stringify({ username })
  });
}

export function deleteRoom(code: string, accessToken: string) {
  return apiFetch<void>(`/api/rooms/${code}`, {
    method: "DELETE",
    accessToken
  });
}

export function leaveRoom(code: string, accessToken: string) {
  return apiFetch<{ message: string }>(`/api/rooms/${code}/leave`, {
    method: "POST",
    accessToken
  });
}
