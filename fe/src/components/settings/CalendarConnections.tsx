import React, { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { CheckCircle2, RefreshCw, Settings, Loader2 } from "lucide-react";

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

interface ComparisonRow {
  provider: string;
  availability: "supported" | "warning" | string;
  create: "supported" | "warning" | string;
  update: "supported" | "warning" | string;
  delete: "supported" | "warning" | string;
  notes: string;
}

const comparisonData: ComparisonRow[] = [
  { provider: "Google Calendar", availability: "supported", create: "supported", update: "supported", delete: "supported", notes: "Full API support" },
  { provider: "Microsoft Outlook", availability: "supported", create: "supported", update: "supported", delete: "supported", notes: "Microsoft Graph API" },
  { provider: "Apple Calendar", availability: "supported", create: "supported", update: "supported", delete: "supported", notes: "Via CalDAV/iCloud" },
  { provider: "Calendly", availability: "warning", create: "Booking based", update: "Limited", delete: "Limited", notes: "Focus on scheduling workflows" },
  { provider: "Cal.com", availability: "supported", create: "supported", update: "supported", delete: "supported", notes: "Excellent APIs, self-host option" },
  { provider: "Notion Calendar", availability: "warning", create: "Mostly via Google sync", update: "Limited", delete: "Limited", notes: "Standalone API is limited" },
  { provider: "Zoho Calendar", availability: "supported", create: "supported", update: "supported", delete: "supported", notes: "Zoho APIs" },
  { provider: "HubSpot Meetings", availability: "warning", create: "Booking workflow", update: "Limited", delete: "Limited", notes: "CRM-centric" },
  { provider: "Acuity Scheduling", availability: "supported", create: "supported", update: "supported", delete: "supported", notes: "Scheduling APIs" },
  { provider: "Square Appointments", availability: "supported", create: "supported", update: "supported", delete: "supported", notes: "Business appointments" },
];

export default function CalendarConnections() {
  const [connectedProviders, setConnectedProviders] = useState<Record<string, boolean>>({
    "Google Calendar": false,
    "Microsoft Outlook": false,
    "Apple Calendar": false,
  });

  const [connectingProviders, setConnectingProviders] = useState<Record<string, boolean>>({});
  const [activeCalendars, setActiveCalendars] = useState<Record<string, string>>({
    "Google Calendar": "primary",
    "Microsoft Outlook": "primary",
  });

  // Global settings
  const [syncBookings, setSyncBookings] = useState(true);
  const [checkConflicts, setCheckConflicts] = useState(true);
  const [sendInvites, setSendInvites] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);

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

  const handleSyncNow = () => {
    setIsSyncing(true);
    const syncToast = toast.loading("Checking for calendar conflicts and sync updates...");
    setTimeout(() => {
      setIsSyncing(false);
      toast.success("Calendars synced successfully! 0 conflicts found.", { id: syncToast });
    }, 1500);
  };

  // Render checkbox checkmark or warning box
  const renderStatusItem = (val: string) => {
    if (val === "supported") {
      return (
        <div className="w-5 h-5 rounded bg-emerald-600 flex items-center justify-center text-white">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="3.5" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </div>
      );
    }
    if (val === "warning") {
      return (
        <div className="w-5 h-5 flex items-center justify-center text-amber-500">
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
        </div>
      );
    }
    return <span className="text-zinc-600 font-medium text-xs font-mono-stat">{val}</span>;
  };

  const hasAnyConnection = Object.values(connectedProviders).some(Boolean);

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
            const isConnected = !!connectedProviders[prov.name];
            const isConnecting = !!connectingProviders[prov.name];
            
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
                    {prov.desc}
                  </p>

                  {/* If connected and requires calendar selection */}
                  {isConnected && prov.requiresCalSelector && (
                    <div className="mt-3 pt-3 border-t border-zinc-100 space-y-1">
                      <Label className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">Select Calendar</Label>
                      <Select 
                        value={activeCalendars[prov.name] || "primary"} 
                        onValueChange={(val) => setActiveCalendars(prev => ({...prev, [prov.name]: val}))}
                      >
                        <SelectTrigger className="h-7 text-[10px] shadow-none py-1">
                          <SelectValue placeholder="Select calendar" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="primary">Primary Calendar (Default)</SelectItem>
                          <SelectItem value="work">Work Meetings</SelectItem>
                          <SelectItem value="bookings">Voice Agent Bookings</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  )}
                </div>

                <div className="mt-4 pt-3 border-t border-zinc-100">
                  <Button
                    variant={isConnected ? "outline" : "default"}
                    size="sm"
                    onClick={() => simulateConnection(prov.name)}
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
