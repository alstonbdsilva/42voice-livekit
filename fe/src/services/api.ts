import axios from "axios";
import { API_ENDPOINTS } from "@/constants/apiEndpoints";
import { tokenManager } from "./tokenManager";

export const API = process.env.REACT_APP_BACKEND_URL || "/api/v1";

import { AxiosInstance, AxiosRequestConfig, InternalAxiosRequestConfig } from "axios";

const instance = axios.create({
  baseURL: API,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

interface CustomInternalAxiosRequestConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

// Single-flight token refresh promise
let refreshPromise: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  const refreshToken = tokenManager.getRefreshToken();
  if (!refreshToken) {
    tokenManager.clearTokens();
    if (typeof window !== "undefined") {
      window.dispatchEvent(new Event("auth-logout"));
    }
    throw new Error("No refresh token available");
  }

  try {
    const res = await axios.post(`${API}${API_ENDPOINTS.REFRESH_TOKEN}`, { refreshToken });
    const data = res.data?.data;
    const accessToken: string | undefined = data?.accessToken;
    const newRefreshToken: string | undefined = data?.refreshToken;

    if (!accessToken) {
      throw new Error("Invalid token refresh response: missing accessToken");
    }

    tokenManager.setTokens(accessToken, newRefreshToken || refreshToken);
    instance.defaults.headers.common.Authorization = `Bearer ${accessToken}`;
    return accessToken;
  } catch (err) {
    tokenManager.clearTokens();
    if (typeof window !== "undefined") {
      window.dispatchEvent(new Event("auth-logout"));
    }
    throw err;
  }
}

// Request Interceptor: Attach Authorization header (accessToken)
instance.interceptors.request.use(
  (config) => {
    const token = tokenManager.getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response Interceptor: Handle 401 with single-flight token refresh
instance.interceptors.response.use(
  (response) => {
    return response.data;
  },
  async (error) => {
    const originalRequest = error.config as CustomInternalAxiosRequestConfig | undefined;

    // Handle 401 Unauthorized errors and retry at most once
    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      // Don't refresh if the error is from the refresh-token endpoint itself, login, or logout
      const isAuthUrl =
        originalRequest.url?.includes(API_ENDPOINTS.REFRESH_TOKEN) ||
        originalRequest.url?.includes(API_ENDPOINTS.LOGIN) ||
        originalRequest.url?.includes(API_ENDPOINTS.LOGOUT);

      if (isAuthUrl) {
        return Promise.reject(error);
      }

      // Mark retry immediately to prevent recursive refresh loops
      originalRequest._retry = true;

      // Ensure exactly ONE refresh request is in flight across all concurrent callers
      if (!refreshPromise) {
        refreshPromise = refreshAccessToken().finally(() => {
          refreshPromise = null;
        });
      }

      try {
        const newAccessToken = await refreshPromise;
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        }
        return instance(originalRequest);
      } catch (refreshError) {
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export interface CustomAxiosInstance {
  get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T>;
  post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>;
  put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>;
  delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T>;
  patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>;
  defaults: AxiosInstance["defaults"];
  interceptors: AxiosInstance["interceptors"];
  (config: AxiosRequestConfig): Promise<any>;
}

export const api = instance as unknown as CustomAxiosInstance;

// Re-export formatting helper functions from utilities to maintain backward compatibility
export {
  formatApiErrorDetail,
  fmtCurrency,
  fmtNumber,
  fmtDate,
  fmtDateTime,
  daysFrom
} from "@/lib/utils";
