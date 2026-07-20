import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import ProtectedRoute from "@/components/ProtectedRoute";
import Layout from "@/components/Layout";

import Login from "@/pages/Login";
import ForgotPassword from "@/pages/ForgotPassword";
import Dashboard from "@/pages/Dashboard";
import MoneyDashboard from "@/pages/MoneyDashboard";
import Clients from "@/pages/Clients";
import ClientDetail from "@/pages/ClientDetail";
import Resellers from "@/pages/Resellers";
import ResellerDetail from "@/pages/ResellerDetail";
import Agents from "@/pages/Agents";
import AgentDetail from "@/pages/AgentDetail";
import Conversations from "@/pages/Conversations";
import ConversationDetail from "@/pages/ConversationDetail";
import Recordings from "@/pages/Recordings";
import Messages from "@/pages/Messages";
import Invoices from "@/pages/Invoices";
import InvoiceDetail from "@/pages/InvoiceDetail";
import Payments from "@/pages/Payments";
import Contracts from "@/pages/Contracts";
import ContractDetail from "@/pages/ContractDetail";
import Renewals from "@/pages/Renewals";
import Notifications from "@/pages/Notifications";
import Reports from "@/pages/Reports";
import Users from "@/pages/Users";
import AuditLogs from "@/pages/AuditLogs";
import Settings from "@/pages/Settings";
import Commissions from "@/pages/Commissions";

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute>
      <Layout>{children}</Layout>
    </ProtectedRoute>
  );
}

export default function App() {
  return (
    <BrowserRouter>
        <Toaster richColors position="top-right" />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Shell><Dashboard /></Shell>} />
          <Route path="/money" element={<Shell><MoneyDashboard /></Shell>} />
          <Route path="/clients" element={<Shell><Clients /></Shell>} />
          <Route path="/clients/:id" element={<Shell><ClientDetail /></Shell>} />
          <Route path="/resellers" element={<Shell><Resellers /></Shell>} />
          <Route path="/resellers/:id" element={<Shell><ResellerDetail /></Shell>} />
          <Route path="/agents" element={<Shell><Agents /></Shell>} />
          <Route path="/agents/:id" element={<Shell><AgentDetail /></Shell>} />
          <Route path="/conversations" element={<Shell><Conversations /></Shell>} />
          <Route path="/conversations/:id" element={<Shell><ConversationDetail /></Shell>} />
          <Route path="/recordings" element={<Shell><Recordings /></Shell>} />
          <Route path="/messages" element={<Shell><Messages /></Shell>} />
          <Route path="/invoices" element={<Shell><Invoices /></Shell>} />
          <Route path="/invoices/:id" element={<Shell><InvoiceDetail /></Shell>} />
          <Route path="/payments" element={<Shell><Payments /></Shell>} />
          <Route path="/contracts" element={<Shell><Contracts /></Shell>} />
          <Route path="/contracts/:id" element={<Shell><ContractDetail /></Shell>} />
          <Route path="/renewals" element={<Shell><Renewals /></Shell>} />
          <Route path="/commissions" element={<Shell><Commissions /></Shell>} />
          <Route path="/notifications" element={<Shell><Notifications /></Shell>} />
          <Route path="/reports" element={<Shell><Reports /></Shell>} />
          <Route path="/settings" element={<Shell><Settings /></Shell>} />
          <Route path="/users" element={<Shell><Users /></Shell>} />
          <Route path="/audit" element={<Shell><AuditLogs /></Shell>} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
  );
}
