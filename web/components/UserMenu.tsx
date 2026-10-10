"use client";

import { useState } from "react";
import Image from "next/image";
import { useAuth } from "@/context/AuthProvider";

export function UserMenu() {
  const { user, baby, isLoading, login, logout, updateBaby } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const [editingBaby, setEditingBaby] = useState(false);
  const [babyNameInput, setBabyNameInput] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  if (isLoading) {
    return <div className="h-8 w-24 animate-pulse rounded-full bg-white/5" />;
  }

  if (!user) {
    return (
      <button
        type="button"
        onClick={login}
        className="flex items-center gap-2 rounded-full bg-white/10 px-3.5 py-1.5 text-xs font-medium text-ink ring-1 ring-white/15 transition hover:bg-white/15 hover:ring-white/25"
        title="Sign in with your Google account to sync parent profile and baby vitals with Tiger Data"
      >
        <svg className="h-3.5 w-3.5" viewBox="0 0 24 24">
          <path
            fill="#EA4335"
            d="M12 5c1.6 0 3 .6 4.1 1.7l3.1-3.1C17.3 1.8 14.8 1 12 1 7.5 1 3.7 3.6 1.9 7.3l3.7 2.9C6.5 7.4 9 5 12 5z"
          />
          <path
            fill="#4285F4"
            d="M23.5 12.3c0-.8-.1-1.7-.2-2.3H12v4.5h6.5c-.3 1.5-1.1 2.8-2.4 3.7l3.7 2.9c2.2-2 3.7-5.1 3.7-8.8z"
          />
          <path
            fill="#FBBC05"
            d="M5.6 14.8c-.2-.7-.4-1.5-.4-2.3 0-.8.2-1.6.4-2.3L1.9 7.3C.7 9.7 0 12.3 0 15.2c0 2.8.7 5.5 1.9 7.8l3.7-2.9c-.3-.7-.5-1.5-.5-2.3z"
          />
          <path
            fill="#34A853"
            d="M12 23.5c3.2 0 6-1.1 8-3l-3.7-2.9c-1.1.7-2.5 1.2-4.3 1.2-3 0-5.5-2.4-6.4-5.2L1.9 16.5C3.7 20.3 7.5 23.5 12 23.5z"
          />
        </svg>
        <span>Sign in</span>
      </button>
    );
  }

  const initials = user.name
    ? user.name
        .split(" ")
        .map((p) => p[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "P";

  const handleSaveBabyName = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!babyNameInput.trim()) return;
    setIsSaving(true);
    await updateBaby({ name: babyNameInput.trim() });
    setIsSaving(false);
    setEditingBaby(false);
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => {
          setMenuOpen((prev) => !prev);
          if (baby?.name) setBabyNameInput(baby.name);
        }}
        className="flex items-center gap-2 rounded-full bg-white/5 py-1 pl-1 pr-3 text-xs text-ink ring-1 ring-white/10 transition hover:bg-white/10"
        aria-expanded={menuOpen}
        aria-haspopup="dialog"
      >
        {user.avatar_url ? (
          <Image
            src={user.avatar_url}
            alt={user.name}
            width={24}
            height={24}
            className="h-6 w-6 rounded-full object-cover"
            unoptimized
          />
        ) : (
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-tone/20 text-[10px] font-semibold text-tone">
            {initials}
          </span>
        )}
        <div className="flex flex-col text-left">
          <span className="max-w-[100px] truncate font-medium text-ink leading-tight">
            {user.name.split(" ")[0]}
          </span>
          <span className="text-[10px] text-ink-dim leading-none">
            {baby?.name ? `${baby.name}’s parent` : "Parent"}
          </span>
        </div>
      </button>

      {menuOpen && (
        <>
          <button
            type="button"
            aria-label="Close user menu"
            className="fixed inset-0 z-40 cursor-default"
            onClick={() => {
              setMenuOpen(false);
              setEditingBaby(false);
            }}
          />
          <div
            role="dialog"
            aria-label="Parent Profile Menu"
            className="absolute right-0 z-50 mt-2 w-80 rounded-2xl bg-[#14131f] p-4 shadow-2xl ring-1 ring-white/15"
          >
            {/* User Profile Header */}
            <div className="flex items-center gap-3 border-b border-white/10 pb-3">
              {user.avatar_url ? (
                <Image
                  src={user.avatar_url}
                  alt={user.name}
                  width={40}
                  height={40}
                  className="h-10 w-10 rounded-full object-cover ring-1 ring-white/20"
                  unoptimized
                />
              ) : (
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-tone/20 text-sm font-semibold text-tone">
                  {initials}
                </div>
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-ink">{user.name}</p>
                <p className="truncate text-xs text-ink-dim">{user.email}</p>
              </div>
            </div>

            {/* Child Profile Section */}
            <div className="my-3 rounded-xl bg-white/5 p-3 ring-1 ring-white/5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-tone">Baby Profile (Tiger Data)</span>
                {!editingBaby && (
                  <button
                    type="button"
                    onClick={() => {
                      setBabyNameInput(baby?.name || "");
                      setEditingBaby(true);
                    }}
                    className="text-[11px] text-ink-dim hover:text-ink hover:underline"
                  >
                    Edit
                  </button>
                )}
              </div>

              {editingBaby ? (
                <form onSubmit={handleSaveBabyName} className="mt-2.5 flex flex-col gap-2">
                  <input
                    type="text"
                    value={babyNameInput}
                    onChange={(e) => setBabyNameInput(e.target.value)}
                    placeholder="Baby’s name"
                    autoFocus
                    maxLength={30}
                    className="rounded-lg bg-black/40 px-2.5 py-1 text-xs text-ink ring-1 ring-white/10 focus:outline-none focus:ring-tone/50"
                  />
                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => setEditingBaby(false)}
                      className="rounded-lg px-2 py-0.5 text-[11px] text-ink-dim hover:text-ink"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={isSaving || !babyNameInput.trim()}
                      className="rounded-lg bg-tone px-2.5 py-0.5 text-[11px] font-semibold text-[#0a0b15] disabled:opacity-50"
                    >
                      {isSaving ? "Saving…" : "Save"}
                    </button>
                  </div>
                </form>
              ) : (
                <div className="mt-1.5 flex flex-col gap-1 text-xs">
                  <div className="flex justify-between text-ink">
                    <span className="text-ink-dim">Name:</span>
                    <span className="font-medium">{baby?.name || "Your baby"}</span>
                  </div>
                  <div className="flex justify-between text-ink">
                    <span className="text-ink-dim">Bedtime schedule:</span>
                    <span className="font-mono text-[11px] text-ink-dim">
                      {baby?.bedtime || "20:00"} – {baby?.wake_time || "07:00"}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Sync Badge */}
            <div className="flex items-center gap-2 px-1 text-[11px] text-emerald-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              <span>Synced with Tiger Data Cloud</span>
            </div>

            {/* Logout button */}
            <div className="mt-3 border-t border-white/10 pt-3">
              <button
                type="button"
                onClick={() => {
                  setMenuOpen(false);
                  logout();
                }}
                className="w-full rounded-xl bg-white/5 py-1.5 text-center text-xs font-medium text-rose-300 transition hover:bg-rose-500/10 hover:text-rose-200"
              >
                Sign out
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
