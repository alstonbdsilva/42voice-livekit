import { Invoice, Payment } from "@/types";
import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { fmtCurrency, fmtDate } from "@/services/api";
import { InvoiceService } from "@/services/invoice.service";
import { PaymentService } from "@/services/payment.service";
import PageHeader from "@/components/PageHeader";
import StatusBadge from "@/components/StatusBadge";
import { ArrowLeft } from "lucide-react";

export default function InvoiceDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const [inv, setInv] = useState<Invoice | null>(null);
  const [payments, setPayments] = useState<Payment[]>([]);

  useEffect(() => {
    if (id) {
      InvoiceService.getById(id).then((data) => setInv(data)).catch(() => {});
      PaymentService.getAll().then((data) => setPayments(data.filter((p: Payment) => p.invoiceId.toString() === id.toString()))).catch(() => {});
    }
  }, [id]);

  if (!inv) return <div className="label-tiny">Loading…</div>;
  const total = inv.total ?? 0;
  const paidAmount = inv.paidAmount ?? 0;
  const outstanding = Math.max(total - paidAmount, 0);

  return (
    <div data-testid="invoice-detail">
      <button onClick={() => nav(-1)} className="label-tiny text-zinc-500 hover:text-zinc-950 mb-2 flex items-center gap-1">
        <ArrowLeft className="w-3 h-3" /> BACK
      </button>
      <PageHeader title={inv.number ?? "Invoice"} subtitle={`${inv.clientName} • Issued ${fmtDate(inv.issueDate || inv.createdAt)} • Due ${fmtDate(inv.dueDate)}`}
        actions={<StatusBadge value={inv.status} />} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white border border-zinc-200">
          <div className="px-5 py-3 border-b border-zinc-200 label-tiny">LINE ITEMS</div>
          <table className="w-full text-sm">
            <thead>
              <tr><th className="px-5 py-2 text-left label-tiny">Description</th><th className="px-5 py-2 text-right label-tiny">Amount</th></tr>
            </thead>
            <tbody>
              {inv.lineItems?.map((li, i) => (
                <tr key={i} className="border-t border-zinc-100">
                  <td className="px-5 py-3">{li.label ?? li.description}</td>
                  <td className="px-5 py-3 text-right font-mono-stat">{fmtCurrency(li.amount)}</td>
                </tr>
              ))}
              <tr className="border-t border-zinc-200 bg-zinc-50">
                <td className="px-5 py-3 label-tiny">TOTAL</td>
                <td className="px-5 py-3 text-right font-mono-stat font-bold text-lg">{fmtCurrency(total)}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="space-y-4">
          <div className="bg-white border border-zinc-200 p-5">
            <div className="label-tiny">OUTSTANDING</div>
            <div className="font-mono-stat text-3xl font-semibold mt-2 text-amber-700">{fmtCurrency(outstanding)}</div>
            <div className="mt-3 text-xs text-zinc-500">
              Paid <span className="font-mono-stat text-emerald-700">{fmtCurrency(paidAmount)}</span> of <span className="font-mono-stat">{fmtCurrency(total)}</span>
            </div>
          </div>
          <div className="bg-white border border-zinc-200">
            <div className="px-5 py-3 border-b border-zinc-200 label-tiny">PAYMENTS RECEIVED</div>
            <div className="divide-y divide-zinc-100">
              {payments.map((p) => (
                <div key={p.id} className="px-5 py-3 text-sm flex items-center gap-3">
                  <div className="flex-1">
                    <div className="font-mono-stat font-medium">{fmtCurrency(p.amount)}</div>
                    <div className="text-xs text-zinc-500">{(p.method ?? p.paymentMethod ?? "").toUpperCase()} • {fmtDate(p.paidAt || p.createdAt)}</div>
                  </div>
                  <StatusBadge value={p.status} />
                </div>
              ))}
              {payments.length === 0 && <div className="px-5 py-6 text-sm text-zinc-400">No payments yet</div>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
