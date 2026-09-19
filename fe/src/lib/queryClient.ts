import { QueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      gcTime: 10 * 60 * 1000, // 10 minutes
      refetchOnWindowFocus: false,
      retry: (failureCount: number, error: Error) => {
        // Conservative retry: Never retry on 401 Unauthorized so Axios interceptor handles token refresh cleanly
        if (isAxiosError(error) && error.response?.status === 401) {
          return false;
        }
        if ("status" in error && (error as { status?: number }).status === 401) {
          return false;
        }
        return failureCount < 1;
      },
    },
  },
});
