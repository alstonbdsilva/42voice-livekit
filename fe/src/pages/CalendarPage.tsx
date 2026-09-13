import React, { useState } from "react";
import PageHeader from "@/components/PageHeader";
import KpiCard from "@/components/KpiCard";
import AppModal from "@/components/AppModal";
import { toast } from "sonner";
import {
  Calendar as CalendarIcon,
  Plus,
  Clock,
  User,
  Phone,
  Video,
  CheckCircle2,
  AlertCircle,
  Search,
  Filter,
  Bot,
  CalendarDays,
  List,
  PhoneCall
} from "lucide-react";

export interface CalendarEvent {
  id: string;
  title: string;
  customerName: string;
  customerPhone: string;
  customerEmail?: string;
  agentName: string;
  eventType: "appointment" | "callback" | "demo" | "followup";
  status: "confirmed" | "scheduled" | "completed" | "cancelled";
  date: string; // YYYY-MM-DD
  time: string; // HH:MM
  durationMinutes: number;
  notes?: string;
}

const INITIAL_EVENTS: CalendarEvent[] = [
  {
    id: "evt-1",
    title: "Product Demo & AI Voice Walkthrough",
    customerName: "Sarah Jenkins",
    customerPhone: "+1 (555) 234-5678",
    customerEmail: "sarah.j@acmecorp.com",
    agentName: "Sales Agent Pro",
    eventType: "demo",
    status: "confirmed",
    date: "2026-09-13",
    time: "10:30",
    durationMinutes: 30,
    notes: "Customer interested in custom ElevenLabs voice integration and outbound lead qualification.",
  },
  {
    id: "evt-2",
    title: "Scheduled Outbound Follow-up Call",
    customerName: "Michael Chang",
    customerPhone: "+1 (555) 876-5432",
    customerEmail: "mchang@nexus.io",
    agentName: "Outbound Lead Qualifier",
    eventType: "callback",
    status: "scheduled",
    date: "2026-09-13",
    time: "14:00",
    durationMinutes: 15,
    notes: "Follow up on pricing invoice sent yesterday.",
  },
  {
    id: "evt-3",
    title: "Dental Consultation Booking",
    customerName: "Emily Davis",
    customerPhone: "+1 (555) 345-6789",
    customerEmail: "emily.davis@gmail.com",
    agentName: "Receptionist AI Bot",
    eventType: "appointment",
    status: "confirmed",
    date: "2026-09-13",
    time: "16:15",
    durationMinutes: 45,
    notes: "Booked via inbound voice call. Needs confirmation reminder.",
  },
  {
    id: "evt-4",
    title: "Client Onboarding & SIP Setup",
    customerName: "David Miller",
    customerPhone: "+1 (555) 901-2345",
    customerEmail: "dmiller@apexsystems.com",
    agentName: "Support Assistant AI",
    eventType: "followup",
    status: "completed",
    date: "2026-09-12",
    time: "11:00",
    durationMinutes: 30,
    notes: "Successfully configured Twilio trunk credentials.",
  },
  {
    id: "evt-5",
    title: "Enterprise Strategy Consultation",
    customerName: "Robert Taylor",
    customerPhone: "+1 (555) 654-3210",
    customerEmail: "rtaylor@globalent.com",
    agentName: "Sales Agent Pro",
    eventType: "demo",
    status: "scheduled",
    date: "2026-09-14",
    time: "11:30",
    durationMinutes: 60,
    notes: "Review custom LLM prompt instructions and multi-language support.",
  },
  {
    id: "evt-6",
    title: "Automated Renewal Reminder Call",
    customerName: "Amanda White",
    customerPhone: "+1 (555) 432-1098",
    customerEmail: "awhite@innovate.co",
    agentName: "Outbound Lead Qualifier",
    eventType: "callback",
    status: "scheduled",
    date: "2026-09-15",
    time: "09:45",
    durationMinutes: 15,
    notes: "Contract renewal date approaching in 14 days.",
  },
  {
    id: "evt-7",
    title: "Technical Integration Review",
    customerName: "Carlos Rodriguez",
    customerPhone: "+1 (555) 789-0123",
    customerEmail: "carlos@techcorp.es",
    agentName: "Support Assistant AI",
    eventType: "appointment",
    status: "scheduled",
    date: "2026-09-16",
    time: "15:00",
    durationMinutes: 30,
    notes: "Webhook notification setup and LiveKit audio latency test.",
  },
];

export default function CalendarPage() {
  const [events, setEvents] = useState<CalendarEvent[]>(INITIAL_EVENTS);
  const [selectedDate, setSelectedDate] = useState<string>("2026-09-13");
  const [viewMode, setViewMode] = useState<"month" | "agenda">("month");
  
  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState<string>("all");
  const [filterStatus, setFilterStatus] = useState<string>("all");

  // Modals state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null);

  // New Event Form State
  const [newEvent, setNewEvent] = useState<{
    title: string;
    customerName: string;
    customerPhone: string;
    customerEmail: string;
    agentName: string;
    eventType: "appointment" | "callback" | "demo" | "followup";
    date: string;
    time: string;
    durationMinutes: number;
    notes: string;
  }>({
    title: "",
    customerName: "",
    customerPhone: "",
    customerEmail: "",
    agentName: "Sales Agent Pro",
    eventType: "appointment",
    date: "2026-09-13",
    time: "10:00",
    durationMinutes: 30,
    notes: "",
  });

  // Filtered Events
  const filteredEvents = events.filter((evt) => {
    const matchesSearch =
      evt.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      evt.customerName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      evt.agentName.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesType = filterType === "all" || evt.eventType === filterType;
    const matchesStatus = filterStatus === "all" || evt.status === filterStatus;
    return matchesSearch && matchesType && matchesStatus;
  });

  const selectedDayEvents = filteredEvents.filter((evt) => evt.date === selectedDate);

  // Stats
  const totalEvents = events.length;
  const confirmedCount = events.filter((e) => e.status === "confirmed").length;
  const scheduledCallbacks = events.filter((e) => e.eventType === "callback" && e.status === "scheduled").length;
  const demosCount = events.filter((e) => e.eventType === "demo").length;

  const handleCreateEvent = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEvent.title || !newEvent.customerName || !newEvent.date || !newEvent.time) {
      toast.error("Please fill in required fields (Title, Customer, Date, Time)");
      return;
    }

    const created: CalendarEvent = {
      id: `evt-${Date.now()}`,
      ...newEvent,
      status: "scheduled",
    };

    setEvents((prev) => [...prev, created]);
    toast.success(`Scheduled ${newEvent.eventType} for ${newEvent.customerName}`);
    setIsCreateModalOpen(false);
    setNewEvent({
      title: "",
      customerName: "",
      customerPhone: "",
      customerEmail: "",
      agentName: "Sales Agent Pro",
      eventType: "appointment",
      date: selectedDate,
      time: "10:00",
      durationMinutes: 30,
      notes: "",
    });
  };

  const handleCancelEvent = (eventId: string) => {
    setEvents((prev) =>
      prev.map((evt) => (evt.id === eventId ? { ...evt, status: "cancelled" } : evt))
    );
    toast.info("Event has been cancelled");
    setSelectedEvent(null);
  };

  const handleInitiateCall = (event: CalendarEvent) => {
    toast.success(`Initiating outbound voice call with ${event.customerName} (${event.customerPhone}) via ${event.agentName}...`);
  };

  // Helper function to render event type badges
  const renderEventTypeBadge = (type: CalendarEvent["eventType"]) => {
    switch (type) {
      case "appointment":
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200"><CalendarIcon className="w-3 h-3" /> Appointment</span>;
      case "callback":
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200"><Phone className="w-3 h-3" /> Callback</span>;
      case "demo":
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-purple-50 text-purple-700 border border-purple-200"><Video className="w-3 h-3" /> Demo Call</span>;
      case "followup":
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200"><Clock className="w-3 h-3" /> Follow-up</span>;
    }
  };

  const renderStatusBadge = (status: CalendarEvent["status"]) => {
    switch (status) {
      case "confirmed":
        return <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 bg-emerald-100/60 px-2 py-0.5 rounded-sm"><CheckCircle2 className="w-3 h-3" /> Confirmed</span>;
      case "scheduled":
        return <span className="inline-flex items-center gap-1 text-xs font-medium text-blue-700 bg-blue-100/60 px-2 py-0.5 rounded-sm"><Clock className="w-3 h-3" /> Scheduled</span>;
      case "completed":
        return <span className="inline-flex items-center gap-1 text-xs font-medium text-zinc-600 bg-zinc-100 px-2 py-0.5 rounded-sm"><CheckCircle2 className="w-3 h-3" /> Completed</span>;
      case "cancelled":
        return <span className="inline-flex items-center gap-1 text-xs font-medium text-rose-700 bg-rose-100/60 px-2 py-0.5 rounded-sm"><AlertCircle className="w-3 h-3" /> Cancelled</span>;
    }
  };

  // Days in month calculation for custom calendar grid
  const daysInMonth = 30; // Sept 2026
  const monthDays = Array.from({ length: daysInMonth }, (_, i) => {
    const dayNum = i + 1;
    const dateStr = `2026-09-${String(dayNum).padStart(2, "0")}`;
    const dayEvents = filteredEvents.filter((e) => e.date === dateStr);
    return { dayNum, dateStr, events: dayEvents };
  });

  return (
    <div className="space-y-6" data-testid="calendar-page">
      <PageHeader
        title="Calendar & Appointments"
        subtitle="Manage AI scheduled meetings, automated callbacks, and customer demos"
        actions={
          <div className="flex items-center gap-2">
            <div className="flex items-center bg-zinc-100 p-1 rounded-md border border-zinc-200">
              <button
                onClick={() => setViewMode("month")}
                className={`flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-sm transition-all ${
                  viewMode === "month" ? "bg-white text-zinc-950 shadow-sm" : "text-zinc-600 hover:text-zinc-950"
                }`}
              >
                <CalendarDays className="w-3.5 h-3.5" />
                Month View
              </button>
              <button
                onClick={() => setViewMode("agenda")}
                className={`flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-sm transition-all ${
                  viewMode === "agenda" ? "bg-white text-zinc-950 shadow-sm" : "text-zinc-600 hover:text-zinc-950"
                }`}
              >
                <List className="w-3.5 h-3.5" />
                Agenda List
              </button>
            </div>
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="inline-flex items-center gap-1.5 bg-zinc-950 hover:bg-zinc-800 text-white px-3.5 py-1.5 rounded-sm text-sm font-medium transition-colors shadow-sm"
              data-testid="schedule-event-btn"
            >
              <Plus className="w-4 h-4" />
              Schedule Event
            </button>
          </div>
        }
      />

      {/* Stats Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard label="Total Scheduled Events" value={totalEvents} sub="All active entries" testId="kpi-total-events" />
        <KpiCard label="Confirmed Appointments" value={confirmedCount} sub="AI Agent booked" accent="success" testId="kpi-confirmed" />
        <KpiCard label="Outbound Callbacks" value={scheduledCallbacks} sub="Pending automated calls" accent="warning" testId="kpi-callbacks" />
        <KpiCard label="Demo Sessions" value={demosCount} sub="High priority leads" testId="kpi-demos" />
      </div>

      {/* Filters Toolbar */}
      <div className="bg-white border border-zinc-200 rounded-md p-4 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 shadow-sm">
        <div className="flex-1 relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
          <input
            type="text"
            placeholder="Search by title, customer name, or agent..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-1.5 bg-zinc-50 border border-zinc-200 rounded-sm text-sm focus:outline-none focus:border-zinc-950 focus:bg-white"
          />
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-zinc-500 font-medium">
            <Filter className="w-3.5 h-3.5" />
            <span>Filters:</span>
          </div>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="bg-zinc-50 border border-zinc-200 text-xs rounded-sm px-2.5 py-1.5 font-medium text-zinc-700 focus:outline-none focus:border-zinc-950"
          >
            <option value="all">All Event Types</option>
            <option value="appointment">Appointments</option>
            <option value="callback">Callbacks</option>
            <option value="demo">Demo Sessions</option>
            <option value="followup">Follow-ups</option>
          </select>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="bg-zinc-50 border border-zinc-200 text-xs rounded-sm px-2.5 py-1.5 font-medium text-zinc-700 focus:outline-none focus:border-zinc-950"
          >
            <option value="all">All Statuses</option>
            <option value="confirmed">Confirmed</option>
            <option value="scheduled">Scheduled</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>
      </div>

      {/* Main View Grid */}
      {viewMode === "month" ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Calendar Month Grid */}
          <div className="lg:col-span-2 bg-white border border-zinc-200 rounded-md p-5 shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-100 pb-3">
              <div className="flex items-center gap-2">
                <CalendarIcon className="w-5 h-5 text-zinc-700" />
                <h2 className="font-display font-semibold text-lg text-zinc-900">September 2026</h2>
              </div>
              <div className="flex items-center gap-1 text-xs font-mono-stat text-zinc-500">
                <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block"></span>
                <span>Active Schedule</span>
              </div>
            </div>

            {/* Days Header */}
            <div className="grid grid-cols-7 text-center text-xs font-semibold text-zinc-500 py-1 border-b border-zinc-100">
              <div>Sun</div>
              <div>Mon</div>
              <div>Tue</div>
              <div>Wed</div>
              <div>Thu</div>
              <div>Fri</div>
              <div>Sat</div>
            </div>

            {/* Month Day Cells */}
            <div className="grid grid-cols-7 gap-1">
              {/* Padding offset for Tuesday start (1 Sept 2026 = Tuesday -> 2 empty cells) */}
              <div className="h-20 bg-zinc-50/50 rounded-sm border border-transparent"></div>
              <div className="h-20 bg-zinc-50/50 rounded-sm border border-transparent"></div>

              {monthDays.map(({ dayNum, dateStr, events: dayEvents }) => {
                const isSelected = selectedDate === dateStr;
                const isToday = dateStr === "2026-09-13";
                return (
                  <div
                    key={dateStr}
                    onClick={() => setSelectedDate(dateStr)}
                    className={`h-24 p-1.5 border rounded-sm transition-all cursor-pointer flex flex-col justify-between overflow-hidden ${
                      isSelected
                        ? "border-zinc-950 bg-zinc-50 ring-1 ring-zinc-950"
                        : isToday
                        ? "border-emerald-300 bg-emerald-50/20"
                        : "border-zinc-100 hover:border-zinc-300 hover:bg-zinc-50/50"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span
                        className={`text-xs font-semibold px-1.5 py-0.5 rounded-sm font-mono-stat ${
                          isToday
                            ? "bg-emerald-700 text-white"
                            : isSelected
                            ? "bg-zinc-950 text-white"
                            : "text-zinc-700"
                        }`}
                      >
                        {dayNum}
                      </span>
                      {dayEvents.length > 0 && (
                        <span className="text-[10px] font-mono-stat text-zinc-500 font-medium">
                          {dayEvents.length} event{dayEvents.length > 1 ? "s" : ""}
                        </span>
                      )}
                    </div>

                    <div className="space-y-1 overflow-y-auto max-h-14 scrollbar-none mt-1">
                      {dayEvents.slice(0, 2).map((evt) => (
                        <div
                          key={evt.id}
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedEvent(evt);
                          }}
                          className={`text-[10px] p-1 rounded-sm truncate font-medium border transition-colors ${
                            evt.eventType === "demo"
                              ? "bg-purple-50 text-purple-800 border-purple-200"
                              : evt.eventType === "callback"
                              ? "bg-blue-50 text-blue-800 border-blue-200"
                              : evt.eventType === "appointment"
                              ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                              : "bg-amber-50 text-amber-800 border-amber-200"
                          }`}
                          title={`${evt.time} - ${evt.title} (${evt.customerName})`}
                        >
                          <span className="font-mono-stat font-bold mr-1">{evt.time}</span>
                          {evt.customerName}
                        </div>
                      ))}
                      {dayEvents.length > 2 && (
                        <div className="text-[9px] text-zinc-500 font-medium pl-1">
                          +{dayEvents.length - 2} more
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Selected Day Schedule Details Sidebar */}
          <div className="bg-white border border-zinc-200 rounded-md p-5 shadow-sm space-y-4 flex flex-col h-full">
            <div className="flex items-center justify-between border-b border-zinc-100 pb-3">
              <div>
                <h3 className="font-display font-semibold text-zinc-900">
                  Schedule for {selectedDate}
                </h3>
                <p className="text-xs text-zinc-500 font-mono-stat">
                  {selectedDayEvents.length} event(s) listed
                </p>
              </div>
              <button
                onClick={() => {
                  setNewEvent((prev) => ({ ...prev, date: selectedDate }));
                  setIsCreateModalOpen(true);
                }}
                className="text-xs text-zinc-800 font-medium hover:text-zinc-950 flex items-center gap-1 border border-zinc-200 px-2 py-1 rounded-sm bg-zinc-50 hover:bg-zinc-100"
              >
                <Plus className="w-3.5 h-3.5" /> Add
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3 pr-1">
              {selectedDayEvents.length === 0 ? (
                <div className="text-center py-12 text-zinc-400 space-y-2">
                  <CalendarIcon className="w-8 h-8 mx-auto stroke-1 text-zinc-300" />
                  <p className="text-xs">No events scheduled for this day</p>
                  <button
                    onClick={() => {
                      setNewEvent((prev) => ({ ...prev, date: selectedDate }));
                      setIsCreateModalOpen(true);
                    }}
                    className="text-xs text-zinc-950 font-medium underline"
                  >
                    Schedule an event now
                  </button>
                </div>
              ) : (
                selectedDayEvents.map((evt) => (
                  <div
                    key={evt.id}
                    onClick={() => setSelectedEvent(evt)}
                    className="p-3 border border-zinc-200 rounded-sm hover:border-zinc-950 transition-all cursor-pointer bg-zinc-50/50 hover:bg-white space-y-2 group"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-0.5">
                        <div className="text-xs font-semibold text-zinc-950 group-hover:text-black">
                          {evt.title}
                        </div>
                        <div className="flex items-center gap-2 text-[11px] text-zinc-500 font-mono-stat">
                          <Clock className="w-3 h-3 text-zinc-400" />
                          <span>{evt.time} ({evt.durationMinutes} min)</span>
                        </div>
                      </div>
                      {renderStatusBadge(evt.status)}
                    </div>

                    <div className="flex items-center justify-between text-xs pt-1 border-t border-zinc-100">
                      <div className="flex items-center gap-1.5 text-zinc-700 font-medium">
                        <User className="w-3 h-3 text-zinc-400" />
                        <span>{evt.customerName}</span>
                      </div>
                      <div className="flex items-center gap-1 text-[11px] text-zinc-500">
                        <Bot className="w-3 h-3 text-zinc-400" />
                        <span>{evt.agentName}</span>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      ) : (
        /* Agenda View List */
        <div className="bg-white border border-zinc-200 rounded-md shadow-sm divide-y divide-zinc-100">
          <div className="p-4 bg-zinc-50 border-b border-zinc-200 font-display font-semibold text-sm text-zinc-900 flex items-center justify-between">
            <span>Upcoming Agenda Events</span>
            <span className="text-xs font-mono-stat font-normal text-zinc-500">
              Showing {filteredEvents.length} items
            </span>
          </div>

          {filteredEvents.length === 0 ? (
            <div className="p-12 text-center text-zinc-400 text-xs">
              No matching events found. Try adjusting your filters.
            </div>
          ) : (
            filteredEvents.map((evt) => (
              <div
                key={evt.id}
                onClick={() => setSelectedEvent(evt)}
                className="p-4 hover:bg-zinc-50/80 transition-colors cursor-pointer flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="flex items-start gap-4">
                  <div className="text-center min-w-[70px] bg-zinc-100 p-2 rounded-sm border border-zinc-200">
                    <div className="text-[10px] font-mono-stat uppercase text-zinc-500">
                      {evt.date}
                    </div>
                    <div className="text-sm font-bold font-mono-stat text-zinc-900">
                      {evt.time}
                    </div>
                  </div>

                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm text-zinc-950">{evt.title}</span>
                      {renderEventTypeBadge(evt.eventType)}
                    </div>
                    <div className="flex items-center gap-4 text-xs text-zinc-500">
                      <span className="flex items-center gap-1">
                        <User className="w-3.5 h-3.5 text-zinc-400" />
                        {evt.customerName} ({evt.customerPhone})
                      </span>
                      <span className="flex items-center gap-1">
                        <Bot className="w-3.5 h-3.5 text-zinc-400" />
                        Agent: {evt.agentName}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  {renderStatusBadge(evt.status)}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleInitiateCall(evt);
                    }}
                    className="inline-flex items-center gap-1 text-xs border border-zinc-200 px-2.5 py-1 rounded-sm bg-zinc-50 hover:bg-zinc-100 font-medium text-zinc-800 transition-colors"
                  >
                    <PhoneCall className="w-3 h-3" /> Call Now
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Modal: Schedule Event */}
      <AppModal
        open={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Schedule Calendar Event"
        description="Book an appointment, demo call, or automated AI callback"
        showFooter={false}
      >
        <form onSubmit={handleCreateEvent} className="space-y-4 pt-2">
          <div>
            <label className="block text-xs font-semibold text-zinc-700 mb-1">Event Title *</label>
            <input
              type="text"
              required
              placeholder="e.g. Sales Consultation & Demo"
              value={newEvent.title}
              onChange={(e) => setNewEvent({ ...newEvent, title: e.target.value })}
              className="w-full border border-zinc-200 rounded-sm px-3 py-1.5 text-sm focus:outline-none focus:border-zinc-950"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-zinc-700 mb-1">Customer Name *</label>
              <input
                type="text"
                required
                placeholder="Jane Doe"
                value={newEvent.customerName}
                onChange={(e) => setNewEvent({ ...newEvent, customerName: e.target.value })}
                className="w-full border border-zinc-200 rounded-sm px-3 py-1.5 text-sm focus:outline-none focus:border-zinc-950"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-zinc-700 mb-1">Phone Number</label>
              <input
                type="text"
                placeholder="+1 (555) 000-0000"
                value={newEvent.customerPhone}
                onChange={(e) => setNewEvent({ ...newEvent, customerPhone: e.target.value })}
                className="w-full border border-zinc-200 rounded-sm px-3 py-1.5 text-sm focus:outline-none focus:border-zinc-950"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-zinc-700 mb-1">Event Type</label>
              <select
                value={newEvent.eventType}
                onChange={(e: any) => setNewEvent({ ...newEvent, eventType: e.target.value })}
                className="w-full border border-zinc-200 rounded-sm px-3 py-1.5 text-sm focus:outline-none focus:border-zinc-950 bg-white"
              >
                <option value="appointment">Appointment</option>
                <option value="callback">Outbound Callback</option>
                <option value="demo">Demo Session</option>
                <option value="followup">Follow-up</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-zinc-700 mb-1">Assigned AI Agent</label>
              <select
                value={newEvent.agentName}
                onChange={(e) => setNewEvent({ ...newEvent, agentName: e.target.value })}
                className="w-full border border-zinc-200 rounded-sm px-3 py-1.5 text-sm focus:outline-none focus:border-zinc-950 bg-white"
              >
                <option value="Sales Agent Pro">Sales Agent Pro</option>
                <option value="Outbound Lead Qualifier">Outbound Lead Qualifier</option>
                <option value="Receptionist AI Bot">Receptionist AI Bot</option>
                <option value="Support Assistant AI">Support Assistant AI</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-semibold text-zinc-700 mb-1">Date *</label>
              <input
                type="date"
                required
                value={newEvent.date}
                onChange={(e) => setNewEvent({ ...newEvent, date: e.target.value })}
                className="w-full border border-zinc-200 rounded-sm px-3 py-1.5 text-sm focus:outline-none focus:border-zinc-950"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-zinc-700 mb-1">Time *</label>
              <input
                type="time"
                required
                value={newEvent.time}
                onChange={(e) => setNewEvent({ ...newEvent, time: e.target.value })}
                className="w-full border border-zinc-200 rounded-sm px-3 py-1.5 text-sm focus:outline-none focus:border-zinc-950"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-zinc-700 mb-1">Duration (Min)</label>
              <input
                type="number"
                value={newEvent.durationMinutes}
                onChange={(e) => setNewEvent({ ...newEvent, durationMinutes: Number(e.target.value) })}
                className="w-full border border-zinc-200 rounded-sm px-3 py-1.5 text-sm focus:outline-none focus:border-zinc-950"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-zinc-700 mb-1">Notes / Special Instructions</label>
            <textarea
              rows={2}
              placeholder="Add key context or parameters for the AI Agent..."
              value={newEvent.notes}
              onChange={(e) => setNewEvent({ ...newEvent, notes: e.target.value })}
              className="w-full border border-zinc-200 rounded-sm px-3 py-1.5 text-sm focus:outline-none focus:border-zinc-950"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-zinc-100">
            <button
              type="button"
              onClick={() => setIsCreateModalOpen(false)}
              className="px-4 py-1.5 text-xs font-medium border border-zinc-200 rounded-sm hover:bg-zinc-100"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-1.5 text-xs font-medium bg-zinc-950 text-white rounded-sm hover:bg-zinc-800"
            >
              Confirm & Schedule
            </button>
          </div>
        </form>
      </AppModal>

      {/* Modal: View Event Detail */}
      {selectedEvent && (
        <AppModal
          open={!!selectedEvent}
          onClose={() => setSelectedEvent(null)}
          title="Event Details"
          description={`Reference ID: ${selectedEvent.id}`}
          showFooter={false}
        >
          <div className="space-y-4 pt-1">
            <div className="flex items-center justify-between border-b border-zinc-100 pb-3">
              <h3 className="font-semibold text-base text-zinc-950">{selectedEvent.title}</h3>
              {renderStatusBadge(selectedEvent.status)}
            </div>

            <div className="grid grid-cols-2 gap-4 text-xs">
              <div>
                <span className="text-zinc-500 block">Customer</span>
                <span className="font-medium text-zinc-900">{selectedEvent.customerName}</span>
                <div className="text-zinc-500 font-mono-stat">{selectedEvent.customerPhone}</div>
              </div>
              <div>
                <span className="text-zinc-500 block">Assigned AI Agent</span>
                <span className="font-medium text-zinc-900">{selectedEvent.agentName}</span>
              </div>
              <div>
                <span className="text-zinc-500 block">Date & Time</span>
                <span className="font-medium font-mono-stat text-zinc-900">
                  {selectedEvent.date} at {selectedEvent.time} ({selectedEvent.durationMinutes} min)
                </span>
              </div>
              <div>
                <span className="text-zinc-500 block">Category</span>
                {renderEventTypeBadge(selectedEvent.eventType)}
              </div>
            </div>

            {selectedEvent.notes && (
              <div className="bg-zinc-50 p-3 rounded-sm border border-zinc-200 text-xs">
                <span className="font-semibold text-zinc-700 block mb-1">Notes:</span>
                <p className="text-zinc-600 leading-relaxed">{selectedEvent.notes}</p>
              </div>
            )}

            <div className="flex items-center justify-between pt-3 border-t border-zinc-100">
              {selectedEvent.status !== "cancelled" ? (
                <button
                  type="button"
                  onClick={() => handleCancelEvent(selectedEvent.id)}
                  className="text-xs text-rose-600 hover:text-rose-800 font-medium"
                >
                  Cancel Event
                </button>
              ) : (
                <span className="text-xs text-zinc-400">Event is cancelled</span>
              )}

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setSelectedEvent(null)}
                  className="px-3 py-1.5 text-xs font-medium border border-zinc-200 rounded-sm hover:bg-zinc-100"
                >
                  Close
                </button>
                <button
                  type="button"
                  onClick={() => handleInitiateCall(selectedEvent)}
                  className="inline-flex items-center gap-1 px-3.5 py-1.5 text-xs font-medium bg-zinc-950 text-white rounded-sm hover:bg-zinc-800"
                >
                  <PhoneCall className="w-3.5 h-3.5" /> Initiate Call
                </button>
              </div>
            </div>
          </div>
        </AppModal>
      )}
    </div>
  );
}
