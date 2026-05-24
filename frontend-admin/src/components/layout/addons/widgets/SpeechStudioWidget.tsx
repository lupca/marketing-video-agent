import { useState, useEffect, useRef } from "react";
import { Volume2, Play, Pause, Save, RefreshCw, AlertCircle, Loader2, CheckCircle2 } from "lucide-react";
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

export default function SpeechStudioWidget() {
  const { projects, loading: projectsLoading } = useProjects();
  const { initialData } = useAIStudioAddon();
  
  // Form State
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [text, setText] = useState("");
  const [model, setModel] = useState<"edge-tts" | "melotts">("edge-tts");
  const [speaker, setSpeaker] = useState("vi-VN-HoaiMyNeural");

  // UI & Audio State
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentJob, setCurrentJob] = useState<GenerationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "success" | "error">("idle");
  const [isPlaying, setIsPlaying] = useState(false);

  // Audio Playback Ref
  const audioRef = useRef<HTMLAudioElement | null>(null);

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

  // Đổi người nói khi model đổi
  useEffect(() => {
    if (model === "edge-tts") {
      setSpeaker("vi-VN-HoaiMyNeural");
    } else {
      setSpeaker("VI-default");
    }
  }, [model]);

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

    setError(null);
    setIsGenerating(true);
    setSaveStatus("idle");
    setIsPlaying(false);

    try {
      const response = await api.post("/api/jobs", {
        job_type: "tts",
        project_id: selectedProjectId,
        config_data: {
          model: model,
          text: text,
          speed: 1.0,
          speaker: speaker
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

        {/* Lựa chọn mô hình */}
        <div className="space-y-1.5">
          <label className="text-[11px] font-semibold text-muted-foreground">Mô hình lồng tiếng (Model)</label>
          <div className="grid grid-cols-2 gap-2">
            {[
              { id: "edge-tts", name: "Edge Cloud", desc: "Giọng đọc rất thật" },
              { id: "melotts", name: "MeloTTS", desc: "Chạy offline local" }
            ].map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => setModel(m.id as any)}
                disabled={isGenerating}
                className={cn(
                  "py-2 rounded-xl text-[10px] font-bold border transition-all cursor-pointer text-center flex flex-col gap-0.5",
                  model === m.id
                    ? "bg-primary/20 border-primary text-primary"
                    : "bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10"
                )}
              >
                <span>{m.name}</span>
                <span className="text-[7.5px] opacity-60 font-normal">{m.desc}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Văn bản cần gen giọng nói */}
        <div className="space-y-1.5">
          <label className="text-[11px] font-semibold text-muted-foreground">Nội dung thuyết minh (Văn bản)</label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={isGenerating}
            placeholder="Nhập nội dung kịch bản hoặc lời thoại cần AI thuyết minh tiếng Việt..."
            className="w-full h-28 bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-xs text-white placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-primary resize-none font-sans leading-relaxed"
          />
        </div>

        {/* Chọn Speaker */}
        <div className="space-y-1.5">
          <label className="text-[11px] font-semibold text-muted-foreground">Chọn Giọng đọc (Speaker)</label>
          {model === "edge-tts" ? (
            <select
              value={speaker}
              onChange={(e) => setSpeaker(e.target.value)}
              disabled={isGenerating}
              className="w-full bg-zinc-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:ring-1 focus:ring-primary font-sans"
            >
              <option value="vi-VN-HoaiMyNeural">Hoài Mỹ (Giọng Nữ Bắc ngọt ngào)</option>
              <option value="vi-VN-NamMinhNeural">Nam Minh (Giọng Nam trầm ấm)</option>
            </select>
          ) : (
            <select
              value={speaker}
              onChange={(e) => setSpeaker(e.target.value)}
              disabled={isGenerating}
              className="w-full bg-zinc-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:ring-1 focus:ring-primary font-sans"
            >
              <option value="VI-default">VI-default (MeloTTS Mặc định)</option>
            </select>
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
