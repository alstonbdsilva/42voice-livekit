import { User, Client, Reseller } from "@/types";
import React, { useEffect, useState } from "react";
import { fmtDateTime } from "@/services/api";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import UserService, { CreateUserDto, UpdateUserDto } from "@/services/user.service";
import ClientService from "@/services/client.service";
import ResellerService from "@/services/reseller.service";
import AppModal from "@/components/AppModal";
import ConfirmDeleteModal from "@/components/ConfirmDeleteModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Plus, Edit, Trash2, Copy, Check } from "lucide-react";
import { toast } from "sonner";

export default function Users() {
  const [rows, setRows] = useState<User[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [resellers, setResellers] = useState<Reseller[]>([]);

  // Modal visibility state
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<User | null>(null);

  // Add User form state
  const [addEmail, setAddEmail] = useState("");
  const [addFirstName, setAddFirstName] = useState("");
  const [addLastName, setAddLastName] = useState("");
  const [addPhone, setAddPhone] = useState("");
  const [addRoleName, setAddRoleName] = useState<"SUPER_ADMIN" | "FINANCE_ADMIN" | "RESELLER" | "CLIENT">("CLIENT");
  const [addResellerId, setAddResellerId] = useState("");
  const [addClientId, setAddClientId] = useState("");

  // Edit User form state
  const [editEmail, setEditEmail] = useState("");
  const [editFirstName, setEditFirstName] = useState("");
  const [editLastName, setEditLastName] = useState("");
  const [editPhone, setEditPhone] = useState("");
  const [editRoleName, setEditRoleName] = useState<"SUPER_ADMIN" | "FINANCE_ADMIN" | "RESELLER" | "CLIENT">("CLIENT");
  const [editResellerId, setEditResellerId] = useState("");
  const [editClientId, setEditClientId] = useState("");
  const [editStatus, setEditStatus] = useState<"active" | "inactive">("active");

  // Temporary credentials feedback
  const [credentials, setCredentials] = useState<{ email: string; password?: string } | null>(null);
  const [copied, setCopied] = useState(false);

  // ── Data Fetching ──────────────────────────────────────────────────────────

  const fetchUsers = async () => {
    try {
      const data = await UserService.getAll();
      setRows(data);
    } catch {
      toast.error("Failed to load user list.");
    }
  };

  const fetchDropdowns = async () => {
    try {
      const [resellersData, clientsData] = await Promise.all([
        ResellerService.getAll(),
        ClientService.getAll()
      ]);
      setResellers(resellersData);
      setClients(clientsData);
    } catch {
      toast.error("Failed to load reference resellers or clients.");
    }
  };

  useEffect(() => {
    fetchUsers();
    fetchDropdowns();
  }, []);

  // ── Close Helpers ──────────────────────────────────────────────────────────

  const closeAdd = () => {
    setIsAddOpen(false);
    setAddEmail("");
    setAddFirstName("");
    setAddLastName("");
    setAddPhone("");
    setAddRoleName("CLIENT");
    setAddResellerId("");
    setAddClientId("");
    setCredentials(null);
    setCopied(false);
  };

  const closeEdit = () => {
    setIsEditOpen(false);
    setSelected(null);
    setEditEmail("");
    setEditFirstName("");
    setEditLastName("");
    setEditPhone("");
    setEditRoleName("CLIENT");
    setEditResellerId("");
    setEditClientId("");
    setEditStatus("active");
  };

  const closeDelete = () => {
    setIsDeleteOpen(false);
    setSelected(null);
  };

  // ── Action Triggers ────────────────────────────────────────────────────────

  const handleEdit = (r: User) => {
    setSelected(r);
    setEditEmail(r.email);
    // Split the name if name is present
    const nameParts = r.name.split(" ");
    setEditFirstName(nameParts[0] || "");
    setEditLastName(nameParts.slice(1).join(" ") || "");
    setEditPhone(r.phone ?? "");
    
    // Map backend lowercase role string back to uppercase enum
    const uppercaseRole = r.role.toUpperCase() as "SUPER_ADMIN" | "FINANCE_ADMIN" | "RESELLER" | "CLIENT";
    setEditRoleName(uppercaseRole);

    setEditResellerId(r.resellerId ? String(r.resellerId) : "");
    setEditClientId(r.clientId ? String(r.clientId) : "");
    setEditStatus(r.status === "inactive" ? "inactive" : "active");
    setIsEditOpen(true);
  };

  const handleDeleteClick = (r: User) => {
    setSelected(r);
    setIsDeleteOpen(true);
  };

  // ── Form Submit Handlers ───────────────────────────────────────────────────

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!addEmail || !addFirstName || !addLastName) {
      return toast.error("Required fields: Email, First Name, Last Name.");
    }

    setLoading(true);
    try {
      const dto: CreateUserDto = {
        email: addEmail,
        firstName: addFirstName,
        lastName: addLastName,
        phone: addPhone || undefined,
        roleName: addRoleName,
        resellerId: (addRoleName === "RESELLER" || addRoleName === "CLIENT") && addResellerId ? addResellerId : null,
        clientId: addRoleName === "CLIENT" && addClientId ? addClientId : null,
      };

      const response = await UserService.create(dto);
      toast.success("User invited successfully!");
      setCredentials(response.credentials);
      fetchUsers();
    } catch (err: any) {
      toast.error(err?.response?.data?.message ?? "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  };

  const handleEditConfirm = async () => {
    if (!selected) return;
    if (!editEmail || !editFirstName || !editLastName) {
      return toast.error("Required fields: Email, First Name, Last Name.");
    }

    setLoading(true);
    try {
      const dto: UpdateUserDto = {
        email: editEmail,
        firstName: editFirstName,
        lastName: editLastName,
        phone: editPhone || null,
        roleName: editRoleName,
        resellerId: (editRoleName === "RESELLER" || editRoleName === "CLIENT") && editResellerId ? editResellerId : null,
        clientId: editRoleName === "CLIENT" && editClientId ? editClientId : null,
        isActive: editStatus === "active",
      };

      await UserService.update(String(selected.id), dto);
      toast.success("User updated successfully!");
      closeEdit();
      fetchUsers();
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
      await UserService.delete(String(selected.id));
      toast.success("User deleted successfully!");
      closeDelete();
      fetchUsers();
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

  // ── Table Columns ──────────────────────────────────────────────────────────

  const columns = [
    {
      key: "name",
      label: "Name",
      render: (r: User) => (
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-sm bg-zinc-200 flex items-center justify-center text-xs font-display font-bold text-zinc-700 uppercase">
            {r.name?.[0] || "?"}
          </div>
          <div>
            <div className="font-medium text-zinc-950">{r.name}</div>
            {r.phone && <div className="text-xs text-zinc-500">{r.phone}</div>}
          </div>
        </div>
      ),
    },
    {
      key: "email",
      label: "Email",
      render: (r: User) => <span className="font-mono-stat text-xs">{r.email}</span>,
    },
    {
      key: "role",
      label: "Role",
      render: (r: User) => (
        <span className="px-2 py-0.5 bg-zinc-100 text-[10px] font-mono-stat rounded-sm uppercase">
          {r.role.replace("_", " ")}
        </span>
      ),
    },
    {
      key: "organisation",
      label: "Organisation / Partner",
      render: (r: User) => {
        if (r.role === "reseller" && r.resellerName) {
          return <span className="text-xs font-medium text-zinc-700">{r.resellerName}</span>;
        }
        if (r.role === "client" && r.clientName) {
          return (
            <div className="text-xs">
              <span className="font-medium text-zinc-700">{r.clientName}</span>
              {r.resellerName && <span className="text-[10px] text-zinc-400 block font-normal">via {r.resellerName}</span>}
            </div>
          );
        }
        return <span className="text-xs text-zinc-400">—</span>;
      },
    },
    {
      key: "status",
      label: "Status",
      render: (r: User) => (
        <span
          className={`px-2 py-0.5 text-[10px] font-mono-stat rounded-sm uppercase ${
            r.status === "active"
              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
              : "bg-rose-50 text-rose-700 border border-rose-200"
          }`}
        >
          {r.status || "active"}
        </span>
      ),
    },
    {
      key: "createdAt",
      label: "Created",
      render: (r: User) => <span className="text-xs">{fmtDateTime(r.createdAt)}</span>,
    },
    {
      key: "actions",
      label: "Actions",
      render: (r: User) => (
        <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
          <Button
            variant="ghost"
            size="icon"
            className="w-8 h-8 text-zinc-500 hover:text-zinc-950 hover:bg-zinc-100"
            onClick={() => handleEdit(r)}
            title="Edit User"
          >
            <Edit className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="w-8 h-8 text-rose-500 hover:text-rose-700 hover:bg-rose-50"
            onClick={() => handleDeleteClick(r)}
            title="Delete User"
          >
            <Trash2 className="w-4 h-4" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div data-testid="users-page">
      <PageHeader
        title="User management"
        subtitle={`${rows.length} platform users with assigned roles`}
        actions={
          <Button
            onClick={() => setIsAddOpen(true)}
            className="flex items-center gap-1.5 bg-zinc-950 text-white hover:bg-zinc-800"
          >
            <Plus className="w-4 h-4" />
            <span>Invite User</span>
          </Button>
        }
      />

      <DataTable
        testId="users-table"
        columns={columns}
        rows={rows}
        searchKeys={["name", "email", "resellerName", "clientName"]}
        filters={[
          {
            key: "role",
            label: "Role",
            options: [
              { value: "super_admin", label: "Super Admin" },
              { value: "finance_admin", label: "Finance" },
              { value: "reseller", label: "Reseller" },
              { value: "client", label: "Client" },
            ],
          },
          {
            key: "status",
            label: "Status",
            options: [
              { value: "active", label: "Active" },
              { value: "inactive", label: "Inactive" },
            ],
          },
        ]}
      />

      {/* ── Add User Modal ─────────────────────────────────────────────────── */}
      <AppModal
        open={isAddOpen}
        onClose={closeAdd}
        title={credentials ? "User Invited Successfully" : "Invite User"}
        showFooter={false}
      >
        {!credentials ? (
          <form onSubmit={handleAddSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="grid gap-2">
                <Label htmlFor="add-user-firstname">First Name *</Label>
                <Input
                  id="add-user-firstname"
                  placeholder="e.g. Jane"
                  value={addFirstName}
                  onChange={(e) => setAddFirstName(e.target.value)}
                  required
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="add-user-lastname">Last Name *</Label>
                <Input
                  id="add-user-lastname"
                  placeholder="e.g. Doe"
                  value={addLastName}
                  onChange={(e) => setAddLastName(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="add-user-email">Email Address *</Label>
              <Input
                id="add-user-email"
                type="email"
                placeholder="e.g. jane.doe@example.com"
                value={addEmail}
                onChange={(e) => setAddEmail(e.target.value)}
                required
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="add-user-phone">Phone Number</Label>
              <Input
                id="add-user-phone"
                placeholder="e.g. +1234567890"
                value={addPhone}
                onChange={(e) => setAddPhone(e.target.value)}
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="add-user-role">Role *</Label>
              <select
                id="add-user-role"
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-base shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring md:text-sm"
                value={addRoleName}
                onChange={(e) => setAddRoleName(e.target.value as any)}
                required
              >
                <option value="SUPER_ADMIN">Super Admin</option>
                <option value="FINANCE_ADMIN">Finance Admin</option>
                <option value="RESELLER">Reseller</option>
                <option value="CLIENT">Client</option>
              </select>
            </div>

            {/* If Client role is selected, first select Reseller, then select Client */}
            {addRoleName === "CLIENT" && (
              <>
                <div className="grid gap-2">
                  <Label htmlFor="add-user-reseller">Reseller *</Label>
                  <select
                    id="add-user-reseller"
                    className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-base shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring md:text-sm"
                    value={addResellerId}
                    onChange={(e) => {
                      setAddResellerId(e.target.value);
                      setAddClientId(""); // Reset client selection on reseller change
                    }}
                    required
                  >
                    <option value="">Select a reseller…</option>
                    {resellers.map((r) => (
                      <option key={String(r.id)} value={String(r.id)}>
                        {r.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="add-user-client">Client Organisation *</Label>
                  <select
                    id="add-user-client"
                    className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-base shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring md:text-sm"
                    value={addClientId}
                    onChange={(e) => setAddClientId(e.target.value)}
                    required
                    disabled={!addResellerId}
                  >
                    <option value="">
                      {addResellerId ? "Select a client…" : "First select a reseller"}
                    </option>
                    {clients
                      .filter((c) => String(c.resellerId) === addResellerId)
                      .map((c) => (
                        <option key={String(c.id)} value={String(c.id)}>
                          {c.name}
                        </option>
                      ))}
                  </select>
                </div>
              </>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={closeAdd}>
                Cancel
              </Button>
              <Button type="submit" disabled={loading}>
                {loading ? "Inviting…" : "Invite User"}
              </Button>
            </div>
          </form>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-zinc-500">
              The user has been registered. Share these temporary login credentials securely.
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
                  <button
                    type="button"
                    onClick={handleCopy}
                    className="text-zinc-500 hover:text-zinc-800 p-1 rounded transition-colors"
                  >
                    {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>
            </div>
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-md">
              <p className="text-xs text-amber-800 leading-normal">
                <strong>Warning:</strong> No automated email has been sent. The password will not be shown again.
              </p>
            </div>
            <div className="flex justify-end pt-1">
              <Button type="button" onClick={closeAdd}>
                Done
              </Button>
            </div>
          </div>
        )}
      </AppModal>

      {/* ── Edit User Modal ────────────────────────────────────────────────── */}
      <AppModal
        open={isEditOpen}
        onClose={closeEdit}
        title="Edit User"
        showFooter={false}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleEditConfirm();
          }}
          className="space-y-4"
        >
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <Label htmlFor="edit-user-firstname">First Name *</Label>
              <Input
                id="edit-user-firstname"
                value={editFirstName}
                onChange={(e) => setEditFirstName(e.target.value)}
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-user-lastname">Last Name *</Label>
              <Input
                id="edit-user-lastname"
                value={editLastName}
                onChange={(e) => setEditLastName(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="edit-user-email">Email Address *</Label>
            <Input
              id="edit-user-email"
              type="email"
              value={editEmail}
              onChange={(e) => setEditEmail(e.target.value)}
              required
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="edit-user-phone">Phone Number</Label>
            <Input
              id="edit-user-phone"
              value={editPhone}
              onChange={(e) => setEditPhone(e.target.value)}
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="edit-user-role">Role *</Label>
            <select
              id="edit-user-role"
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-base shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring md:text-sm"
              value={editRoleName}
              onChange={(e) => setEditRoleName(e.target.value as any)}
              required
            >
              <option value="SUPER_ADMIN">Super Admin</option>
              <option value="FINANCE_ADMIN">Finance Admin</option>
              <option value="RESELLER">Reseller</option>
              <option value="CLIENT">Client</option>
            </select>
          </div>

          {/* If Client role is selected, select Reseller first, then Client */}
          {editRoleName === "CLIENT" && (
            <>
              <div className="grid gap-2">
                <Label htmlFor="edit-user-reseller">Reseller *</Label>
                <select
                  id="edit-user-reseller"
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-base shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring md:text-sm"
                  value={editResellerId}
                  onChange={(e) => {
                    setEditResellerId(e.target.value);
                    setEditClientId(""); // Reset client selection on reseller change
                  }}
                  required
                >
                  <option value="">Select a reseller…</option>
                  {resellers.map((r) => (
                    <option key={String(r.id)} value={String(r.id)}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="edit-user-client">Client Organisation *</Label>
                <select
                  id="edit-user-client"
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-base shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring md:text-sm"
                  value={editClientId}
                  onChange={(e) => setEditClientId(e.target.value)}
                  required
                  disabled={!editResellerId}
                >
                  <option value="">
                    {editResellerId ? "Select a client…" : "First select a reseller"}
                  </option>
                  {clients
                    .filter((c) => String(c.resellerId) === editResellerId)
                    .map((c) => (
                      <option key={String(c.id)} value={String(c.id)}>
                        {c.name}
                      </option>
                    ))}
                </select>
              </div>
            </>
          )}

          <div className="grid gap-2">
            <Label htmlFor="edit-user-status">Status *</Label>
            <select
              id="edit-user-status"
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-base shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring md:text-sm"
              value={editStatus}
              onChange={(e) => setEditStatus(e.target.value as any)}
              required
            >
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={closeEdit}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? "Saving…" : "Save Changes"}
            </Button>
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
        entityLabel="user"
        warningNote="All data associated with this user (session tokens, login credentials) will be permanently deleted."
      />
    </div>
  );
}
