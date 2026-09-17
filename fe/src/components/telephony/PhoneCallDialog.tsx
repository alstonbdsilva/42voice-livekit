import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, PhoneCall as PhoneCallIcon } from "lucide-react";
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
import TelephonyConfigService, {
  TelephonyConfigurationListItem,
  TelephonyPhoneNumberItem,
} from "@/services/telephonyConfigService";

interface PhoneCallDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  agentId?: string;
}

export function PhoneCallDialog({
  open,
  onOpenChange,
  agentId,
}: PhoneCallDialogProps) {
  const navigate = useNavigate();

  const [phoneNumber, setPhoneNumber] = useState<string>("");
  const [sipMode, setSipMode] = useState<boolean>(false);
  const [checkingConfig, setCheckingConfig] = useState<boolean>(false);
  const [needsConfiguration, setNeedsConfiguration] = useState<boolean | null>(null);
  const [telephonyConfigs, setTelephonyConfigs] = useState<TelephonyConfigurationListItem[]>([]);
  const [selectedConfigId, setSelectedConfigId] = useState<string>("");
  const [fromPhoneNumbers, setFromPhoneNumbers] = useState<TelephonyPhoneNumberItem[]>([]);
  const [selectedFromPhoneNumberId, setSelectedFromPhoneNumberId] = useState<string>("");
  const [loadingPhoneNumbers, setLoadingPhoneNumbers] = useState<boolean>(false);

  const [callLoading, setCallLoading] = useState<boolean>(false);
  const [callError, setCallError] = useState<string | null>(null);
  const [callSuccessMsg, setCallSuccessMsg] = useState<string | null>(null);

  // Check telephony configuration when dialog opens
  useEffect(() => {
    if (!open) return;
    let isSubscribed = true;

    (async () => {
      setCheckingConfig(true);
      try {
        const res = await TelephonyConfigService.listConfigurations();
        if (!isSubscribed) return;
        const configs = res.configurations ?? [];
        if (configs.length === 0) {
          setNeedsConfiguration(true);
          setTelephonyConfigs([]);
          setSelectedConfigId("");
        } else {
          setNeedsConfiguration(false);
          setTelephonyConfigs(configs);
          const defaultConfig = configs.find((c) => c.is_default_outbound) ?? configs[0];
          setSelectedConfigId(String(defaultConfig.id));
        }
      } catch (err) {
        if (!isSubscribed) return;
        console.error("Failed to check telephony config:", err);
        setNeedsConfiguration(false);
        setTelephonyConfigs([]);
        setSelectedConfigId("");
      } finally {
        if (isSubscribed) setCheckingConfig(false);
      }
    })();

    return () => {
      isSubscribed = false;
    };
  }, [open]);

  // Fetch phone numbers whenever selected telephony configuration changes
  useEffect(() => {
    if (!open || !selectedConfigId) {
      setFromPhoneNumbers([]);
      setSelectedFromPhoneNumberId("");
      return;
    }

    let isSubscribed = true;
    (async () => {
      setLoadingPhoneNumbers(true);
      try {
        const res = await TelephonyConfigService.listPhoneNumbers(selectedConfigId);
        if (!isSubscribed) return;
        const all = res.phone_numbers ?? [];
        const active = all.filter((p) => p.is_active);
        setFromPhoneNumbers(active);
        const defaultPhone = active.find((p) => p.is_default_caller_id) ?? active[0];
        setSelectedFromPhoneNumberId(defaultPhone ? String(defaultPhone.id) : "");
      } catch (err) {
        if (!isSubscribed) return;
        console.error("Failed to load phone numbers for config:", err);
        setFromPhoneNumbers([]);
        setSelectedFromPhoneNumberId("");
      } finally {
        if (isSubscribed) setLoadingPhoneNumbers(false);
      }
    })();

    return () => {
      isSubscribed = false;
    };
  }, [open, selectedConfigId]);

  // Reset state when dialog closes
  useEffect(() => {
    if (!open) {
      setCallError(null);
      setCallSuccessMsg(null);
      setCallLoading(false);
      setNeedsConfiguration(null);
      setTelephonyConfigs([]);
      setSelectedConfigId("");
      setFromPhoneNumbers([]);
      setSelectedFromPhoneNumberId("");
      setPhoneNumber("");
    }
  }, [open]);

  const handleConfigureContinue = () => {
    onOpenChange(false);
    navigate("/telephony-configurations");
  };

  const handleStartCall = async () => {
    if (!phoneNumber.trim()) {
      setCallError("Please enter a destination phone number or SIP address.");
      return;
    }

    setCallLoading(true);
    setCallError(null);
    setCallSuccessMsg(null);

    try {
      const res = await TelephonyConfigService.initiateCall({
        agent_id: agentId,
        phone_number: phoneNumber.trim(),
        telephony_configuration_id: selectedConfigId || undefined,
        from_phone_number_id: selectedFromPhoneNumberId || undefined,
      });

      const msg = res.message || "Call initiated successfully!";
      setCallSuccessMsg(msg);
      toast.success(msg);
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || "Failed to initiate call";
      setCallError(msg);
      toast.error(msg);
    } finally {
      setCallLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        {checkingConfig || needsConfiguration === null ? (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <PhoneCallIcon className="h-5 w-5 text-emerald-600" /> Phone Call
              </DialogTitle>
            </DialogHeader>
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
            </div>
          </>
        ) : needsConfiguration ? (
          <>
            <DialogHeader>
              <DialogTitle>Configure Telephony</DialogTitle>
              <DialogDescription>
                You need to configure your telephony settings before making phone calls.
                You will be redirected to the telephony configuration page.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter className="gap-2 sm:gap-0 pt-4">
              <Button variant="ghost" onClick={() => onOpenChange(false)}>
                Do it Later
              </Button>
              <Button onClick={handleConfigureContinue}>
                Continue
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <PhoneCallIcon className="h-5 w-5 text-emerald-600" /> Phone Call
              </DialogTitle>
              <DialogDescription>
                Enter the phone number or SIP endpoint to call for testing this agent.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-2">
              {telephonyConfigs.length > 0 && (
                <div className="space-y-1.5">
                  <Label htmlFor="telephony-config">Telephony configuration</Label>
                  <Select value={selectedConfigId} onValueChange={setSelectedConfigId}>
                    <SelectTrigger id="telephony-config">
                      <SelectValue placeholder="Select a configuration" />
                    </SelectTrigger>
                    <SelectContent>
                      {telephonyConfigs.map((config) => (
                        <SelectItem key={config.id} value={String(config.id)}>
                          {config.name} ({config.provider})
                          {config.is_default_outbound ? " - default" : ""}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {selectedConfigId && (
                <div className="space-y-1.5">
                  <Label htmlFor="from-phone-number">Caller ID (from)</Label>
                  {loadingPhoneNumbers ? (
                    <div className="flex items-center text-xs text-zinc-500 py-1">
                      <Loader2 className="h-3.5 w-3.5 animate-spin mr-2" />
                      Loading phone numbers...
                    </div>
                  ) : fromPhoneNumbers.length > 0 ? (
                    <Select
                      value={selectedFromPhoneNumberId}
                      onValueChange={setSelectedFromPhoneNumberId}
                    >
                      <SelectTrigger id="from-phone-number">
                        <SelectValue placeholder="Select a phone number" />
                      </SelectTrigger>
                      <SelectContent>
                        {fromPhoneNumbers.map((phone) => (
                          <SelectItem key={phone.id} value={String(phone.id)}>
                            {phone.label ? `${phone.label} - ${phone.address}` : phone.address}
                            {phone.is_default_caller_id ? " - default" : ""}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <p className="text-xs text-zinc-500">
                      No phone numbers in this configuration. The provider will pick one automatically.
                    </p>
                  )}
                </div>
              )}

              <div className="space-y-1.5">
                <Label htmlFor="dest-phone-number">
                  {sipMode ? "SIP Endpoint" : "Destination Phone Number"}
                </Label>
                <Input
                  id="dest-phone-number"
                  value={phoneNumber}
                  onChange={(e) => {
                    setPhoneNumber(e.target.value);
                    setCallError(null);
                    setCallSuccessMsg(null);
                  }}
                  placeholder={sipMode ? "sip:101@asterisk.local" : "+14155551234"}
                />
                <button
                  type="button"
                  className="text-xs text-zinc-500 hover:text-zinc-900 underline pt-1"
                  onClick={() => {
                    setSipMode(!sipMode);
                    setPhoneNumber("");
                    setCallError(null);
                    setCallSuccessMsg(null);
                  }}
                >
                  {sipMode ? "Use phone number instead" : "Use SIP endpoint instead"}
                </button>
              </div>

              {callError && (
                <div className="text-xs font-medium text-red-600 bg-red-50 border border-red-200 rounded p-2.5">
                  {callError}
                </div>
              )}
              {callSuccessMsg && (
                <div className="text-xs font-medium text-emerald-600 bg-emerald-50 border border-emerald-200 rounded p-2.5">
                  {callSuccessMsg}
                </div>
              )}
            </div>

            <DialogFooter className="flex-col sm:flex-row gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  onOpenChange(false);
                  navigate("/telephony-configurations");
                }}
              >
                Configure Telephony
              </Button>
              <div className="flex gap-2 flex-1 justify-end">
                <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
                  Cancel
                </Button>
                {!callSuccessMsg ? (
                  <Button
                    size="sm"
                    onClick={handleStartCall}
                    disabled={callLoading || !phoneNumber.trim()}
                  >
                    {callLoading ? "Calling..." : "Start Call"}
                  </Button>
                ) : (
                  <>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setCallSuccessMsg(null);
                        setCallError(null);
                      }}
                    >
                      Call Again
                    </Button>
                    <Button size="sm" onClick={() => onOpenChange(false)}>
                      Close
                    </Button>
                  </>
                )}
              </div>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default PhoneCallDialog;
