export type PlayerClass = "Warrior" | "Mage" | "Archer" | "Healer" | "Rogue";

export interface PartyMember {
  id: string;
  name: string;
  className: PlayerClass;
  health: number;
  mana: number;
  isReady: boolean;
}

export interface StoryEntry {
  id: string;
  roomId: string;
  narration: string;
  createdAt: string;
}

export interface Character {
  id: string;
  user_id: string;
  room_id: string;
  character_name: string;
  class: PlayerClass;
  avatar: string;
  level: number;
  experience: number;
  health: number;
  mana: number;
  strength: number;
  intelligence: number;
  agility: number;
  defense: number;
  luck: number;
  current_health: number;
  current_mana: number;
  gold: number;
  ready_for_game: boolean;
  created_at: string;
}

export interface RoomPlayer {
  id: string;
  user: {
    id: string;
    email: string;
    username: string;
    is_active: boolean;
    is_verified: boolean;
    created_at: string;
  };
  role: "HOST" | "PLAYER";
  is_connected: boolean;
  is_ready: boolean;
  joined_at: string;
  character?: Character | null;
}

export interface RoomPresence {
  code: string;
  status: Room["status"];
  host: Room["host"];
  players: RoomPlayer[];
}

export interface Room {
  id: string;
  code: string;
  status: "waiting" | "in_progress" | string;
  host: RoomPlayer["user"];
  players: RoomPlayer[];
  current_user_role: "HOST" | "PLAYER";
  created_at: string;
}
