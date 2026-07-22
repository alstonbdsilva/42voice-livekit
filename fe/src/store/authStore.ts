import { create } from "zustand";
import { AuthService } from "@/services/auth.service";
import { formatApiErrorDetail } from "@/services/api";
import { tokenManager } from "@/services/tokenManager";
import { User } from "@/types";

interface LoginResult {
  ok: boolean;
  error?: string;
}

interface AuthState {
  user: User | null | undefined; // undefined = loading, null = unauthenticated
  loading: boolean;
  login: (email: string, password: string) => Promise<LoginResult>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: undefined,
  loading: true,
  login: async (email, password) => {
    console.log(`[AuthStore] Attempting login for: ${email}`);
    try {
      const user = await AuthService.login(email, password);
      console.log("[AuthStore] Login successful, updating state with user:", user.email);
      set({ user, loading: false });
      return { ok: true };
    } catch (e: any) {
      const errorMsg = formatApiErrorDetail(e?.response?.data?.detail) || e.message;
      console.warn(`[AuthStore] Login failed for ${email}:`, errorMsg);
      return { ok: false, error: errorMsg };
    }
  },
  logout: async () => {
    console.log("[AuthStore] Logging out user and resetting auth state...");
    await AuthService.logout();
    set({ user: null, loading: false });
  },
  refresh: async () => {
    console.log("[AuthStore] Checking session tokens for re-authentication...");
    const token = tokenManager.getAccessToken();
    const refreshToken = tokenManager.getRefreshToken();
    if (!token && !refreshToken) {
      console.log("[AuthStore] No tokens present. Marking user as unauthenticated.");
      set({ user: null, loading: false });
      return;
    }
    try {
      console.log("[AuthStore] Tokens present. Fetching user profile...");
      const user = await AuthService.getProfile();
      console.log("[AuthStore] Re-authentication successful for user:", user.email);
      set({ user, loading: false });
    } catch (error) {
      console.error("[AuthStore] Profile fetch failed on session refresh:", error);
      set({ user: null, loading: false });
    }
  },
}));

// Export useAuth hook referencing the Zustand store for compatibility
export const useAuth = () => useAuthStore();

export const canSee = (user: User | null | undefined, allowed: string[] = []): boolean => {
  if (!user) return false;
  if (allowed.length === 0) return true;
  const userRole = user.role?.toLowerCase();
  return allowed.map((r) => r.toLowerCase()).includes(userRole);
};

// Handle automatic logout from interceptor
if (typeof window !== "undefined") {
  window.addEventListener("auth-logout", () => {
    useAuthStore.getState().logout();
  });
}

// Trigger initial user fetch on module load
useAuthStore.getState().refresh();
