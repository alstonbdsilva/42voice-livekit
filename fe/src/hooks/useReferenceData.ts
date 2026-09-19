import { useQuery } from "@tanstack/react-query";
import ToolsService from "@/services/tools.service";
import ResellerService from "@/services/reseller.service";
import ClientService from "@/services/client.service";
import { TelephonyConfigService } from "@/services/telephonyConfigService";
import PhoneNumberService from "@/services/phone-number.service";
import ElevenLabsService, { GetVoicesResponse } from "@/services/elevenlabs.service";
import { Tool, Reseller, Client } from "@/types";

/**
 * React Query hook to fetch active tools.
 * Cache key: ["tools", "active"]
 */
export function useActiveTools() {
  return useQuery<Tool[]>({
    queryKey: ["tools", "active"],
    queryFn: () => ToolsService.getAll({ status: "active" }),
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * React Query hook to fetch all resellers.
 * Cache key: ["resellers"]
 */
export function useResellers(enabled: boolean = true) {
  return useQuery<Reseller[]>({
    queryKey: ["resellers"],
    queryFn: () => ResellerService.getAll(),
    enabled,
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * React Query hook to fetch all clients.
 * Cache key: ["clients"]
 */
export function useClients(enabled: boolean = true) {
  return useQuery<Client[]>({
    queryKey: ["clients"],
    queryFn: () => ClientService.getAll(),
    enabled,
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * React Query hook to fetch telephony configurations.
 * Cache key: ["telephony-configs"]
 */
export function useTelephonyConfigs() {
  return useQuery({
    queryKey: ["telephony-configs"],
    queryFn: () => TelephonyConfigService.listConfigurations(),
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * React Query hook to fetch available phone numbers.
 * Cache key: ["phone-numbers"]
 */
export function usePhoneNumbers() {
  return useQuery<any[]>({
    queryKey: ["phone-numbers"],
    queryFn: () => PhoneNumberService.getAll(),
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * React Query hook to fetch voice catalogs with distinct cache keys per provider.
 * Cache key: ["voice-catalog", provider]
 * Example: ["voice-catalog", "elevenlabs"] vs ["voice-catalog", "cartesia"]
 */
export function useVoiceCatalog(provider?: string) {
  const resolvedProvider = (provider || "elevenlabs").toLowerCase();
  return useQuery<GetVoicesResponse>({
    queryKey: ["voice-catalog", resolvedProvider],
    queryFn: () => ElevenLabsService.getVoices(resolvedProvider),
    enabled: Boolean(resolvedProvider),
    staleTime: 5 * 60 * 1000,
  });
}
