export const tokenManager = {
  getAccessToken: () => {
    const token = typeof window !== "undefined" ? sessionStorage.getItem("access_token") : null;
    console.debug("[TokenManager] Get Access Token:", token ? "Exists" : "None");
    return token;
  },
  getRefreshToken: () => {
    const token = typeof window !== "undefined" ? sessionStorage.getItem("refresh_token") : null;
    console.debug("[TokenManager] Get Refresh Token:", token ? "Exists" : "None");
    return token;
  },
  setTokens: (access: string | null, refresh: string | null) => {
    console.log("[TokenManager] Updating tokens in sessionStorage...");
    if (typeof window !== "undefined") {
      if (access) {
        sessionStorage.setItem("access_token", access);
      } else {
        sessionStorage.removeItem("access_token");
      }
      if (refresh) {
        sessionStorage.setItem("refresh_token", refresh);
      } else {
        sessionStorage.removeItem("refresh_token");
      }
    }
  },
  clearTokens: () => {
    console.log("[TokenManager] Clearing tokens from sessionStorage...");
    if (typeof window !== "undefined") {
      sessionStorage.removeItem("access_token");
      sessionStorage.removeItem("refresh_token");
    }
  },
};

export default tokenManager;
