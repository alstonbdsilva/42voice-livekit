export type UserRole = "super_admin" | "finance_admin" | "reseller" | "client";

export interface User {
  id: string | number;
  name: string;
  email: string;
  role: UserRole;
  status?: string;
  createdAt?: string;
  clientId?: string | number;
  resellerId?: string | number;
  phone?: string;
  resellerName?: string;
  clientName?: string;
}

export type AgentStatus = "active" | "paused" | "testing" | string;

export interface AgentEntityRef {
  id: string | number;
  name: string;
}

export interface Agent {
  id: string | number;
  name: string;
  type: string;
  callType?: string;
  useCase?: string;
  activityDescription?: string;
  channels: string[];
  totalCalls: number;
  totalMessages: number;
  totalMinutes: number;
  successRate: number;
  escalationRate: number;
  status: AgentStatus;
  promptVersion?: number | string;
  kbVersion?: number | string;
  totalCost?: number;
  lastActivity?: string;
  clientId?: string | number;
  assignedResellers?: AgentEntityRef[];
  assignedClients?: AgentEntityRef[];
}

export interface TranscriptLine {
  speaker: "agent" | "customer" | string;
  text: string;
}

export interface Transcript {
  fullText: string;
  lines: TranscriptLine[];
  actionItems?: string[];
}

export interface Conversation {
  id: string | number;
  agentId?: string | number;
  agentName?: string;
  customerName: string;
  customerContact?: string;
  summary: string;
  channel: string;
  outcome: string;
  startedAt: string;
  cost: number;
  sentiment: string;
  duration?: number;
  intent?: string;
  leadScore?: number;
  sentimentScore?: number;
  humanHandoff?: boolean;
  escalationReason?: string;
}

export interface Recording {
  id: string | number;
  filename: string;
  duration: number;
  size: number;
  createdAt: string;
  conversationId: string | number;
}

export interface RecordingAudio {
  id: string | number;
  url: string;
  filename: string;
}

export interface Client {
  id: string | number;
  name: string;
  industry: string;
  country: string;
  monthlyRecurring: number;
  contactEmail: string;
  status: string;
  createdAt: string;
  resellerId?: string | number;
}

export interface Reseller {
  id: string | number;
  name: string;
  country: string;
  commissionPct: number;
  contactEmail: string;
  status: string;
  createdAt: string;
}

export interface InvoiceLineItem {
  description: string;
  quantity: number;
  rate: number;
  amount: number;
  label?: string;
}

export interface Invoice {
  id: string | number;
  clientId: string | number;
  clientName?: string;
  amount: number;
  status: string;
  dueDate: string;
  createdAt: string;
  total?: number;
  paidAmount?: number;
  number?: string;
  issueDate?: string;
  lineItems?: InvoiceLineItem[];
}

export interface Payment {
  id: string | number;
  invoiceId: string | number;
  amount: number;
  status: string;
  paymentMethod: string;
  createdAt: string;
  paidAt?: string;
  reference?: string;
  invoiceNumber?: string;
  method?: string;
}

export interface Contract {
  id: string | number;
  clientId: string | number;
  clientName?: string;
  value: number;
  status: string;
  startDate: string;
  endDate: string;
  createdAt: string;
  autoRenewal?: boolean;
  contractValue?: number;
  number?: string;
  paymentTerms?: string;
  billingCycle?: string;
  noticePeriodDays?: number;
  renewalDate?: string;
  renewalStatus?: string;
  renewalOwner?: string;
  renewalProbability?: number;
  notes?: string;
}

export interface Renewal {
  id: string | number;
  clientId: string | number;
  clientName?: string;
  contractId: string | number;
  value: number;
  status: string;
  date: string;
  renewalDate?: string;
  endDate?: string;
  probability?: number;
}

export interface Commission {
  id: string | number;
  resellerId: string | number;
  resellerName?: string;
  amount: number;
  status: string;
  date: string;
  createdAt?: string;
  clientName?: string;
  invoiceNumber?: string;
  commissionPct?: number;
}

export interface Notification {
  id: string | number;
  title: string;
  message: string;
  type: string;
  read: boolean;
  createdAt: string;
  priority?: string;
  description?: string;
}

export interface AuditLog {
  id: string | number;
  userId: string | number;
  userName?: string;
  action: string;
  details: string;
  createdAt: string;
  actorEmail?: string;
  actorRole?: string;
  target?: string;
}

export interface Message {
  id: string | number;
  createdAt: string;
  from: string;
  channel: string;
  preview: string;
  unread: boolean;
}

export interface DashboardSummary {
  totals: {
    revenueCollected: number;
    revenueDue: number;
    revenueOverdue: number;
    pendingInvoices: number;
    mrr: number;
    arr: number;
    activeClients: number;
    activeResellers: number;
    activeAgents: number;
    totalCalls: number;
    totalMessages: number;
    totalMinutes: number;
    totalConversations: number;
  };
  monthlyTrend: Array<{
    month: string;
    revenueCollected: number;
    revenueDue: number;
  }>;
  contractsExpiring?: Record<string, number>;
  revenueByClient?: Array<{ name: string; value: number }>;
  revenueByReseller?: Array<{ name: string; value: number }>;
  ageing?: Record<string, number>;
}

export interface DashboardMoney {
  totals: {
    revenueCollected: number;
    mrr: number;
    commissionsPaid: number;
    netRevenue: number;
    grossMargin?: number;
    platformCost?: number;
    totalInvoicesRaised?: number;
    totalInvoicesUnpaid?: number;
    totalInvoicesPartial?: number;
    commissionPayable?: number;
    totalCollected?: number;
    totalAvailable?: number;
    totalDue?: number;
    totalOverdue?: number;
    grossRevenue?: number;
  };
  commissionsTrend: Array<{
    month: string;
    commissions: number;
  }>;
}
