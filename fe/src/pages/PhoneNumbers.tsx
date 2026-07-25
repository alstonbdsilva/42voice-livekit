import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Plus, Search, Server } from "lucide-react";
import AgentService from "@/services/agent.service";
import PhoneNumberService from "@/services/phone-number.service";
import { Agent } from "@/types";
import { useAuth } from "@/store/authStore";

import ConfirmDeleteModal from "@/components/ConfirmDeleteModal";
import PublishedTab from "@/components/phone-numbers/PublishedTab";
import DraftsTab from "@/components/phone-numbers/DraftsTab";
import DisconnectedTab from "@/components/phone-numbers/DisconnectedTab";
import LiveKitMonitorTab from "@/components/phone-numbers/LiveKitMonitorTab";
import ClientOwnedTab from "@/components/phone-numbers/ClientOwnedTab";
import ClientBrowseTab from "@/components/phone-numbers/ClientBrowseTab";
import EditNumberModal from "@/components/phone-numbers/EditNumberModal";

interface PhoneNumberItem {
  id: string;
  number: string;
  name: string;
  agentId: string; // References Agent.id
  status: "active" | "available" | "pending_sip" | "inactive";
  capabilities: { voice: boolean; sms: boolean };
  provider: "Twilio" | "CITL";
  monthlyCost: string;
  setupCost?: string;
  ownerId?: string | number; // References user.clientId or user.id
  ownerName?: string; // Client/Company Name
  sipConfig?: {
    domain: string;
    authUsername: string;
    password?: string;
    proxy: string;
    dtmfMode: string;
    preferredCodec: string;
  };
  createdAt?: string;
}

export default function PhoneNumbers() {
  const navigate = useNavigate();
  const { user } = useAuth();
  
  const isSuperAdmin = user?.role === "super_admin" || user?.role === "finance_admin";

  const [activeTab, setActiveTab] = useState<"numbers" | "browse">("numbers");
  const [superadminTab, setSuperadminTab] = useState<"published" | "drafts" | "disconnected" | "livekit">("published");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [numbers, setNumbers] = useState<PhoneNumberItem[]>([]);
  const [searchQuery, setSearchQuery] = useState("");

  // LiveKit Status Monitor State
  const [livekitStatus, setLivekitStatus] = useState<{
    connected: boolean;
    mode: "live" | "simulated" | "error" | "offline";
    error?: string;
    trunks: Array<{ id: string; name: string; numbers: string[] }>;
    dispatch_rules: Array<{ id: string; name: string; trunk_ids: string[] }>;
  } | null>(null);
  const [isLivekitLoading, setIsLivekitLoading] = useState(false);

  // Edit Modal State
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editTargetItem, setEditTargetItem] = useState<PhoneNumberItem | null>(null);

  // Delete/Release Confirmation Modal State
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState("");
  const [deleteTargetNumStr, setDeleteTargetNumStr] = useState("");
  const [deleteActionType, setDeleteActionType] = useState<"delete" | "release">("delete");
  const [deleteLoading, setDeleteLoading] = useState(false);

  const fetchLivekitStatus = () => {
    setIsLivekitLoading(true);
    PhoneNumberService.getLiveKitStatus()
      .then((res) => {
        setLivekitStatus(res);
      })
      .catch((err) => {
        console.error("Failed to load LiveKit SIP status", err);
      })
      .finally(() => {
        setIsLivekitLoading(false);
      });
  };

  const fetchNumbers = () => {
    PhoneNumberService.getAll()
      .then((data) => {
        // Map backend properties to local UI properties for compatibility
        const mapped = data.map((item: any) => ({
          ...item,
          ownerId: item.clientId || item.resellerId || "",
          ownerName: item.clientId ? "Client Account" : (item.resellerId ? "Reseller Partner" : "")
        }));
        setNumbers(mapped);
      })
      .catch((err) => {
        toast.error("Failed to load phone numbers from backend.");
        console.error(err);
      });
  };

  // Load numbers, agents, and settings on mount
  useEffect(() => {
    AgentService.getAll()
      .then((data) => {
        setAgents(data);
      })
      .catch(() => {});

    fetchNumbers();
  }, []);

  // Update tab selection automatically when user role changes
  useEffect(() => {
    setActiveTab("numbers");
    setSuperadminTab("published");
  }, [user?.role]);

  // Load LiveKit status when livekit tab is active
  useEffect(() => {
    if (isSuperAdmin && superadminTab === "livekit") {
      fetchLivekitStatus();
    }
  }, [superadminTab, isSuperAdmin]);

  const toggleStatus = (id: string) => {
    toast.info("Status changes are updated automatically via dynamic routing or sold configurations.");
  };

  const handleAgentChange = (id: string, agentId: string) => {
    PhoneNumberService.assignAgent(id, agentId)
      .then(() => {
        const agentName = agents.find(a => a.id === agentId)?.name || "Unassigned";
        toast.success(`DID assigned to AI Agent: ${agentName}`);
        fetchNumbers();
      })
      .catch(() => {
        toast.error("Failed to assign agent routing on backend.");
      });
  };

  // Handlers for edit modal
  const handleOpenEditModal = (item: PhoneNumberItem) => {
    setEditTargetItem(item);
    setEditModalOpen(true);
  };

  // Trigger custom delete modal for complete deletion (Superadmin)
  const handleDeleteClick = (id: string, numStr: string) => {
    setDeleteTargetId(id);
    setDeleteTargetNumStr(numStr);
    setDeleteActionType("delete");
    setDeleteModalOpen(true);
  };

  // Trigger custom delete modal for releasing leased number (Client)
  const handleReleaseClick = (id: string, numStr: string) => {
    setDeleteTargetId(id);
    setDeleteTargetNumStr(numStr);
    setDeleteActionType("release");
    setDeleteModalOpen(true);
  };

  // Execute actual deletion/release inside standard ConfirmDeleteModal callback
  const handleConfirmDeleteAction = () => {
    setDeleteLoading(true);
    PhoneNumberService.release(deleteTargetId)
      .then(() => {
        toast.success(
          deleteActionType === "delete"
            ? `Deleted phone number ${deleteTargetNumStr} successfully`
            : `Released line ${deleteTargetNumStr} back to public pool.`
        );
        setDeleteModalOpen(false);
        fetchNumbers();
      })
      .catch(() => {
        toast.error("Action failed.");
      })
      .finally(() => {
        setDeleteLoading(false);
      });
  };

  // Handle Client purchasing an available line
  const handlePurchaseAction = async (id: string, friendlyName: string, agentId: string) => {
    try {
      await PhoneNumberService.lease(id, {
        name: friendlyName,
        agentId: agentId
      });
      toast.success("Successfully purchased voice line!");
      setActiveTab("numbers");
      fetchNumbers();
    } catch {
      toast.error("Failed to purchase phone line.");
      throw new Error("Failed to purchase line");
    }
  };

  // Filtering based on search query
  const filteredNumbers = numbers.filter(num => {
    const query = searchQuery.toLowerCase();
    return (
      num.number.toLowerCase().includes(query) ||
      num.name.toLowerCase().includes(query) ||
      num.provider.toLowerCase().includes(query) ||
      (num.ownerName && num.ownerName.toLowerCase().includes(query))
    );
  });

  // Split logic based on roles
  const publishedNumbers = filteredNumbers.filter(n => n.status === "available" || n.status === "active");
  const draftNumbers = filteredNumbers.filter(n => n.status === "pending_sip" || n.status === "inactive");
  const disconnectedNumbers = filteredNumbers.filter(
    n => !n.sipConfig || !n.sipConfig.password || !n.sipConfig.domain || n.status === "pending_sip" || n.status === "inactive"
  );
  const clientNumbers = filteredNumbers.filter(num => num.ownerId === (user?.clientId || user?.id || "client-123"));
  const availableToRent = filteredNumbers.filter(num => num.status === "available");

  return (
    <div className="space-y-6" data-testid="phone-numbers-page">
      {/* Header section */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-zinc-200 pb-5">
        <div>
          <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-widest bg-zinc-100 px-2 py-0.5 rounded-sm">DID Portal</span>
          <h1 className="text-2xl font-bold text-zinc-950 mt-1 font-display tracking-tight">
            Phone Numbers
          </h1>
          <p className="text-xs text-zinc-500 mt-0.5">
            {isSuperAdmin 
              ? "Register, publish, and monitor phone numbers across client accounts."
              : "Manage your active voice lines, configure agent routing, and purchase new numbers."
            }
          </p>
        </div>
      </div>

      {/* SUPERADMIN INTERFACE */}
      {isSuperAdmin && (
        <div className="space-y-6">
          {/* Superadmin KPIs */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white border border-zinc-200 p-4 rounded-sm shadow-xs">
              <p className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider">Total Registered DIDs</p>
              <h3 className="text-xl font-bold text-zinc-950 mt-1 font-mono-stat">{numbers.length}</h3>
            </div>
            <div className="bg-white border border-zinc-200 p-4 rounded-sm shadow-xs">
              <p className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider">Sold DIDs</p>
              <h3 className="text-xl font-bold text-zinc-950 mt-1 font-mono-stat">
                {numbers.filter(n => n.status === "active").length}
              </h3>
            </div>
            <div className="bg-white border border-zinc-200 p-4 rounded-sm shadow-xs">
              <p className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider">Available DIDs</p>
              <h3 className="text-xl font-bold text-emerald-600 mt-1 font-mono-stat">
                {numbers.filter(n => n.status === "available").length}
              </h3>
            </div>
            <div className="bg-white border border-zinc-200 p-4 rounded-sm shadow-xs">
              <p className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider">Estimated System Yield</p>
              <h3 className="text-xl font-bold text-zinc-950 mt-1 font-mono-stat">
                ${numbers
                  .filter(n => n.status === "active")
                  .reduce((acc, n) => acc + parseFloat(n.monthlyCost.replace("$", "")), 0)
                  .toFixed(2)}/mo
              </h3>
            </div>
          </div>

          {/* Superadmin Tabs */}
          <div className="border-b border-zinc-200 flex gap-6 text-sm font-medium">
            <button
              onClick={() => setSuperadminTab("published")}
              className={`pb-3 border-b-2 transition-all ${
                superadminTab === "published" 
                  ? "border-zinc-950 text-zinc-950 font-bold" 
                  : "border-transparent text-zinc-500 hover:text-zinc-950"
              }`}
            >
              Published Numbers ({publishedNumbers.length})
            </button>
            <button
              onClick={() => setSuperadminTab("drafts")}
              className={`pb-3 border-b-2 transition-all ${
                superadminTab === "drafts" 
                  ? "border-zinc-950 text-zinc-950 font-bold" 
                  : "border-transparent text-zinc-500 hover:text-zinc-950"
              }`}
            >
              Draft Numbers ({draftNumbers.length})
            </button>
            <button
              onClick={() => setSuperadminTab("disconnected")}
              className={`pb-3 border-b-2 transition-all ${
                superadminTab === "disconnected" 
                  ? "border-zinc-950 text-zinc-950 font-bold" 
                  : "border-transparent text-zinc-500 hover:text-zinc-950"
              }`}
            >
              Not Connected to LiveKit ({disconnectedNumbers.length})
            </button>
            <button
              onClick={() => setSuperadminTab("livekit")}
              className={`pb-3 border-b-2 transition-all flex items-center gap-1.5 ${
                superadminTab === "livekit" 
                  ? "border-zinc-950 text-zinc-950 font-bold" 
                  : "border-transparent text-zinc-500 hover:text-zinc-950"
              }`}
            >
              <Server className="w-3.5 h-3.5" />
              <span>LiveKit SIP Monitor</span>
              <span className={`h-2 w-2 rounded-full ${
                livekitStatus?.connected ? "bg-emerald-500 animate-pulse" : "bg-zinc-300"
              }`} />
            </button>
          </div>

          {/* REGISTERED DIDs TABLE */}
          <div className="space-y-4">
            <div className="flex justify-between items-center gap-3">
              {/* Search Bar */}
              <div className="relative max-w-sm w-full">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
                <input
                  type="text"
                  placeholder="Search DIDs, friendly names, or clients..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-white border border-zinc-200 rounded-sm pl-9 pr-3 py-1.5 text-xs focus:outline-none focus:border-zinc-950"
                />
              </div>

              <button
                onClick={() => navigate("/phone-numbers/add")}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-950 text-white hover:bg-zinc-800 text-xs font-semibold rounded-sm transition-colors shadow-xs"
              >
                <Plus className="w-4 h-4" />
                <span>Register Purchased DID</span>
              </button>
            </div>

            {/* TAB CONTENTS (Superadmin) */}
            {superadminTab === "published" && (
              <PublishedTab
                numbers={publishedNumbers}
                onEdit={handleOpenEditModal}
                onDelete={handleDeleteClick}
              />
            )}

            {superadminTab === "drafts" && (
              <DraftsTab
                numbers={draftNumbers}
                onEdit={handleOpenEditModal}
                onDelete={handleDeleteClick}
              />
            )}

            {superadminTab === "disconnected" && (
              <DisconnectedTab
                numbers={disconnectedNumbers}
                onEdit={handleOpenEditModal}
                onDelete={handleDeleteClick}
              />
            )}

            {superadminTab === "livekit" && (
              <LiveKitMonitorTab
                livekitStatus={livekitStatus}
                isLivekitLoading={isLivekitLoading}
                fetchLivekitStatus={fetchLivekitStatus}
              />
            )}
          </div>
        </div>
      )}

      {/* CLIENT / CUSTOMER INTERFACE */}
      {!isSuperAdmin && (
        <div className="space-y-6">
          {/* Client Tabs */}
          <div className="border-b border-zinc-200 flex gap-6 text-sm font-medium">
            <button
              onClick={() => setActiveTab("numbers")}
              className={`pb-3 border-b-2 transition-all ${
                activeTab === "numbers" 
                  ? "border-zinc-950 text-zinc-950 font-bold" 
                  : "border-transparent text-zinc-500 hover:text-zinc-950"
              }`}
            >
              My Purchased Numbers ({clientNumbers.length})
            </button>
            <button
              onClick={() => setActiveTab("browse")}
              className={`pb-3 border-b-2 transition-all ${
                activeTab === "browse" 
                  ? "border-zinc-950 text-zinc-950 font-bold" 
                  : "border-transparent text-zinc-500 hover:text-zinc-950"
              }`}
            >
              Browse & Buy Lines ({availableToRent.length})
            </button>
          </div>

          {/* TAB CONTENTS (Client) */}
          {activeTab === "numbers" && (
            <ClientOwnedTab
              numbers={clientNumbers}
              agents={agents}
              searchQuery={searchQuery}
              setSearchQuery={setSearchQuery}
              onAgentChange={handleAgentChange}
              onRelease={handleReleaseClick}
              onToggleStatus={toggleStatus}
              onBrowseRedirect={() => setActiveTab("browse")}
            />
          )}

          {activeTab === "browse" && (
            <ClientBrowseTab
              availableNumbers={availableToRent}
              agents={agents}
              searchQuery={searchQuery}
              setSearchQuery={setSearchQuery}
              onPurchase={handlePurchaseAction}
            />
          )}
        </div>
      )}

      {/* EDIT PHONE NUMBER DETAILS DIALOG */}
      <EditNumberModal
        open={editModalOpen}
        onClose={() => {
          setEditModalOpen(false);
          setEditTargetItem(null);
        }}
        numberItem={editTargetItem}
        onSave={fetchNumbers}
      />

      {/* DESTRICTION CONFIRMATION MODAL */}
      <ConfirmDeleteModal
        open={deleteModalOpen}
        onClose={() => {
          setDeleteModalOpen(false);
          setDeleteTargetId("");
          setDeleteTargetNumStr("");
        }}
        onConfirm={handleConfirmDeleteAction}
        loading={deleteLoading}
        entityName={deleteTargetNumStr}
        entityLabel="phone line"
        warningNote={
          deleteActionType === "delete"
            ? "This will completely delete and deprovision the phone line from the system database and LiveKit SIP registrar configs."
            : "This will release the phone line back to the public pool so it can be purchased by other client accounts."
        }
      />
    </div>
  );
}
