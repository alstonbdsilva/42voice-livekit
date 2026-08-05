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
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import ElevenLabsService, { ElevenLabsVoice } from "@/services/elevenlabs.service";

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

interface ElevenLabsVoiceSelectorProps {
  selectedVoiceName: string;
  selectedVoiceGender: "female" | "male";
  onSelectVoice: (voiceName: string, gender: "female" | "male", voiceId?: string) => void;
  voiceSettings?: ElevenLabsVoiceSettings;
  onUpdateSettings?: (settings: ElevenLabsVoiceSettings) => void;
  disabled?: boolean;
}

export default function ElevenLabsVoiceSelector({
  selectedVoiceName,
  selectedVoiceGender,
  onSelectVoice,
  voiceSettings = DEFAULT_ELEVENLABS_SETTINGS,
  onUpdateSettings,
  disabled = false,
}: ElevenLabsVoiceSelectorProps) {
  const [voices, setVoices] = useState<ElevenLabsVoice[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [genderFilter, setGenderFilter] = useState<"all" | "female" | "male">("all");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [hasApiKey, setHasApiKey] = useState(false);
  const [loadingVoices, setLoadingVoices] = useState(false);

  // Audio preview state
  const [playingVoiceId, setPlayingVoiceId] = useState<string | null>(null);
  const [loadingAudioId, setLoadingAudioId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Custom Voice ID state
  const [isCustomMode, setIsCustomMode] = useState(false);
  const [customVoiceId, setCustomVoiceId] = useState("");
  const [customVoiceName, setCustomVoiceName] = useState("");

  // Settings dropdown accordion
  const [showSettings, setShowSettings] = useState(false);
  const [localSettings, setLocalSettings] = useState<ElevenLabsVoiceSettings>(voiceSettings);

  // Fetch dynamic ElevenLabs voices from backend on load
  useEffect(() => {
    let isMounted = true;
    async function loadVoices() {
      setLoadingVoices(true);
      try {
        const res = await ElevenLabsService.getVoices();
        if (isMounted) {
          setHasApiKey(res.hasApiKey);
          if (res.voices && Array.isArray(res.voices)) {
            setVoices(res.voices);
          }
        }
      } catch (err) {
        console.error("Failed to load ElevenLabs voices:", err);
      } finally {
        if (isMounted) setLoadingVoices(false);
      }
    }
    loadVoices();
    return () => {
      isMounted = false;
      stopAudio();
    };
  }, []);

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

  const handlePlayPreview = async (voice: ElevenLabsVoice) => {
    if (disabled) return;

    if (playingVoiceId === voice.voice_id) {
      stopAudio();
      return;
    }

    stopAudio();
    setLoadingAudioId(voice.voice_id);

    try {
      let audioUrl = voice.preview_url;

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
      if (hasApiKey && voice.voice_id) {
        const liveAudioUrl = await ElevenLabsService.previewVoice({
          voiceId: voice.voice_id,
          text: `Hello! This is a live voice preview for ${voice.name}.`,
          modelId: localSettings.modelId,
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

      toast.error("No valid preview audio source available for this voice.");
      setPlayingVoiceId(null);
    } catch (err: any) {
      console.error("Failed to play voice sample:", err);
      toast.error(err?.response?.data?.message || "Failed to generate or play voice preview.");
    } finally {
      setLoadingAudioId(null);
    }
  };

  const handlePlayCustomPreview = async () => {
    if (!customVoiceId.trim()) {
      return toast.error("Please enter an ElevenLabs Voice ID.");
    }

    const tempVoice: ElevenLabsVoice = {
      voice_id: customVoiceId.trim(),
      name: customVoiceName.trim() || "Custom Voice",
      gender: selectedVoiceGender,
      description: "Custom ElevenLabs Voice ID",
    };

    await handlePlayPreview(tempVoice);
  };

  const handleSelectVoiceCard = (voice: ElevenLabsVoice) => {
    if (disabled) return;
    onSelectVoice(voice.name, voice.gender === "male" ? "male" : "female", voice.voice_id);
  };

  const handleApplyCustomVoice = () => {
    if (!customVoiceId.trim()) {
      return toast.error("Please enter a valid ElevenLabs Voice ID.");
    }
    const nameToSave = customVoiceName.trim() ? customVoiceName.trim() : customVoiceId.trim();
    onSelectVoice(nameToSave, selectedVoiceGender, customVoiceId.trim());
    toast.success(`Selected ElevenLabs voice ID: ${customVoiceId.trim()}`);
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
      v.name.toLowerCase() === selectedVoiceName.toLowerCase() ||
      v.voice_id === selectedVoiceName
  );

  return (
    <div className="space-y-4 w-full">
      {/* ── ElevenLabs Header & Provider Info ──────────────────────────────── */}
      <div className="bg-gradient-to-r from-zinc-900 via-zinc-950 to-zinc-900 text-white p-4 rounded-sm shadow-md border border-zinc-800 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-sm bg-gradient-to-tr from-amber-500 to-indigo-500 p-0.5 flex items-center justify-center shadow-xs">
            <div className="w-full h-full bg-zinc-950 rounded-xs flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-amber-400" />
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold tracking-tight font-display">ElevenLabs AI Voice Engine</h2>
              <span className="px-2 py-0.5 text-[10px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 rounded-full">
                Active Integration
              </span>
            </div>
            <p className="text-[11px] text-zinc-400">
              High-fidelity, expressive ultra-realistic voice synthesis powered by ElevenLabs
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {hasApiKey && (
            <span className="text-[11px] text-emerald-400 font-medium flex items-center gap-1 bg-zinc-800/80 px-2.5 py-1 rounded-sm border border-zinc-700">
              <Check className="w-3 h-3" /> ElevenLabs API Key Loaded
            </span>
          )}
          <button
            type="button"
            onClick={() => setShowSettings(!showSettings)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 rounded-sm transition-colors font-medium shadow-xs"
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
            <span>Voice Parameters</span>
            {showSettings ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* ── Advanced Parameters Accordion ────────────────────────────────── */}
      {showSettings && (
        <div className="bg-zinc-50 border border-zinc-200 p-4 rounded-sm shadow-xs space-y-4 animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="flex items-center justify-between border-b border-zinc-200 pb-2">
            <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-800 flex items-center gap-1.5">
              <Sliders className="w-3.5 h-3.5 text-zinc-600" /> ElevenLabs Voice Settings & Model
            </h4>
            <span className="text-[11px] text-zinc-500">Fine-tune voice emotion, clarity & performance</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="space-y-1.5">
              <Label className="text-[11px] font-medium text-zinc-700">ElevenLabs Model</Label>
              <select
                value={localSettings.modelId}
                onChange={(e) => handleSettingChange("modelId", e.target.value)}
                disabled={disabled}
                className="w-full text-xs h-8 rounded-sm border border-zinc-300 bg-white px-2.5 shadow-xs focus:outline-hidden focus:ring-1 focus:ring-zinc-950"
              >
                <option value="eleven_multilingual_v2">Multilingual v2 (Recommended)</option>
                <option value="eleven_turbo_v2_5">Turbo v2.5 (Lowest Latency)</option>
                <option value="eleven_flash_v2_5">Flash v2.5 (Ultra Fast)</option>
                <option value="eleven_monolingual_v1">Monolingual v1 (English)</option>
              </select>
            </div>

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
              <p className="text-[10px] text-zinc-400">Higher = more consistent, Lower = more dynamic</p>
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
              <p className="text-[10px] text-zinc-400">Boosts voice fidelity and target accent</p>
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

      {/* ── Mode Switcher: Pre-built vs Custom Voice ID ────────────────────── */}
      <div className="flex items-center justify-between gap-3 bg-white p-3 border border-zinc-200 rounded-sm shadow-xs flex-wrap">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setIsCustomMode(false)}
            className={`px-3 py-1.5 text-xs font-semibold rounded-sm transition-all flex items-center gap-1.5 ${!isCustomMode
              ? "bg-zinc-950 text-white shadow-xs"
              : "bg-zinc-100 text-zinc-700 hover:bg-zinc-200"
              }`}
          >
            <Mic className="w-3.5 h-3.5" /> ElevenLabs Voice Catalog ({voices.length})
          </button>
          <button
            type="button"
            onClick={() => setIsCustomMode(true)}
            className={`px-3 py-1.5 text-xs font-semibold rounded-sm transition-all flex items-center gap-1.5 ${isCustomMode
              ? "bg-zinc-950 text-white shadow-xs"
              : "bg-zinc-100 text-zinc-700 hover:bg-zinc-200"
              }`}
          >
            <Sparkles className="w-3.5 h-3.5" /> Custom Voice ID / Cloned Voice
          </button>
        </div>

        <div className="text-[11px] text-zinc-500 font-medium">
          Selected Voice: <span className="font-bold text-zinc-900">{selectedVoiceName}</span> ({selectedVoiceGender})
        </div>
      </div>

      {/* ── CUSTOM VOICE ID MODE ───────────────────────────────────────────── */}
      {isCustomMode ? (
        <div className="bg-white border border-zinc-200 p-6 rounded-sm shadow-xs space-y-4">
          <div className="space-y-1">
            <h3 className="text-sm font-bold text-zinc-900 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-500" /> Use Custom ElevenLabs Voice ID
            </h3>
            <p className="text-xs text-zinc-500">
              Enter your cloned or private ElevenLabs Voice ID generated from your ElevenLabs dashboard.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label className="text-xs font-medium">ElevenLabs Voice ID *</Label>
              <Input
                placeholder="e.g. 21m00Tcm4TlvDq8ikWAM or custom_voice_id"
                value={customVoiceId}
                onChange={(e) => setCustomVoiceId(e.target.value)}
                className="text-xs font-mono"
                disabled={disabled}
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-medium">Custom Voice Name (Optional)</Label>
              <Input
                placeholder="e.g. My Executive Brand Voice"
                value={customVoiceName}
                onChange={(e) => setCustomVoiceName(e.target.value)}
                className="text-xs"
                disabled={disabled}
              />
            </div>
          </div>

          <div className="flex items-center gap-3 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={handlePlayCustomPreview}
              disabled={disabled || !customVoiceId.trim()}
              className="text-xs"
            >
              {loadingAudioId === customVoiceId.trim() ? (
                <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" />
              ) : playingVoiceId === customVoiceId.trim() ? (
                <Pause className="w-3.5 h-3.5 mr-1.5 text-rose-600" />
              ) : (
                <Play className="w-3.5 h-3.5 mr-1.5 text-emerald-600" />
              )}
              {playingVoiceId === customVoiceId.trim() ? "Stop Audio" : "Test Custom Voice"}
            </Button>

            <Button
              type="button"
              onClick={handleApplyCustomVoice}
              disabled={disabled || !customVoiceId.trim()}
              className="text-xs bg-zinc-950 hover:bg-zinc-800 text-white"
            >
              Apply Custom Voice ID
            </Button>
          </div>
        </div>
      ) : (
        /* ── PRE-BUILT CATALOG MODE ───────────────────────────────────────── */
        <div className="space-y-4">
          {/* Filters Bar */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-white p-3 border border-zinc-200 rounded-sm shadow-xs">
            <div className="relative w-full sm:w-64">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-zinc-400" />
              <Input
                placeholder="Search ElevenLabs voices..."
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
                    className={`px-2.5 py-1 text-[11px] font-medium rounded-xs transition-colors capitalize ${genderFilter === g
                      ? "bg-white text-zinc-950 shadow-xs font-semibold"
                      : "text-zinc-600 hover:text-zinc-950"
                      }`}
                  >
                    {g}
                  </button>
                ))}
              </div>

              {/* Category filter pills */}
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
                selectedVoiceName.toLowerCase() === voice.name.toLowerCase() ||
                selectedVoiceName === voice.voice_id;

              const isPlaying = playingVoiceId === voice.voice_id;
              const isLoadingThis = loadingAudioId === voice.voice_id;

              return (
                <div
                  key={voice.voice_id}
                  onClick={() => handleSelectVoiceCard(voice)}
                  className={`p-3.5 border rounded-sm transition-all cursor-pointer flex flex-col justify-between space-y-3 relative ${isSelected
                    ? "border-zinc-950 bg-zinc-50 ring-1 ring-zinc-950 shadow-sm"
                    : "border-zinc-200 hover:border-zinc-300 bg-white hover:bg-zinc-50/50"
                    }`}
                >
                  <div className="space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <div
                          className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${voice.gender === "female"
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
                      {voice.description || `${voice.name} is an ElevenLabs synthesized voice.`}
                    </p>
                  </div>

                  <div className="pt-2 border-t border-zinc-200 flex items-center justify-between gap-2">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handlePlayPreview(voice);
                      }}
                      className={`flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-medium border rounded-sm transition-all ${isPlaying
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
                          {/* Animated sound wave bars */}
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
                      className={`px-2 py-1 text-[11px] font-semibold rounded-sm transition-colors ${isSelected
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
              <p className="text-xs font-semibold text-zinc-600">No ElevenLabs voices found matching your search</p>
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
              <span className="text-xs font-semibold text-zinc-300">Selected ElevenLabs Voice:</span>
              <span className="text-sm font-bold text-white">{selectedVoiceName}</span>
            </div>
            <div className="text-[11px] text-zinc-400 flex items-center gap-2 mt-0.5">
              <span className="capitalize">{selectedVoiceGender} Voice</span>
              {currentVoiceObj?.voice_id && (
                <span className="font-mono text-zinc-500 text-[10px]">ID: {currentVoiceObj.voice_id}</span>
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
