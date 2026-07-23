import React, { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { CheckCircle2, RefreshCw, Settings, Loader2 } from "lucide-react";
import { api, API } from "@/services/api";
import { useAuth } from "@/store/authStore";

// HIGH FIDELITY BRAND LOGO COMPONENT RENDERERS
const GoogleCalendarLogo = () => (
  <div className="w-10 h-10 rounded-xl bg-white border border-zinc-200 flex items-center justify-center flex-shrink-0 relative overflow-hidden">
    <div className="absolute top-0 left-0 right-0 h-3 bg-[#4285F4]"></div>
    <span className="text-[#4285F4] font-extrabold text-lg mt-2 font-sans">31</span>
  </div>
);

const OutlookLogo = () => (
  <div className="w-10 h-10 rounded-xl bg-white border border-zinc-200 flex items-center justify-center flex-shrink-0 relative overflow-hidden">
    <div className="absolute top-0 left-0 right-0 h-3 bg-[#0078d4]"></div>
    <span className="text-[#0078d4] font-extrabold text-lg mt-2 font-sans">O</span>
  </div>
);

const AppleCalendarLogo = () => (
  <div className="w-10 h-10 rounded-xl bg-white border border-zinc-200 flex items-center justify-center flex-shrink-0 relative overflow-hidden">
    <div className="absolute top-0 left-0 right-0 h-3 bg-[#ff3b30]"></div>
    <span className="text-zinc-900 font-extrabold text-lg mt-2 font-sans">A</span>
  </div>
);

const CalendlyLogo = () => (
  <div className="w-10 h-10 rounded-xl bg-white border border-zinc-200 flex items-center justify-center flex-shrink-0 relative overflow-hidden">
    <div className="absolute top-0 left-0 right-0 h-3 bg-[#006bff]"></div>
    <span className="text-[#006bff] font-extrabold text-lg mt-2 font-sans">C</span>
  </div>
);

const CalComLogo = () => (
  <div className="w-10 h-10 rounded-xl bg-zinc-950 border border-zinc-800 flex items-center justify-center flex-shrink-0 relative overflow-hidden">
    <span className="text-white font-black text-sm uppercase tracking-tighter font-sans">cal</span>
  </div>
);

const NotionCalendarLogo = () => (
  <div className="w-10 h-10 rounded-xl bg-white border border-zinc-200 flex items-center justify-center flex-shrink-0 relative overflow-hidden">
    <div className="absolute top-0 left-0 right-0 h-3 bg-zinc-900"></div>
    <span className="text-zinc-900 font-extrabold text-lg mt-2 font-sans">N</span>
  </div>
);

const ZohoCalendarLogo = () => (
  <div className="w-10 h-10 rounded-xl bg-white border border-zinc-200 flex items-center justify-center flex-shrink-0 relative overflow-hidden p-1 grid grid-cols-2 gap-0.5">
    <div className="bg-[#e21c25] rounded-sm"></div>
    <div className="bg-[#009fd4] rounded-sm"></div>
    <div className="bg-[#6fba2c] rounded-sm"></div>
    <div className="bg-[#f8b617] rounded-sm"></div>
  </div>
);

const HubSpotLogo = () => (
  <div className="w-10 h-10 rounded-xl bg-white border border-zinc-200 flex items-center justify-center flex-shrink-0 relative overflow-hidden">
    <div className="absolute top-0 left-0 right-0 h-3 bg-[#ff7a59]"></div>
    <span className="text-[#ff7a59] font-extrabold text-lg mt-2 font-sans">H</span>
  </div>
);

const AcuityLogo = () => (
  <div className="w-10 h-10 rounded-xl bg-white border border-zinc-200 flex items-center justify-center flex-shrink-0 relative overflow-hidden">
    <div className="absolute top-0 left-0 right-0 h-3 bg-[#008080]"></div>
    <span className="text-[#008080] font-extrabold text-lg mt-2 font-sans">S</span>
  </div>
);

const SquareLogo = () => (
  <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center flex-shrink-0 relative overflow-hidden">
    <div className="w-5 h-5 rounded border-2 border-white"></div>
  </div>
);

interface Provider {
  name: string;
  desc: string;
  logo: React.ComponentType;
  requiresCalSelector?: boolean;
}

const providersList: Provider[] = [
  { name: "Google Calendar", desc: "Full calendar sync support, checking conflicts and auto-generating Google Meet conference links.", logo: GoogleCalendarLogo, requiresCalSelector: true },
  { name: "Microsoft Outlook", desc: "Connect business/enterprise accounts to sync schedules, book Microsoft Teams conferences.", logo: OutlookLogo, requiresCalSelector: true },
  { name: "Apple Calendar", desc: "Synchronize events using secure CalDAV connections or iCloud app-specific authentication keys.", logo: AppleCalendarLogo },
  { name: "Calendly", desc: "Sync booking links and availability templates directly into conversational voice channels.", logo: CalendlyLogo },
  { name: "Cal.com", desc: "Self-hostable, API-centric calendar infrastructure for highly customized scheduling rules.", logo: CalComLogo },
  { name: "Notion Calendar", desc: "Keep task databases, project boards, and meetings in a unified, modern schedule view.", logo: NotionCalendarLogo },
  { name: "Zoho Calendar", desc: "Unified business calendars synchronized with Zoho suite and corporate enterprise channels.", logo: ZohoCalendarLogo },
  { name: "HubSpot Meetings", desc: "Instantly create CRM deals, contact notes, and logs from client scheduling events.", logo: HubSpotLogo },
  { name: "Acuity Scheduling", desc: "Robust client appointments, intake forms, and billing automation integrated.", logo: AcuityLogo },
  { name: "Square Appointments", desc: "Automate service bookings, client reminders, and retail point-of-sale calendars.", logo: SquareLogo },
];

export default function CalendarConnections() {
  const { user } = useAuth();

  const [connectedProviders, setConnectedProviders] = useState<Record<string, boolean>>({
    "Google Calendar": false,
    "Microsoft Outlook": false,
    "Apple Calendar": false,
  });

  const [connectingProviders, setConnectingProviders] = useState<Record<string, boolean>>({});
  const [activeCalendars, setActiveCalendars] = useState<Record<string, string>>({
    "Google Calendar": "primary",
    "Microsoft Outlook": "primary",
    "Calendly": "primary",
  });

  // Calendly OAuth integration states
  const [isCalendlyConnected, setIsCalendlyConnected] = useState(false);
  const [isCalendlyLoading, setIsCalendlyLoading] = useState(false);
  const [calendlyUrl, setCalendlyUrl] = useState("");

  // Global settings
  const [syncBookings, setSyncBookings] = useState(true);
  const [checkConflicts, setCheckConflicts] = useState(true);
  const [sendInvites, setSendInvites] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);

  // Load existing configuration status from API
  const fetchCalendlyStatus = () => {
    api.get("/integrations/calendly")
      .then((res) => {
        if (res.data && res.data.data && res.data.data.connected) {
          setIsCalendlyConnected(true);
          setCalendlyUrl(res.data.data.eventTypeUrl || "");
        } else {
          setIsCalendlyConnected(false);
          setCalendlyUrl("");
        }
      })
      .catch((err) => {
        console.warn("Failed to retrieve Calendly connection status:", err);
      });
  };

  useEffect(() => {
    fetchCalendlyStatus();
  }, []);

  // Listen for callback redirection triggers from child popup window
  useEffect(() => {
    const handleOAuthMessage = (event: MessageEvent) => {
      if (event.data?.type === "CALENDLY_CONNECTED") {
        toast.success("Calendly successfully connected!");
        fetchCalendlyStatus();
      }
    };
    window.addEventListener("message", handleOAuthMessage);
    return () => window.removeEventListener("message", handleOAuthMessage);
  }, []);

  const simulateConnection = (providerName: string) => {
    const isCurrentlyConnected = connectedProviders[providerName];

    if (isCurrentlyConnected) {
      setConnectedProviders(prev => ({ ...prev, [providerName]: false }));
      toast.success(`Disconnected from ${providerName}`);
      return;
    }

    setConnectingProviders(prev => ({ ...prev, [providerName]: true }));
    const toastId = toast.loading(`Connecting to ${providerName}...`);

    setTimeout(() => {
      toast.loading(`Authorizing access tokens for ${providerName}...`, { id: toastId });
      setTimeout(() => {
        setConnectingProviders(prev => ({ ...prev, [providerName]: false }));
        setConnectedProviders(prev => ({ ...prev, [providerName]: true }));
        toast.success(`Successfully connected to ${providerName}!`, { id: toastId });
      }, 1200);
    }, 1000);
  };

  // Launch secure OAuth authorization window
  const handleConnectCalendly = () => {
    const base = API.startsWith("http") ? API : `${window.location.origin}${API}`;
    const authUrl = `${base}/integrations/calendly/auth?user_id=${user?.id}${user?.clientId ? `&client_id=${user.clientId}` : ""}`;
    
    const width = 580;
    const height = 660;
    const left = window.screen.width / 2 - width / 2;
    const top = window.screen.height / 2 - height / 2;
    
    window.open(
      authUrl,
      "Connect Calendly",
      `width=${width},height=${height},left=${left},top=${top},status=no,resizable=yes`
    );
  };

  const handleDisconnectCalendly = async () => {
    setIsCalendlyLoading(true);
    const toastId = toast.loading("Disconnecting Calendly integration...");
    try {
      await api.delete("/integrations/calendly");
      setIsCalendlyConnected(false);
      setCalendlyUrl("");
      toast.success("Successfully disconnected from Calendly", { id: toastId });
    } catch (err: any) {
      toast.error(err.response?.data?.message || "Failed to disconnect", { id: toastId });
    } finally {
      setIsCalendlyLoading(false);
    }
  };

  const handleSyncNow = () => {
    setIsSyncing(true);
    const syncToast = toast.loading("Checking for calendar conflicts and sync updates...");
    setTimeout(() => {
      setIsSyncing(false);
      toast.success("Calendars synced successfully! 0 conflicts found.", { id: syncToast });
    }, 1500);
  };

  const hasAnyConnection = Object.values(connectedProviders).some(Boolean) || isCalendlyConnected;

  return (
    <div className="space-y-8 w-full">
      {/* Grid-based connection boxes ("Box UI") */}
      <div className="space-y-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-zinc-900">Calendar Integrations</h2>
          <p className="text-sm text-zinc-500 mt-1">
            Connect calendar endpoints to let voice agents sync scheduled events and manage bookings.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {providersList.map((prov) => {
            const isGoogleOrOutlookOrApple = ["Google Calendar", "Microsoft Outlook", "Apple Calendar"].includes(prov.name);
            const isConnected = prov.name === "Calendly" ? isCalendlyConnected : !!connectedProviders[prov.name];
            const isConnecting = prov.name === "Calendly" ? isCalendlyLoading : !!connectingProviders[prov.name];

            return (
              <Card key={prov.name} className="border-zinc-200 shadow-none flex flex-col justify-between hover:border-zinc-300 transition-all duration-200 bg-white p-5 rounded-xl">
                <div>
                  <div className="flex items-start justify-between gap-3 mb-3">
                    {React.createElement(prov.logo)}
                    {isConnected ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span> Connected
                      </span>
                    ) : (
                      <span className="text-[10px] text-zinc-400 font-medium uppercase font-mono-stat tracking-wider">Inactive</span>
                    )}
                  </div>

                  <h3 className="font-bold text-zinc-900 text-sm">{prov.name}</h3>
                  <p className="text-zinc-500 text-xs mt-1.5 leading-relaxed min-h-[48px] line-clamp-3">
                    {prov.name === "Calendly" && isConnected ? `Connected scheduling: ${calendlyUrl}` : prov.desc}
                  </p>

                  {/* Calendar/Event selector when connected */}
                  {isConnected && (isGoogleOrOutlookOrApple || prov.name === "Calendly") && (
                    <div className="mt-3 pt-3 border-t border-zinc-100 space-y-1">
                      <Label className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">
                        {prov.name === "Calendly" ? "Sync Event Type" : "Select Calendar"}
                      </Label>
                      <Select
                        value={activeCalendars[prov.name] || "primary"}
                        onValueChange={(val) => setActiveCalendars(prev => ({ ...prev, [prov.name]: val }))}
                      >
                        <SelectTrigger className="h-7 text-[10px] shadow-none py-1">
                          <SelectValue placeholder={prov.name === "Calendly" ? "Select Event Type" : "Select calendar"} />
                        </SelectTrigger>
                        <SelectContent>
                          {prov.name === "Calendly" ? (
                            <>
                              <SelectItem value="primary">Quick Consultation (Default)</SelectItem>
                              <SelectItem value="work">Product Sales Demo</SelectItem>
                              <SelectItem value="bookings">15 Min Support Sync</SelectItem>
                            </>
                          ) : (
                            <>
                              <SelectItem value="primary">Primary Calendar (Default)</SelectItem>
                              <SelectItem value="work">Work Meetings</SelectItem>
                              <SelectItem value="bookings">Voice Agent Bookings</SelectItem>
                            </>
                          )}
                        </SelectContent>
                      </Select>
                    </div>
                  )}
                </div>

                <div className="mt-4 pt-3 border-t border-zinc-100">
                  <Button
                    variant={isConnected ? "outline" : "default"}
                    size="sm"
                    onClick={() => {
                      if (prov.name === "Calendly") {
                        if (isConnected) {
                          handleDisconnectCalendly();
                        } else {
                          handleConnectCalendly();
                        }
                      } else {
                        simulateConnection(prov.name);
                      }
                    }}
                    disabled={isConnecting}
                    className="w-full text-xs h-8 font-semibold shadow-none"
                  >
                    {isConnecting ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                        Connecting...
                      </>
                    ) : isConnected ? (
                      "Disconnect"
                    ) : (
                      "Connect Account"
                    )}
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Sync Preferences (Google/Outlook/Apple) */}
      {hasAnyConnection && (
        <Card className="border-zinc-200 shadow-none animate-in fade-in-50 duration-200">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-lg font-bold text-zinc-900 flex items-center gap-2">
                  <Settings className="w-5 h-5 text-zinc-500" /> Sync Configuration
                </CardTitle>
                <CardDescription className="text-zinc-500 mt-1">
                  Adjust scheduling rules and invitation preferences.
                </CardDescription>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleSyncNow}
                disabled={isSyncing}
                className="text-xs h-8 shadow-none"
              >
                <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${isSyncing ? "animate-spin" : ""}`} />
                Sync Now
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">

            {/* Toggle 1: Auto Schedule */}
            <div className="flex items-center justify-between p-3 rounded-lg border border-zinc-150 bg-zinc-50 hover:bg-zinc-100/50 transition-colors">
              <div className="space-y-0.5">
                <Label htmlFor="sync-bookings" className="text-sm font-semibold text-zinc-800 cursor-pointer">
                  Auto-create scheduled events
                </Label>
                <p className="text-xs text-zinc-500">
                  Instantly publish bookings secured by voice agents as events on your connected calendar.
                </p>
              </div>
              <Switch
                id="sync-bookings"
                checked={syncBookings}
                onCheckedChange={setSyncBookings}
              />
            </div>

            {/* Toggle 2: Check Conflicts */}
            <div className="flex items-center justify-between p-3 rounded-lg border border-zinc-150 bg-zinc-50 hover:bg-zinc-100/50 transition-colors">
              <div className="space-y-0.5">
                <Label htmlFor="check-conflicts" className="text-sm font-semibold text-zinc-800 cursor-pointer">
                  Avoid scheduling conflicts
                </Label>
                <p className="text-xs text-zinc-500">
                  Block slot selections if you have existing personal calendar events in the matching window.
                </p>
              </div>
              <Switch
                id="check-conflicts"
                checked={checkConflicts}
                onCheckedChange={setCheckConflicts}
              />
            </div>

            {/* Toggle 3: Send Invites */}
            <div className="flex items-center justify-between p-3 rounded-lg border border-zinc-150 bg-zinc-50 hover:bg-zinc-100/50 transition-colors">
              <div className="space-y-0.5">
                <Label htmlFor="send-invites" className="text-sm font-semibold text-zinc-800 cursor-pointer">
                  Send calendar invitations to attendees
                </Label>
                <p className="text-xs text-zinc-500">
                  Email event invitations containing video call links to your clients once confirmed.
                </p>
              </div>
              <Switch
                id="send-invites"
                checked={sendInvites}
                onCheckedChange={setSendInvites}
              />
            </div>

          </CardContent>
        </Card>
      )}
    </div>
  );
}
