import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/store/authStore";
import { toast } from "sonner";
import { ArrowRight } from "lucide-react";


export default function Login() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  React.useEffect(() => { if (user) navigate("/dashboard", { replace: true }); }, [user, navigate]);

  const onSubmit = async (e: React.FormEvent) => {
    e?.preventDefault();
    if (!email || !password) return toast.error("Email and password are required");
    setBusy(true);
    const r = await login(email, password);
    setBusy(false);
    if (r.ok) {
      toast.success("Welcome back");
      navigate("/dashboard", { replace: true });
    } else {
      toast.error(r.error || "Login failed");
    }
  };

  return (
    <div className="min-h-screen grid md:grid-cols-2 bg-zinc-50" data-testid="login-page">
      {/* Left brand panel */}
      <div className="hidden md:flex flex-col justify-between bg-zinc-950 text-white p-12 relative overflow-hidden">
        <div className="absolute inset-0 bg-grid opacity-10" />
        <div className="relative z-10 flex items-center gap-3">
          <div className="w-10 h-10 bg-white text-zinc-950 flex items-center justify-center font-display font-bold rounded-sm">42</div>
          <div>
            <div className="font-display text-lg font-bold tracking-tight">42Voice</div>
            <div className="label-tiny text-zinc-400" style={{ fontSize: 9 }}>COMMAND CENTRE</div>
          </div>
        </div>
        <div className="relative z-10">
          <div className="label-tiny text-zinc-400 mb-4">ENTERPRISE OPERATIONS</div>
          <h1 className="font-display text-5xl font-bold leading-[1.05] tracking-tight">
            The financial<br />command centre<br />for AI voice.
          </h1>
          <p className="mt-6 text-zinc-400 text-sm max-w-md leading-relaxed">
            Manage every reseller, client, agent, invoice and renewal in one disciplined workspace.
            Built for control, audited end-to-end.
          </p>
        </div>
        <div className="relative z-10 grid grid-cols-3 gap-6 border-t border-zinc-800 pt-6">
          <div>
            <div className="font-mono-stat text-2xl font-semibold">99.98%</div>
            <div className="label-tiny text-zinc-500 mt-1">UPTIME</div>
          </div>
          <div>
            <div className="font-mono-stat text-2xl font-semibold">4 roles</div>
            <div className="label-tiny text-zinc-500 mt-1">RBAC</div>
          </div>
          <div>
            <div className="font-mono-stat text-2xl font-semibold">SOC-2</div>
            <div className="label-tiny text-zinc-500 mt-1">READY</div>
          </div>
        </div>
      </div>

      {/* Right form */}
      <div className="flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <div className="md:hidden mb-8 flex items-center gap-2">
            <div className="w-8 h-8 bg-zinc-950 text-white flex items-center justify-center font-display font-bold text-sm rounded-sm">42</div>
            <div className="font-display font-bold">42Voice Command Centre</div>
          </div>
          <div className="label-tiny mb-2">SIGN IN</div>
          <h2 className="font-display text-3xl font-bold tracking-tight mb-1">Access your portal</h2>
          <p className="text-sm text-zinc-500 mb-8">Use your 42Voice credentials to continue.</p>

          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <label className="label-tiny block mb-1.5">EMAIL</label>
              <input
                data-testid="login-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-white border border-zinc-300 rounded-sm px-3 py-2.5 text-sm focus:outline-none focus:border-zinc-950"
                placeholder="you@company.com"
                autoComplete="username"
              />
            </div>
            <div>
              <div className="flex justify-between items-center mb-1.5">
                <label className="label-tiny">PASSWORD</label>
                <Link to="/forgot-password" className="text-xs text-zinc-500 hover:text-zinc-950" data-testid="forgot-link">Forgot?</Link>
              </div>
              <input
                data-testid="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-white border border-zinc-300 rounded-sm px-3 py-2.5 text-sm focus:outline-none focus:border-zinc-950"
                placeholder="••••••••"
                autoComplete="current-password"
              />
            </div>
            <button
              data-testid="login-submit"
              type="submit"
              disabled={busy}
              className="w-full bg-zinc-950 text-white rounded-sm px-4 py-2.5 text-sm font-medium hover:bg-zinc-800 transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {busy ? "Signing in…" : "Sign in"}
              {!busy && <ArrowRight className="w-4 h-4" />}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
