import { Client, Agent, Invoice, Contract } from "@/types";
import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api, fmtCurrency, fmtDate } from "@/services/api";
import PageHeader from "@/components/PageHeader";
import KpiCard from "@/components/KpiCard";
import StatusBadge from "@/components/StatusBadge";
import { ArrowLeft } from "lucide-react";

import { ContractService } from "@/services/contract.service";
import AppModal from "@/components/AppModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/store/authStore";
import { toast } from "sonner";

export default function ClientDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();

  const [c, setC] = useState<Client | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [contracts, setContracts] = useState<Contract[]>([]);

  // Modal and form states
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [contractValue, setContractValue] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [autoRenewal, setAutoRenewal] = useState(false);
  const [paymentTerms, setPaymentTerms] = useState("Net 30");
  const [billingCycle, setBillingCycle] = useState("Monthly");
  const [noticePeriodDays, setNoticePeriodDays] = useState("30");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get(`/clients/${id}`).then((r) => setC(r.data)).catch(() => {});
    api.get(`/agents?clientId=${id}`).then((r) => setAgents(r.data)).catch(() => {});
    api.get(`/invoices`).then((r) => setInvoices(r.data.filter((x: Invoice) => x.clientId.toString() === id?.toString()))).catch(() => {});
    api.get(`/contracts`).then((r) => setContracts(r.data.filter((x: Contract) => x.clientId.toString() === id?.toString()))).catch(() => {});
  }, [id]);

  if (!c) return <div className="label-tiny">Loading…</div>;

  const canCreate = user?.role && ["super_admin", "finance_admin", "reseller"].includes(user.role.toLowerCase());

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;
    setLoading(true);
    try {
      await ContractService.create({
        clientId: id,
        contractValue: parseFloat(contractValue) || 0,
        startDate: new Date(startDate).toISOString(),
        endDate: new Date(endDate).toISOString(),
        autoRenewal,
        paymentTerms,
        billingCycle,
        noticePeriodDays: parseInt(noticePeriodDays) || 30,
        notes,
      });
      toast.success("Contract created successfully.");
      setIsCreateOpen(false);

      // Refresh list
      api.get(`/contracts`).then((r) => setContracts(r.data.filter((x: Contract) => x.clientId.toString() === id?.toString()))).catch(() => {});

      // Reset form
      setContractValue("");
      setStartDate("");
      setEndDate("");
      setAutoRenewal(false);
      setPaymentTerms("Net 30");
      setBillingCycle("Monthly");
      setNoticePeriodDays("30");
      setNotes("");
    } catch (err: any) {
      toast.error(err.response?.data?.message || err.message || "Failed to create contract.");
    } finally {
      setLoading(false);
    }
  };

  const outstanding = invoices.reduce((sum, i) => sum + (i.status !== "paid" ? ((i.total ?? 0) - (i.paidAmount ?? 0)) : 0), 0);
  const collected = invoices.reduce((sum, i) => sum + (i.paidAmount ?? 0), 0);

  return (
    <div data-testid="client-detail">
      <button onClick={() => nav(-1)} className="label-tiny text-zinc-500 hover:text-zinc-950 mb-2 flex items-center gap-1" data-testid="back-btn">
        <ArrowLeft className="w-3 h-3" /> BACK
      </button>
      <PageHeader
        title={c.name}
        subtitle={`${c.industry} • ${c.country} • ${c.contactEmail}`}
        actions={<StatusBadge value={c.status} />}
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <KpiCard label="MRR" value={fmtCurrency(c.monthlyRecurring)} />
        <KpiCard label="Collected" value={fmtCurrency(collected)} accent="success" />
        <KpiCard label="Outstanding" value={fmtCurrency(outstanding)} accent="warning" />
        <KpiCard label="AI Agents" value={agents.length} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border border-zinc-200">
          <div className="px-5 py-3 border-b border-zinc-200"><div className="label-tiny">AGENTS</div></div>
          <div className="divide-y divide-zinc-100">
            {agents.map((a) => (
              <div key={a.id} className="px-5 py-3 flex items-center gap-3 cursor-pointer hover:bg-zinc-50" onClick={() => nav(`/agents/${a.id}`)}>
                <div className="flex-1">
                  <div className="text-sm font-medium">{a.name}</div>
                  <div className="text-xs text-zinc-500 font-mono-stat">{a.type} • {a.channels.join(", ")}</div>
                </div>
                <StatusBadge value={a.status} />
              </div>
            ))}
            {agents.length === 0 && <div className="px-5 py-6 text-sm text-zinc-400">No agents</div>}
          </div>
        </div>

        <div className="bg-white border border-zinc-200">
          <div className="px-5 py-3 border-b border-zinc-200"><div className="label-tiny">INVOICES</div></div>
          <div className="divide-y divide-zinc-100">
            {invoices.slice(0, 8).map((i) => (
              <div key={i.id} className="px-5 py-3 flex items-center gap-3 cursor-pointer hover:bg-zinc-50" onClick={() => nav(`/invoices/${i.id}`)}>
                <div className="flex-1">
                  <div className="text-sm font-mono-stat font-medium">{i.number ?? "Invoice"}</div>
                  <div className="text-xs text-zinc-500">Due {fmtDate(i.dueDate)}</div>
                </div>
                <div className="font-mono-stat text-sm">{fmtCurrency(i.total ?? 0)}</div>
                <StatusBadge value={i.status} />
              </div>
            ))}
            {invoices.length === 0 && <div className="px-5 py-6 text-sm text-zinc-400">No invoices</div>}
          </div>
        </div>

        <div className="bg-white border border-zinc-200 lg:col-span-2">
          <div className="px-5 py-3 border-b border-zinc-200 flex justify-between items-center">
            <div className="label-tiny">CONTRACTS</div>
            {canCreate && (
              <button 
                onClick={() => setIsCreateOpen(true)}
                className="text-xs font-semibold text-zinc-900 hover:text-zinc-500"
              >
                + Create Contract
              </button>
            )}
          </div>
          <div className="divide-y divide-zinc-100">
            {contracts.map((ct) => (
              <div key={ct.id} className="px-5 py-3 flex items-center gap-3 cursor-pointer hover:bg-zinc-50" onClick={() => nav(`/contracts/${ct.id}`)}>
                <div className="flex-1">
                  <div className="text-sm font-mono-stat font-medium">{ct.number ?? "Contract"}</div>
                  <div className="text-xs text-zinc-500">{fmtDate(ct.startDate)} → {fmtDate(ct.endDate)}</div>
                </div>
                <div className="font-mono-stat text-sm">{fmtCurrency(ct.contractValue ?? ct.value ?? 0)}</div>
                <StatusBadge value={ct.status} />
              </div>
            ))}
            {contracts.length === 0 && <div className="px-5 py-6 text-sm text-zinc-400">No contracts</div>}
          </div>
        </div>
      </div>

      {/* Contract Creation Modal */}
      <AppModal open={isCreateOpen} onClose={() => setIsCreateOpen(false)} title={`Create Contract for ${c.name}`} showFooter={false}>
        <form onSubmit={handleCreate} className="space-y-4">
          <div>
            <Label className="label-tiny mb-1">Client</Label>
            <Input value={c.name} disabled className="rounded-none bg-zinc-50 text-zinc-500" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="contractValue" className="label-tiny mb-1">Contract Value (USD) *</Label>
              <Input
                id="contractValue"
                type="number"
                step="0.01"
                value={contractValue}
                onChange={(e) => setContractValue(e.target.value)}
                required
                placeholder="30000.00"
                className="rounded-none"
              />
            </div>
            <div>
              <Label htmlFor="noticePeriod" className="label-tiny mb-1">Notice Period (Days) *</Label>
              <Input
                id="noticePeriod"
                type="number"
                value={noticePeriodDays}
                onChange={(e) => setNoticePeriodDays(e.target.value)}
                required
                placeholder="30"
                className="rounded-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="startDate" className="label-tiny mb-1">Start Date *</Label>
              <Input
                id="startDate"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                required
                className="rounded-none"
              />
            </div>
            <div>
              <Label htmlFor="endDate" className="label-tiny mb-1">End Date *</Label>
              <Input
                id="endDate"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                required
                className="rounded-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="paymentTerms" className="label-tiny mb-1">Payment Terms</Label>
              <select
                id="paymentTerms"
                value={paymentTerms}
                onChange={(e) => setPaymentTerms(e.target.value)}
                className="w-full h-9 rounded-none border border-zinc-200 bg-white px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-950"
              >
                <option value="Net 30">Net 30</option>
                <option value="Net 15">Net 15</option>
                <option value="Net 45">Net 45</option>
                <option value="Due on Receipt">Due on Receipt</option>
              </select>
            </div>
            <div>
              <Label htmlFor="billingCycle" className="label-tiny mb-1">Billing Cycle</Label>
              <select
                id="billingCycle"
                value={billingCycle}
                onChange={(e) => setBillingCycle(e.target.value)}
                className="w-full h-9 rounded-none border border-zinc-200 bg-white px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-950"
              >
                <option value="Monthly">Monthly</option>
                <option value="Quarterly">Quarterly</option>
                <option value="Annually">Annually</option>
              </select>
            </div>
          </div>

          <div className="flex items-center gap-2 py-2">
            <input
              type="checkbox"
              id="autoRenewal"
              checked={autoRenewal}
              onChange={(e) => setAutoRenewal(e.target.checked)}
              className="rounded-none border-zinc-300 text-zinc-950 focus:ring-zinc-950 cursor-pointer w-4 h-4"
            />
            <Label htmlFor="autoRenewal" className="text-sm font-semibold select-none cursor-pointer">Enable Auto-Renewal</Label>
          </div>

          <div>
            <Label htmlFor="notes" className="label-tiny mb-1">Notes</Label>
            <Textarea
              id="notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Any custom terms, SLA info, etc..."
              className="rounded-none"
            />
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-zinc-100">
            <Button type="button" variant="outline" onClick={() => setIsCreateOpen(false)} disabled={loading} className="rounded-none">Cancel</Button>
            <Button type="submit" disabled={loading} className="bg-zinc-950 hover:bg-zinc-800 text-white rounded-none">
              {loading ? "Creating..." : "Create Contract"}
            </Button>
          </div>
        </form>
      </AppModal>
    </div>
  );
}
