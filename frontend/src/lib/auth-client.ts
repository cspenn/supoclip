import { createAuthClient } from "better-auth/react";

// Check if authentication is disabled (local development mode)
const DISABLE_AUTH = process.env.NEXT_PUBLIC_DISABLE_AUTH === "true";
const MOCK_USER_ID = process.env.NEXT_PUBLIC_MOCK_USER_ID || "local-user";

// Create real auth client
const realAuthClient = createAuthClient({
  baseURL: process.env.NEXT_PUBLIC_APP_URL,
});

// Create mock auth client for when auth is disabled
const mockAuthClient = {
  signIn: {
    email: async () => ({ data: null, error: null }),
    google: async () => ({ data: null, error: null }),
    github: async () => ({ data: null, error: null }),
  },
  signOut: async () => ({ data: null, error: null }),
  signUp: {
    email: async () => ({ data: null, error: null }),
  },
  useSession: () => ({
    data: {
      session: {
        id: "mock-session",
        token: "mock-token",
        createdAt: new Date(),
        expiresAt: new Date(Date.now() + 24 * 60 * 60 * 1000),
      },
      user: {
        id: MOCK_USER_ID,
        email: "local@development.local",
        emailVerified: true,
        name: "Local Developer",
        image: null,
        createdAt: new Date(),
      },
    },
    isPending: false,
    error: null,
  }),
  $fetch: async (url: string, options?: any) => {
    // Mock fetch for when auth is disabled
    return { ok: true, status: 200, json: async () => ({}) };
  },
} as any;

// Use mock client if auth is disabled, otherwise use real client
export const authClient = DISABLE_AUTH ? mockAuthClient : realAuthClient;

export const {
  signIn,
  signOut,
  signUp,
  useSession,
} = authClient;
