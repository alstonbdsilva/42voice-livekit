export const API_ENDPOINTS = {
  LOGIN: "/auth/login",
  LOGOUT: "/auth/logout",
  REFRESH_TOKEN: "/auth/refresh-token",
  PROFILE: "/auth/profile",
  RESELLERS: "/resellers",
  CLIENTS: "/clients",
  USERS: "/users",
  AGENTS: "/agents",
} as const;

export type ApiEndpoints = typeof API_ENDPOINTS;
