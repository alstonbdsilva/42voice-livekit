import React, { useState, useRef } from "react";
import { useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowLeft,
  UploadCloud,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  ChevronDown,
  ChevronUp
} from "lucide-react";
import PageHeader from "@/components/PageHeader";
import { useCampaignStore } from "@/store/campaignStore";

export default function CreateCampaign() {
  const navigate = useNavigate();
  const addCampaign = useCampaignStore((state) => state.addCampaign);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Form State
  const [name, setName] = useState("");
  const [workflow, setWorkflow] = useState("");
  const [telephonyConfig, setTelephonyConfig] = useState("");
  const [dataSourceType, setDataSourceType] = useState("CSV File");
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);

  // Advanced Settings Collapsible Accordion (Collapsed by default!)
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);

  // Advanced Fields
  const [maxConcurrentCalls, setMaxConcurrentCalls] = useState("10");

  // Enable Retries
  const [enableRetries, setEnableRetries] = useState(true);
  const [maxRetries, setMaxRetries] = useState("1");
  const [retryDelay, setRetryDelay] = useState("120");
  const [retryOnBusy, setRetryOnBusy] = useState(true);
  const [retryOnNoAnswer, setRetryOnNoAnswer] = useState(true);
  const [retryOnVoicemail, setRetryOnVoicemail] = useState(false);

  // Call Schedule
  const [callSchedule, setCallSchedule] = useState(false);
  const [scheduleStart, setScheduleStart] = useState("09:00");
  const [scheduleEnd, setScheduleEnd] = useState("18:00");

  // Circuit Breaker
  const [circuitBreaker, setCircuitBreaker] = useState(false);
  const [failureThreshold, setFailureThreshold] = useState("50");
  const [windowSeconds, setWindowSeconds] = useState("120");
  const [minCallsInWindow, setMinCallsInWindow] = useState("5");

  // Submit Handler
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      toast.error("Please enter a valid campaign name.");
      return;
    }

    const newCampaign = addCampaign({
      name: name.trim(),
      description: workflow ? `Workflow: ${workflow}` : "Custom voice workflow campaign",
      agent: workflow || "Sarah - Enterprise SDR",
      channel: "voice",
      status: "active",
      totalLeads: uploadedFileName ? 250 : 100,
      answerRate: 0,
      conversionRate: 0,
      callerId: telephonyConfig || "+1 (800) 420-9182",
      schedule: callSchedule ? `${scheduleStart} - ${scheduleEnd} EST` : "Immediate execution",
      concurrencyLimit: parseInt(maxConcurrentCalls) || 10,
      maxRetries: enableRetries ? parseInt(maxRetries) || 1 : 0,
    });

    toast.success(`Campaign '${newCampaign.name}' created successfully!`);
    navigate("/campaigns");
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setUploadedFileName(file.name);
      toast.success(`Uploaded CSV file: ${file.name}`);
    }
  };

  return (
    <div className="space-y-6 w-full pb-12" data-testid="create-campaign-page">

      {/* Back Navigation Link at Far Left Edge */}
      <div>
        <Link
          to="/campaigns"
          className="inline-flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-950 font-medium transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Campaigns</span>
        </Link>
      </div>

      {/* Centered Main Content Wrapper */}
      <div className="max-w-3xl mx-auto space-y-6">
        <PageHeader
          title="Create New Campaign"
          subtitle="Set up a new campaign to execute workflows at scale"
        />

        {/* Form Card */}
        <form onSubmit={handleSubmit} className="bg-white border border-zinc-200 rounded-sm p-6 md:p-8 space-y-6 shadow-xs">

          {/* SECTION 1: CAMPAIGN DETAILS */}
          <div className="space-y-5">
            <div className="border-b border-zinc-200 pb-3">
              <h2 className="text-base font-bold text-zinc-950">Campaign Details</h2>
              <p className="text-xs text-zinc-500">Configure your core campaign settings and data source</p>
            </div>

            {/* Campaign Name */}
            <div className="space-y-1.5">
              <label className="block text-xs font-bold uppercase tracking-wider text-zinc-700">
                Campaign Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                required
                placeholder="Enter campaign name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-3.5 py-2 text-xs text-zinc-900 focus:outline-none focus:border-zinc-950 focus:bg-white font-medium transition-colors"
              />
              <p className="text-[11px] text-zinc-500">Choose a descriptive name for your campaign</p>
            </div>

            {/* Workflow */}
            <div className="space-y-1.5">
              <label className="block text-xs font-bold uppercase tracking-wider text-zinc-700">
                Workflow
              </label>
              <select
                value={workflow}
                onChange={(e) => setWorkflow(e.target.value)}
                className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-3 py-2 text-xs text-zinc-900 focus:outline-none focus:border-zinc-950 focus:bg-white font-medium cursor-pointer"
              >
                <option value="">Select a workflow</option>
                <option value="Outbound Sales Outreach Agent">Outbound Sales Outreach Agent</option>
                <option value="Customer Feedback Router">Customer Feedback Router</option>
                <option value="Renewal Retention Assistant">Renewal Retention Assistant</option>
                <option value="Event RSVP Qualification Agent">Event RSVP Qualification Agent</option>
              </select>
              <p className="text-[11px] text-zinc-500">Select the workflow to execute for each row in the data source</p>
            </div>

            {/* Telephony Configuration */}
            <div className="space-y-1.5">
              <label className="block text-xs font-bold uppercase tracking-wider text-zinc-700">
                Telephony Configuration
              </label>
              <select
                value={telephonyConfig}
                onChange={(e) => setTelephonyConfig(e.target.value)}
                className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-3 py-2 text-xs text-zinc-900 focus:outline-none focus:border-zinc-950 focus:bg-white font-medium cursor-pointer"
              >
                <option value="">Select a telephony configuration</option>
                <option value="+1 (800) 420-9182 (US Toll-Free Main)">+1 (800) 420-9182 (US Toll-Free Main)</option>
                <option value="+1 (888) 332-9011 (Survey & Feedback Line)">+1 (888) 332-9011 (Survey & Feedback Line)</option>
                <option value="+1 (415) 902-1144 (San Francisco Local CLI)">+1 (415) 902-1144 (San Francisco Local CLI)</option>
              </select>
              <p className="text-[11px] text-zinc-500">Outbound calls for this campaign will use this configuration's caller IDs</p>
            </div>

            {/* Data Source Type */}
            <div className="space-y-1.5">
              <label className="block text-xs font-bold uppercase tracking-wider text-zinc-700">
                Data Source Type
              </label>
              <select
                value={dataSourceType}
                onChange={(e) => setDataSourceType(e.target.value)}
                className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-3 py-2 text-xs text-zinc-900 focus:outline-none focus:border-zinc-950 focus:bg-white font-medium cursor-pointer"
              >
                <option value="CSV File">CSV File</option>
                <option value="API Webhook Payload">API Webhook Payload</option>
                <option value="Database Lead Sync">Database Lead Sync</option>
              </select>
              <p className="text-[11px] text-zinc-500">Choose where your contact data is stored</p>
            </div>

            {/* CSV File Upload */}
            <div className="space-y-2">
              <label className="block text-xs font-bold uppercase tracking-wider text-zinc-700">
                CSV File
              </label>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="px-4 py-2 border border-zinc-200 bg-white hover:bg-zinc-50 text-zinc-800 font-semibold text-xs rounded-sm transition-colors flex items-center gap-2 shadow-xs"
                >
                  <UploadCloud className="w-4 h-4 text-zinc-500" />
                  <span>Upload CSV File</span>
                </button>
                <input ref={fileInputRef} type="file" accept=".csv" onChange={handleFileUpload} className="hidden" />
                {uploadedFileName && (
                  <span className="text-xs text-emerald-700 font-semibold flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    {uploadedFileName}
                  </span>
                )}
              </div>
              <p className="text-[11px] text-zinc-500 leading-relaxed">
                Upload a CSV file with contact data. Must include <code className="text-zinc-900 font-mono font-semibold bg-zinc-100 px-1.5 py-0.5 rounded">phone_number</code> column. The columns can be accessed as <code className="text-zinc-900 font-mono font-semibold bg-zinc-100 px-1.5 py-0.5 rounded">initial_context</code> in the workflow nodes. Max 10MB.
              </p>
            </div>
          </div>

          {/* SECTION 2: ADVANCED SETTINGS (COLLAPSED BY DEFAULT) */}
          <div className="border border-zinc-200 rounded-sm overflow-hidden bg-zinc-50/50">
            <button
              type="button"
              onClick={() => setIsAdvancedOpen(!isAdvancedOpen)}
              className="w-full px-4 py-3 bg-zinc-100/70 flex justify-between items-center text-xs font-bold text-zinc-950 hover:bg-zinc-100 transition-colors"
            >
              <span>Advanced Settings</span>
              {isAdvancedOpen ? (
                <ChevronUp className="w-4 h-4 text-zinc-500" />
              ) : (
                <ChevronDown className="w-4 h-4 text-zinc-500" />
              )}
            </button>

            {isAdvancedOpen && (
              <div className="p-5 space-y-6 border-t border-zinc-200 bg-white animate-in fade-in duration-150">

                {/* Max Concurrent Calls */}
                <div className="space-y-1.5">
                  <label className="block text-xs font-bold uppercase tracking-wider text-zinc-700">
                    Max Concurrent Calls
                  </label>
                  <input
                    type="number"
                    placeholder="Default: 10"
                    value={maxConcurrentCalls}
                    onChange={(e) => setMaxConcurrentCalls(e.target.value)}
                    className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-3.5 py-2 text-xs text-zinc-900 focus:outline-none focus:border-zinc-950 font-mono"
                  />
                  <p className="text-[11px] text-zinc-500">Maximum number of simultaneous calls. Leave empty to use 10.</p>

                  {/* Warning Alert Note */}
                  <div className="p-3 bg-amber-50 border border-amber-200 rounded-sm flex items-start gap-2 text-xs text-amber-900 mt-2">
                    <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                    <div className="text-[11px] text-amber-800 leading-normal">
                      No phone numbers configured. Add CLIs in <span className="font-bold underline cursor-pointer hover:text-amber-950">Telephony Configuration</span> before running the campaign.
                    </div>
                  </div>
                </div>

                {/* Enable Retries */}
                <div className="space-y-3 pt-3 border-t border-zinc-100">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs font-bold text-zinc-950">Enable Retries</div>
                      <div className="text-[11px] text-zinc-500">Automatically retry failed calls</div>
                    </div>
                    <input
                      type="checkbox"
                      checked={enableRetries}
                      onChange={(e) => setEnableRetries(e.target.checked)}
                      className="rounded-sm border-zinc-300 text-zinc-950 focus:ring-zinc-950 w-4 h-4 cursor-pointer"
                    />
                  </div>

                  {enableRetries && (
                    <div className="space-y-4 pt-2 bg-zinc-50/50 p-4 border border-zinc-200/80 rounded-sm animate-in fade-in duration-150">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <label className="block text-[11px] font-semibold text-zinc-700 mb-1">Max Retries</label>
                          <input
                            type="number"
                            value={maxRetries}
                            onChange={(e) => setMaxRetries(e.target.value)}
                            className="w-full bg-white border border-zinc-200 rounded-sm px-3 py-1.5 text-xs text-zinc-900 focus:outline-none focus:border-zinc-950"
                          />
                        </div>
                        <div>
                          <label className="block text-[11px] font-semibold text-zinc-700 mb-1">Retry Delay (seconds)</label>
                          <input
                            type="number"
                            value={retryDelay}
                            onChange={(e) => setRetryDelay(e.target.value)}
                            className="w-full bg-white border border-zinc-200 rounded-sm px-3 py-1.5 text-xs text-zinc-900 focus:outline-none focus:border-zinc-950"
                          />
                        </div>
                      </div>

                      <div className="space-y-2 pt-1">
                        <label className="block text-[11px] font-semibold text-zinc-700">Retry On</label>
                        <div className="space-y-2">
                          {[
                            { label: "Busy Signal", state: retryOnBusy, setter: setRetryOnBusy },
                            { label: "No Answer", state: retryOnNoAnswer, setter: setRetryOnNoAnswer },
                            { label: "Voicemail", state: retryOnVoicemail, setter: setRetryOnVoicemail },
                          ].map((item) => (
                            <div key={item.label} className="flex items-center justify-between py-1 bg-white px-3 border border-zinc-200/60 rounded-sm">
                              <span className="text-xs text-zinc-700 font-medium">{item.label}</span>
                              <input
                                type="checkbox"
                                checked={item.state}
                                onChange={(e) => item.setter(e.target.checked)}
                                className="rounded-sm border-zinc-300 text-zinc-950 focus:ring-zinc-950 w-3.5 h-3.5 cursor-pointer"
                              />
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Call Schedule */}
                <div className="pt-3 border-t border-zinc-100 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs font-bold text-zinc-950">Call Schedule</div>
                      <div className="text-[11px] text-zinc-500">Restrict when calls are made</div>
                    </div>
                    <input
                      type="checkbox"
                      checked={callSchedule}
                      onChange={(e) => setCallSchedule(e.target.checked)}
                      className="rounded-sm border-zinc-300 text-zinc-950 focus:ring-zinc-950 w-4 h-4 cursor-pointer"
                    />
                  </div>

                  {callSchedule && (
                    <div className="grid grid-cols-2 gap-3 p-4 bg-zinc-50/50 border border-zinc-200/80 rounded-sm">
                      <div>
                        <label className="block text-[11px] font-semibold text-zinc-700 mb-1">Window Start Time</label>
                        <input
                          type="time"
                          value={scheduleStart}
                          onChange={(e) => setScheduleStart(e.target.value)}
                          className="w-full bg-white border border-zinc-200 rounded-sm px-3 py-1.5 text-xs text-zinc-900 focus:outline-none focus:border-zinc-950 font-mono"
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] font-semibold text-zinc-700 mb-1">Window End Time</label>
                        <input
                          type="time"
                          value={scheduleEnd}
                          onChange={(e) => setScheduleEnd(e.target.value)}
                          className="w-full bg-white border border-zinc-200 rounded-sm px-3 py-1.5 text-xs text-zinc-900 focus:outline-none focus:border-zinc-950 font-mono"
                        />
                      </div>
                    </div>
                  )}
                </div>

                {/* Circuit Breaker */}
                <div className="pt-3 border-t border-zinc-100 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs font-bold text-zinc-950">Circuit Breaker</div>
                      <div className="text-[11px] text-zinc-500">Auto-pause campaign on high failure rates</div>
                    </div>
                    <input
                      type="checkbox"
                      checked={circuitBreaker}
                      onChange={(e) => setCircuitBreaker(e.target.checked)}
                      className="rounded-sm border-zinc-300 text-zinc-950 focus:ring-zinc-950 w-4 h-4 cursor-pointer"
                    />
                  </div>

                  {circuitBreaker && (
                    <div className="space-y-3 p-4 bg-zinc-50/50 border border-zinc-200/80 rounded-sm">
                      <div>
                        <label className="block text-[11px] font-semibold text-zinc-700 mb-1">Failure Threshold (%)</label>
                        <input
                          type="number"
                          value={failureThreshold}
                          onChange={(e) => setFailureThreshold(e.target.value)}
                          className="w-full bg-white border border-zinc-200 rounded-sm px-3 py-1.5 text-xs text-zinc-900 focus:outline-none focus:border-zinc-950"
                        />
                        <p className="text-[10px] text-zinc-500 mt-1">Pause when failure rate exceeds this percentage</p>
                      </div>

                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="block text-[11px] font-semibold text-zinc-700 mb-1">Window (seconds)</label>
                          <input
                            type="number"
                            value={windowSeconds}
                            onChange={(e) => setWindowSeconds(e.target.value)}
                            className="w-full bg-white border border-zinc-200 rounded-sm px-3 py-1.5 text-xs text-zinc-900 focus:outline-none focus:border-zinc-950"
                          />
                        </div>
                        <div>
                          <label className="block text-[11px] font-semibold text-zinc-700 mb-1">Min Calls in Window</label>
                          <input
                            type="number"
                            value={minCallsInWindow}
                            onChange={(e) => setMinCallsInWindow(e.target.value)}
                            className="w-full bg-white border border-zinc-200 rounded-sm px-3 py-1.5 text-xs text-zinc-900 focus:outline-none focus:border-zinc-950"
                          />
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* SECTION 3: ACTIONS BAR */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-zinc-200">
            <button
              type="button"
              onClick={() => navigate("/campaigns")}
              className="px-4 py-2 border border-zinc-200 bg-white hover:bg-zinc-50 text-zinc-700 font-semibold text-xs rounded-sm transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2 bg-zinc-950 hover:bg-zinc-800 text-white font-semibold text-xs rounded-sm transition-colors shadow-sm flex items-center gap-1.5"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Create Campaign</span>
            </button>
          </div>

        </form>
      </div>
    </div>
  );
}
