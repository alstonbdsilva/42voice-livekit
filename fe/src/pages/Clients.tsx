import { Client, Reseller } from "@/types";
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fmtCurrency, fmtDate } from "@/services/api";
import ClientService, { CreateClientDto, UpdateClientDto } from "@/services/client.service";
import ResellerService from "@/services/reseller.service";
import { useAuth } from "@/store/authStore";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import StatusBadge from "@/components/StatusBadge";
import AppModal from "@/components/AppModal";
import ConfirmDeleteModal from "@/components/ConfirmDeleteModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Plus, Eye, Edit, Trash2, Copy, Check } from "lucide-react";
import { toast } from "sonner";

export default function Clients() {
  const { user } = useAuth();
  const nav = useNavigate();

  const isAdmin = user?.role === "super_admin" || user?.role === "finance_admin";
  const isReseller = user?.role === "reseller";

  const [rows, setRows] = useState<Client[]>([]);
  const [resellers, setResellers] = useState<Reseller[]>([]);

  // Modal state
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Client | null>(null);

  // Add form
  const [addName, setAddName] = useState("");
  const [addEmail, setAddEmail] = useState("");
  const [addIndustry, setAddIndustry] = useState("");
  const [addCountry, setAddCountry] = useState("");
  const [addMrr, setAddMrr] = useState("0");
  const [addResellerId, setAddResellerId] = useState("");

  // Edit form
  const [editName, setEditName] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [editIndustry, setEditIndustry] = useState("");
  const [editCountry, setEditCountry] = useState("");
  const [editMrr, setEditMrr] = useState("0");
  const [editStatus, setEditStatus] = useState<"active" | "paused" | "inactive">("active");
  const [editResellerId, setEditResellerId] = useState("");

  // Credentials shown after creation
  const [credentials, setCredentials] = useState<{ email: string; password?: string } | null>(null);
  const [copied, setCopied] = useState(false);

  // ── Data fetching ──────────────────────────────────────────────────────────

  const fetchClients = async () => {
    try { setRows(await ClientService.getAll()); } catch { /* empty state */ }
  };

  useEffect(() => {
    fetchClients();
    // Fetch resellers for admin dropdown
    if (isAdmin) {
      ResellerService.getAll()
        .then(setResellers)
        .catch(() => { });
    }
  }, [isAdmin]);

  // ── Close helpers ──────────────────────────────────────────────────────────

  const closeAdd = () => {
    setIsAddOpen(false);
    setAddName(""); setAddEmail(""); setAddIndustry(""); setAddCountry(""); setAddMrr("0"); setAddResellerId("");
    setCredentials(null); setCopied(false);
  };

  const closeEdit = () => {
    setIsEditOpen(false);
    setSelected(null);
    setEditName(""); setEditEmail(""); setEditIndustry(""); setEditCountry(""); setEditMrr("0");
    setEditStatus("active"); setEditResellerId("");
  };

  const closeDelete = () => { setIsDeleteOpen(false); setSelected(null); };

  // ── Row action triggers ────────────────────────────────────────────────────

  const handleEdit = (r: Client) => {
    setSelected(r);
    setEditName(r.name);
    setEditEmail(r.contactEmail);
    setEditIndustry(r.industry ?? "");
    setEditCountry(r.country ?? "");
    setEditMrr(r.monthlyRecurring.toString());
    setEditStatus((r.status as any) ?? "active");
    setEditResellerId(r.resellerId ? String(r.resellerId) : "");
    setIsEditOpen(true);
  };

  const handleDeleteClick = (r: Client) => { setSelected(r); setIsDeleteOpen(true); };

  // ── Form submit handlers ───────────────────────────────────────────────────

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!addName || !addEmail) return toast.error("Name and contact email are required.");

    // Determine resellerId: admin must pick one; reseller uses their own ID
    const resellerId = isReseller ? String(user?.resellerId ?? "") : addResellerId;
    if (!resellerId) return toast.error("Please select a reseller for this client.");

    setLoading(true);
    try {
      const dto: CreateClientDto = {
        name: addName,
        contactEmail: addEmail,
        industry: addIndustry,
        country: addCountry,
        monthlyRecurring: parseFloat(addMrr) || 0,
        resellerId,
      };
      const { credentials: creds } = await ClientService.create(dto);
      toast.success("Client added successfully!");
      setCredentials(creds);
      fetchClients();
    } catch (err: any) {
      toast.error(err?.response?.data?.message ?? "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  };

  const handleEditConfirm = async () => {
    if (!selected) return;
    if (!editName || !editEmail) return toast.error("Name and contact email are required.");

    setLoading(true);
    try {
      const dto: UpdateClientDto = {
        name: editName,
        contactEmail: editEmail,
        industry: editIndustry,
        country: editCountry,
        monthlyRecurring: parseFloat(editMrr) || 0,
        status: editStatus,
        // Resellers cannot change the resellerId — only admins can
        ...(isAdmin && editResellerId ? { resellerId: editResellerId } : {}),
      };
      await ClientService.update(String(selected.id), dto);
      toast.success("Client updated successfully!");
      closeEdit();
      fetchClients();
    } catch (err: any) {
      toast.error(err?.response?.data?.message ?? "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!selected) return;
    setLoading(true);
    try {
      await ClientService.delete(String(selected.id));
      toast.success("Client deleted successfully!");
      closeDelete();
      fetchClients();
    } catch (err: any) {
      toast.error(err?.response?.data?.message ?? "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (credentials?.password) {
      navigator.clipboard.writeText(credentials.password);
      setCopied(true);
      toast.success("Password copied to clipboard.");
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // ── Table columns ──────────────────────────────────────────────────────────

  const columns = [
    {
      key: "name", label: "Client",
      render: (r: Client) => (
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-sm bg-zinc-200 flex items-center justify-center text-xs font-display font-bold text-zinc-700">
            {r.name?.[0]}
          </div>
          <div>
            <div className="font-medium text-zinc-950">{r.name}</div>
            <div className="text-xs text-zinc-500">{r.industry} {r.country ? `• ${r.country}` : ""}</div>
          </div>
        </div>
      ),
    },
    {
      key: "monthlyRecurring", label: "MRR",
      render: (r: Client) => <span className="font-mono-stat">{fmtCurrency(r.monthlyRecurring)}</span>,
    },
    {
      key: "contactEmail", label: "Contact",
      render: (r: Client) => <span className="text-xs text-zinc-600">{r.contactEmail}</span>,
    },
    {
      key: "status", label: "Status",
      render: (r: Client) => <StatusBadge value={r.status} />,
    },
    {
      key: "createdAt", label: "Joined",
      render: (r: Client) => <span className="text-xs text-zinc-600">{fmtDate(r.createdAt)}</span>,
    },
    {
      key: "actions", label: "Actions",
      render: (r: Client) => (
        <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
          <Button variant="ghost" size="icon" className="w-8 h-8 text-zinc-500 hover:text-zinc-950 hover:bg-zinc-100"
            onClick={() => nav(`/clients/${r.id}`)} title="View Details">
            <Eye className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="icon" className="w-8 h-8 text-zinc-500 hover:text-zinc-950 hover:bg-zinc-100"
            onClick={() => handleEdit(r)} title="Edit Client">
            <Edit className="w-4 h-4" />
          </Button>
          {isAdmin && (
            <Button variant="ghost" size="icon" className="w-8 h-8 text-rose-500 hover:text-rose-700 hover:bg-rose-50"
              onClick={() => handleDeleteClick(r)} title="Delete Client">
              <Trash2 className="w-4 h-4" />
            </Button>
          )}
        </div>
      ),
    },
  ];

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div data-testid="clients-page">
      <PageHeader
        title="Clients"
        subtitle={`${rows.length} accounts across your portfolio`}
        actions={
          <Button onClick={() => setIsAddOpen(true)} className="flex items-center gap-1.5" data-testid="add-client-btn">
            <Plus className="w-4 h-4" /> Add Client
          </Button>
        }
      />

      <DataTable
        testId="clients-table"
        columns={columns}
        rows={rows}
        searchKeys={["name", "industry", "country", "contactEmail"]}
        filters={[{
          key: "status", label: "Status", options: [
            { value: "active", label: "Active" },
            { value: "paused", label: "Paused" },
          ]
        }]}
        onRowClick={(r) => nav(`/clients/${r.id}`)}
      />

      {/* ── Add Client Modal ───────────────────────────────────────────────── */}
      <AppModal
        open={isAddOpen}
        onClose={closeAdd}
        title={credentials ? "Client Added Successfully" : "Add Client"}
        showFooter={false}
      >
        {!credentials ? (
          <form onSubmit={handleAddSubmit} className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="add-client-name">Client Name *</Label>
              <Input id="add-client-name" placeholder="e.g. Acme Corp"
                value={addName} onChange={(e) => setAddName(e.target.value)} required />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="add-client-email">Contact Email *</Label>
              <Input id="add-client-email" type="email" placeholder="e.g. contact@acme.com"
                value={addEmail} onChange={(e) => setAddEmail(e.target.value)} required />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="grid gap-2">
                <Label htmlFor="add-client-industry">Industry</Label>
                <Input id="add-client-industry" placeholder="e.g. SaaS"
                  value={addIndustry} onChange={(e) => setAddIndustry(e.target.value)} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="add-client-country">Country</Label>
                <Input id="add-client-country" placeholder="e.g. Germany"
                  value={addCountry} onChange={(e) => setAddCountry(e.target.value)} />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="add-client-mrr">Monthly Recurring Revenue ($)</Label>
              <Input id="add-client-mrr" type="number" min="0" step="0.01" placeholder="0.00"
                value={addMrr} onChange={(e) => setAddMrr(e.target.value)} />
            </div>

            {/* Reseller selection — admins pick; resellers see their own name */}
            {isAdmin ? (
              <div className="grid gap-2">
                <Label htmlFor="add-client-reseller">Reseller *</Label>
                <select
                  id="add-client-reseller"
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-base shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring md:text-sm"
                  value={addResellerId}
                  onChange={(e) => setAddResellerId(e.target.value)}
                  required
                >
                  <option value="">Select a reseller…</option>
                  {resellers.map((r) => (
                    <option key={String(r.id)} value={String(r.id)}>{r.name}</option>
                  ))}
                </select>
              </div>
            ) : isReseller ? (
              <div className="grid gap-2">
                <Label>Reseller</Label>
                <div className="flex h-9 w-full items-center rounded-md border border-input bg-zinc-50 px-3 text-sm text-zinc-500">
                  {user?.name} <span className="ml-1.5 text-xs text-zinc-400">(auto-assigned)</span>
                </div>
              </div>
            ) : null}

            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={closeAdd}>Cancel</Button>
              <Button type="submit" disabled={loading}>{loading ? "Adding…" : "Add Client"}</Button>
            </div>
          </form>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-zinc-500">
              The client has been registered. Share these temporary login credentials securely.
            </p>
            <div className="p-4 bg-zinc-50 border border-zinc-200 rounded-md space-y-2.5 font-mono text-sm">
              <div className="flex justify-between items-center">
                <span className="text-zinc-500 text-xs uppercase font-sans font-semibold">Email</span>
                <span className="font-medium text-zinc-900 select-all">{credentials.email}</span>
              </div>
              <div className="flex justify-between items-center border-t border-zinc-200 pt-2.5">
                <span className="text-zinc-500 text-xs uppercase font-sans font-semibold">Temp Password</span>
                <div className="flex items-center gap-1.5">
                  <span className="font-medium text-zinc-900 select-all">{credentials.password}</span>
                  <button type="button" onClick={handleCopy}
                    className="text-zinc-500 hover:text-zinc-800 p-1 rounded transition-colors">
                    {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>
            </div>
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-md">
              <p className="text-xs text-amber-800 leading-normal">
                <strong>Warning:</strong> No email has been sent. The password will not be shown again.
              </p>
            </div>
            <div className="flex justify-end pt-1">
              <Button type="button" onClick={closeAdd}>Done</Button>
            </div>
          </div>
        )}
      </AppModal>

      {/* ── Edit Client Modal ──────────────────────────────────────────────── */}
      <AppModal
        open={isEditOpen}
        onClose={closeEdit}
        title="Edit Client"
        showFooter={false}
      >
        <form onSubmit={(e) => { e.preventDefault(); handleEditConfirm(); }} className="space-y-4">
          <div className="grid gap-2">
            <Label htmlFor="edit-client-name">Client Name *</Label>
            <Input id="edit-client-name" value={editName} onChange={(e) => setEditName(e.target.value)} required />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="edit-client-email">Contact Email *</Label>
            <Input id="edit-client-email" type="email" value={editEmail} onChange={(e) => setEditEmail(e.target.value)} required />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <Label htmlFor="edit-client-industry">Industry</Label>
              <Input id="edit-client-industry" value={editIndustry} onChange={(e) => setEditIndustry(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-client-country">Country</Label>
              <Input id="edit-client-country" value={editCountry} onChange={(e) => setEditCountry(e.target.value)} />
            </div>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="edit-client-mrr">Monthly Recurring Revenue ($)</Label>
            <Input id="edit-client-mrr" type="number" min="0" step="0.01"
              value={editMrr} onChange={(e) => setEditMrr(e.target.value)} />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="edit-client-status">Status</Label>
            <select id="edit-client-status"
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-base shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring md:text-sm"
              value={editStatus} onChange={(e) => setEditStatus(e.target.value as any)}>
              <option value="active">Active</option>
              <option value="paused">Paused</option>
              <option value="inactive">Inactive</option>
            </select>
          </div>

          {/* Admins can reassign reseller; resellers cannot */}
          {isAdmin && (
            <div className="grid gap-2">
              <Label htmlFor="edit-client-reseller">Reseller</Label>
              <select id="edit-client-reseller"
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-base shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring md:text-sm"
                value={editResellerId} onChange={(e) => setEditResellerId(e.target.value)}>
                <option value="">No change</option>
                {resellers.map((r) => (
                  <option key={String(r.id)} value={String(r.id)}>{r.name}</option>
                ))}
              </select>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={closeEdit}>Cancel</Button>
            <Button type="submit" disabled={loading}>{loading ? "Saving…" : "Save Changes"}</Button>
          </div>
        </form>
      </AppModal>

      {/* ── Delete Confirmation Modal ──────────────────────────────────────── */}
      <ConfirmDeleteModal
        open={isDeleteOpen}
        onClose={closeDelete}
        onConfirm={handleDeleteConfirm}
        loading={loading}
        entityName={selected?.name}
        entityLabel="client"
        warningNote="All data associated with this client will be permanently removed."
      />
    </div>
  );
}
