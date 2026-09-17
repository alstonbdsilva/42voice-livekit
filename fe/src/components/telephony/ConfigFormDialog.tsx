import React, { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Copy, ExternalLink } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import TelephonyConfigService, {
  TelephonyConfigurationDetail,
  TelephonyProviderMetadata,
  TelephonyProviderField,
} from "@/services/telephonyConfigService";

interface ConfigFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  existing?: TelephonyConfigurationDetail | null;
  onSaved: () => void;
}

type FieldValue = string | number | boolean | undefined;
type FieldValues = Record<string, FieldValue>;

function parseCredentials(creds: any): Record<string, any> {
  if (!creds) return {};
  if (typeof creds === "string") {
    try {
      const parsed = JSON.parse(creds);
      if (parsed && typeof parsed === "object") return parsed;
    } catch (e) {
      return {};
    }
  }
  if (typeof creds === "object") return creds;
  return {};
}

function flattenValues(
  value: Record<string, unknown>,
  prefix = ""
): FieldValues {
  const flattened: FieldValues = {};
  for (const [key, child] of Object.entries(value)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (child && typeof child === "object" && !Array.isArray(child)) {
      Object.assign(flattened, flattenValues(child as Record<string, unknown>, path));
    } else if (
      child === undefined ||
      typeof child === "string" ||
      typeof child === "number" ||
      typeof child === "boolean"
    ) {
      flattened[path] = child;
    }
  }
  return flattened;
}

function nestValues(values: FieldValues): Record<string, unknown> {
  const nested: Record<string, unknown> = {};
  for (const [path, value] of Object.entries(values)) {
    if (value === undefined || value === "") continue;
    const parts = path.split(".");
    let current = nested;
    for (const part of parts.slice(0, -1)) {
      const child = current[part];
      if (!child || typeof child !== "object" || Array.isArray(child)) {
        current[part] = {};
      }
      current = current[part] as Record<string, unknown>;
    }
    current[parts[parts.length - 1]] = value;
  }
  return nested;
}

export function ConfigFormDialog({
  open,
  onOpenChange,
  existing,
  onSaved,
}: ConfigFormDialogProps) {
  const [providers, setProviders] = useState<TelephonyProviderMetadata[]>([]);
  const [providerName, setProviderName] = useState<string>("");
  const [name, setName] = useState<string>("");
  const [isDefault, setIsDefault] = useState<boolean>(false);
  const [values, setValues] = useState<FieldValues>({});
  const [submitting, setSubmitting] = useState<boolean>(false);

  const isEdit = !!existing;
  const lockedProvider = isEdit;

  const currentProvider = useMemo(
    () => providers.find((p) => p.provider === providerName),
    [providers, providerName]
  );

  const visibleFields = useMemo(
    () =>
      currentProvider?.fields.filter(
        (field) =>
          !field.visible_when ||
          values[field.visible_when.field] === field.visible_when.equals
      ) ?? [],
    [currentProvider, values]
  );

  // Fetch provider metadata once when opened
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await TelephonyConfigService.getMetadata();
        if (cancelled) return;
        const list = res.providers ?? [];
        setProviders(list);
        if (!existing && list.length > 0 && !providerName) {
          setProviderName(list[0].provider);
        }
      } catch (err) {
        toast.error("Failed to load provider metadata");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open]);

  // Sync existing config values whenever open or existing prop changes
  useEffect(() => {
    if (!open) return;
    if (existing) {
      setProviderName(existing.provider);
      setName(existing.name);
      setIsDefault(existing.is_default_outbound);
      const rawCreds = (existing as any).credentials || (existing as any).config || {};
      const parsedCreds = parseCredentials(rawCreds);
      setValues(flattenValues(parsedCreds));
    } else {
      setName("");
      setIsDefault(false);
      setValues({});
    }
  }, [open, existing]);

  const updateField = (fieldName: string, value: FieldValue) => {
    setValues((prev) => {
      const next = { ...prev, [fieldName]: value };
      if (value === undefined) {
        for (const field of currentProvider?.fields ?? []) {
          if (field.visible_when?.field === fieldName) delete next[field.name];
        }
      }
      return next;
    });
  };

  const handleSubmit = async () => {
    if (!currentProvider) return;
    if (!isEdit && !name.trim()) {
      toast.error("Name is required");
      return;
    }

    setSubmitting(true);
    try {
      const configPayload = {
        provider: providerName,
        ...nestValues(values),
      };

      if (isEdit && existing) {
        await TelephonyConfigService.updateConfiguration(existing.id, {
          name: name.trim() || undefined,
          config: configPayload,
        });
        toast.success("Configuration updated");
      } else {
        await TelephonyConfigService.createConfiguration({
          name: name.trim(),
          is_default_outbound: isDefault,
          config: configPayload,
        });
        toast.success("Configuration created");
      }
      onOpenChange(false);
      onSaved();
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || "Failed to save configuration";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? "Edit telephony configuration" : "Add telephony configuration"}
          </DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Update credentials for this configuration. Phone numbers are managed separately."
              : "Connect a telephony provider account. Phone numbers are added after the configuration is created."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {isEdit && existing && (
            <div className="space-y-1">
              <Label>Configuration ID</Label>
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard
                    .writeText(String(existing.id))
                    .then(() => toast.success("Configuration ID copied"))
                    .catch(() => toast.error("Failed to copy ID"));
                }}
                title="Click to copy"
                className="group flex w-full items-center gap-2 rounded-md border border-zinc-200 bg-zinc-50 p-2 text-left font-mono text-xs transition-colors hover:bg-zinc-100"
              >
                <code className="flex-1 truncate">{existing.id}</code>
                <Copy className="h-3 w-3 shrink-0 text-zinc-500 group-hover:text-zinc-900" />
              </button>
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="cfg-name">Name</Label>
            <Input
              id="cfg-name"
              placeholder="e.g. Twilio US prod"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="cfg-provider">Provider</Label>
            <Select
              value={providerName}
              onValueChange={setProviderName}
              disabled={lockedProvider || providers.length === 0}
            >
              <SelectTrigger id="cfg-provider">
                <SelectValue placeholder="Select a provider" />
              </SelectTrigger>
              <SelectContent>
                {providers.map((p) => (
                  <SelectItem key={p.provider} value={p.provider}>
                    {p.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {lockedProvider && (
              <p className="text-xs text-zinc-500">
                Provider cannot be changed after creation.
              </p>
            )}
            {currentProvider?.docs_url && (
              <a
                href={currentProvider.docs_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-blue-600 underline"
              >
                {currentProvider.display_name} docs <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>

          {!isEdit && (
            <div className="flex items-center justify-between rounded border border-zinc-200 p-3">
              <div>
                <Label className="text-sm">Set as default for outbound calls</Label>
                <p className="text-xs text-zinc-500">
                  Used by test calls and campaigns when no specific config is selected.
                </p>
              </div>
              <Switch checked={isDefault} onCheckedChange={setIsDefault} />
            </div>
          )}

          {currentProvider && (
            <div className="space-y-3 border-t border-zinc-200 pt-3">
              {visibleFields.map((field, index) => (
                <div className="space-y-1" key={field.name}>
                  {field.section && field.section !== visibleFields[index - 1]?.section && (
                    <div className="pb-2 pt-3">
                      <h3 className="text-sm font-semibold">{field.section}</h3>
                    </div>
                  )}
                  <Label htmlFor={`cfg-field-${field.name}`}>
                    {field.label}
                    {!field.required && (
                      <span className="ml-1 text-xs text-zinc-500">
                        (optional)
                      </span>
                    )}
                  </Label>
                  <FieldInput
                    field={field}
                    value={values[field.name]}
                    onChange={(v) => updateField(field.name, v)}
                    isEdit={isEdit}
                  />
                  {field.description && (
                    <p className="text-xs text-zinc-500">{field.description}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <DialogFooter className="pt-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={submitting || !currentProvider}>
            {submitting ? "Saving..." : isEdit ? "Save changes" : "Create"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface FieldInputProps {
  field: TelephonyProviderField;
  value: FieldValue;
  onChange: (v: FieldValue) => void;
  isEdit: boolean;
}

function FieldInput({ field, value, onChange, isEdit }: FieldInputProps) {
  if (field.name === "from_numbers") {
    return (
      <p className="text-xs text-zinc-500">
        Phone numbers are managed separately on the configuration page.
      </p>
    );
  }

  const placeholder =
    field.placeholder ??
    (field.sensitive && isEdit ? "Leave masked to keep existing" : "");

  if (field.type === "textarea") {
    return (
      <Textarea
        id={`cfg-field-${field.name}`}
        placeholder={placeholder}
        value={(value as string) ?? ""}
        onChange={(e) => onChange(e.target.value)}
        rows={6}
        className="field-sizing-fixed resize-y break-all font-mono text-xs"
      />
    );
  }
  if (field.type === "number") {
    return (
      <Input
        id={`cfg-field-${field.name}`}
        type="number"
        placeholder={placeholder}
        value={(value as number | string) ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))}
      />
    );
  }
  if (field.type === "boolean") {
    return (
      <Switch
        id={`cfg-field-${field.name}`}
        checked={Boolean(value)}
        onCheckedChange={onChange}
      />
    );
  }
  if (field.type === "select") {
    return (
      <Select
        value={value === undefined ? "__none__" : String(value)}
        onValueChange={(next) => onChange(next === "__none__" ? undefined : next)}
      >
        <SelectTrigger id={`cfg-field-${field.name}`}>
          <SelectValue placeholder={placeholder || "Select an option"} />
        </SelectTrigger>
        <SelectContent>
          {!field.required && <SelectItem value="__none__">Not configured</SelectItem>}
          {(field.options ?? []).map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    );
  }
  return (
    <Input
      id={`cfg-field-${field.name}`}
      type={field.type === "password" ? "password" : "text"}
      placeholder={placeholder}
      value={(value as string) ?? ""}
      onChange={(e) => onChange(e.target.value)}
      autoComplete={field.sensitive ? "current-password" : undefined}
    />
  );
}

export default ConfigFormDialog;
