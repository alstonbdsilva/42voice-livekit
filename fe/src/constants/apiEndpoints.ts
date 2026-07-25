export const API_ENDPOINTS = {
  LOGIN: "/auth/login",
  LOGOUT: "/auth/logout",
  REFRESH_TOKEN: "/auth/refresh-token",
  PROFILE: "/auth/profile",
  RESELLERS: "/resellers",
  CLIENTS: "/clients",
  USERS: "/users",
  AGENTS: "/agents",
  INVOICES: "/invoices",
  PAYMENTS: "/payments",
  CONTRACTS: "/contracts",
  RENEWALS: "/renewals",
  COMMISSIONS: "/commissions",
  DASHBOARD_MONEY: "/dashboard/money",
  DASHBOARD_SUMMARY: "/dashboard/summary",
  PHONE_NUMBERS: "/phone-numbers",
} as const;

export type ApiEndpoints = typeof API_ENDPOINTS;
