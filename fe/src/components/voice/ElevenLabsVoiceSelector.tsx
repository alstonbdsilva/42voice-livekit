import React, { useState, useEffect, useRef } from "react";
import {
  Play,
  Pause,
  Search,
  Mic,
  Sliders,
  Check,
  Volume2,
  RefreshCw,
  Sparkles,
  Info,
  SlidersHorizontal,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useVoiceCatalog } from "@/hooks/useReferenceData";
import ElevenLabsService, { ElevenLabsVoice, ModelOption } from "@/services/elevenlabs.service";

export interface ElevenLabsVoiceSettings {
  modelId: string;
  stability: number;
  similarityBoost: number;
  styleExaggeration: number;
  speakerBoost: boolean;
}

export const DEFAULT_ELEVENLABS_SETTINGS: ElevenLabsVoiceSettings = {
  modelId: "eleven_multilingual_v2",
  stability: 0.5,
  similarityBoost: 0.75,
  styleExaggeration: 0.0,
  speakerBoost: true,
};

export const BUILTIN_ELEVENLABS_VOICES: ElevenLabsVoice[] = [];

export const ELEVENLABS_DEFAULT_MODELS: ModelOption[] = [
  { id: "eleven_multilingual_v2", name: "eleven_multilingual_v2 (Recommended)" },
  { id: "eleven_flash_v2_5", name: "eleven_flash_v2_5 (Ultra Fast)" },
  { id: "eleven_flash_v2", name: "eleven_flash_v2" },
  { id: "eleven_turbo_v2_5", name: "eleven_turbo_v2_5 (Lowest Latency)" },
  { id: "eleven_turbo_v2", name: "eleven_turbo_v2" },
];

export const CARTESIA_DEFAULT_MODELS: ModelOption[] = [
  { id: "sonic-3", name: "sonic-3" },
];

interface ElevenLabsVoiceSelectorProps {
  selectedProvider?: string;
  selectedModel?: string;
  selectedVoiceId?: string;
  selectedVoiceName: string;
  selectedVoiceGender: "female" | "male";
  onSelectProvider?: (provider: "elevenlabs" | "cartesia") => void;
  onSelectModel?: (model: string) => void;
  onSelectVoice: (voiceName: string, gender: "female" | "male", voiceId?: string) => void;
  voiceSettings?: ElevenLabsVoiceSettings;
  onUpdateSettings?: (settings: ElevenLabsVoiceSettings) => void;
  disabled?: boolean;
}

export default function ElevenLabsVoiceSelector({
  selectedProvider = "elevenlabs",
  selectedModel,
  selectedVoiceId,
  selectedVoiceName,
  selectedVoiceGender,
  onSelectProvider,
  onSelectModel,
  onSelectVoice,
  voiceSettings = DEFAULT_ELEVENLABS_SETTINGS,
  onUpdateSettings,
  disabled = false,
}: ElevenLabsVoiceSelectorProps) {
  const currentProvider = (selectedProvider || "elevenlabs").toLowerCase() as "elevenlabs" | "cartesia";

  const {
    data: voiceCatalogData,
    isLoading: isCatalogLoading,
    isFetching: isCatalogFetching,
    error: catalogError,
  } = useVoiceCatalog(currentProvider);

  const [voices, setVoices] = useState<ElevenLabsVoice[]>([]);
  const [catalogStatus, setCatalogStatus] = useState<
    | "loading"
    | "success"
    | "auth_error"
    | "key_missing"
    | "provider_unavailable"
    | "provider_error"
    | "rate_limited"
    | "empty"
  >("loading");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [providerModels, setProviderModels] = useState<ModelOption[]>([]);
  const [hasApiKey, setHasApiKey] = useState(false);
  const [loadingVoices, setLoadingVoices] = useState(false);

  const [searchQuery, setSearchQuery] = useState("");
  const [genderFilter, setGenderFilter] = useState<"all" | "female" | "male">("all");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");

  // Audio preview state
  const [playingVoiceId, setPlayingVoiceId] = useState<string | null>(null);
  const [loadingAudioId, setLoadingAudioId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Settings dropdown accordion
  const [showSettings, setShowSettings] = useState(false);
  const [localSettings, setLocalSettings] = useState<ElevenLabsVoiceSettings>(voiceSettings);

  // Stop audio whenever provider changes
  useEffect(() => {
    stopAudio();
  }, [currentProvider]);

  // Synchronize React Query cached catalog data into component state
  useEffect(() => {
    if (isCatalogLoading && !voiceCatalogData) {
      setLoadingVoices(true);
      setCatalogStatus("loading");
      setErrorMessage(null);
      return;
    }
    setLoadingVoices(isCatalogFetching && !voiceCatalogData);

    if (catalogError) {
      setCatalogStatus("provider_error");
      setErrorMessage((catalogError as any)?.message || "Failed to load voice catalog.");
      setVoices([]);
      return;
    }

    if (voiceCatalogData) {
      setHasApiKey(voiceCatalogData.hasApiKey);
      setCatalogStatus(voiceCatalogData.status);
      setErrorMessage(voiceCatalogData.errorMessage || null);

      if (voiceCatalogData.models && voiceCatalogData.models.length > 0) {
        setProviderModels(voiceCatalogData.models);
      } else {
        setProviderModels(
          currentProvider === "cartesia" ? CARTESIA_DEFAULT_MODELS : ELEVENLABS_DEFAULT_MODELS
        );
      }

      if (voiceCatalogData.voices && Array.isArray(voiceCatalogData.voices)) {
        setVoices(voiceCatalogData.voices);
      } else {
        setVoices([]);
      }
    }
  }, [voiceCatalogData, isCatalogLoading, isCatalogFetching, catalogError, currentProvider]);

  // Update local settings if parent prop changes
  useEffect(() => {
    setLocalSettings(voiceSettings);
  }, [voiceSettings]);

  const stopAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    setPlayingVoiceId(null);
  };

  const handleProviderChange = (newProvider: "elevenlabs" | "cartesia") => {
    if (disabled) return;
    if (onSelectProvider) {
      onSelectProvider(newProvider);
    }
    if (newProvider === "cartesia") {
      if (onSelectModel) onSelectModel("sonic-3");
      onSelectVoice("", "female", "");
    } else {
      if (onSelectModel) onSelectModel("eleven_multilingual_v2");
      onSelectVoice("", "female", "");
    }
  };

  const handleModelChange = (newModel: string) => {
    if (disabled) return;
    if (onSelectModel) {
      onSelectModel(newModel);
    }
    handleSettingChange("modelId", newModel);
  };

  const handlePlayPreview = async (voice: ElevenLabsVoice) => {
    if (disabled) return;

    if (playingVoiceId === voice.voice_id) {
      stopAudio();
      return;
    }

    stopAudio();
    setLoadingAudioId(voice.voice_id);

    try {
      const audioUrl = voice.preview_url;

      const playUrl = (url: string): Promise<boolean> => {
        return new Promise((resolve) => {
          const audio = new Audio(url);
          audioRef.current = audio;

          audio.onended = () => {
            setPlayingVoiceId(null);
            setLoadingAudioId(null);
          };

          audio.onerror = (e) => {
            console.warn("Direct preview URL failed, falling back to live preview:", e);
            resolve(false);
          };

          audio
            .play()
            .then(() => {
              setPlayingVoiceId(voice.voice_id);
              resolve(true);
            })
            .catch((err) => {
              console.warn("Audio play() promise rejected:", err);
              resolve(false);
            });
        });
      };

      // 1. Try playing direct preview_url if available
      if (audioUrl) {
        const success = await playUrl(audioUrl);
        if (success) {
          setLoadingAudioId(null);
          return;
        }
      }

      // 2. If direct URL failed or is missing, generate live preview via backend TTS endpoint
      if (hasApiKey && voice.voice_id && currentProvider === "elevenlabs") {
        const liveAudioUrl = await ElevenLabsService.previewVoice({
          voiceId: voice.voice_id,
          text: `Hello! This is a live voice preview for ${voice.name}.`,
          modelId: selectedModel || localSettings.modelId,
          stability: localSettings.stability,
          similarityBoost: localSettings.similarityBoost,
        });

        if (liveAudioUrl) {
          const success = await playUrl(liveAudioUrl);
          if (success) {
            setLoadingAudioId(null);
            return;
          }
        }
      }

      toast.error("No preview audio available for this voice.");
      setPlayingVoiceId(null);
    } catch (err: any) {
      console.error("Failed to play voice sample:", err);
      toast.error(err?.response?.data?.message || "Failed to generate or play voice preview.");
    } finally {
      setLoadingAudioId(null);
    }
  };

  const handleSelectVoiceCard = (voice: ElevenLabsVoice) => {
    if (disabled) return;
    onSelectVoice(voice.name, voice.gender === "male" ? "male" : "female", voice.voice_id);
  };

  const handleSettingChange = <K extends keyof ElevenLabsVoiceSettings>(
    key: K,
    val: ElevenLabsVoiceSettings[K]
  ) => {
    const updated = { ...localSettings, [key]: val };
    setLocalSettings(updated);
    if (onUpdateSettings) {
      onUpdateSettings(updated);
    }
  };

  // Filtering voices
  const filteredVoices = voices.filter((v) => {
    const matchSearch =
      v.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (v.description && v.description.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (v.accent && v.accent.toLowerCase().includes(searchQuery.toLowerCase())) ||
      v.voice_id.toLowerCase().includes(searchQuery.toLowerCase());

    const matchGender = genderFilter === "all" || v.gender === genderFilter;
    const matchCategory =
      categoryFilter === "all" ||
      (v.category && v.category.toLowerCase() === categoryFilter.toLowerCase());

    return matchSearch && matchGender && matchCategory;
  });

  const categories = Array.from(
    new Set(voices.map((v) => v.category).filter(Boolean))
  ) as string[];

  // Find currently selected voice object
  const currentVoiceObj = voices.find(
    (v) =>
      (selectedVoiceId && v.voice_id === selectedVoiceId) ||
      (selectedVoiceName && v.name.toLowerCase() === selectedVoiceName.toLowerCase())
  );

  const activeModel =
    selectedModel ||
    (currentProvider === "cartesia" ? "sonic-3" : localSettings.modelId || "eleven_multilingual_v2");

  const modelsList =
    providerModels.length > 0
      ? providerModels
      : currentProvider === "cartesia"
      ? CARTESIA_DEFAULT_MODELS
      : ELEVENLABS_DEFAULT_MODELS;

  return (
    <div className="space-y-4 w-full">
      {/* ── TTS Provider & Model Selector Card ────────────────────────────── */}
      <div className="bg-white border border-zinc-200 p-4 rounded-sm shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-zinc-100 pb-3 flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-indigo-600" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-900 font-display">
              Text-to-Speech Engine & Voice Model
            </h3>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`px-2 py-0.5 text-[10px] font-semibold rounded-full border ${
                currentProvider === "elevenlabs" && hasApiKey
                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                  : currentProvider === "cartesia"
                  ? "bg-zinc-100 text-zinc-600 border-zinc-200"
                  : "bg-amber-50 text-amber-700 border-amber-200"
              }`}
            >
              {currentProvider === "elevenlabs"
                ? hasApiKey
                  ? "ElevenLabs Connected"
                  : "ElevenLabs (Key Required)"
                : hasApiKey
                ? "Cartesia Connected"
                : "Cartesia (Key Required)"}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold text-zinc-800">TTS Provider</Label>
            <select
              value={currentProvider}
              onChange={(e) => handleProviderChange(e.target.value as "elevenlabs" | "cartesia")}
              disabled={disabled}
              className="w-full text-xs h-9 rounded-sm border border-zinc-300 bg-white px-3 shadow-xs focus:outline-hidden focus:ring-1 focus:ring-zinc-950 font-medium"
            >
              <option value="elevenlabs">ElevenLabs</option>
              <option value="cartesia">Cartesia</option>
            </select>
            <p className="text-[10px] text-zinc-400">
              {currentProvider === "elevenlabs"
                ? "High-fidelity, ultra-realistic voice synthesis powered by ElevenLabs."
                : "Ultra-low latency streaming TTS engine (requires livekit-plugins-cartesia)."}
            </p>
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs font-semibold text-zinc-800">TTS Model</Label>
            <select
              value={activeModel}
              onChange={(e) => handleModelChange(e.target.value)}
              disabled={disabled}
              className="w-full text-xs h-9 rounded-sm border border-zinc-300 bg-white px-3 shadow-xs focus:outline-hidden focus:ring-1 focus:ring-zinc-950 font-medium font-mono"
            >
              {modelsList.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name || m.id}
                </option>
              ))}
            </select>
            <p className="text-[10px] text-zinc-400">
              {currentProvider === "cartesia"
                ? "Sonic 3 model supported by Cartesia."
                : "Multilingual v2 recommended for natural conversations; Flash/Turbo for minimum latency."}
            </p>
          </div>
        </div>

        {/* ElevenLabs Advanced Parameters Accordion Toggle */}
        {currentProvider === "elevenlabs" && (
          <div className="pt-2 border-t border-zinc-100 flex items-center justify-between">
            <button
              type="button"
              onClick={() => setShowSettings(!showSettings)}
              className="flex items-center gap-1.5 text-xs text-zinc-600 hover:text-zinc-900 font-medium transition-colors"
            >
              <SlidersHorizontal className="w-3.5 h-3.5 text-zinc-500" />
              <span>Voice Fine-Tuning Parameters</span>
              {showSettings ? <ChevronUp className="w-3.5 h-3.5 ml-1" /> : <ChevronDown className="w-3.5 h-3.5 ml-1" />}
            </button>
          </div>
        )}

        {/* ElevenLabs Fine-Tuning Parameters */}
        {showSettings && currentProvider === "elevenlabs" && (
          <div className="bg-zinc-50 border border-zinc-200 p-3.5 rounded-sm space-y-3 animate-in fade-in slide-in-from-top-2 duration-200">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label className="text-[11px] font-medium text-zinc-700">Stability</Label>
                  <span className="text-[11px] font-mono font-medium text-zinc-600">
                    {Math.round(localSettings.stability * 100)}%
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={localSettings.stability}
                  onChange={(e) => handleSettingChange("stability", parseFloat(e.target.value))}
                  disabled={disabled}
                  className="w-full accent-zinc-950 h-1.5 bg-zinc-200 rounded-lg cursor-pointer"
                />
                <p className="text-[10px] text-zinc-400">Higher = consistent, Lower = expressive</p>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label className="text-[11px] font-medium text-zinc-700">Similarity / Clarity</Label>
                  <span className="text-[11px] font-mono font-medium text-zinc-600">
                    {Math.round(localSettings.similarityBoost * 100)}%
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={localSettings.similarityBoost}
                  onChange={(e) => handleSettingChange("similarityBoost", parseFloat(e.target.value))}
                  disabled={disabled}
                  className="w-full accent-zinc-950 h-1.5 bg-zinc-200 rounded-lg cursor-pointer"
                />
                <p className="text-[10px] text-zinc-400">Boosts fidelity to target speaker accent</p>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label className="text-[11px] font-medium text-zinc-700">Style Exaggeration</Label>
                  <span className="text-[11px] font-mono font-medium text-zinc-600">
                    {Math.round(localSettings.styleExaggeration * 100)}%
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={localSettings.styleExaggeration}
                  onChange={(e) => handleSettingChange("styleExaggeration", parseFloat(e.target.value))}
                  disabled={disabled}
                  className="w-full accent-zinc-950 h-1.5 bg-zinc-200 rounded-lg cursor-pointer"
                />
                <p className="text-[10px] text-zinc-400">Amplifies speaker expressiveness</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Voice Catalog Header ─────────────────────────────────────────── */}
      <div className="flex items-center justify-between gap-3 bg-white p-3 border border-zinc-200 rounded-sm shadow-xs flex-wrap">
        <div className="flex items-center gap-2 font-semibold text-xs text-zinc-900">
          <Mic className="w-3.5 h-3.5 text-zinc-700" />
          <span className="capitalize">{currentProvider} Voice Catalog</span>
          {catalogStatus === "success" && (
            <span className="px-2 py-0.5 text-[10px] bg-zinc-100 border border-zinc-200 text-zinc-600 rounded-full font-medium">
              {voices.length} voices available
            </span>
          )}
        </div>

        <div className="text-[11px] text-zinc-500 font-medium">
          Selected Voice:{" "}
          <span className="font-bold text-zinc-900">
            {selectedVoiceName || "None"}
          </span>{" "}
          {selectedVoiceId && (
            <span className="font-mono text-zinc-400 text-[10px]">({selectedVoiceId})</span>
          )}
        </div>
      </div>

      {/* ── DISTINCT STATE BANNERS ────────────────────────────────────────── */}

      {/* 1. Loading State */}
      {loadingVoices && (
        <div className="py-12 border border-zinc-200 rounded-sm bg-white text-center space-y-2">
          <RefreshCw className="w-5 h-5 mx-auto animate-spin text-zinc-500" />
          <p className="text-xs font-semibold text-zinc-700">
            Loading voices from {currentProvider === "cartesia" ? "Cartesia" : "ElevenLabs"}...
          </p>
          <p className="text-[11px] text-zinc-400">Querying provider voice catalog</p>
        </div>
      )}

      {/* 2. Authentication Error (e.g. 401 Invalid API Key) */}
      {!loadingVoices && catalogStatus === "auth_error" && (
        <div className="p-4 rounded-sm border border-rose-200 bg-rose-50/80 text-rose-900 space-y-2">
          <div className="flex items-center gap-2 font-bold text-xs">
            <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>Authentication / API Key Error</span>
          </div>
          <p className="text-xs text-rose-800 leading-relaxed font-mono">
            {errorMessage || "ElevenLabs API rejected the request with HTTP 401: Invalid API key."}
          </p>
          <p className="text-[11px] text-rose-700">
            Please verify your <code className="px-1 py-0.5 bg-rose-100 rounded text-rose-900 font-mono text-[10px]">ELEVENLABS_API_KEY</code> configuration on the backend server.
          </p>
        </div>
      )}

      {/* 3. API Key Missing */}
      {!loadingVoices && catalogStatus === "key_missing" && (
        <div className="p-4 rounded-sm border border-amber-200 bg-amber-50/80 text-amber-900 space-y-2">
          <div className="flex items-center gap-2 font-bold text-xs">
            <Info className="w-4 h-4 text-amber-600 shrink-0" />
            <span>API Key Not Configured</span>
          </div>
          <p className="text-xs text-amber-800 leading-relaxed">
            {errorMessage || "ELEVENLABS_API_KEY is not configured on the backend server."}
          </p>
        </div>
      )}

      {/* 4. Provider Unavailable (e.g. Cartesia plugin not installed) */}
      {!loadingVoices && catalogStatus === "provider_unavailable" && (
        <div className="p-5 rounded-sm border border-zinc-200 bg-zinc-50 text-zinc-800 space-y-2">
          <div className="flex items-center gap-2 font-bold text-xs text-zinc-900">
            <Info className="w-4 h-4 text-zinc-500 shrink-0" />
            <span>Cartesia Provider Unavailable</span>
          </div>
          <p className="text-xs text-zinc-600 leading-relaxed">
            {errorMessage || "Cartesia plugin (livekit-plugins-cartesia) is not installed in this environment."}
          </p>
          <div className="text-[11px] text-zinc-500 pt-1 border-t border-zinc-200">
            Model <code className="font-mono text-zinc-700">sonic-3</code> is registered for configuration, but LiveKit requires the plugin package to establish audio streams.
          </div>
        </div>
      )}

      {/* 5. Provider Connection Error */}
      {!loadingVoices && catalogStatus === "provider_error" && (
        <div className="p-4 rounded-sm border border-amber-200 bg-amber-50/80 text-amber-900 space-y-2">
          <div className="flex items-center gap-2 font-bold text-xs">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>Provider Connection Error</span>
          </div>
          <p className="text-xs text-amber-800 leading-relaxed font-mono">
            {errorMessage || "Could not connect to provider."}
          </p>
        </div>
      )}

      {/* 5b. Rate Limited */}
      {!loadingVoices && catalogStatus === "rate_limited" && (
        <div className="p-4 rounded-sm border border-amber-200 bg-amber-50/80 text-amber-900 space-y-2">
          <div className="flex items-center gap-2 font-bold text-xs">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>Provider Rate Limit Exceeded</span>
          </div>
          <p className="text-xs text-amber-800 leading-relaxed font-mono">
            {errorMessage || "ElevenLabs API rate limit exceeded. Please try again later."}
          </p>
        </div>
      )}

      {/* 6. Empty Catalog */}
      {!loadingVoices && catalogStatus === "empty" && (
        <div className="py-12 border border-dashed border-zinc-200 rounded-sm bg-white text-center text-zinc-400 space-y-2">
          <Mic className="w-8 h-8 mx-auto opacity-40" />
          <p className="text-xs font-semibold text-zinc-600">No voices returned by {currentProvider}</p>
          <p className="text-[11px] text-zinc-400">The voice catalog for this account is currently empty.</p>
        </div>
      )}

      {/* ── ACTIVE VOICE CATALOG GRID ────────────────────────────────────── */}
      {!loadingVoices && catalogStatus === "success" && (
        <div className="space-y-4">
          {/* Filters Bar */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-white p-3 border border-zinc-200 rounded-sm shadow-xs">
            <div className="relative w-full sm:w-64">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-zinc-400" />
              <Input
                placeholder="Search voices by name, accent, ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 text-xs h-8 bg-zinc-50/50"
              />
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto overflow-x-auto pb-1 sm:pb-0">
              {/* Gender filter buttons */}
              <div className="flex items-center border border-zinc-200 rounded-sm bg-zinc-50 p-0.5 shrink-0">
                {(["all", "female", "male"] as const).map((g) => (
                  <button
                    key={g}
                    type="button"
                    onClick={() => setGenderFilter(g)}
                    className={`px-2.5 py-1 text-[11px] font-medium rounded-xs transition-colors capitalize ${
                      genderFilter === g
                        ? "bg-white text-zinc-950 shadow-xs font-semibold"
                        : "text-zinc-600 hover:text-zinc-950"
                    }`}
                  >
                    {g}
                  </button>
                ))}
              </div>

              {/* Category filter dropdown */}
              {categories.length > 0 && (
                <select
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className="text-xs h-7 rounded-sm border border-zinc-200 bg-zinc-50 px-2 text-zinc-700 shrink-0"
                >
                  <option value="all">All Categories</option>
                  {categories.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>

          {/* Voice Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 max-h-[460px] overflow-y-auto pr-1">
            {filteredVoices.map((voice) => {
              const isSelected =
                (selectedVoiceId && voice.voice_id === selectedVoiceId) ||
                (!selectedVoiceId &&
                  selectedVoiceName &&
                  voice.name.toLowerCase() === selectedVoiceName.toLowerCase());

              const isPlaying = playingVoiceId === voice.voice_id;
              const isLoadingThis = loadingAudioId === voice.voice_id;

              return (
                <div
                  key={voice.voice_id}
                  onClick={() => handleSelectVoiceCard(voice)}
                  className={`p-3.5 border rounded-sm transition-all cursor-pointer flex flex-col justify-between space-y-3 relative ${
                    isSelected
                      ? "border-zinc-950 bg-zinc-50 ring-1 ring-zinc-950 shadow-sm"
                      : "border-zinc-200 hover:border-zinc-300 bg-white hover:bg-zinc-50/50"
                  }`}
                >
                  <div className="space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <div
                          className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
                            voice.gender === "female"
                              ? "bg-amber-100 text-amber-900 border border-amber-200"
                              : "bg-indigo-100 text-indigo-900 border border-indigo-200"
                          }`}
                        >
                          {voice.name.charAt(0)}
                        </div>
                        <div>
                          <div className="flex items-center gap-1.5">
                            <h4 className="text-xs font-bold text-zinc-950">{voice.name}</h4>
                            {isSelected && (
                              <span className="bg-zinc-950 text-white rounded-full p-0.5">
                                <Check className="w-2.5 h-2.5" />
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-1 text-[10px] text-zinc-500 font-medium">
                            <span className="capitalize">{voice.gender}</span>
                            {voice.accent && <span>• {voice.accent}</span>}
                          </div>
                        </div>
                      </div>

                      {voice.category && (
                        <span className="px-1.5 py-0.5 text-[9px] font-semibold bg-zinc-100 border border-zinc-200 text-zinc-600 rounded-sm uppercase tracking-wider shrink-0">
                          {voice.category}
                        </span>
                      )}
                    </div>

                    <p className="text-[11px] text-zinc-600 line-clamp-2 leading-relaxed">
                      {voice.description || `${voice.name} is a synthesized voice.`}
                    </p>

                    <div className="text-[10px] font-mono text-zinc-400 truncate">
                      ID: {voice.voice_id}
                    </div>
                  </div>

                  <div className="pt-2 border-t border-zinc-200 flex items-center justify-between gap-2">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handlePlayPreview(voice);
                      }}
                      className={`flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-medium border rounded-sm transition-all ${
                        isPlaying
                          ? "bg-rose-50 border-rose-300 text-rose-700 font-semibold"
                          : "bg-zinc-50 hover:bg-zinc-100 border-zinc-200 text-zinc-700"
                      }`}
                    >
                      {isLoadingThis ? (
                        <RefreshCw className="w-3 h-3 animate-spin text-zinc-500" />
                      ) : isPlaying ? (
                        <>
                          <Pause className="w-3 h-3 text-rose-600 fill-rose-600" />
                          <span>Stop</span>
                          <span className="flex items-end gap-0.5 h-3 ml-1">
                            <span className="w-0.5 bg-rose-500 animate-bounce h-2" />
                            <span className="w-0.5 bg-rose-500 animate-bounce h-3 delay-75" />
                            <span className="w-0.5 bg-rose-500 animate-bounce h-1.5 delay-150" />
                          </span>
                        </>
                      ) : (
                        <>
                          <Play className="w-3 h-3 text-zinc-700 fill-zinc-700" />
                          <span>Play Sample</span>
                        </>
                      )}
                    </button>

                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleSelectVoiceCard(voice);
                      }}
                      className={`px-2 py-1 text-[11px] font-semibold rounded-sm transition-colors ${
                        isSelected
                          ? "bg-zinc-950 text-white"
                          : "text-zinc-600 hover:text-zinc-950"
                      }`}
                    >
                      {isSelected ? "Selected" : "Select"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {filteredVoices.length === 0 && (
            <div className="py-12 border border-dashed border-zinc-200 rounded-sm bg-white text-center text-zinc-400 space-y-2">
              <Mic className="w-8 h-8 mx-auto opacity-40" />
              <p className="text-xs font-semibold text-zinc-600">No voices found matching your search</p>
              <p className="text-[11px] text-zinc-400">Try clearing filters or search query.</p>
            </div>
          )}
        </div>
      )}

      {/* ── Active Selection Preview Footer ──────────────────────────────── */}
      <div className="bg-zinc-900 text-zinc-100 p-4 rounded-sm shadow-xs flex items-center justify-between flex-wrap gap-3 border border-zinc-800">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-zinc-800 text-white flex items-center justify-center font-bold text-sm border border-zinc-700 shadow-xs">
            {(selectedVoiceName || "V").charAt(0).toUpperCase()}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-zinc-300">Selected Voice:</span>
              <span className="text-sm font-bold text-white">
                {selectedVoiceName || "None selected"}
              </span>
              <span className="px-1.5 py-0.5 text-[10px] bg-zinc-800 border border-zinc-700 text-zinc-300 rounded font-mono uppercase">
                {currentProvider}
              </span>
            </div>
            <div className="text-[11px] text-zinc-400 flex items-center gap-2 mt-0.5">
              <span className="capitalize">{selectedVoiceGender}</span>
              <span>• Model: {activeModel}</span>
              {(selectedVoiceId || currentVoiceObj?.voice_id) && (
                <span className="font-mono text-zinc-400 text-[10px]">
                  ID: {selectedVoiceId || currentVoiceObj?.voice_id}
                </span>
              )}
            </div>
          </div>
        </div>

        {currentVoiceObj && (
          <Button
            type="button"
            variant="outline"
            onClick={() => handlePlayPreview(currentVoiceObj)}
            disabled={disabled}
            className="text-xs bg-zinc-800 border-zinc-700 text-zinc-200 hover:bg-zinc-700 hover:text-white"
          >
            {playingVoiceId === currentVoiceObj.voice_id ? (
              <Pause className="w-3.5 h-3.5 mr-1.5 text-rose-400" />
            ) : (
              <Volume2 className="w-3.5 h-3.5 mr-1.5 text-emerald-400" />
            )}
            {playingVoiceId === currentVoiceObj.voice_id ? "Pause Preview" : "Play Voice Preview"}
          </Button>
        )}
      </div>
    </div>
  );
}
