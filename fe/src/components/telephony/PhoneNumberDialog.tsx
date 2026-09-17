import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import TelephonyConfigService, {
  TelephonyPhoneNumberItem,
} from "@/services/telephonyConfigService";
import AgentService from "@/services/agent.service";
import { Agent } from "@/types";

interface PhoneNumberDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  configId: string;
  existing?: TelephonyPhoneNumberItem | null;
  onSaved: () => void;
}

const ADDRESS_FORMAT_STRIP_RE = /[\s\-()]/g;
const ADDRESS_E164_RE = /^\+\d{8,15}$/;
const ADDRESS_BARE_DIGITS_RE = /^\d{8,15}$/;

function validateAddress(rawAddress: string, countryCode: string): string | null {
  const trimmed = rawAddress.trim();
  if (!trimmed) return "Address is required";
  if (/^sips?:/i.test(trimmed)) return null;
  const stripped = trimmed.replace(ADDRESS_FORMAT_STRIP_RE, "");
  if (ADDRESS_E164_RE.test(stripped)) return null;
  if (ADDRESS_BARE_DIGITS_RE.test(stripped) && !countryCode.trim()) {
    return "PSTN addresses without a leading '+' need a Country (ISO-2) hint, or include the country code in the address (e.g. +14155551234).";
  }
  return null;
}

export function PhoneNumberDialog({
  open,
  onOpenChange,
  configId,
  existing,
  onSaved,
}: PhoneNumberDialogProps) {
  const isEdit = !!existing;

  const [address, setAddress] = useState<string>("");
  const [countryCode, setCountryCode] = useState<string>("");
  const [label, setLabel] = useState<string>("");
  const [isActive, setIsActive] = useState<boolean>(true);
  const [isDefaultCallerId, setIsDefaultCallerId] = useState<boolean>(false);
  const [inboundAgentId, setInboundAgentId] = useState<string>("__none__");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [addressTouched, setAddressTouched] = useState<boolean>(false);

  useEffect(() => {
    if (!open) return;
    let isSubscribed = true;

    (async () => {
      try {
        const agentList = await AgentService.getAll();
        if (isSubscribed) {
          setAgents(agentList);
        }
      } catch (err) {
        console.warn("Could not fetch agents list:", err);
      }
    })();

    if (existing) {
      setAddress(existing.address);
      setCountryCode(existing.country_code || "");
      setLabel(existing.label || "");
      setIsActive(existing.is_active);
      setIsDefaultCallerId(existing.is_default_caller_id);
      setInboundAgentId(existing.inbound_agent_id || "__none__");
    } else {
      setAddress("");
      setCountryCode("");
      setLabel("");
      setIsActive(true);
      setIsDefaultCallerId(false);
      setInboundAgentId("__none__");
    }
    setAddressTouched(false);

    return () => {
      isSubscribed = false;
    };
  }, [open, existing]);

  const addressError = isEdit ? null : validateAddress(address, countryCode);

  const handleSubmit = async () => {
    if (!isEdit) {
      const err = validateAddress(address, countryCode);
      if (err) {
        setAddressTouched(true);
        toast.error(err);
        return;
      }
    }

    setSubmitting(true);
    try {
      const selectedAgentId = inboundAgentId === "__none__" ? undefined : inboundAgentId;

      if (isEdit && existing) {
        await TelephonyConfigService.updatePhoneNumber(configId, existing.id, {
          country_code: countryCode || undefined,
          label: label.trim() || undefined,
          is_active: isActive,
          inbound_agent_id: selectedAgentId,
        });
        toast.success("Phone number updated");
      } else {
        await TelephonyConfigService.addPhoneNumber(configId, {
          address: address.trim(),
          country_code: countryCode || undefined,
          label: label.trim() || undefined,
          is_active: isActive,
          is_default_caller_id: isDefaultCallerId,
          inbound_agent_id: selectedAgentId,
        });
        toast.success("Phone number added");
      }
      onOpenChange(false);
      onSaved();
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || "Failed to save phone number";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? "Edit phone number" : "Add phone number"}
          </DialogTitle>
          <DialogDescription>
            PSTN numbers (E.164), SIP URIs (sip:user@host), and SIP extensions are all supported.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-1">
            <Label htmlFor="pn-address">Address</Label>
            <Input
              id="pn-address"
              placeholder="+19781899185, sip:101@asterisk.local, or 101"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              onBlur={() => setAddressTouched(true)}
              disabled={isEdit}
            />
            {!isEdit && addressTouched && addressError && (
              <p className="text-xs text-red-500">{addressError}</p>
            )}
            {isEdit && (
              <p className="text-xs text-zinc-500">
                Address cannot be changed. Delete this number and create a new one to change it.
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="pn-country">Country (ISO-2)</Label>
              <Input
                id="pn-country"
                placeholder="US"
                maxLength={2}
                value={countryCode}
                onChange={(e) => setCountryCode(e.target.value.toUpperCase())}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="pn-label">Label</Label>
              <Input
                id="pn-label"
                placeholder="e.g. Sales caller ID"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-1">
            <Label htmlFor="pn-agent">Inbound AI Agent</Label>
            <Select value={inboundAgentId} onValueChange={setInboundAgentId}>
              <SelectTrigger id="pn-agent">
                <SelectValue placeholder="(none)" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">(none)</SelectItem>
                {agents.map((agent) => (
                  <SelectItem key={agent.id} value={String(agent.id)}>
                    {agent.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-zinc-500">
              Assigned agent to handle inbound calls received on this phone number.
            </p>
          </div>

          <div className="flex items-center justify-between rounded border border-zinc-200 p-3 bg-zinc-50">
            <Label className="text-sm">Active</Label>
            <Switch checked={isActive} onCheckedChange={setIsActive} />
          </div>

          {!isEdit && (
            <div className="flex items-center justify-between rounded border border-zinc-200 p-3 bg-zinc-50">
              <div>
                <Label className="text-sm">Default caller ID for this configuration</Label>
                <p className="text-xs text-zinc-500">
                  Used as the from-number for test calls when set.
                </p>
              </div>
              <Switch
                checked={isDefaultCallerId}
                onCheckedChange={setIsDefaultCallerId}
              />
            </div>
          )}
        </div>

        <DialogFooter className="pt-2">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={submitting || (!isEdit && !!addressError)}
          >
            {submitting ? "Saving..." : isEdit ? "Save changes" : "Add"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default PhoneNumberDialog;
