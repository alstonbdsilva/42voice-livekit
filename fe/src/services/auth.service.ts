import { API_ENDPOINTS } from "@/constants/apiEndpoints";
import { api } from "./api";
import { tokenManager } from "./tokenManager";
import { User, UserRole } from "@/types";

export interface LoginResponseData {
  user: {
    id: string;
    email: string;
    first_name: string;
    last_name: string;
    phone: string | null;
    avatar_url: string | null;
    role_id: number;
    reseller_id: string | null;
    is_active: boolean;
    is_verified: boolean;
    created_at: string;
    updated_at: string;
    role_name: string;
  };
  tokens: {
    accessToken: string;
    refreshToken: string;
  };
}

class AuthServiceClass {
  private mapBackendUserToFrontendUser(backendUser: LoginResponseData["user"]): User {
    return {
      id: backendUser.id,
      name: `${backendUser.first_name || ""} ${backendUser.last_name || ""}`.trim() || backendUser.email,
      email: backendUser.email,
      role: (backendUser.role_name || "client").toLowerCase().replace("-", "_") as UserRole,
      status: backendUser.is_active ? "active" : "inactive",
      createdAt: backendUser.created_at,
      resellerId: backendUser.reseller_id ?? undefined,
    };
  }

  async login(email: string, password: string): Promise<User> {
    const res = await api.post<{ success: boolean; data: LoginResponseData }>(API_ENDPOINTS.LOGIN, {
      email,
      password,
    });

    const { user, tokens } = res.data;
    tokenManager.setTokens(tokens.accessToken, tokens.refreshToken);

    return this.mapBackendUserToFrontendUser(user);
  }

  async logout(): Promise<void> {
    const refreshToken = tokenManager.getRefreshToken();
    if (refreshToken) {
      try {
        await api.post(API_ENDPOINTS.LOGOUT, { refreshToken });
      } catch (err) {
        console.error("Logout request failed:", err);
      }
    }
    tokenManager.clearTokens();
  }

  async getProfile(): Promise<User> {
    const res = await api.get<{ success: boolean; data: LoginResponseData["user"] }>(API_ENDPOINTS.PROFILE);
    return this.mapBackendUserToFrontendUser(res.data);
  }
}

export const AuthService = new AuthServiceClass();
export default AuthService;
