import React from "react";
import PageHeader from "@/components/PageHeader";
import { PhoneCall } from "lucide-react";

export default function TelephonyConfigurations() {
  return (
    <div className="space-y-6" data-testid="telephony-configurations-page">
      <PageHeader
        title="Telephony Configurations"
        subtitle="Manage telephony providers, SIP trunks, routing rules, and voice configuration settings."
      />

      <div className="bg-white rounded-lg border border-zinc-200 p-12 text-center shadow-sm">
        <div className="mx-auto w-12 h-12 bg-zinc-100 rounded-full flex items-center justify-center text-zinc-500 mb-4">
          <PhoneCall className="w-6 h-6 text-zinc-700" />
        </div>
        <h3 className="text-lg font-semibold text-zinc-950 mb-1">
          Telephony Configurations
        </h3>
        <p className="text-sm text-zinc-500 max-w-md mx-auto">
          This page is currently empty and ready for custom telephony setup, SIP trunk settings, and provider configurations.
        </p>
      </div>
    </div>
  );
}
