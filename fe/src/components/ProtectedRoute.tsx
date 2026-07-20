import React, { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/store/authStore";

interface ProtectedRouteProps {
  children: ReactNode;
  roles?: string[];
}

export default function ProtectedRoute({ children, roles = [] }: ProtectedRouteProps) {
  const { user, loading } = useAuth();
  
  if (loading || user === undefined) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-50">
        <div className="text-xs label-tiny" data-testid="loading-state">Loading workspace…</div>
      </div>
    );
  }
  
  if (!user) return <Navigate to="/login" replace />;
  
  if (roles.length && !roles.includes(user.role)) {
    return <Navigate to="/dashboard" replace />;
  }
  
  return <>{children}</>;
}
