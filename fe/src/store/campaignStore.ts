import { create } from "zustand";

export interface CampaignItem {
  id: string;
  name: string;
  description: string;
  agent: string;
  agentId?: string;
  channel: "voice" | "sms" | "multichannel";
  status: "active" | "paused" | "completed" | "scheduled" | "draft";
  totalLeads: number;
  completedLeads: number;
  callsMade: number;
  answerRate: number; // percentage e.g. 72.4
  conversionRate: number; // percentage e.g. 18.5
  callerId: string;
  schedule: string;
  createdAt: string;
  concurrencyLimit: number;
  maxRetries: number;
}

export interface LeadItem {
  id: string;
  name: string;
  phone: string;
  email?: string;
  company?: string;
  campaignId: string;
  campaignName: string;
  status: "pending" | "calling" | "completed" | "failed" | "voicemail" | "opted_out";
  attempts: number;
  lastCalled?: string;
}

interface CampaignState {
  campaigns: CampaignItem[];
  leads: LeadItem[];
  
  // Campaign Actions
  addCampaign: (campaign: Omit<CampaignItem, "id" | "createdAt" | "callsMade" | "completedLeads">) => CampaignItem;
  updateCampaignStatus: (id: string, status: CampaignItem["status"]) => void;
  deleteCampaign: (id: string) => void;
  
  // Lead Actions
  addLead: (lead: Omit<LeadItem, "id">) => void;
  addBulkLeads: (campaignId: string, campaignName: string, items: { name: string; phone: string; email?: string; company?: string }[]) => void;
  deleteLead: (id: string) => void;
  updateLeadStatus: (id: string, status: LeadItem["status"]) => void;
  triggerCallLead: (id: string) => void;
  triggerCallAllPending: (campaignId: string) => number;
}

const INITIAL_CAMPAIGNS: CampaignItem[] = [
  {
    id: "camp-101",
    name: "Q3 Enterprise Outbound SDR",
    description: "Cold outreach campaign targeting VP of Operations across Mid-Market SaaS accounts.",
    agent: "Sarah - Enterprise SDR",
    channel: "voice",
    status: "active",
    totalLeads: 450,
    completedLeads: 306,
    callsMade: 342,
    answerRate: 74.2,
    conversionRate: 19.8,
    callerId: "+1 (800) 420-9182",
    schedule: "Mon-Fri 9:00 AM - 5:00 PM EST",
    createdAt: "2026-07-28",
    concurrencyLimit: 10,
    maxRetries: 2,
  },
  {
    id: "camp-102",
    name: "Q2 Customer Feedback Survey",
    description: "Automated post-purchase experience survey calls to recent buyers.",
    agent: "Alex - Feedback Specialist",
    channel: "voice",
    status: "active",
    totalLeads: 800,
    completedLeads: 336,
    callsMade: 380,
    answerRate: 64.5,
    conversionRate: 28.0,
    callerId: "+1 (888) 332-9011",
    schedule: "Mon-Sat 10:00 AM - 6:00 PM EST",
    createdAt: "2026-08-01",
    concurrencyLimit: 15,
    maxRetries: 1,
  },
  {
    id: "camp-103",
    name: "Expired Subscription Renewals",
    description: "Urgent outreach to past-due accounts offering custom renewal discount codes.",
    agent: "David - Account Manager",
    channel: "multichannel",
    status: "paused",
    totalLeads: 210,
    completedLeads: 178,
    callsMade: 220,
    answerRate: 81.0,
    conversionRate: 34.2,
    callerId: "+1 (800) 420-9182",
    schedule: "Mon-Fri 9:00 AM - 6:00 PM EST",
    createdAt: "2026-07-15",
    concurrencyLimit: 5,
    maxRetries: 3,
  },
  {
    id: "camp-104",
    name: "Webinar Attendee SMS & Call Follow-Up",
    description: "Instant engagement sequence for post-webinar registered attendees.",
    agent: "Emily - Event Coordinator",
    channel: "sms",
    status: "completed",
    totalLeads: 1200,
    completedLeads: 1200,
    callsMade: 1200,
    answerRate: 91.5,
    conversionRate: 41.0,
    callerId: "+1 (800) 771-0029",
    schedule: "Immediate",
    createdAt: "2026-07-10",
    concurrencyLimit: 25,
    maxRetries: 1,
  },
  {
    id: "camp-105",
    name: "VIP Lead Reactivation Blitz",
    description: "Re-engage cold leads dormant over 90 days with customized promotional offers.",
    agent: "Sarah - Enterprise SDR",
    channel: "voice",
    status: "scheduled",
    totalLeads: 350,
    completedLeads: 0,
    callsMade: 0,
    answerRate: 0,
    conversionRate: 0,
    callerId: "+1 (800) 420-9182",
    schedule: "Starts Aug 10, 2026",
    createdAt: "2026-08-02",
    concurrencyLimit: 8,
    maxRetries: 2,
  },
  {
    id: "camp-106",
    name: "Product Beta Tester Onboarding",
    description: "Draft voice agent sequence to collect initial onboarding feedback.",
    agent: "Alex - Feedback Specialist",
    channel: "voice",
    status: "draft",
    totalLeads: 120,
    completedLeads: 0,
    callsMade: 0,
    answerRate: 0,
    conversionRate: 0,
    callerId: "+1 (888) 332-9011",
    schedule: "Unscheduled Draft",
    createdAt: "2026-08-02",
    concurrencyLimit: 5,
    maxRetries: 1,
  }
];

const INITIAL_LEADS: LeadItem[] = [
  { id: "lead-1", name: "David Miller", phone: "+1 (555) 019-2831", email: "david.m@acme.com", company: "Acme Corp", campaignId: "camp-101", campaignName: "Q3 Enterprise Outbound SDR", status: "completed", attempts: 1, lastCalled: "2026-08-02 14:20" },
  { id: "lead-2", name: "Sarah Jenkins", phone: "+1 (555) 024-9182", email: "s.jenkins@techflow.io", company: "TechFlow", campaignId: "camp-101", campaignName: "Q3 Enterprise Outbound SDR", status: "calling", attempts: 2, lastCalled: "2026-08-02 17:05" },
  { id: "lead-3", name: "Michael Chang", phone: "+1 (555) 081-3921", email: "mchang@nexus.org", company: "Nexus Systems", campaignId: "camp-102", campaignName: "Q2 Customer Feedback Survey", status: "pending", attempts: 0 },
  { id: "lead-4", name: "Elena Rostova", phone: "+1 (555) 074-1290", email: "elena@horizon.co", company: "Horizon AI", campaignId: "camp-103", campaignName: "Expired Subscription Renewals", status: "completed", attempts: 1, lastCalled: "2026-08-01 11:15" },
  { id: "lead-5", name: "Marcus Thompson", phone: "+1 (555) 043-8891", email: "m.thompson@global.com", company: "Global Logistics", campaignId: "camp-102", campaignName: "Q2 Customer Feedback Survey", status: "failed", attempts: 3, lastCalled: "2026-08-02 10:45" },
  { id: "lead-6", name: "Amina Al-Mansoor", phone: "+1 (555) 092-4412", email: "amina@crescent.ae", company: "Crescent Digital", campaignId: "camp-101", campaignName: "Q3 Enterprise Outbound SDR", status: "voicemail", attempts: 1, lastCalled: "2026-08-02 15:30" },
  { id: "lead-7", name: "Gregory Peck", phone: "+1 (555) 031-6677", email: "greg@apex.io", company: "Apex Media", campaignId: "camp-101", campaignName: "Q3 Enterprise Outbound SDR", status: "pending", attempts: 0 }
];

export const useCampaignStore = create<CampaignState>((set, get) => ({
  campaigns: INITIAL_CAMPAIGNS,
  leads: INITIAL_LEADS,

  addCampaign: (campaignData) => {
    const newId = `camp-${Date.now().toString().slice(-4)}`;
    const newCampaign: CampaignItem = {
      ...campaignData,
      id: newId,
      callsMade: 0,
      completedLeads: 0,
      answerRate: 0,
      conversionRate: 0,
      createdAt: new Date().toISOString().split("T")[0],
    };

    set((state) => ({
      campaigns: [newCampaign, ...state.campaigns],
    }));

    return newCampaign;
  },

  updateCampaignStatus: (id, status) => {
    set((state) => ({
      campaigns: state.campaigns.map((c) => (c.id === id ? { ...c, status } : c)),
    }));
  },

  deleteCampaign: (id) => {
    set((state) => ({
      campaigns: state.campaigns.filter((c) => c.id !== id),
      leads: state.leads.filter((l) => l.campaignId !== id),
    }));
  },

  addLead: (leadData) => {
    const newLead: LeadItem = {
      ...leadData,
      id: `lead-${Date.now()}`,
    };
    set((state) => ({
      leads: [newLead, ...state.leads],
      campaigns: state.campaigns.map((c) =>
        c.id === leadData.campaignId ? { ...c, totalLeads: c.totalLeads + 1 } : c
      ),
    }));
  },

  addBulkLeads: (campaignId, campaignName, items) => {
    const newLeads: LeadItem[] = items.map((item, idx) => ({
      id: `lead-bulk-${Date.now()}-${idx}`,
      name: item.name,
      phone: item.phone,
      email: item.email,
      company: item.company,
      campaignId,
      campaignName,
      status: "pending",
      attempts: 0,
    }));

    set((state) => ({
      leads: [...newLeads, ...state.leads],
      campaigns: state.campaigns.map((c) =>
        c.id === campaignId ? { ...c, totalLeads: c.totalLeads + newLeads.length } : c
      ),
    }));
  },

  deleteLead: (id) => {
    set((state) => {
      const targetLead = state.leads.find((l) => l.id === id);
      return {
        leads: state.leads.filter((l) => l.id !== id),
        campaigns: state.campaigns.map((c) =>
          c.id === targetLead?.campaignId ? { ...c, totalLeads: Math.max(0, c.totalLeads - 1) } : c
        ),
      };
    });
  },

  updateLeadStatus: (id, status) => {
    set((state) => ({
      leads: state.leads.map((l) => (l.id === id ? { ...l, status } : l)),
    }));
  },

  triggerCallLead: (id) => {
    const nowStr = new Date().toISOString().replace("T", " ").slice(0, 16);
    set((state) => {
      const targetLead = state.leads.find((l) => l.id === id);
      if (!targetLead) return state;

      const updatedLeads = state.leads.map((l) =>
        l.id === id
          ? {
              ...l,
              status: "calling" as const,
              attempts: l.attempts + 1,
              lastCalled: nowStr,
            }
          : l
      );

      const updatedCampaigns = state.campaigns.map((c) =>
        c.id === targetLead.campaignId
          ? {
              ...c,
              callsMade: c.callsMade + 1,
            }
          : c
      );

      return { leads: updatedLeads, campaigns: updatedCampaigns };
    });
  },

  triggerCallAllPending: (campaignId) => {
    const nowStr = new Date().toISOString().replace("T", " ").slice(0, 16);
    let count = 0;
    set((state) => {
      const pendingLeads = state.leads.filter(
        (l) => l.campaignId === campaignId && (l.status === "pending" || l.status === "failed")
      );
      count = pendingLeads.length;

      if (count === 0) return state;

      const pendingIds = new Set(pendingLeads.map((l) => l.id));

      const updatedLeads = state.leads.map((l) =>
        pendingIds.has(l.id)
          ? {
              ...l,
              status: "calling" as const,
              attempts: l.attempts + 1,
              lastCalled: nowStr,
            }
          : l
      );

      const updatedCampaigns = state.campaigns.map((c) =>
        c.id === campaignId
          ? {
              ...c,
              callsMade: c.callsMade + count,
            }
          : c
      );

      return { leads: updatedLeads, campaigns: updatedCampaigns };
    });
    return count;
  },
}));
