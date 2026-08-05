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

export interface GetVoicesResponse {
  voices: ElevenLabsVoice[];
  hasApiKey: boolean;
}

export interface PreviewVoiceParams {
  voiceId: string;
  text?: string;
  modelId?: string;
  stability?: number;
  similarityBoost?: number;
}

class ElevenLabsService {
  async getVoices(): Promise<GetVoicesResponse> {
    try {
      const response = await api.get("/agents/elevenlabs/voices");
      const data = response?.data ?? response;
      if (data && Array.isArray(data.voices)) {
        return { voices: data.voices, hasApiKey: Boolean(data.hasApiKey) };
      }
      if (data?.data && Array.isArray(data.data.voices)) {
        return { voices: data.data.voices, hasApiKey: Boolean(data.data.hasApiKey) };
      }
      return { voices: [], hasApiKey: false };
    } catch (error) {
      console.warn("Failed to fetch ElevenLabs voices from backend:", error);
      return { voices: [], hasApiKey: false };
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
