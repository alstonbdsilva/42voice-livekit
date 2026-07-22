import React from "react";
import { useAuth } from "@/store/authStore";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Shield, Briefcase, Building, Mail } from "lucide-react";

export default function ProfileSettings() {
  const { user } = useAuth();

  return (
    <Card className="border-zinc-200 shadow-none">
      <CardHeader>
        <CardTitle className="text-xl font-bold tracking-tight text-zinc-900">Profile Details</CardTitle>
        <CardDescription className="text-zinc-500">
          Manage your account credentials and workspace assignments.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* User Identity Banner */}
        <div className="flex items-center gap-4 p-5 rounded-xl bg-zinc-50 border border-zinc-200/60">
          <div className="w-14 h-14 rounded-full bg-zinc-900 text-white flex items-center justify-center font-semibold text-xl">
            {user?.name?.charAt(0).toUpperCase() || "U"}
          </div>
          <div>
            <h3 className="font-semibold text-zinc-900 text-lg flex items-center gap-2">
              {user?.name || "User Account"}
            </h3>
            <div className="flex items-center gap-1.5 text-zinc-500 mt-0.5">
              <Mail className="w-3.5 h-3.5" />
              <span className="text-sm font-mono-stat">{user?.email}</span>
            </div>
          </div>
        </div>

        {/* Profile Attributes Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="border border-zinc-200 rounded-xl p-4 bg-white hover:border-zinc-300 transition-all duration-200 flex items-start gap-3">
            <div className="p-2 bg-zinc-50 rounded-lg border border-zinc-100">
              <Shield className="w-5 h-5 text-zinc-600" />
            </div>
            <div>
              <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Access Role</div>
              <div className="font-semibold text-zinc-900 mt-1 uppercase text-sm font-mono-stat tracking-normal">
                {user?.role?.replace("_", " ")}
              </div>
            </div>
          </div>

          {user?.clientId && (
            <div className="border border-zinc-200 rounded-xl p-4 bg-white hover:border-zinc-300 transition-all duration-200 flex items-start gap-3">
              <div className="p-2 bg-zinc-50 rounded-lg border border-zinc-100">
                <Briefcase className="w-5 h-5 text-zinc-600" />
              </div>
              <div>
                <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Client Assignment</div>
                <div className="font-semibold text-zinc-900 mt-1 font-mono-stat text-sm break-all">
                  {user.clientId}
                </div>
              </div>
            </div>
          )}

          {user?.resellerId && (
            <div className="border border-zinc-200 rounded-xl p-4 bg-white hover:border-zinc-300 transition-all duration-200 flex items-start gap-3">
              <div className="p-2 bg-zinc-50 rounded-lg border border-zinc-100">
                <Building className="w-5 h-5 text-zinc-600" />
              </div>
              <div>
                <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Reseller Assignment</div>
                <div className="font-semibold text-zinc-900 mt-1 font-mono-stat text-sm break-all">
                  {user.resellerId}
                </div>
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
