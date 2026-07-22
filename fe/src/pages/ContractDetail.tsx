import { Contract } from "@/types";
import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { fmtCurrency, fmtDate, daysFrom } from "@/services/api";
import { ContractService } from "@/services/contract.service";
import PageHeader from "@/components/PageHeader";
import KpiCard from "@/components/KpiCard";
import StatusBadge from "@/components/StatusBadge";
import { ArrowLeft, Edit } from "lucide-react";

import AppModal from "@/components/AppModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/store/authStore";
import { toast } from "sonner";

export default function ContractDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  
  const [c, setC] = useState<Contract | null>(null);

  // Edit form states
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [contractValue, setContractValue] = useState("");
  const [endDate, setEndDate] = useState("");
  const [autoRenewal, setAutoRenewal] = useState(false);
  const [notes, setNotes] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (id) {
      ContractService.getById(id)
        .then((data) => setC(data))
        .catch(() => {});
    }
  }, [id]);

  useEffect(() => {
    if (c) {
      setContractValue((c.contractValue ?? c.value ?? 0).toString());
      setEndDate(c.endDate ? c.endDate.substring(0, 10) : "");
      setAutoRenewal(!!c.autoRenewal);
      setNotes(c.notes ?? "");
      setStatus(c.status);
    }
  }, [c]);

  if (!c) return <div className="label-tiny">Loading…</div>;

  const days = daysFrom(c.endDate);
  const canEdit = user?.role && ["super_admin", "finance_admin", "reseller"].includes(user.role.toLowerCase());

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;
    setLoading(true);
    try {
      const updated = await ContractService.update(id, {
        status,
        contractValue: parseFloat(contractValue) || 0,
        endDate: new Date(endDate).toISOString(),
        autoRenewal,
        notes,
      });
      toast.success("Contract updated successfully.");
      setIsEditOpen(false);
      setC(updated);
    } catch (err: any) {
      toast.error(err.response?.data?.message || err.message || "Failed to update contract.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div data-testid="contract-detail">
      <button onClick={() => nav(-1)} className="label-tiny text-zinc-500 hover:text-zinc-950 mb-2 flex items-center gap-1">
        <ArrowLeft className="w-3 h-3" /> BACK
      </button>
      <PageHeader
        title={c.number ?? "Contract"}
        subtitle={`${c.clientName ?? ""} • ${c.paymentTerms ?? ""} • ${c.billingCycle ?? ""}`}
        actions={
          <div className="flex items-center gap-2">
            <StatusBadge value={c.status} />
            {canEdit && (
              <Button onClick={() => setIsEditOpen(true)} variant="outline" className="rounded-none flex items-center gap-1">
                <Edit className="w-3.5 h-3.5" /> Edit Contract
              </Button>
            )}
          </div>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <KpiCard label="Contract value" value={fmtCurrency(c.contractValue ?? c.value ?? 0)} />
        <KpiCard label="Start date" value={fmtDate(c.startDate)} />
        <KpiCard label="End date" value={fmtDate(c.endDate)} sub={days != null && days >= 0 ? `${days} days left` : "Expired"} accent={days != null && days < 30 ? "danger" : "default"} />
        <KpiCard label="Renewal probability" value={`${c.renewalProbability ?? 0}%`} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border border-zinc-200 p-5">
          <div className="label-tiny mb-3">TERMS</div>
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div><dt className="label-tiny mb-1">Notice period</dt><dd>{c.noticePeriodDays ?? 0} days</dd></div>
            <div><dt className="label-tiny mb-1">Auto-renewal</dt><dd>{c.autoRenewal ? "Yes" : "No"}</dd></div>
            <div><dt className="label-tiny mb-1">Renewal date</dt><dd>{fmtDate(c.renewalDate ?? "")}</dd></div>
            <div><dt className="label-tiny mb-1">Renewal status</dt><dd><StatusBadge value={c.renewalStatus ?? c.status ?? ""} /></dd></div>
            <div className="col-span-2"><dt className="label-tiny mb-1">Renewal owner</dt><dd>{c.renewalOwner ?? "Account Manager"}</dd></div>
          </dl>
        </div>
        <div className="bg-white border border-zinc-200 p-5">
          <div className="label-tiny mb-3">NOTES</div>
          <p className="text-sm text-zinc-700 leading-relaxed">{c.notes ?? ""}</p>
        </div>
      </div>

      {/* Edit Contract Modal */}
      <AppModal open={isEditOpen} onClose={() => setIsEditOpen(false)} title="Edit Contract Details" showFooter={false}>
        <form onSubmit={handleUpdate} className="space-y-4">
          <div>
            <Label htmlFor="statusSelect" className="label-tiny mb-1">Contract Status</Label>
            <select
              id="statusSelect"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              required
              className="w-full h-9 rounded-none border border-zinc-200 bg-white px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-950"
            >
              <option value="active">Active</option>
              <option value="paused">Paused</option>
              <option value="inactive">Inactive</option>
              <option value="terminated">Terminated</option>
            </select>
          </div>

          <div>
            <Label htmlFor="contractValue" className="label-tiny mb-1">Contract Value (USD) *</Label>
            <Input
              id="contractValue"
              type="number"
              step="0.01"
              value={contractValue}
              onChange={(e) => setContractValue(e.target.value)}
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
              className="rounded-none"
            />
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-zinc-100">
            <Button type="button" variant="outline" onClick={() => setIsEditOpen(false)} disabled={loading} className="rounded-none">Cancel</Button>
            <Button type="submit" disabled={loading} className="bg-zinc-950 hover:bg-zinc-800 text-white rounded-none">
              {loading ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        </form>
      </AppModal>
    </div>
  );
}
