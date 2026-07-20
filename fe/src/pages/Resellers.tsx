import { Reseller } from "@/types";
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fmtDate } from "@/services/api";
import ResellerService, { CreateResellerDto, UpdateResellerDto } from "@/services/reseller.service";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import StatusBadge from "@/components/StatusBadge";
import AppModal from "@/components/AppModal";
import ConfirmDeleteModal from "@/components/ConfirmDeleteModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Plus, Copy, Check, Eye, Edit, Trash2 } from "lucide-react";
import { toast } from "sonner";

export default function Resellers() {
  const [rows, setRows] = useState<Reseller[]>([]);

  // Modal open states
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);

  const [loading, setLoading] = useState(false);
  const [selectedPartner, setSelectedPartner] = useState<Reseller | null>(null);

  // Add form
  const [name, setName] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [country, setCountry] = useState("");
  const [commissionPct, setCommissionPct] = useState("10");

  // Edit form
  const [editName, setEditName] = useState("");
  const [editContactEmail, setEditContactEmail] = useState("");
  const [editCountry, setEditCountry] = useState("");
  const [editCommissionPct, setEditCommissionPct] = useState("");
  const [editStatus, setEditStatus] = useState<"active" | "inactive">("active");

  // Credentials shown after creation
  const [credentials, setCredentials] = useState<{ email: string; password?: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const nav = useNavigate();

  // ── Data fetching ──────────────────────────────────────────────────────────

  const fetchResellers = async () => {
    try {
      setRows(await ResellerService.getAll());
    } catch {
      /* silently show empty state */
    }
  };

  useEffect(() => { fetchResellers(); }, []);

  // ── Close helpers (reset state on close) ──────────────────────────────────

  const closeAdd = () => {
    setIsAddOpen(false);
    setName(""); setContactEmail(""); setCountry(""); setCommissionPct("10");
    setCredentials(null); setCopied(false);
  };

  const closeEdit = () => {
    setIsEditOpen(false);
    setSelectedPartner(null);
    setEditName(""); setEditContactEmail(""); setEditCountry(""); setEditCommissionPct("");
    setEditStatus("active");
  };

  const closeDelete = () => {
    setIsDeleteOpen(false);
    setSelectedPartner(null);
  };

  // ── Row action triggers ────────────────────────────────────────────────────

  const handleEdit = (r: Reseller) => {
    setSelectedPartner(r);
    setEditName(r.name);
    setEditContactEmail(r.contactEmail);
    setEditCountry(r.country);
    setEditCommissionPct(r.commissionPct.toString());
    setEditStatus(r.status as "active" | "inactive");
    setIsEditOpen(true);
  };

  const handleDeleteClick = (r: Reseller) => {
    setSelectedPartner(r);
    setIsDeleteOpen(true);
  };

  // ── Form submit handlers ───────────────────────────────────────────────────

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !contactEmail || !country || !commissionPct) {
      return toast.error("Please fill in all required fields.");
    }
    const pct = parseFloat(commissionPct);
    if (isNaN(pct) || pct < 0 || pct > 100) {
      return toast.error("Commission rate must be between 0 and 100.");
    }
    setLoading(true);
    try {
      const dto: CreateResellerDto = { name, contactEmail, country, commissionPct: pct };
      const { credentials: creds } = await ResellerService.create(dto);
      toast.success("Partner added successfully!");
      setCredentials(creds);
      fetchResellers();
    } catch (err: any) {
      toast.error(err?.response?.data?.message ?? "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  };

  const handleEditConfirm = async () => {
    if (!selectedPartner) return;
    if (!editName || !editContactEmail || !editCountry || !editCommissionPct) {
      return toast.error("Please fill in all required fields.");
    }
    const pct = parseFloat(editCommissionPct);
    if (isNaN(pct) || pct < 0 || pct > 100) {
      return toast.error("Commission rate must be between 0 and 100.");
    }
    setLoading(true);
    try {
      const dto: UpdateResellerDto = {
        name: editName, contactEmail: editContactEmail, country: editCountry,
        commissionPct: pct, status: editStatus,
      };
      await ResellerService.update(String(selectedPartner.id), dto);
      toast.success("Partner updated successfully!");
      closeEdit();
      fetchResellers();
    } catch (err: any) {
      toast.error(err?.response?.data?.message ?? "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!selectedPartner) return;
    setLoading(true);
    try {
      await ResellerService.delete(String(selectedPartner.id));
      toast.success("Partner deleted successfully!");
      closeDelete();
      fetchResellers();
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
      key: "name", label: "Partner",
      render: (r: Reseller) => (
        <div>
          <div className="font-medium">{r.name}</div>
          <div className="text-xs text-zinc-500">{r.country}</div>
        </div>
      ),
    },
    {
      key: "commissionPct", label: "Commission",
      render: (r: Reseller) => <span className="font-mono-stat">{r.commissionPct}%</span>,
    },
    {
      key: "contactEmail", label: "Contact",
      render: (r: Reseller) => <span className="text-xs text-zinc-600">{r.contactEmail}</span>,
    },
    {
      key: "status", label: "Status",
      render: (r: Reseller) => <StatusBadge value={r.status} />,
    },
    {
      key: "createdAt", label: "Joined",
      render: (r: Reseller) => <span className="text-xs text-zinc-600">{fmtDate(r.createdAt)}</span>,
    },
    {
      key: "actions", label: "Actions",
      render: (r: Reseller) => (
        <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
          <Button variant="ghost" size="icon" className="w-8 h-8 text-zinc-500 hover:text-zinc-950 hover:bg-zinc-100"
            onClick={() => nav(`/resellers/${r.id}`)} title="View Details">
            <Eye className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="icon" className="w-8 h-8 text-zinc-500 hover:text-zinc-950 hover:bg-zinc-100"
            onClick={() => handleEdit(r)} title="Edit Partner">
            <Edit className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="icon" className="w-8 h-8 text-rose-500 hover:text-rose-700 hover:bg-rose-50"
            onClick={() => handleDeleteClick(r)} title="Delete Partner">
            <Trash2 className="w-4 h-4" />
          </Button>
        </div>
      ),
    },
  ];

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div data-testid="resellers-page">
      <PageHeader
        title="Partners"
        subtitle="Distribution partners worldwide"
        actions={
          <Button onClick={() => setIsAddOpen(true)} className="flex items-center gap-1.5" data-testid="add-reseller-btn">
            <Plus className="w-4 h-4" /> Add Partner
          </Button>
        }
      />

      <DataTable testId="resellers-table" columns={columns} rows={rows} searchKeys={["name", "country"]}
        onRowClick={(r) => nav(`/resellers/${r.id}`)} />

      {/* ── Add Partner Modal ──────────────────────────────────────────────── */}
      <AppModal
        open={isAddOpen}
        onClose={closeAdd}
        title={credentials ? "Partner Added Successfully" : "Add Distribution Partner"}
        showFooter={false}       /* form owns its own footer */
      >
        {!credentials ? (
          <form onSubmit={handleAddSubmit} className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="partner-name">Partner Name</Label>
              <Input id="partner-name" placeholder="e.g. Global Distribution Corp"
                value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="contact-email">Contact Email</Label>
              <Input id="contact-email" type="email" placeholder="e.g. contact@globaldist.com"
                value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} required />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="country">Country</Label>
              <Input id="country" placeholder="e.g. Germany"
                value={country} onChange={(e) => setCountry(e.target.value)} required />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="commission">Commission Rate (%)</Label>
              <Input id="commission" type="number" min="0" max="100" step="0.1" placeholder="e.g. 15"
                value={commissionPct} onChange={(e) => setCommissionPct(e.target.value)} required />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={closeAdd}>Cancel</Button>
              <Button type="submit" disabled={loading}>{loading ? "Adding…" : "Add Partner"}</Button>
            </div>
          </form>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-zinc-500">
              The partner has been registered. Share these temporary credentials securely.
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

      {/* ── Edit Partner Modal ─────────────────────────────────────────────── */}
      <AppModal
        open={isEditOpen}
        onClose={closeEdit}
        title="Edit Distribution Partner"
        showFooter={false}       /* form owns its own footer */
      >
        <form onSubmit={(e) => { e.preventDefault(); handleEditConfirm(); }} className="space-y-4">
          <div className="grid gap-2">
            <Label htmlFor="edit-name">Partner Name</Label>
            <Input id="edit-name" value={editName} onChange={(e) => setEditName(e.target.value)} required />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="edit-email">Contact Email</Label>
            <Input id="edit-email" type="email" value={editContactEmail}
              onChange={(e) => setEditContactEmail(e.target.value)} required />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="edit-country">Country</Label>
            <Input id="edit-country" value={editCountry} onChange={(e) => setEditCountry(e.target.value)} required />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="edit-commission">Commission Rate (%)</Label>
            <Input id="edit-commission" type="number" min="0" max="100" step="0.1"
              value={editCommissionPct} onChange={(e) => setEditCommissionPct(e.target.value)} required />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="edit-status">Status</Label>
            <select
              id="edit-status"
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-base shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring md:text-sm"
              value={editStatus}
              onChange={(e) => setEditStatus(e.target.value as "active" | "inactive")}
            >
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </div>
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
        entityName={selectedPartner?.name}
        entityLabel="partner"
        warningNote="Their linked login credentials will also be permanently removed."
      />
    </div>
  );
}
