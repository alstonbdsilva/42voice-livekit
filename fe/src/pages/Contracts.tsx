import { Contract, Client } from "@/types";
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fmtCurrency, fmtDate, daysFrom } from "@/services/api";
import { ContractService } from "@/services/contract.service";
import { ClientService } from "@/services/client.service";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import StatusBadge from "@/components/StatusBadge";
import AppModal from "@/components/AppModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/store/authStore";
import { toast } from "sonner";
import { Plus } from "lucide-react";

export default function Contracts() {
  const [rows, setRows] = useState<Contract[]>([]);
  const nav = useNavigate();
  const { user } = useAuth();

  // Modal and form states
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [clients, setClients] = useState<Client[]>([]);
  const [clientId, setClientId] = useState("");
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
    ContractService.getAll()
      .then((data) => setRows(data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (isCreateOpen) {
      ClientService.getAll()
        .then((data) => setClients(data))
        .catch(() => {});
    }
  }, [isCreateOpen]);

  const canCreate = user?.role && ["super_admin", "finance_admin", "reseller"].includes(user.role.toLowerCase());

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!clientId) {
      toast.error("Please select a client.");
      return;
    }
    setLoading(true);
    try {
      await ContractService.create({
        clientId,
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
      const data = await ContractService.getAll();
      setRows(data);

      // Reset form
      setClientId("");
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

  const columns = [
    { key: "number", label: "Contract", render: (r: Contract) => <span className="font-mono-stat font-medium">{r.number ?? "Contract"}</span> },
    { key: "clientName", label: "Client" },
    { key: "startDate", label: "Start", render: (r: Contract) => <span className="text-xs">{fmtDate(r.startDate)}</span> },
    { key: "endDate", label: "End", render: (r: Contract) => {
      const d = daysFrom(r.endDate) ?? 999;
      const cls = d < 0 ? "text-rose-700" : d <= 30 ? "text-amber-700" : "text-zinc-900";
      return <span className={`text-xs font-mono-stat ${cls}`}>{fmtDate(r.endDate)} {d !== 999 && d >= 0 && d <= 90 && `(${d}d)`}</span>;
    }},
    { key: "contractValue", label: "Value", render: (r: Contract) => <span className="font-mono-stat">{fmtCurrency(r.contractValue ?? r.value ?? 0)}</span> },
    { key: "autoRenewal", label: "Auto-renew", render: (r: Contract) => <span className="text-xs">{r.autoRenewal ? "Yes" : "No"}</span> },
    { key: "status", label: "Status", render: (r: Contract) => <StatusBadge value={r.status} /> },
  ];

  return (
    <div data-testid="contracts-page">
      <PageHeader
        title="Contracts"
        subtitle="Active, expiring and expired agreements"
        actions={
          canCreate ? (
            <Button onClick={() => setIsCreateOpen(true)} className="bg-zinc-950 hover:bg-zinc-800 text-white rounded-none flex items-center gap-1">
              <Plus className="w-4 h-4" /> Create Contract
            </Button>
          ) : undefined
        }
      />
      <DataTable testId="contracts-table" columns={columns} rows={rows} searchKeys={["number", "clientName"]}
        filters={[{ key: "status", label: "Status", options: [
          { value: "active", label: "Active" }, { value: "expiring_soon", label: "Expiring soon" }, { value: "expired", label: "Expired" }
        ]}]}
        onRowClick={(r) => nav(`/contracts/${r.id}`)}
      />

      {/* Contract Creation Modal */}
      <AppModal open={isCreateOpen} onClose={() => setIsCreateOpen(false)} title="Create New Contract" showFooter={false}>
        <form onSubmit={handleCreate} className="space-y-4">
          <div>
            <Label htmlFor="clientSelect" className="label-tiny mb-1">Client *</Label>
            <select
              id="clientSelect"
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              required
              className="w-full h-9 rounded-none border border-zinc-200 bg-white px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-950"
            >
              <option value="">Select a client...</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.contactEmail})
                </option>
              ))}
            </select>
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
