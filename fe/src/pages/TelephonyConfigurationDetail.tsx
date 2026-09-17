import React, { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowLeft,
  Copy,
  Pencil,
  Plus,
  Star,
  Trash2,
  ExternalLink,
  Phone,
} from "lucide-react";
import ConfigFormDialog from "@/components/telephony/ConfigFormDialog";
import PhoneNumberDialog from "@/components/telephony/PhoneNumberDialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
  TelephonyConfigurationDetail as DetailType,
  TelephonyPhoneNumberItem,
} from "@/services/telephonyConfigService";

const INBOUND_WEBHOOK_PATH = "/api/v1/telephony/inbound/run";

export default function TelephonyConfigurationDetail() {
  const navigate = useNavigate();
  const { configId } = useParams<{ configId: string }>();

  const [config, setConfig] = useState<DetailType | null>(null);
  const [phoneNumbers, setPhoneNumbers] = useState<TelephonyPhoneNumberItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  // Dialog states
  const [editConfigOpen, setEditConfigOpen] = useState<boolean>(false);
  const [phoneDialogOpen, setPhoneDialogOpen] = useState<boolean>(false);
  const [phoneEditTarget, setPhoneEditTarget] = useState<TelephonyPhoneNumberItem | null>(null);
  const [phoneDeleteTarget, setPhoneDeleteTarget] = useState<TelephonyPhoneNumberItem | null>(null);

  const inboundWebhookUrl = `${window.location.origin}${INBOUND_WEBHOOK_PATH}`;

  const fetchAll = useCallback(async () => {
    if (!configId) return;
    setLoading(true);
    try {
      const [cfgRes, numbersRes] = await Promise.all([
        TelephonyConfigService.getConfiguration(configId),
        TelephonyConfigService.listPhoneNumbers(configId),
      ]);
      setConfig(cfgRes);
      setPhoneNumbers(numbersRes.phone_numbers ?? []);
    } catch (err: any) {
      toast.error(err.message || "Failed to load configuration");
    } finally {
      setLoading(false);
    }
  }, [configId]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const onSetDefaultOutbound = async () => {
    if (!configId) return;
    try {
      await TelephonyConfigService.setDefaultOutbound(configId);
      toast.success("Set as default outbound");
      fetchAll();
    } catch (err: any) {
      toast.error("Failed to set default");
    }
  };

  const onSetDefaultCaller = async (n: TelephonyPhoneNumberItem) => {
    if (!configId) return;
    try {
      await TelephonyConfigService.setDefaultCallerId(configId, n.id);
      toast.success(`${n.address} is now the default caller ID`);
      fetchAll();
    } catch (err: any) {
      toast.error("Failed to set default caller");
    }
  };

  const onConfirmDeletePhone = async () => {
    if (!configId || !phoneDeleteTarget) return;
    try {
      await TelephonyConfigService.deletePhoneNumber(configId, phoneDeleteTarget.id);
      toast.success("Phone number deleted");
      setPhoneDeleteTarget(null);
      fetchAll();
    } catch (err: any) {
      toast.error("Failed to delete phone number");
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8 space-y-3">
        <Skeleton className="h-10 w-1/3" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!config) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Button variant="ghost" onClick={() => navigate("/telephony-configurations")}>
          <ArrowLeft className="h-4 w-4 mr-2" /> Back
        </Button>
        <p className="mt-4 text-zinc-500">Configuration not found.</p>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 space-y-6" data-testid="telephony-configuration-detail-page">
      <div>
        <Link
          to="/telephony-configurations"
          className="inline-flex items-center text-sm text-zinc-500 hover:underline"
        >
          <ArrowLeft className="h-4 w-4 mr-1" /> All configurations
        </Link>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div className="space-y-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <CardTitle className="truncate text-xl font-bold">{config.name}</CardTitle>
              <Badge variant="secondary">{config.provider}</Badge>
              {config.is_default_outbound && (
                <Badge className="gap-1 bg-purple-100 text-purple-800 hover:bg-purple-100 border border-purple-200">
                  <Star className="h-3 w-3 fill-current text-purple-600" />
                  Default Outbound
                </Badge>
              )}
            </div>
            <CardDescription>
              Updated {config.updated_at ? new Date(config.updated_at).toLocaleString() : "-"}
            </CardDescription>
            <button
              type="button"
              onClick={() => {
                navigator.clipboard.writeText(String(config.id));
                toast.success("Configuration ID copied");
              }}
              title="Click to copy"
              className="inline-flex items-center gap-1 self-start rounded font-mono text-xs text-zinc-500 hover:text-zinc-950"
            >
              <span className="truncate">Configuration ID: {config.id}</span>
              <Copy className="h-3 w-3 shrink-0" />
            </button>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {!config.is_default_outbound && (
              <Button variant="outline" size="sm" onClick={onSetDefaultOutbound}>
                <Star className="h-4 w-4 mr-2" /> Set as default
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={() => setEditConfigOpen(true)}>
              <Pencil className="h-4 w-4 mr-2" /> Edit credentials
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            {Object.entries(config.credentials ?? {}).map(([k, v]) => (
              <div key={k} className="flex justify-between gap-3">
                <dt className="text-zinc-500 font-mono">{k}</dt>
                <dd className="font-mono text-right truncate max-w-[60%] font-medium text-zinc-900">
                  {v && typeof v === "object" ? "Configured" : String(v ?? "")}
                </dd>
              </div>
            ))}
          </dl>
          <div className="space-y-1">
            <p className="text-xs text-zinc-500">Inbound webhook URL</p>
            <button
              type="button"
              onClick={() => {
                navigator.clipboard.writeText(inboundWebhookUrl);
                toast.success("Inbound webhook URL copied");
              }}
              title="Click to copy inbound webhook URL"
              className="inline-flex items-center gap-1 self-start rounded font-mono text-xs text-zinc-500 hover:text-zinc-950"
            >
              <span className="truncate">{inboundWebhookUrl}</span>
              <Copy className="h-3 w-3 shrink-0" />
            </button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div className="space-y-1">
            <CardTitle>Phone numbers</CardTitle>
            <CardDescription>
              Numbers used as caller ID for outbound and accepted for inbound matching.
              SIP URIs and extensions are supported alongside PSTN numbers.{" "}
              <a
                href="https://docs.dograh.com/integrations/telephony/inbound"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-0.5 underline"
              >
                Inbound docs <ExternalLink className="h-3 w-3" />
              </a>
            </CardDescription>
          </div>
          <Button
            size="sm"
            onClick={() => {
              setPhoneEditTarget(null);
              setPhoneDialogOpen(true);
            }}
          >
            <Plus className="h-4 w-4 mr-2" /> Add phone number
          </Button>
        </CardHeader>
        <CardContent>
          {phoneNumbers.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-center space-y-3">
              <Phone className="h-10 w-10 text-zinc-400 stroke-[1.5]" />
              <h3 className="text-base font-semibold text-zinc-900">No phone numbers yet</h3>
              <p className="text-sm text-zinc-500 max-w-sm">
                Add one to start placing or receiving calls on this configuration.
              </p>
              <Button
                size="sm"
                onClick={() => {
                  setPhoneEditTarget(null);
                  setPhoneDialogOpen(true);
                }}
              >
                <Plus className="h-4 w-4 mr-2" /> Add phone number
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Address</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Label</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Inbound AI agent</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {phoneNumbers.map((n) => (
                  <TableRow key={n.id}>
                    <TableCell className="font-mono">{n.address}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{n.address_type}</Badge>
                    </TableCell>
                    <TableCell className="text-zinc-500">
                      {n.label ?? "-"}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {n.is_active ? (
                          <Badge variant="secondary">Active</Badge>
                        ) : (
                          <Badge variant="outline">Inactive</Badge>
                        )}
                        {n.is_default_caller_id && (
                          <Badge className="gap-1 bg-purple-100 text-purple-800 hover:bg-purple-100 border border-purple-200">
                            <Star className="h-3 w-3 fill-current text-purple-600" /> Default caller
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-zinc-500">
                      {n.inbound_agent_name ? (
                        <span className="font-medium text-zinc-900">{n.inbound_agent_name}</span>
                      ) : (
                        "-"
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        {!n.is_default_caller_id && n.is_active && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => onSetDefaultCaller(n)}
                            title="Set as default caller ID"
                          >
                            <Star className="h-4 w-4" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setPhoneEditTarget(n);
                            setPhoneDialogOpen(true);
                          }}
                          title="Edit"
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setPhoneDeleteTarget(n)}
                          title="Delete"
                        >
                          <Trash2 className="h-4 w-4 text-red-600" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <ConfigFormDialog
        open={editConfigOpen}
        onOpenChange={setEditConfigOpen}
        existing={config}
        onSaved={fetchAll}
      />

      {configId && (
        <PhoneNumberDialog
          open={phoneDialogOpen}
          onOpenChange={setPhoneDialogOpen}
          configId={configId}
          existing={phoneEditTarget}
          onSaved={fetchAll}
        />
      )}

      <AlertDialog
        open={!!phoneDeleteTarget}
        onOpenChange={(o) => !o && setPhoneDeleteTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete phone number?</AlertDialogTitle>
            <AlertDialogDescription>
              {phoneDeleteTarget?.address} will no longer accept inbound calls or be
              available as a caller ID for this configuration.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={onConfirmDeletePhone}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
