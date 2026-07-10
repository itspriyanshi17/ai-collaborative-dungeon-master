"use client";

import React, { useState } from "react";
import {
  Shield,
  Wand2,
  Swords,
  Flame,
  Heart,
  Skull,
  Crown,
  Ghost,
  Sparkles,
  Target,
  Music,
  Compass,
  Sun,
  Leaf,
  FlaskConical,
  Loader2,
  Dices,
  Info,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { createCharacter } from "@/services/characters";

interface CharacterCreationProps {
  roomCode: string;
  accessToken: string;
  onSuccess: () => void;
}

export interface ClassPreset {
  name: string;
  description: string;
  stats: {
    health: number;
    mana: number;
    strength: number;
    intelligence: number;
    agility: number;
    defense: number;
    luck: number;
    gold: number;
  };
}

export const CLASS_PRESETS: Record<string, ClassPreset> = {
  Warrior: {
    name: "Warrior",
    description: "A mighty champion of strength and defense. Thrives in the heat of battle with high health and devastating melee power.",
    stats: {
      health: 140,
      mana: 20,
      strength: 16,
      intelligence: 6,
      agility: 8,
      defense: 12,
      luck: 8,
      gold: 100,
    },
  },
  Mage: {
    name: "Mage",
    description: "A master of the arcane arts. Commands overwhelming mana and intelligence to launch devastating spells, though physically vulnerable.",
    stats: {
      health: 80,
      mana: 150,
      strength: 6,
      intelligence: 18,
      agility: 9,
      defense: 6,
      luck: 10,
      gold: 120,
    },
  },
  Archer: {
    name: "Archer",
    description: "A swift and precise marksman. High agility and critical strike potential allow them to take down foes from a safe distance.",
    stats: {
      health: 100,
      mana: 40,
      strength: 10,
      intelligence: 10,
      agility: 16,
      defense: 8,
      luck: 14,
      gold: 90,
    },
  },
  Rogue: {
    name: "Rogue",
    description: "A master of stealth and fortune. Incredible speed and luck let them strike swiftly, evade attacks, and find hidden riches.",
    stats: {
      health: 90,
      mana: 30,
      strength: 9,
      intelligence: 8,
      agility: 18,
      defense: 7,
      luck: 16,
      gold: 150,
    },
  },
  Healer: {
    name: "Healer",
    description: "A devoted protector and support. Wields powerful restorative magic with high mana and healing bonuses to sustain the party.",
    stats: {
      health: 110,
      mana: 100,
      strength: 8,
      intelligence: 12,
      agility: 10,
      defense: 9,
      luck: 14,
      gold: 110,
    },
  },
};

export const AVATARS = [
  { id: "avatar_1", name: "Shieldmaiden", gradient: "from-amber-600 to-yellow-800", Icon: Shield },
  { id: "avatar_2", name: "Shadow Weaver", gradient: "from-purple-600 to-indigo-800", Icon: Wand2 },
  { id: "avatar_3", name: "Gladiator", gradient: "from-red-600 to-rose-900", Icon: Swords },
  { id: "avatar_4", name: "Pyromancer", gradient: "from-orange-500 to-red-700", Icon: Flame },
  { id: "avatar_5", name: "Holy Cleric", gradient: "from-pink-500 to-rose-600", Icon: Heart },
  { id: "avatar_6", name: "Necromancer", gradient: "from-slate-700 to-zinc-900", Icon: Skull },
  { id: "avatar_7", name: "Rune Knight", gradient: "from-yellow-500 to-amber-700", Icon: Crown },
  { id: "avatar_8", name: "Plague Doctor", gradient: "from-cyan-600 to-blue-800", Icon: Ghost },
  { id: "avatar_9", name: "Archmage", gradient: "from-indigo-500 to-purple-700", Icon: Sparkles },
  { id: "avatar_10", name: "Assassin", gradient: "from-emerald-600 to-teal-800", Icon: Target },
  { id: "avatar_11", name: "Bard of Lore", gradient: "from-fuchsia-500 to-pink-700", Icon: Music },
  { id: "avatar_12", name: "Elven Ranger", gradient: "from-lime-600 to-green-800", Icon: Compass },
  { id: "avatar_13", name: "Monk of Light", gradient: "from-yellow-400 to-orange-600", Icon: Sun },
  { id: "avatar_14", name: "Druid of Wilds", gradient: "from-green-500 to-emerald-700", Icon: Leaf },
  { id: "avatar_15", name: "Alchemist", gradient: "from-blue-500 to-cyan-700", Icon: FlaskConical },
];

export default function CharacterCreation({ roomCode, accessToken, onSuccess }: CharacterCreationProps) {
  const [characterName, setCharacterName] = useState("");
  const [selectedClass, setSelectedClass] = useState<string>("Warrior");
  const [selectedAvatar, setSelectedAvatar] = useState<string>("avatar_1");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const activePreset = CLASS_PRESETS[selectedClass];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!characterName.trim()) {
      setError("Character name is required.");
      return;
    }
    if (!selectedClass) {
      setError("Please select a class.");
      return;
    }
    if (!selectedAvatar) {
      setError("Please select an avatar.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await createCharacter(
        roomCode,
        {
          character_name: characterName.trim(),
          class: selectedClass,
          avatar: selectedAvatar,
        },
        accessToken
      );
      onSuccess();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to create character. Please try a different name.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const generateRandomName = () => {
    const prefixes = ["Thorin", "Eldrin", "Lyra", "Gideon", "Valerie", "Zephyr", "Riona", "Kaelen", "Freya", "Bram", "Sylas", "Morrigan"];
    const suffixes = ["Oakshield", "Stormweaver", "Swiftbow", "Ironclad", "Sunweaver", "Shadowwhisper", "Goldhand", "Dawnwarden"];
    const randomPrefix = prefixes[Math.floor(Math.random() * prefixes.length)];
    const randomSuffix = suffixes[Math.floor(Math.random() * suffixes.length)];
    setCharacterName(`${randomPrefix} ${randomSuffix}`);
  };

  return (
    <div className="flex flex-col gap-6 rounded-lg border border-border bg-card/85 p-6 shadow-glow backdrop-blur-md">
      <div className="border-b border-border pb-4">
        <h2 className="text-2xl font-bold tracking-tight text-foreground">Create Your Character</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Forge your hero before joining the adventure. Choose class and stats wisely.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        {error && (
          <div className="rounded-md border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
            {error}
          </div>
        )}

        {/* Character Name */}
        <div className="flex flex-col gap-2">
          <label htmlFor="characterName" className="text-sm font-semibold tracking-wider text-muted-foreground uppercase">
            Character Name
          </label>
          <div className="flex gap-2">
            <input
              id="characterName"
              type="text"
              placeholder="Enter hero name..."
              value={characterName}
              onChange={(e) => setCharacterName(e.target.value)}
              className="flex-1 rounded-md border border-border bg-background/50 px-4 py-2 text-foreground focus:border-primary focus:outline-none"
              maxLength={100}
              disabled={isSubmitting}
            />
            <Button
              type="button"
              variant="secondary"
              onClick={generateRandomName}
              disabled={isSubmitting}
              title="Generate Random Name"
              className="px-3"
            >
              <Dices className="h-4 w-4 mr-1.5" />
              Random
            </Button>
          </div>
        </div>

        <div className="grid gap-6 md:grid-cols-[1fr_0.8fr]">
          <div className="flex flex-col gap-6">
            {/* Class Selection */}
            <div className="flex flex-col gap-2">
              <span className="text-sm font-semibold tracking-wider text-muted-foreground uppercase">
                Choose Class
              </span>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {Object.keys(CLASS_PRESETS).map((key) => {
                  const preset = CLASS_PRESETS[key];
                  const isSelected = selectedClass === key;

                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setSelectedClass(key)}
                      disabled={isSubmitting}
                      className={`flex flex-col items-center justify-center gap-2 rounded-md border p-4 transition-all ${
                        isSelected
                          ? "border-primary bg-primary/10 shadow-glow"
                          : "border-border bg-background/40 hover:border-border/80"
                      }`}
                    >
                      <span className="font-semibold text-foreground text-sm sm:text-base">{preset.name}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Avatar Selection */}
            <div className="flex flex-col gap-2">
              <span className="text-sm font-semibold tracking-wider text-muted-foreground uppercase">
                Choose Avatar
              </span>
              <div className="grid grid-cols-5 gap-2 rounded-lg bg-background/30 p-3 border border-border">
                {AVATARS.map((avatar) => {
                  const AvatarIcon = avatar.Icon;
                  const isSelected = selectedAvatar === avatar.id;

                  return (
                    <button
                      key={avatar.id}
                      type="button"
                      onClick={() => setSelectedAvatar(avatar.id)}
                      disabled={isSubmitting}
                      title={avatar.name}
                      className={`relative flex aspect-square items-center justify-center rounded-full bg-gradient-to-br text-white shadow-md transition-transform active:scale-95 ${
                        avatar.gradient
                      } ${isSelected ? "ring-2 ring-primary ring-offset-2 ring-offset-card" : "hover:brightness-110"}`}
                    >
                      <AvatarIcon className="h-5 w-5 sm:h-6 sm:w-6" />
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Live Stat Preview */}
          <div className="flex flex-col gap-4 rounded-lg border border-border bg-background/40 p-4">
            <div>
              <div className="flex items-center gap-1.5">
                <h3 className="text-base font-semibold text-primary">{activePreset.name} Preview</h3>
              </div>
              <p className="mt-2 text-xs text-muted-foreground leading-relaxed">
                {activePreset.description}
              </p>
            </div>

            <div className="border-t border-border pt-3">
              <span className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                Starting Stats
              </span>
              <div className="mt-3 space-y-2 text-xs sm:text-sm">
                {/* Health */}
                <div className="flex flex-col gap-1">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Health</span>
                    <span className="font-semibold text-rose-400">{activePreset.stats.health}</span>
                  </div>
                  <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full bg-rose-500 rounded-full transition-all duration-300"
                      style={{ width: `${Math.min(100, (activePreset.stats.health / 150) * 100)}%` }}
                    />
                  </div>
                </div>

                {/* Mana */}
                <div className="flex flex-col gap-1">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Mana</span>
                    <span className="font-semibold text-blue-400">{activePreset.stats.mana}</span>
                  </div>
                  <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full bg-blue-500 rounded-full transition-all duration-300"
                      style={{ width: `${Math.min(100, (activePreset.stats.mana / 150) * 100)}%` }}
                    />
                  </div>
                </div>

                {/* Strength, Intelligence, Agility, Defense, Luck */}
                <div className="grid grid-cols-2 gap-x-4 gap-y-2 border-t border-border/40 pt-3">
                  <div className="flex justify-between border-b border-border/20 pb-1">
                    <span className="text-muted-foreground text-xs">Strength</span>
                    <span className="font-semibold text-foreground">{activePreset.stats.strength}</span>
                  </div>
                  <div className="flex justify-between border-b border-border/20 pb-1">
                    <span className="text-muted-foreground text-xs">Agility</span>
                    <span className="font-semibold text-foreground">{activePreset.stats.agility}</span>
                  </div>
                  <div className="flex justify-between border-b border-border/20 pb-1">
                    <span className="text-muted-foreground text-xs">Intelligence</span>
                    <span className="font-semibold text-foreground">{activePreset.stats.intelligence}</span>
                  </div>
                  <div className="flex justify-between border-b border-border/20 pb-1">
                    <span className="text-muted-foreground text-xs">Defense</span>
                    <span className="font-semibold text-foreground">{activePreset.stats.defense}</span>
                  </div>
                  <div className="flex justify-between col-span-2">
                    <span className="text-muted-foreground text-xs">Luck</span>
                    <span className="font-semibold text-foreground">{activePreset.stats.luck}</span>
                  </div>
                </div>

                {/* Gold */}
                <div className="flex justify-between border-t border-border/40 pt-3 text-xs sm:text-sm font-semibold">
                  <span className="text-amber-500">Starting Gold</span>
                  <span className="text-amber-400">{activePreset.stats.gold}g</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Submit Button */}
        <Button
          type="submit"
          className="w-full bg-primary text-primary-foreground font-bold hover:bg-primary/95 text-base py-5 tracking-wide shadow-lg"
          disabled={isSubmitting}
        >
          {isSubmitting ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin mr-2" />
              Forging Character...
            </>
          ) : (
            "Create Character"
          )}
        </Button>
      </form>
    </div>
  );
}
