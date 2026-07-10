import { apiFetch } from "@/services/api";
import type { Character } from "@/types/game";

export function createCharacter(
  code: string,
  payload: { character_name: string; class: string; avatar: string },
  accessToken: string
) {
  return apiFetch<Character>(`/api/rooms/${code}/character`, {
    method: "POST",
    accessToken,
    body: JSON.stringify(payload),
  });
}

export function fetchCharacter(code: string, accessToken: string) {
  return apiFetch<Character>(`/api/rooms/${code}/character`, {
    method: "GET",
    accessToken,
  });
}
