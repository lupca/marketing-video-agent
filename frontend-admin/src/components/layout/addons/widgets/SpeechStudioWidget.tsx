import { useState, useEffect, useRef } from "react";
import { Volume2, Play, Pause, Save, RefreshCw, AlertCircle, Loader2, CheckCircle2, Key, Database } from "lucide-react";
import api from "../../../../lib/api";
import { cn } from "../../../../lib/utils";
import { useProjects } from "../../../../hooks/useProjects";
import { useAIStudioAddon } from "../../../../context/AIStudioAddonContext";

interface GenerationResult {
  jobId: number;
  status: string;
  url?: string;
  s3Url?: string;
  error?: string;
}

interface TTSModelConfig {
  id: string;
  name: string;
  provider: string;
  base_url?: string;
  api_key?: string;
  model_name?: string;
}

export default function SpeechStudioWidget() {
  const { projects, loading: projectsLoading } = useProjects();
  const { initialData } = useAIStudioAddon();
  
  // Dynamic TTS Models
  const [ttsModels, setTtsModels] = useState<TTSModelConfig[]>([]);
  const [loadingModels, setLoadingModels] = useState(true);

  // Form State
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [text, setText] = useState("");
  const [model, setModel] = useState<string>(""); // Database model ID
  const [speaker, setSpeaker] = useState("vi-VN-HoaiMyNeural");
  const [customVoiceId, setCustomVoiceId] = useState("");

  // UI & Audio State
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentJob, setCurrentJob] = useState<GenerationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "success" | "error">("idle");
  const [isPlaying, setIsPlaying] = useState(false);

  // Audio Playback Ref
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Fetch TTS Models on mount
  const fetchTtsModels = async () => {
    setLoadingModels(true);
    try {
      const res = await api.get("/api/system/tts-models");
      setTtsModels(res.data);
      if (res.data.length > 0) {
        const defaultModel = res.data.find((m: any) => m.provider === "edge-tts") || res.data[0];
        setModel(defaultModel.id);
      }
    } catch (err) {
      console.error("Failed to fetch TTS models in widget:", err);
    } finally {
      setLoadingModels(false);
    }
  };

  useEffect(() => {
    fetchTtsModels();
  }, []);

  // Tự động nạp kịch bản được truyền nhanh từ màn hình chính (Deep-linking)
  useEffect(() => {
    if (initialData && initialData.text) {
      setText(initialData.text);
      if (initialData.projectId) {
        setSelectedProjectId(initialData.projectId);
      }
    }
  }, [initialData]);

  // Thiết lập dự án mặc định ban đầu
  useEffect(() => {
    if (projects.length > 0 && !selectedProjectId) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  // Resolve current active model provider
  const activeModelObj = ttsModels.find((m) => m.id === model);
  const activeProvider = activeModelObj?.provider || "edge-tts";

  // Đổi người nói khi model/provider đổi
  useEffect(() => {
    if (activeProvider === "edge-tts") {
      setSpeaker("vi-VN-HoaiMyNeural");
    } else if (activeProvider === "melotts") {
      setSpeaker("VI-default");
    } else if (activeProvider === "elevenlabs") {
      setSpeaker("EXAVITQu4vr4xnSDxMaL"); // Bella
    }
  }, [activeProvider, model]);

  // Quản lý trạng thái Audio Player
  useEffect(() => {
    if (currentJob?.url) {
      if (audioRef.current) {
        audioRef.current.pause();
      }
      audioRef.current = new Audio(currentJob.url);
      audioRef.current.addEventListener("ended", () => setIsPlaying(false));
      audioRef.current.addEventListener("pause", () => setIsPlaying(false));
      audioRef.current.addEventListener("play", () => setIsPlaying(true));
    }
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
      }
    };
  }, [currentJob?.url]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play().catch((err) => {
        console.error("Audio play failed in widget:", err);
      });
    }
  };

  const handleGenerate = async () => {
    if (!text.trim()) {
      setError("Vui lòng nhập đoạn văn bản.");
      return;
    }
    if (!selectedProjectId) {
      setError("Vui lòng chọn Dự án để lưu giọng nói.");
      return;
    }
    if (!model) {
      setError("Chưa chọn cấu hình mô hình TTS.");
      return;
    }

    setError(null);
    setIsGenerating(true);
    setSaveStatus("idle");
    setIsPlaying(false);

    // Resolve final speaker choice (for elevenlabs custom voice)
    const finalSpeaker = (activeProvider === "elevenlabs" && speaker === "custom") 
      ? customVoiceId 
      : speaker;

    if (activeProvider === "elevenlabs" && speaker === "custom" && !customVoiceId.trim()) {
      setError("Vui lòng nhập Voice ID tùy chỉnh ElevenLabs.");
      setIsGenerating(false);
      return;
    }

    try {
      const response = await api.post("/api/jobs", {
        job_type: "tts",
        project_id: selectedProjectId,
        config_data: {
          model: model,
          text: text,
          speed: 1.0,
          speaker: finalSpeaker
        }
      });

      const jobId = response.data.id;
      setCurrentJob({ jobId, status: "PENDING" });
      startPolling(jobId);
    } catch (err: any) {
      console.error("Failed to generate speech in widget:", err);
      setError(err.response?.data?.detail || "Không thể gửi yêu cầu tạo giọng nói.");
      setIsGenerating(false);
    }
  };

  const startPolling = (jobId: number) => {
    const interval = setInterval(async () => {
      try {
        const res = await api.get(`/api/jobs/${jobId}`);
        const job = res.data;

        if (job.status === "SUCCESS") {
          try {
            const dlRes = await api.get(`/api/jobs/${jobId}/download`);
            setCurrentJob({ 
              jobId, 
              status: "SUCCESS", 
              url: dlRes.data.download_url, 
              s3Url: job.result_url 
            });
          } catch (dlErr) {
            setCurrentJob({ 
              jobId, 
              status: "SUCCESS", 
              url: job.result_url, 
              s3Url: job.result_url 
            });
          }
          setIsGenerating(false);
          clearInterval(interval);
        } else if (job.status === "FAILED") {
          setCurrentJob({ jobId, status: "FAILED", error: job.error_message });
          setIsGenerating(false);
          clearInterval(interval);
        } else {
          setCurrentJob({ jobId, status: job.status });
        }
      } catch (err) {
        console.error("Speech polling error in widget:", err);
      }
    }, 2000);

    // Timeout sau 5 phút
    setTimeout(() => {
      clearInterval(interval);
      if (isGenerating) {
        setIsGenerating(false);
        setError("Quá thời gian phản hồi từ máy chủ.");
      }
    }, 300000);
  };

  const handleSaveToAssets = async () => {
    const s3Url = currentJob?.s3Url || currentJob?.url;
    if (!s3Url) return;
    
    setSaveStatus("saving");
    try {
      await api.post("/api/assets", {
        project_id: selectedProjectId,
        s3_url: s3Url,
        asset_type: "audio",
        file_name: `tts_addon_${currentJob.jobId}.mp3`,
        mime_type: "audio/mpeg"
      });
      setSaveStatus("success");
      setTimeout(() => setSaveStatus("idle"), 3000);
    } catch (err) {
      console.error("Failed to save audio asset:", err);
      setSaveStatus("error");
    }
  };

  return (
    <div className="space-y-4">
      {/* Khung chơi nhạc/TTS output */}
      {isGenerating || currentJob?.url || currentJob?.status === "FAILED" ? (
        <div className="bg-black/30 border border-white/10 rounded-2xl p-4 flex flex-col items-center justify-center min-h-[160px]">
          {isGenerating ? (
            <div className="text-center space-y-3">
              <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto" />
              <div className="space-y-1">
                <p className="text-xs font-bold text-white">AI đang đọc kịch bản...</p>
                <p className="text-[10px] text-muted-foreground animate-pulse">Trạng thái: {currentJob?.status || "PENDING"}</p>
              </div>
            </div>
          ) : currentJob?.url ? (
            <div className="w-full space-y-4 text-center animate-in fade-in duration-300">
              <div className="flex items-center justify-center gap-3 p-3 bg-white/5 border border-white/10 rounded-2xl max-w-xs mx-auto">
                <button
                  onClick={togglePlay}
                  className="w-12 h-12 bg-primary hover:scale-105 active:scale-95 transition-all rounded-full flex items-center justify-center text-white cursor-pointer shadow-[0_0_10px_rgba(124,58,237,0.4)]"
                >
                  {isPlaying ? <Pause className="w-5 h-5 fill-white text-white" /> : <Play className="w-5 h-5 fill-white text-white ml-0.5" />}
                </button>
                <div className="text-left overflow-hidden">
                  <p className="text-xs font-bold text-white truncate">Audio Thuyết Minh #{currentJob.jobId}</p>
                  <p className="text-[9px] text-emerald-400 font-semibold uppercase tracking-wider">Ready to use</p>
                </div>
              </div>

              {/* Toolbar */}
              <div className="flex gap-2">
                <button
                  onClick={handleSaveToAssets}
                  disabled={saveStatus !== "idle"}
                  className={cn(
                    "flex-1 py-2.5 rounded-xl text-[11px] font-bold uppercase tracking-wider flex items-center justify-center gap-2 border transition-all cursor-pointer",
                    saveStatus === "success" 
                      ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400" 
                      : "bg-white/5 hover:bg-white/10 border-white/10 text-white"
                  )}
                >
                  {saveStatus === "saving" ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : saveStatus === "success" ? (
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  ) : (
                    <Save className="w-3.5 h-3.5" />
                  )}
                  {saveStatus === "success" ? "Đã lưu vào kho" : "Lưu vào kho tư liệu"}
                </button>

                <button
                  onClick={() => {
                    setCurrentJob(null);
                    setText("");
                  }}
                  className="px-3.5 py-2.5 bg-white/5 hover:bg-white/10 border border-white/10 text-white rounded-xl text-xs cursor-pointer"
                  title="Tạo giọng mới"
                >
                  <RefreshCw className="w-4 h-4" />
                </button>
              </div>
            </div>
          ) : (
            <div className="text-center space-y-3 p-4">
              <AlertCircle className="w-8 h-8 text-red-500 mx-auto" />
              <p className="text-xs font-bold text-white">Lỗi tạo giọng nói</p>
              <p className="text-[10px] text-muted-foreground leading-tight">{currentJob?.error || "Vui lòng thử lại sau."}</p>
              <button 
                onClick={handleGenerate}
                className="px-4 py-2 bg-primary/20 hover:bg-primary/30 border border-primary/30 rounded-xl text-[10px] font-bold uppercase text-white cursor-pointer"
              >
                Thử lại
              </button>
            </div>
          )}
        </div>
      ) : (
        /* Trạng thái trống (Canvas) */
        <div className="bg-black/30 border border-dashed border-white/10 rounded-2xl p-6 text-center text-muted-foreground/60 select-none">
          <Volume2 className="w-10 h-10 mx-auto opacity-30 mb-2" />
          <p className="text-[11px] font-medium leading-relaxed max-w-[200px] mx-auto">
            Nhập văn bản kịch bản và nhấn nút để chuyển thành giọng nói thuyết minh chất lượng cao.
          </p>
        </div>
      )}

      {/* Form Cấu hình */}
      <div className="space-y-4 pt-2">
        {/* Chọn Dự Án */}
        <div className="space-y-1.5">
          <label className="text-[11px] font-semibold text-muted-foreground">Chọn Dự án lưu trữ</label>
          <select
            value={selectedProjectId}
            onChange={(e) => setSelectedProjectId(e.target.value)}
            disabled={projectsLoading || isGenerating}
            className="w-full bg-zinc-900 border border-white/10 rounded-xl px-3 py-2.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-primary"
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>

        {/* Lựa chọn mô hình từ DB */}
        <div className="space-y-1.5">
          <label className="text-[11px] font-semibold text-muted-foreground flex items-center justify-between">
            <span>Mô hình thuyết minh (Model)</span>
            <span className="text-[8px] opacity-40 flex items-center gap-0.5"><Database className="w-2.5 h-2.5" /> DB Loaded</span>
          </label>
          {loadingModels ? (
            <div className="flex items-center gap-1.5 py-2.5 bg-white/5 border border-white/10 rounded-xl px-3 text-[10px] text-muted-foreground">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" /> Đang quét mô hình...
            </div>
          ) : (
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              disabled={isGenerating}
              className="w-full bg-zinc-900 border border-white/10 rounded-xl px-3 py-2.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-primary"
            >
              {ttsModels.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} ({m.provider === "melotts" ? "MeloTTS" : m.provider === "elevenlabs" ? "ElevenLabs" : "Edge-TTS"})
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Văn bản cần gen giọng nói */}
        <div className="space-y-1.5">
          <label className="text-[11px] font-semibold text-muted-foreground">Nội dung thuyết minh (Văn bản)</label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={isGenerating}
            placeholder="Nhập nội dung kịch bản hoặc lời thoại cần AI thuyết minh tiếng Việt..."
            className="w-full h-24 bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs text-white placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-primary resize-none font-sans leading-relaxed"
          />
        </div>

        {/* Chọn Speaker */}
        <div className="space-y-1.5">
          <label className="text-[11px] font-semibold text-muted-foreground">Chọn Giọng đọc (Speaker)</label>
          {activeProvider === "edge-tts" ? (
            <select
              value={speaker}
              onChange={(e) => setSpeaker(e.target.value)}
              disabled={isGenerating}
              className="w-full bg-zinc-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:ring-1 focus:ring-primary font-sans"
            >
              <option value="vi-VN-HoaiMyNeural">Hoài Mỹ (Giọng Nữ Bắc ngọt ngào)</option>
              <option value="vi-VN-NamMinhNeural">Nam Minh (Giọng Nam trầm ấm)</option>
            </select>
          ) : activeProvider === "melotts" ? (
            <select
              value={speaker}
              onChange={(e) => setSpeaker(e.target.value)}
              disabled={isGenerating}
              className="w-full bg-zinc-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:ring-1 focus:ring-primary font-sans"
            >
              <option value="VI-default">VI-default (MeloTTS Mặc định)</option>
            </select>
          ) : (
            <div className="space-y-2">
              <select
                value={speaker}
                onChange={(e) => setSpeaker(e.target.value)}
                disabled={isGenerating}
                className="w-full bg-zinc-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:ring-1 focus:ring-primary font-sans"
              >
                <option value="EXAVITQu4vr4xnSDxMaL">Bella (Nữ - Multilingual)</option>
                <option value="21m00Tcm4TlvDq8ikWAM">Rachel (Nữ - Multilingual)</option>
                <option value="pNInz6obpgDQGcFmaJgB">Adam (Nam - Multilingual)</option>
                <option value="custom">Voice ID Tùy chọn</option>
              </select>

              {speaker === "custom" && (
                <div className="space-y-1.5 animate-in fade-in duration-200">
                  <label className="text-[9px] font-semibold text-muted-foreground flex items-center gap-1">
                    <Key className="w-3.5 h-3.5 text-primary" /> Nhập ElevenLabs Voice ID tùy chọn
                  </label>
                  <input
                    type="text"
                    required
                    value={customVoiceId}
                    onChange={(e) => setCustomVoiceId(e.target.value)}
                    placeholder="Ví dụ: pNInz6obpgq5mWzIA5Bj"
                    className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-1.5 text-[10px] text-white focus:outline-none focus:ring-1 focus:ring-primary font-mono text-[9px]"
                  />
                </div>
              )}
            </div>
          )}
        </div>

        {error && (
          <div className="p-2.5 bg-red-500/10 border border-red-500/20 rounded-xl text-[10px] text-red-400 flex items-center gap-2">
            <AlertCircle className="w-3.5 h-3.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Nút Tạo */}
        <button
          onClick={handleGenerate}
          disabled={isGenerating || projectsLoading}
          className={cn(
            "w-full py-3 rounded-xl text-xs font-bold text-white flex items-center justify-center gap-2 transition-all cursor-pointer shadow-lg",
            isGenerating 
              ? "bg-zinc-800 cursor-not-allowed" 
              : "bg-gradient-to-r from-violet-600 to-indigo-600 hover:scale-[1.01]"
          )}
        >
          {isGenerating ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Đang tạo giọng nói AI...
            </>
          ) : (
            <>
              <Volume2 className="w-4 h-4 animate-pulse" />
              Chuyển đổi Giọng nói
            </>
          )}
        </button>
      </div>
    </div>
  );
}
