import React, { useState, useEffect } from "react";
import { toast } from "sonner";
import AppModal from "@/components/AppModal";
import PhoneNumberService from "@/services/phone-number.service";
import { Phone, Settings2, Key, Server } from "lucide-react";

interface EditNumberModalProps {
  open: boolean;
  onClose: () => void;
  numberItem: any;
  onSave: () => void;
}

export function EditNumberModal({ open, onClose, numberItem, onSave }: EditNumberModalProps) {
  const [name, setName] = useState("");
  const [monthlyCost, setMonthlyCost] = useState("");
  const [setupCost, setSetupCost] = useState("");
  const [loading, setLoading] = useState(false);
  
  // SIP Config fields
  const [sipDomain, setSipDomain] = useState("");
  const [sipUsername, setSipUsername] = useState("");
  const [sipPassword, setSipPassword] = useState("");
  const [sipProxy, setSipProxy] = useState("");

  // Sync state with selected number
  useEffect(() => {
    if (numberItem) {
      setName(numberItem.name || "");
      
      // Handle cost formatting (removing currency symbols)
      const cleanCost = (cost: any) => {
        if (typeof cost === "string") {
          return cost.replace(/[^0-9.]/g, "");
        }
        return cost?.toString() || "0.00";
      };
      
      setMonthlyCost(cleanCost(numberItem.monthlyCost));
      setSetupCost(cleanCost(numberItem.setupCost));
      
      const config = numberItem.sipConfig || {};
      setSipDomain(config.domain || "");
      setSipUsername(config.authUsername || "");
      setSipPassword(config.password || "");
      setSipProxy(config.proxy || "");
    }
  }, [numberItem, open]);

  const handleConfirm = () => {
    if (!name.trim()) {
      toast.error("Please provide a friendly label name.");
      return;
    }

    setLoading(true);

    const updatedSipConfig = {
      ...(numberItem?.sipConfig || {}),
      domain: sipDomain.trim(),
      authUsername: sipUsername.trim(),
      password: sipPassword.trim(),
      proxy: sipProxy.trim()
    };

    const payload = {
      name: name.trim(),
      monthlyCost: parseFloat(monthlyCost) || 0,
      setupCost: parseFloat(setupCost) || 0,
      sipConfig: updatedSipConfig
    };

    PhoneNumberService.update(numberItem.id, payload)
      .then(() => {
        toast.success("Phone number updated successfully.");
        onSave();
        onClose();
      })
      .catch((err) => {
        const errMsg = err?.response?.data?.message || err?.message || "Failed to update phone number.";
        toast.error(`Update failed: ${errMsg}`);
      })
      .finally(() => {
        setLoading(false);
      });
  };

  return (
    <AppModal
      open={open}
      onClose={onClose}
      title="Edit Phone Line Details"
      description={`Update metadata and registrar parameters for number ${numberItem?.number}`}
      maxWidth="sm:max-w-[480px]"
      confirmLabel={loading ? "Saving..." : "Save Changes"}
      onConfirm={handleConfirm}
      loading={loading}
    >
      <div className="space-y-4 py-2 text-xs">
        {/* Friendly Name */}
        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-1">Friendly Label / Name</label>
          <input
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 focus:outline-none focus:border-zinc-950 focus:bg-white text-xs"
            placeholder="e.g. Main Support DID"
          />
        </div>

        {/* Pricing */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-1">Monthly Cost (USD)</label>
            <div className="relative">
              <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-400 font-mono">$</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={monthlyCost}
                onChange={(e) => setMonthlyCost(e.target.value)}
                className="w-full bg-zinc-50 border border-zinc-200 rounded-sm pl-6 pr-2.5 py-1.5 focus:outline-none focus:border-zinc-950 focus:bg-white text-xs font-mono"
              />
            </div>
          </div>
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-1">Setup Cost (USD)</label>
            <div className="relative">
              <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-400 font-mono">$</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={setupCost}
                onChange={(e) => setSetupCost(e.target.value)}
                className="w-full bg-zinc-50 border border-zinc-200 rounded-sm pl-6 pr-2.5 py-1.5 focus:outline-none focus:border-zinc-950 focus:bg-white text-xs font-mono"
              />
            </div>
          </div>
        </div>

        {/* SIP Configurations Header */}
        <div className="border-t border-zinc-100 pt-3">
          <h4 className="text-[10px] font-bold uppercase tracking-wider text-zinc-900 flex items-center gap-1.5">
            <Server className="w-3.5 h-3.5 text-zinc-500" />
            <span>LiveKit SIP Registrar Credentials</span>
          </h4>
        </div>

        {/* SIP Domain & Auth Username */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-[9px] font-bold uppercase tracking-wider text-zinc-400 mb-1">SIP Server Domain</label>
            <input
              type="text"
              value={sipDomain}
              onChange={(e) => setSipDomain(e.target.value)}
              className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 focus:outline-none focus:border-zinc-950 focus:bg-white text-xs font-mono"
              placeholder="e.g. phone.c-tel.co.nz"
            />
          </div>
          <div>
            <label className="block text-[9px] font-bold uppercase tracking-wider text-zinc-400 mb-1">Auth Username</label>
            <input
              type="text"
              value={sipUsername}
              onChange={(e) => setSipUsername(e.target.value)}
              className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 focus:outline-none focus:border-zinc-950 focus:bg-white text-xs font-mono"
              placeholder="e.g. +6492993301"
            />
          </div>
        </div>

        {/* SIP Password & Proxy */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-[9px] font-bold uppercase tracking-wider text-zinc-400 mb-1">SIP Password</label>
            <input
              type="password"
              value={sipPassword}
              onChange={(e) => setSipPassword(e.target.value)}
              className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 focus:outline-none focus:border-zinc-950 focus:bg-white text-xs font-mono"
              placeholder="••••••••"
            />
          </div>
          <div>
            <label className="block text-[9px] font-bold uppercase tracking-wider text-zinc-400 mb-1">Outbound Proxy</label>
            <input
              type="text"
              value={sipProxy}
              onChange={(e) => setSipProxy(e.target.value)}
              className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 focus:outline-none focus:border-zinc-950 focus:bg-white text-xs font-mono"
              placeholder="e.g. proxy.domain.com"
            />
          </div>
        </div>
      </div>
    </AppModal>
  );
}

export default EditNumberModal;
