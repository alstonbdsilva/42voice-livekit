import React, { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  Plus,
  Star,
  Pencil,
  Trash2,
  ChevronRight,
  Copy,
  ExternalLink,
} from "lucide-react";
import ConfigFormDialog from "@/components/telephony/ConfigFormDialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import TelephonyConfigService, {
  TelephonyConfigurationListItem,
  TelephonyConfigurationDetail,
} from "@/services/telephonyConfigService";

export default function TelephonyConfigurations() {
  const navigate = useNavigate();
  const [items, setItems] = useState<TelephonyConfigurationListItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  // Dialog states
  const [createOpen, setCreateOpen] = useState<boolean>(false);
  const [editTarget, setEditTarget] = useState<TelephonyConfigurationDetail | null>(null);
  const [editOpen, setEditOpen] = useState<boolean>(false);
  const [deleteTarget, setDeleteTarget] = useState<TelephonyConfigurationListItem | null>(null);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const res = await TelephonyConfigService.listConfigurations();
      setItems(res.configurations ?? []);
    } catch (err: any) {
      toast.error(err.message || "Failed to load configurations");
    } finally {
      setLoading(false);
    }
  }, []);

  const onSaved = useCallback(async () => {
    await fetchItems();
  }, [fetchItems]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  const onEdit = async (item: TelephonyConfigurationListItem) => {
    try {
      setEditTarget(null);
      const detail = await TelephonyConfigService.getConfiguration(item.id);
      setEditTarget(detail);
      setEditOpen(true);
    } catch (err: any) {
      toast.error("Failed to load configuration");
    }
  };

  const onSetDefault = async (item: TelephonyConfigurationListItem) => {
    try {
      await TelephonyConfigService.setDefaultOutbound(item.id);
      toast.success(`${item.name} is now the default outbound configuration`);
      fetchItems();
    } catch (err: any) {
      toast.error("Failed to set default");
    }
  };

  const onConfirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      await TelephonyConfigService.deleteConfiguration(deleteTarget.id);
      toast.success("Configuration deleted");
      setDeleteTarget(null);
      fetchItems();
    } catch (err: any) {
      toast.error("Failed to delete configuration");
    }
  };

  return (
    <div className="min-h-screen">
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-start justify-between gap-4 mb-6">
          <div>
            <h1 className="text-3xl font-bold mb-2">Telephony configurations</h1>
            <p className="text-zinc-500 text-sm">
              Connect one or more telephony provider accounts. Each campaign uses one
              configuration; inbound calls are routed to the right one by account ID.{" "}
              <a
                href="https://docs.dograh.com/integrations/telephony/overview"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-0.5 underline text-zinc-700"
              >
                Learn more <ExternalLink className="h-3 w-3" />
              </a>
            </p>
          </div>
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4 mr-2" /> Add configuration
          </Button>
        </div>

        {loading ? (
          <div className="grid gap-3">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : items.length === 0 ? (
          <Card>
            <CardHeader>
              <CardTitle>No telephony configurations yet</CardTitle>
              <CardDescription>
                Add one to enable outbound calls and receive inbound calls.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button onClick={() => setCreateOpen(true)}>
                <Plus className="h-4 w-4 mr-2" /> Add configuration
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-3">
            {items.map((item) => (
              <Card key={item.id}>
                <CardContent className="flex flex-col gap-4 py-4 sm:flex-row sm:items-center">
                  <Link
                    to={`/telephony-configurations/${item.id}`}
                    className="flex flex-1 items-center gap-4 min-w-0"
                  >
                    <div className="flex flex-col gap-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium truncate">{item.name}</span>
                        <Badge variant="secondary">{item.provider}</Badge>
                        {item.is_default_outbound && (
                          <Badge className="gap-1 bg-zinc-900 text-white">
                            <Star className="h-3 w-3 fill-current text-amber-400" />
                            Default
                          </Badge>
                        )}
                      </div>
                      <span className="text-sm text-zinc-500">
                        {item.phone_number_count} phone{" "}
                        {item.phone_number_count === 1 ? "number" : "numbers"}
                      </span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          navigator.clipboard
                            .writeText(String(item.id))
                            .then(() => toast.success("Configuration ID copied"))
                            .catch(() => toast.error("Failed to copy ID"));
                        }}
                        title="Click to copy"
                        className="inline-flex items-center gap-1 self-start rounded font-mono text-xs text-zinc-500 hover:text-zinc-950"
                      >
                        <span className="truncate">Configuration ID: {item.id}</span>
                        <Copy className="h-3 w-3 shrink-0" />
                      </button>
                    </div>
                  </Link>
                  <div className="flex w-full flex-wrap items-center justify-end gap-1 sm:w-auto sm:flex-nowrap">
                    {!item.is_default_outbound && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onSetDefault(item)}
                        title="Set as default outbound"
                      >
                        <Star className="h-4 w-4" />
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onEdit(item)}
                      title="Edit"
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setDeleteTarget(item)}
                      title="Delete"
                    >
                      <Trash2 className="h-4 w-4 text-red-600" />
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => navigate(`/telephony-configurations/${item.id}`)}>
                      Manage Phone Numbers
                      <ChevronRight className="h-4 w-4 ml-1" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      <ConfigFormDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        existing={null}
        onSaved={onSaved}
      />
      <ConfigFormDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        existing={editTarget}
        onSaved={onSaved}
      />

      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete configuration?</AlertDialogTitle>
            <AlertDialogDescription>
              {deleteTarget?.name} and all of its phone numbers will be removed. Any
              campaigns that reference this configuration will block the deletion until
              they are reassigned.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={onConfirmDelete}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
