import React, { useState, ReactNode } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { useAuth, canSee } from "@/store/authStore";
import { LucideIcon } from "lucide-react";
import {
  LayoutDashboard, Users, Briefcase, Bot, MessageSquare, Mic, FileText,
  Receipt, CreditCard, FileSignature, RefreshCw, Bell, BarChart3, Settings,
  ChevronDown, Search, LogOut, Wallet, ScrollText, Phone, PhoneCall, Wrench, Megaphone, Webhook
} from "lucide-react";

interface NavLinkItem {
  to: string;
  label: string;
  icon: LucideIcon;
  roles: string[];
  section?: never;
  comingSoon?: boolean;
}

interface NavSectionItem {
  section: string;
  to?: never;
  label?: never;
  icon?: never;
  roles?: never;
}

type NavItem = NavLinkItem | NavSectionItem;

const navItems: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: [] },
  { to: "/money", label: "Money Dashboard", icon: Wallet, roles: ["super_admin", "finance_admin"] },
  { section: "OPERATIONS" },
  { to: "/resellers", label: "Partners", icon: Users, roles: ["super_admin", "finance_admin"] },
  { to: "/clients", label: "Clients", icon: Briefcase, roles: ["super_admin", "finance_admin", "reseller"] },
  { to: "/agents", label: "AI Agents", icon: Bot, roles: [] },
  { to: "/conversations", label: "Conversations", icon: MessageSquare, roles: [] },
  { to: "/recordings", label: "Recordings", icon: Mic, roles: [] },
  { to: "/messages", label: "Messages", icon: MessageSquare, roles: [] },
  { to: "/phone-numbers", label: "Phone Numbers", icon: Phone, roles: [] },
  { to: "/campaigns", label: "Campaigns", icon: Megaphone, roles: [] },
  { to: "/tools", label: "Tools", icon: Wrench, roles: [] },
  { section: "FINANCE" },
  { to: "/plans", label: "Plans", icon: ScrollText, roles: [] },
  { to: "/invoices", label: "Invoices", icon: Receipt, roles: [] },
  { to: "/payments", label: "Payments", icon: CreditCard, roles: ["super_admin", "finance_admin", "reseller"] },
  { to: "/contracts", label: "Contracts", icon: FileSignature, roles: [] },
  { to: "/renewals", label: "Renewals", icon: RefreshCw, roles: ["super_admin", "finance_admin", "reseller"] },
  { to: "/commissions", label: "Commissions", icon: FileText, roles: ["super_admin", "finance_admin", "reseller"] },
  { section: "INSIGHTS" },
  { to: "/notifications", label: "Notifications", icon: Bell, roles: [] },
  { to: "/reports", label: "Reports", icon: BarChart3, roles: [] },
  { section: "ADMIN" },
  { to: "/users", label: "User Management", icon: Users, roles: ["super_admin"] },
  { to: "/audit", label: "Audit Logs", icon: ScrollText, roles: ["super_admin"] },
  { to: "/settings", label: "Settings", icon: Settings, roles: [] },
];

function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  return (
    <aside className="w-64 border-r border-zinc-200 bg-white flex flex-col h-screen sticky top-0" data-testid="sidebar">
      <div className="h-14 border-b border-zinc-200 flex items-center px-5 gap-2">
        <div className="w-7 h-7 bg-zinc-950 text-white flex items-center justify-center font-display font-bold text-sm rounded-sm">42</div>
        <div>
          <div className="font-display font-bold text-sm tracking-tight">42Voice</div>
          <div className="label-tiny" style={{ fontSize: 9 }}>COMMAND CENTRE</div>
        </div>
      </div>
      <nav className="flex-1 overflow-y-auto py-3 px-2">
        {navItems.map((it, i) => {
          if ("section" in it) {
            return <div key={`s${i}`} className="label-tiny px-3 mt-4 mb-1">{it.section}</div>;
          }
          if (it.to === undefined) return null;
          if (!canSee(user, it.roles)) return null;
          const Icon = it.icon;
          if (it.comingSoon) {
            return (
              <NavLink
                key={it.to}
                to={it.to}
                data-testid={`nav-${it.to.replace("/", "")}`}
                className={({ isActive }) =>
                  `flex items-center justify-between px-3 py-2 text-sm rounded-sm transition-colors ${isActive
                    ? "bg-zinc-950 text-white"
                    : "text-zinc-700 hover:bg-zinc-100 hover:text-zinc-950"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <div className="flex items-center gap-2">
                      <Icon className="w-4 h-4" />
                      <span>{it.label}</span>
                    </div>
                    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-sm uppercase tracking-wider scale-90 origin-right transition-colors ${isActive
                        ? "bg-zinc-800 text-zinc-300"
                        : "bg-zinc-100 text-zinc-500"
                      }`}>
                      Soon
                    </span>
                  </>
                )}
              </NavLink>
            );
          }
          return (
            <NavLink
              key={it.to}
              to={it.to}
              data-testid={`nav-${it.to.replace("/", "")}`}
              className={({ isActive }) =>
                `flex items-center gap-2 px-3 py-2 text-sm rounded-sm transition-colors ${isActive
                  ? "bg-zinc-950 text-white"
                  : "text-zinc-700 hover:bg-zinc-100 hover:text-zinc-950"
                }`
              }
            >
              <Icon className="w-4 h-4" />
              <span>{it.label}</span>
            </NavLink>
          );
        })}
      </nav>
      <div className="border-t border-zinc-200 p-3">
        <div className="flex items-center gap-2 px-2 py-1.5">
          <div className="w-8 h-8 bg-zinc-200 rounded-sm flex items-center justify-center font-display font-bold text-xs text-zinc-700">
            {user?.name?.[0] || "?"}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs font-semibold truncate">{user?.name}</div>
            <div className="label-tiny" style={{ fontSize: 9 }}>{user?.role?.replace("_", " ")}</div>
          </div>
          <button
            onClick={async () => { await logout(); navigate("/login"); }}
            className="text-zinc-500 hover:text-zinc-950 p-1.5"
            data-testid="logout-btn"
            title="Sign out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}

function Topbar() {
  const { user } = useAuth();
  const loc = useLocation();
  const [q, setQ] = useState("");
  return (
    <div className="h-14 border-b border-zinc-200 bg-white/80 backdrop-blur-md flex items-center px-6 sticky top-0 z-10" data-testid="topbar">
      <div className="flex items-center gap-2 text-xs text-zinc-500">
        <span className="label-tiny">{user?.role?.replace("_", " ") || "user"}</span>
        <span>/</span>
        <span className="font-mono-stat text-zinc-900">{loc.pathname}</span>
      </div>
      <div className="flex-1 max-w-md mx-auto relative">
        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
        <input
          data-testid="global-search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search clients, agents, conversations…"
          className="w-full bg-zinc-50 border border-zinc-200 rounded-sm pl-9 pr-3 py-1.5 text-sm focus:outline-none focus:border-zinc-950 focus:bg-white"
        />
      </div>
      <div className="flex items-center gap-3">
        <Link to="/notifications" className="text-zinc-600 hover:text-zinc-950 relative" data-testid="topbar-notifications">
          <Bell className="w-4 h-4" />
        </Link>
        <div className="text-xs text-zinc-600 font-mono-stat hidden md:block">
          {new Date().toLocaleDateString("en-US", { weekday: "short", day: "2-digit", month: "short" })}
        </div>
      </div>
    </div>
  );
}

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen bg-zinc-50">
      <Sidebar />
      <div className="flex-1 min-w-0 flex flex-col">
        <Topbar />
        <main className="flex-1 p-6 md:p-8 w-full" data-testid="page-content">{children}</main>
      </div>
    </div>
  );
}
