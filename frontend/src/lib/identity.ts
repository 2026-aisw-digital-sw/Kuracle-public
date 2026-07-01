"use client";

import { useSyncExternalStore } from "react";

export interface Identity {
  userId: string;
  sessionId: string;
}

const STORAGE_KEY = "hobit_ax_identity";
let cachedIdentity: Identity | null = null;

export function getOrCreateIdentity(): Identity {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw) as Identity;
  } catch {
    // ignore parse errors
  }
  const id: Identity = {
    userId: `u_${crypto.randomUUID().replace(/-/g, "").slice(0, 12)}`,
    sessionId: `s_${crypto.randomUUID().replace(/-/g, "").slice(0, 12)}`,
  };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(id));
  } catch {
    // ignore storage errors
  }
  return id;
}

export function useIdentity(): Identity | null {
  return useSyncExternalStore(
    () => () => undefined,
    () => {
      if (cachedIdentity) return cachedIdentity;
      cachedIdentity = getOrCreateIdentity();
      return cachedIdentity;
    },
    () => null,
  );
}
