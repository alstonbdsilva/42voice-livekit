import React, { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useAuth } from "@/store/authStore";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import StatusBadge from "@/components/StatusBadge";
import AppModal from "@/components/AppModal";
import KpiCard from "@/components/KpiCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Plan, PlanService } from "@/services/plan.service";
import { BillingService } from "@/services/billing.service";
import { fmtCurrency, fmtNumber } from "@/services/api";
import { toast } from "sonner";
import { CreditCard, Plus, DollarSign, Clock, Settings, ShieldCheck, CheckCircle } from "lucide-react";

export default function Plans() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const nav = useNavigate();

  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);

  // Modals state
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isRateOpen, setIsRateOpen] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<Plan | null>(null);

  // Form states
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [minutes, setMinutes] = useState("");
  const [isCustom, setIsCustom] = useState(false);
  const [resellerId, setResellerId] = useState("");
  const [clientPrice, setClientPrice] = useState("");

  const isAdmin = user?.role === "super_admin" || user?.role === "finance_admin";
  const isReseller = user?.role === "reseller";
  const isClient = user?.role === "client";

  // Check URL parameters for Stripe callbacks or simulations
  const mockCheckout = searchParams.get("mock_checkout") === "true";
  const success = searchParams.get("success") === "true";
  const cancelled = searchParams.get("cancelled") === "true";

  const loadPlans = async () => {
    setLoading(true);
    try {
      const data = await PlanService.getAll();
      setPlans(data);
    } catch (err) {
      toast.error("Failed to load plans");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPlans();
    if (success) {
      toast.success("Payment succeeded! Credits added to balance.");
      setSearchParams({});
    }
    if (cancelled) {
      toast.error("Payment session was cancelled.");
      setSearchParams({});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [success, cancelled]);

  // Handle plan purchase
  const handleBuy = async (planId: string) => {
    try {
      toast.loading("Initiating checkout session...");
      const checkoutUrl = await BillingService.buyPlan(planId);
      toast.dismiss();
      // Redirect to Stripe or Mock simulation
      window.location.href = checkoutUrl;
    } catch (err: any) {
      toast.dismiss();
      toast.error(err.response?.data?.message || "Checkout failed");
    }
  };

  // Handle mock checkout simulation success
  const handleMockSuccess = async () => {
    const planId = searchParams.get("plan_id") || "";
    const buyerType = searchParams.get("buyer_type") || "";
    const buyerId = searchParams.get("buyer_id") || "";
    const priceVal = parseFloat(searchParams.get("price") || "0");

    try {
      toast.loading("Simulating payment completion...");
      await BillingService.simulateSuccess({
        planId,
        buyerType,
        buyerId,
        price: priceVal
      });
      toast.dismiss();
      nav("/plans?success=true");
    } catch (err) {
      toast.dismiss();
      toast.error("Simulation failed");
    }
  };

  // Create new base plan (Admin)
  const handleCreatePlan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !price || !minutes) {
      toast.error("Please fill in required fields");
      return;
    }
    try {
      await PlanService.create({
        name,
        description,
        price: parseFloat(price),
        minutes: parseInt(minutes),
        isCustom,
        resellerId: resellerId || undefined
      });
      toast.success("Plan created successfully");
      setIsCreateOpen(false);
      setName("");
      setDescription("");
      setPrice("");
      setMinutes("");
      setIsCustom(false);
      setResellerId("");
      loadPlans();
    } catch (err) {
      toast.error("Failed to create plan");
    }
  };

  // Set Reseller markup price
  const handleSetRate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPlan || !clientPrice) return;
    try {
      await PlanService.setRate(selectedPlan.id, parseFloat(clientPrice));
      toast.success("Pricing markup configured");
      setIsRateOpen(false);
      setClientPrice("");
      loadPlans();
    } catch (err) {
      toast.error("Failed to configure pricing");
    }
  };

  // Render mock checkout simulator screen
  if (mockCheckout) {
    const planId = searchParams.get("plan_id") || "";
    const buyerType = searchParams.get("buyer_type") || "";
    const priceVal = searchParams.get("price") || "0";

    return (
      <div className="max-w-md mx-auto my-12 bg-white border border-zinc-200 shadow-xl rounded-sm p-6" data-testid="mock-checkout-page">
        <div className="flex items-center gap-2 mb-4 text-emerald-600">
          <ShieldCheck className="w-8 h-8" />
          <h2 className="text-xl font-bold tracking-tight">Stripe Sandbox Simulator</h2>
        </div>
        <p className="text-sm text-zinc-500 mb-6">
          This simulates a secure Stripe checkout session for sandbox validation.
        </p>

        <div className="space-y-4 mb-8 bg-zinc-50 p-4 border border-zinc-200">
          <div className="flex justify-between text-sm">
            <span className="text-zinc-500">Plan Ref:</span>
            <span className="font-mono-stat font-medium">{planId.substring(0, 8)}...</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-zinc-500">Account Role:</span>
            <span className="font-mono-stat font-medium uppercase">{buyerType}</span>
          </div>
          <div className="flex justify-between text-sm border-t border-zinc-200 pt-3">
            <span className="text-zinc-900 font-semibold">Total Charged:</span>
            <span className="font-mono-stat font-bold text-lg text-emerald-700">{fmtCurrency(parseFloat(priceVal))}</span>
          </div>
        </div>

        <div className="space-y-3">
          <Button onClick={handleMockSuccess} className="w-full bg-emerald-600 hover:bg-emerald-700 text-white rounded-none">
            Simulate Payment Success
          </Button>
          <Button variant="outline" onClick={() => nav("/plans?cancelled=true")} className="w-full rounded-none">
            Cancel Transaction
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div data-testid="plans-page">
      <PageHeader
        title="Minute Recharge Plans"
        subtitle="Manage wholesale plans, configure client markups, and purchase prepaid minutes."
        actions={
          isAdmin && (
            <Button onClick={() => setIsCreateOpen(true)} className="bg-zinc-950 text-white rounded-none flex items-center gap-2">
              <Plus className="w-4 h-4" /> CREATE PLAN
            </Button>
          )
        }
      />

      {loading ? (
        <div className="label-tiny">Loading plans…</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {plans.map((p) => {
            const hasMarkup = p.clientPrice !== null && p.clientPrice !== undefined;
            const displaysMarkupPrice = isClient || isReseller;

            return (
              <div key={p.id} className="bg-white border border-zinc-200 flex flex-col justify-between p-6 shadow-sm hover:shadow-md transition-shadow relative">
                {p.isCustom && (
                  <span className="absolute top-3 right-3 text-[9px] font-bold bg-amber-100 text-amber-800 px-2 py-0.5 uppercase tracking-wider">
                    Custom Plan
                  </span>
                )}
                <div>
                  <h3 className="font-bold text-lg text-zinc-950 leading-tight mb-1">{p.name}</h3>
                  <p className="text-zinc-500 text-xs mb-4 min-h-[32px]">{p.description}</p>

                  <div className="grid grid-cols-2 gap-4 border-y border-zinc-100 py-3 mb-4">
                    <div>
                      <div className="text-[10px] text-zinc-400 font-semibold uppercase tracking-wider mb-1">Plan Minutes</div>
                      <div className="flex items-center gap-1.5 font-mono-stat font-bold text-zinc-900">
                        <Clock className="w-3.5 h-3.5 text-zinc-500" />
                        {fmtNumber(p.minutes)} mins
                      </div>
                    </div>

                    <div>
                      {isReseller ? (
                        <>
                          <div className="text-[10px] text-zinc-400 font-semibold uppercase tracking-wider mb-1">Wholesale Cost</div>
                          <div className="font-mono-stat font-bold text-zinc-900">
                            {fmtCurrency(p.price)}
                          </div>
                        </>
                      ) : isClient ? (
                        <>
                          <div className="text-[10px] text-zinc-400 font-semibold uppercase tracking-wider mb-1">Price</div>
                          <div className="font-mono-stat font-bold text-emerald-700">
                            {fmtCurrency(p.clientPrice ?? 0)}
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="text-[10px] text-zinc-400 font-semibold uppercase tracking-wider mb-1">Base Price</div>
                          <div className="font-mono-stat font-bold text-zinc-900">
                            {fmtCurrency(p.price)}
                          </div>
                        </>
                      )}
                    </div>
                  </div>

                  {isReseller && (
                    <div className="bg-zinc-50 border border-zinc-200 p-3 mb-4 rounded-none text-xs">
                      <div className="font-semibold text-zinc-700 flex items-center justify-between mb-1">
                        <span>Client Rate:</span>
                        <span className="font-mono-stat text-emerald-700 font-bold">
                          {hasMarkup ? fmtCurrency(p.clientPrice!) : "Not Configured"}
                        </span>
                      </div>
                      <p className="text-[10px] text-zinc-400">
                        {hasMarkup
                          ? `Commission: ${fmtCurrency(p.clientPrice! - p.price)} per sale`
                          : "Configure a client markup price to make this plan available to your clients."}
                      </p>
                    </div>
                  )}
                </div>

                <div className="space-y-2 mt-4 pt-2 border-t border-zinc-100">
                  {isClient && (
                    <Button onClick={() => handleBuy(p.id)} className="w-full bg-emerald-600 hover:bg-emerald-700 text-white rounded-none flex items-center justify-center gap-2">
                      <CreditCard className="w-4 h-4" /> Buy Recharge
                    </Button>
                  )}
                  {isReseller && (
                    <div className="flex gap-2">
                      <Button onClick={() => handleBuy(p.id)} className="flex-1 bg-zinc-950 hover:bg-zinc-800 text-white rounded-none flex items-center justify-center gap-1.5 text-xs">
                        <CreditCard className="w-3.5 h-3.5" /> Buy Wholesale
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => {
                          setSelectedPlan(p);
                          setClientPrice(p.clientPrice?.toString() || "");
                          setIsRateOpen(true);
                        }}
                        className="rounded-none flex items-center justify-center border-zinc-300 px-3"
                        title="Configure Client Markup"
                      >
                        <Settings className="w-4 h-4" />
                      </Button>
                    </div>
                  )}
                  {isAdmin && (
                    <div className="text-xs text-zinc-400 flex items-center justify-between">
                      <span>Status:</span>
                      <StatusBadge value={p.status} />
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {plans.length === 0 && (
            <div className="col-span-full py-12 text-center text-sm text-zinc-400 bg-white border border-dashed border-zinc-200">
              No plans available.
            </div>
          )}
        </div>
      )}

      {/* Admin: Create Plan Modal */}
      <AppModal open={isCreateOpen} onClose={() => setIsCreateOpen(false)} title="Create New Wholesale Plan">
        <form onSubmit={handleCreatePlan} className="space-y-4">
          <div>
            <Label htmlFor="planName" className="label-tiny mb-1">Plan Name *</Label>
            <Input id="planName" value={name} onChange={(e) => setName(e.target.value)} required placeholder="e.g. Starter Minutes Package" />
          </div>
          <div>
            <Label htmlFor="planDesc" className="label-tiny mb-1">Description</Label>
            <Textarea id="planDesc" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Provide information about included minutes..." />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="planPrice" className="label-tiny mb-1">Wholesale Price (USD) *</Label>
              <Input id="planPrice" type="number" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} required placeholder="50.00" />
            </div>
            <div>
              <Label htmlFor="planMinutes" className="label-tiny mb-1">Included Minutes *</Label>
              <Input id="planMinutes" type="number" value={minutes} onChange={(e) => setMinutes(e.target.value)} required placeholder="1000" />
            </div>
          </div>
          <div className="flex items-center gap-2 py-2">
            <input type="checkbox" id="planCustom" checked={isCustom} onChange={(e) => setIsCustom(e.target.checked)} className="rounded-sm border-zinc-300 text-zinc-950 focus:ring-zinc-950" />
            <Label htmlFor="planCustom" className="text-sm font-semibold select-none cursor-pointer">Custom/Exclusive Plan</Label>
          </div>
          {isCustom && (
            <div>
              <Label htmlFor="customReseller" className="label-tiny mb-1">Assigned Reseller Partner ID</Label>
              <Input id="customReseller" value={resellerId} onChange={(e) => setResellerId(e.target.value)} placeholder="e.g. UUID-of-Reseller" />
            </div>
          )}
          <div className="flex justify-end gap-3 pt-4 border-t border-zinc-100">
            <Button type="button" variant="outline" onClick={() => setIsCreateOpen(false)} className="rounded-none">Cancel</Button>
            <Button type="submit" className="bg-zinc-950 text-white rounded-none">Create Plan</Button>
          </div>
        </form>
      </AppModal>

      {/* Reseller: Set Markup Price Modal */}
      <AppModal open={isRateOpen} onClose={() => setIsRateOpen(false)} title={`Configure Client Markup Rate`}>
        {selectedPlan && (
          <form onSubmit={handleSetRate} className="space-y-4">
            <div className="bg-zinc-50 p-4 border border-zinc-200 space-y-2 text-xs">
              <div className="flex justify-between"><span className="text-zinc-500">Wholesale Base Cost:</span><span className="font-mono-stat font-semibold">{fmtCurrency(selectedPlan.price)}</span></div>
              <div className="flex justify-between"><span className="text-zinc-500">Included Minutes:</span><span className="font-mono-stat font-semibold">{fmtNumber(selectedPlan.minutes)}</span></div>
            </div>

            <div>
              <Label htmlFor="clientRate" className="label-tiny mb-1">Client Retail Price (USD) *</Label>
              <Input id="clientRate" type="number" step="0.01" value={clientPrice} onChange={(e) => setClientPrice(e.target.value)} required placeholder="e.g. 75.00" />
              <p className="text-[10px] text-zinc-400 mt-1">
                Must be higher than the wholesale cost of {fmtCurrency(selectedPlan.price)} to earn a profit.
              </p>
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t border-zinc-100">
              <Button type="button" variant="outline" onClick={() => setIsRateOpen(false)} className="rounded-none">Cancel</Button>
              <Button type="submit" className="bg-emerald-600 hover:bg-emerald-700 text-white rounded-none">Save Rates</Button>
            </div>
          </form>
        )}
      </AppModal>
    </div>
  );
}
