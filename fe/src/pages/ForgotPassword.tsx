import React, { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/services/api";
import { toast } from "sonner";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;
    try {
      await api.post("/auth/forgot-password", { email });
      setSent(true);
      toast.success("If the email exists, a reset link has been sent.");
    } catch (e) {
      toast.error("Could not process request");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-zinc-50" data-testid="forgot-page">
      <div className="w-full max-w-md bg-white border border-zinc-200 p-8">
        <Link to="/login" className="label-tiny text-zinc-500 hover:text-zinc-950" data-testid="back-to-login">← BACK TO SIGN IN</Link>
        <h1 className="font-display text-2xl font-bold tracking-tight mt-6">Reset your password</h1>
        <p className="text-sm text-zinc-500 mt-1">Enter your email and we'll send instructions.</p>
        {sent ? (
          <div className="mt-6 p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm rounded-sm">
            Check your inbox for the reset link. (In dev, see backend logs.)
          </div>
        ) : (
          <form onSubmit={submit} className="mt-6 space-y-4">
            <div>
              <label className="label-tiny block mb-1.5">EMAIL</label>
              <input
                type="email"
                data-testid="forgot-email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-white border border-zinc-300 rounded-sm px-3 py-2.5 text-sm focus:outline-none focus:border-zinc-950"
              />
            </div>
            <button data-testid="forgot-submit" className="w-full bg-zinc-950 text-white rounded-sm px-4 py-2.5 text-sm font-medium hover:bg-zinc-800">
              Send reset link
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
