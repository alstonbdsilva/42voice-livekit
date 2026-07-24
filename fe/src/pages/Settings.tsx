import React from "react";
import PageHeader from "@/components/PageHeader";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import ProfileSettings from "@/components/settings/ProfileSettings";
import CalendarConnections from "@/components/settings/CalendarConnections";
import { User, Calendar, Mail, MessageCircle, Sparkles, ShieldCheck } from "lucide-react";

export default function Settings() {
  return (
    <div data-testid="settings-page" className="w-full space-y-6">
      <PageHeader 
        title="Settings" 
        subtitle="Manage your profile settings, active calendar integrations, and messaging gateways." 
      />
      
      <Tabs defaultValue="profile" className="w-full">
        <TabsList className="grid w-full grid-cols-4 max-w-[780px] mb-6">
          <TabsTrigger 
            value="profile" 
            className="flex items-center justify-center gap-2 border border-transparent data-[state=active]:border-zinc-200 shadow-none data-[state=active]:shadow-none"
          >
            <User className="w-4 h-4" />
            Profile
          </TabsTrigger>
          <TabsTrigger 
            value="calendar" 
            className="flex items-center justify-center gap-2 border border-transparent data-[state=active]:border-zinc-200 shadow-none data-[state=active]:shadow-none"
          >
            <Calendar className="w-4 h-4" />
            Calendar Connections
          </TabsTrigger>
          <TabsTrigger 
            value="smtp" 
            className="flex items-center justify-center gap-2 border border-transparent data-[state=active]:border-zinc-200 shadow-none data-[state=active]:shadow-none"
          >
            <Mail className="w-4 h-4" />
            <span>SMTP</span>
            <span className="text-[9px] font-bold bg-zinc-100 text-zinc-500 px-1 py-0.2 rounded-xs uppercase tracking-wide">Soon</span>
          </TabsTrigger>
          <TabsTrigger 
            value="whatsapp" 
            className="flex items-center justify-center gap-2 border border-transparent data-[state=active]:border-zinc-200 shadow-none data-[state=active]:shadow-none"
          >
            <MessageCircle className="w-4 h-4" />
            <span>WhatsApp</span>
            <span className="text-[9px] font-bold bg-zinc-100 text-zinc-500 px-1 py-0.2 rounded-xs uppercase tracking-wide">Soon</span>
          </TabsTrigger>
        </TabsList>
        
        <TabsContent value="profile" className="outline-none">
          <ProfileSettings />
        </TabsContent>
        
        <TabsContent value="calendar" className="outline-none">
          <CalendarConnections />
        </TabsContent>

        {/* SMTP Configuration Tab */}
        <TabsContent value="smtp" className="outline-none">
          <div className="bg-white border border-zinc-200 rounded-sm p-6 relative overflow-hidden">
            {/* Blurry coming soon overlay */}
            <div className="absolute inset-0 bg-white/40 backdrop-blur-[2px] z-10 flex flex-col items-center justify-center p-6 text-center select-none">
              <div className="bg-white border border-zinc-250 p-6 shadow-xl rounded-sm max-w-sm flex flex-col items-center gap-3">
                <div className="w-10 h-10 bg-indigo-50 text-indigo-600 flex items-center justify-center rounded-full">
                  <Sparkles className="w-5 h-5 animate-pulse" />
                </div>
                <h4 className="font-bold text-sm text-zinc-950">Email Gateway Integration</h4>
                <p className="text-xs text-zinc-500 leading-relaxed">
                  Configure SMTP relays to trigger agent action alerts, forward summaries, and send system emails from your domain.
                </p>
                <span className="inline-flex px-2 py-0.5 bg-zinc-950 text-white text-[10px] font-bold uppercase tracking-wider rounded-xs">
                  Coming Soon
                </span>
              </div>
            </div>

            {/* Mocked disabled form content for visual richness */}
            <div className="space-y-6 opacity-40">
              <div className="border-b border-zinc-200 pb-3">
                <h3 className="font-bold text-base text-zinc-900">SMTP Settings</h3>
                <p className="text-xs text-zinc-500">Configure outbound email relay parameters</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-zinc-600 uppercase">SMTP Hostname</label>
                  <input disabled type="text" placeholder="smtp.mailgun.org" className="w-full bg-zinc-50 border border-zinc-200 px-3 py-2 text-sm rounded-sm" />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-zinc-600 uppercase">SMTP Port</label>
                  <input disabled type="text" placeholder="587" className="w-full bg-zinc-50 border border-zinc-200 px-3 py-2 text-sm rounded-sm" />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-zinc-600 uppercase">SMTP Username</label>
                  <input disabled type="text" placeholder="postmaster@yourdomain.com" className="w-full bg-zinc-50 border border-zinc-200 px-3 py-2 text-sm rounded-sm" />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-zinc-600 uppercase">SMTP Password</label>
                  <input disabled type="password" value="••••••••••••" className="w-full bg-zinc-50 border border-zinc-200 px-3 py-2 text-sm rounded-sm" />
                </div>
              </div>
            </div>
          </div>
        </TabsContent>

        {/* WhatsApp Configuration Tab */}
        <TabsContent value="whatsapp" className="outline-none">
          <div className="bg-white border border-zinc-200 rounded-sm p-6 relative overflow-hidden">
            {/* Blurry coming soon overlay */}
            <div className="absolute inset-0 bg-white/40 backdrop-blur-[2px] z-10 flex flex-col items-center justify-center p-6 text-center select-none">
              <div className="bg-white border border-zinc-250 p-6 shadow-xl rounded-sm max-w-sm flex flex-col items-center gap-3">
                <div className="w-10 h-10 bg-emerald-50 text-emerald-600 flex items-center justify-center rounded-full">
                  <MessageCircle className="w-5 h-5 animate-pulse" />
                </div>
                <h4 className="font-bold text-sm text-zinc-950">WhatsApp API Integration</h4>
                <p className="text-xs text-zinc-500 leading-relaxed">
                  Manage WhatsApp Cloud API connection details to power automated messaging templates, conversational AI, and SMS failover routing.
                </p>
                <span className="inline-flex px-2 py-0.5 bg-zinc-950 text-white text-[10px] font-bold uppercase tracking-wider rounded-xs">
                  Coming Soon
                </span>
              </div>
            </div>

            {/* Mocked disabled form content for visual richness */}
            <div className="space-y-6 opacity-40">
              <div className="border-b border-zinc-200 pb-3">
                <h3 className="font-bold text-base text-zinc-900">WhatsApp Business API</h3>
                <p className="text-xs text-zinc-500">Configure access tokens and IDs from Meta Developer Console</p>
              </div>

              <div className="space-y-4">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-zinc-600 uppercase">System User Access Token</label>
                  <input disabled type="password" value="EAAGxxxxxxxxxxxxxxxxxxxxxxxxxx" className="w-full bg-zinc-50 border border-zinc-200 px-3 py-2 text-sm rounded-sm font-mono" />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-zinc-600 uppercase">WhatsApp Business Account ID</label>
                    <input disabled type="text" placeholder="1058392194812" className="w-full bg-zinc-50 border border-zinc-200 px-3 py-2 text-sm rounded-sm" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-zinc-600 uppercase">Phone Number ID</label>
                    <input disabled type="text" placeholder="2094857201948" className="w-full bg-zinc-50 border border-zinc-200 px-3 py-2 text-sm rounded-sm" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

