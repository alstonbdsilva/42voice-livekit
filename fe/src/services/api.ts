import axios from "axios";
import { API_ENDPOINTS } from "@/constants/apiEndpoints";
import { tokenManager } from "./tokenManager";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "http://localhost:8000";
// Normalize base URL: if it already includes /api, use it, otherwise append /api/v1
export const API = BACKEND_URL.includes("/api") ? BACKEND_URL : `${BACKEND_URL}/api/v1`;

import { AxiosInstance, AxiosRequestConfig } from "axios";

const instance = axios.create({
  baseURL: API,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

// Queue to hold requests while refreshing
let isRefreshing = false;
let failedQueue: any[] = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

// Request Interceptor: Attach Authorization header (accessToken)
instance.interceptors.request.use(
  (config) => {
    const token = tokenManager.getAccessToken();
    if (token) {
      console.log(`[API Client] Attaching token to request: ${config.method?.toUpperCase()} ${config.url}`);
      config.headers.Authorization = `Bearer ${token}`;
    } else {
      console.debug(`[API Client] Request without token: ${config.method?.toUpperCase()} ${config.url}`);
    }
    return config;
  },
  (error) => {
    console.error("[API Client] Request error:", error);
    return Promise.reject(error);
  }
);

// Response Interceptor: Handle 401 and Refresh Token rotation
instance.interceptors.response.use(
  (response) => {
    console.debug(`[API Client] Response success: ${response.config.method?.toUpperCase()} ${response.config.url}`);
    return response.data;
  },
  async (error) => {
    const originalRequest = error.config;

    // Handle 401 Unauthorized errors and retry
    if (error.response?.status === 401 && !originalRequest._retry) {
      console.warn(`[API Client] 401 Unauthorized detected for: ${originalRequest.method?.toUpperCase()} ${originalRequest.url}`);

      // Don't refresh if the error is from the refresh-token endpoint itself, login, or logout
      if (
        originalRequest.url?.includes(API_ENDPOINTS.REFRESH_TOKEN) ||
        originalRequest.url?.includes(API_ENDPOINTS.LOGIN) ||
        originalRequest.url?.includes(API_ENDPOINTS.LOGOUT)
      ) {
        console.warn("[API Client] 401 occurred on auth login/refresh/logout endpoint. Bypassing refresh flow.");
        return Promise.reject(error);
      }

      if (isRefreshing) {
        console.log(`[API Client] Token refresh already in progress. Queuing request: ${originalRequest.url}`);
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return instance(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = tokenManager.getRefreshToken();
      if (!refreshToken) {
        console.warn("[API Client] No refresh token found. Aborting refresh.");
        isRefreshing = false;
        return Promise.reject(error);
      }

      try {
        console.log("[API Client] Attempting to refresh tokens...");
        const res = await axios.post(`${API}${API_ENDPOINTS.REFRESH_TOKEN}`, { refreshToken });

        // Response contains success, statusCode, message, and data { accessToken, refreshToken }
        const { accessToken, refreshToken: newRefreshToken } = res.data.data;

        console.log("[API Client] Token refresh successful. Saving new tokens.");
        tokenManager.setTokens(accessToken, newRefreshToken);

        instance.defaults.headers.common.Authorization = `Bearer ${accessToken}`;
        originalRequest.headers.Authorization = `Bearer ${accessToken}`;

        console.log(`[API Client] Retrying original request: ${originalRequest.method?.toUpperCase()} ${originalRequest.url}`);
        processQueue(null, accessToken);
        isRefreshing = false;

        return instance(originalRequest);
      } catch (refreshError) {
        console.error("[API Client] Token refresh failed:", refreshError);
        processQueue(refreshError, null);
        isRefreshing = false;

        // Clear tokens on failure
        tokenManager.clearTokens();

        // Force reload / logout
        console.warn("[API Client] Dispatching auth-logout event to clear state.");
        window.dispatchEvent(new Event("auth-logout"));

        return Promise.reject(refreshError);
      }
    }

    console.error(`[API Client] Response error [${error.response?.status || "network"}]: ${originalRequest?.method?.toUpperCase()} ${originalRequest?.url}`, error.message);
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
