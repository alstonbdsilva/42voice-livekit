// import api from "./api";

import { api } from "./api";

export interface ElevenLabsVoice {
  voice_id: string;
  name: string;
  gender: "female" | "male" | "non-binary";
  category?: string;
  accent?: string;
  description?: string;
  preview_url?: string;
  is_custom?: boolean;
}

export interface ModelOption {
  id: string;
  name: string;
}

export interface GetVoicesResponse {
  voices: ElevenLabsVoice[];
  hasApiKey: boolean;
  status: "loading" | "success" | "auth_error" | "key_missing" | "provider_unavailable" | "provider_error" | "rate_limited" | "empty";
  errorMessage?: string | null;
  models?: ModelOption[];
  provider?: string;
}

export interface PreviewVoiceParams {
  voiceId: string;
  text?: string;
  modelId?: string;
  stability?: number;
  similarityBoost?: number;
}

class ElevenLabsService {
  async getVoices(provider: string = "elevenlabs"): Promise<GetVoicesResponse> {
    try {
      const response = await api.get(`/agents/elevenlabs/voices?provider=${encodeURIComponent(provider)}`);
      // api interceptor may unwrap response.data
      const raw = (response as any)?.data ?? response;
      const data = raw?.data ?? raw;

      const voices = Array.isArray(data?.voices) ? data.voices : [];
      const hasApiKey = Boolean(data?.hasApiKey);
      const status = data?.status || (voices.length > 0 ? "success" : hasApiKey ? "empty" : "key_missing");
      const errorMessage = data?.errorMessage || null;
      const models = Array.isArray(data?.models) ? data.models : [];
      const resolvedProvider = data?.provider || provider;

      return {
        voices,
        hasApiKey,
        status,
        errorMessage,
        models,
        provider: resolvedProvider,
      };
    } catch (error: any) {
      console.warn("Failed to fetch voices from backend:", error);
      const errDetail = error?.response?.data?.message || error?.message || "Network / API error";
      return {
        voices: [],
        hasApiKey: false,
        status: "provider_error",
        errorMessage: errDetail,
        models: [],
        provider,
      };
    }
  }

  async previewVoice(params: PreviewVoiceParams): Promise<string> {
    const response = await api.post("/agents/elevenlabs/preview", params, {
      responseType: "blob",
    });
    const blob = new Blob([response.data], { type: "audio/mpeg" });
    return URL.createObjectURL(blob);
  }
}

export default new ElevenLabsService();
