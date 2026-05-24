import { useState, useEffect, useRef } from "react";
import { 
  Volume2, 
  Play, 
  Pause, 
  Download, 
  Save, 
  RefreshCw, 
  AlertCircle, 
  Loader2, 
  CheckCircle2, 
  Sliders, 
  Music,
  AudioLines,
  Cpu,
  CloudLightning,
  Trash2
} from "lucide-react";
import api from "../lib/api";
import { cn } from "../lib/utils";
import { useProjects } from "../hooks/useProjects";

interface GenerationResult {
  jobId: number;
  status: string;
  url?: string;
  s3Url?: string;
  error?: string;
}

export default function SpeechStudio() {
  const { projects, loading: projectsLoading } = useProjects();
  
  // Form State
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [text, setText] = useState("");
  const [model, setModel] = useState<"edge-tts" | "melotts">("edge-tts");
  const [speed, setSpeed] = useState<number>(1.0);
  const [speaker, setSpeaker] = useState("vi-VN-HoaiMyNeural");

  // UI State
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentJob, setCurrentJob] = useState<GenerationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "success" | "error">("idle");
  const [isPlaying, setIsPlaying] = useState(false);

  // Audio Ref for playing
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Set default project
  useEffect(() => {
    if (projects.length > 0 && !selectedProjectId) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  // Voice History States
  const [savedAudioList, setSavedAudioList] = useState<any[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [activeHistoryTab, setActiveHistoryTab] = useState<"history" | "suggestions">("history");
  const [playingHistoryId, setPlayingHistoryId] = useState<string | null>(null);
  const historyAudioRef = useRef<HTMLAudioElement | null>(null);

  const fetchSavedAudio = async () => {
    if (!selectedProjectId) return;
    setLoadingHistory(true);
    try {
      const res = await api.get("/api/assets", {
        params: { asset_type: "audio" }
      });
      // Filter for TTS generated assets
      const ttsAssets = res.data.filter((a: any) => 
        a.source === "generated" && (a.file_name.includes("tts") || a.file_name.includes("voice"))
      );
      setSavedAudioList(ttsAssets);
    } catch (err) {
      console.error("Failed to fetch saved audio list:", err);
    } finally {
      setLoadingHistory(false);
    }
  };

  useEffect(() => {
    if (selectedProjectId) {
      fetchSavedAudio();
    }
  }, [selectedProjectId, saveStatus]);

  const togglePlayHistory = (asset: any) => {
    if (playingHistoryId === asset.id) {
      if (historyAudioRef.current) {
        historyAudioRef.current.pause();
      }
      setPlayingHistoryId(null);
    } else {
      if (historyAudioRef.current) {
        historyAudioRef.current.pause();
      }
      const audioUrl = asset.presigned_url || asset.s3_url;
      historyAudioRef.current = new Audio(audioUrl);
      historyAudioRef.current.addEventListener("ended", () => setPlayingHistoryId(null));
      historyAudioRef.current.addEventListener("pause", () => setPlayingHistoryId(null));
      historyAudioRef.current.play().catch(err => console.error("Playback error:", err));
      setPlayingHistoryId(asset.id);
    }
  };

  const handleDeleteHistoryAsset = async (assetId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Bạn có chắc chắn muốn xóa tệp âm thanh này khỏi thư viện và giải phóng bộ nhớ MinIO không?")) return;
    try {
      await api.delete(`/api/assets/${assetId}`);
      setSavedAudioList((prev) => prev.filter((a) => a.id !== assetId));
      if (playingHistoryId === assetId) {
        if (historyAudioRef.current) {
          historyAudioRef.current.pause();
        }
        setPlayingHistoryId(null);
      }
    } catch (err) {
      console.error("Failed to delete asset:", err);
    }
  };

  // Adjust speaker default choice when model changes
  useEffect(() => {
    if (model === "edge-tts") {
      setSpeaker("vi-VN-HoaiMyNeural");
    } else {
      setSpeaker("VI-default");
    }
  }, [model]);

  // Audio ended listener
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
      audioRef.current.play().catch(err => {
        console.error("Audio playback error:", err);
      });
    }
  };

  const handleGenerate = async () => {
    if (!text.trim()) {
      setError("Vui lòng nhập văn bản để chuyển đổi sang giọng nói.");
      return;
    }
    if (!selectedProjectId) {
      setError("Vui lòng chọn hoặc tạo một Project.");
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
          speed: speed,
          speaker: speaker
        }
      });

      const jobId = response.data.id;
      setCurrentJob({ jobId, status: "PENDING" });
      startPolling(jobId);
    } catch (err: any) {
      console.error("Failed to start speech generation:", err);
      setError(err.response?.data?.detail || "Không thể khởi tạo tiến trình tạo giọng nói.");
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
            console.error("Failed to get download URL:", dlErr);
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
        console.error("Polling error:", err);
      }
    }, 2000);

    // Timeout after 5 minutes
    setTimeout(() => {
      clearInterval(interval);
      if (isGenerating) {
        setIsGenerating(false);
        setError("Quá thời gian chờ (Timeout). Vui lòng thử lại.");
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
        file_name: `tts_gen_${currentJob.jobId}.mp3`,
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
    <div className="flex h-[calc(100vh-2rem)] gap-6 p-2 overflow-hidden">
      {/* Left Column: Form Settings */}
      <div className="w-96 flex flex-col gap-4 overflow-y-auto pr-2 custom-scrollbar">
        <div className="bg-black/40 border border-white/10 rounded-2xl p-6 backdrop-blur-xl">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 bg-primary/20 rounded-lg">
              <Volume2 className="w-5 h-5 text-primary" />
            </div>
            <h2 className="text-xl font-bold text-white font-sans">Speech Studio</h2>
          </div>

          <div className="space-y-6">
            {/* Project Selection */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-muted-foreground">Dự án (Project)</label>
              <select
                value={selectedProjectId}
                onChange={(e) => setSelectedProjectId(e.target.value)}
                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50"
              >
                {projects.map((p) => (
                  <option key={p.id} value={p.id} className="bg-zinc-900">{p.name}</option>
                ))}
              </select>
            </div>

            {/* TTS Model Choice */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-muted-foreground">Mô hình TTS (Model)</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setModel("edge-tts")}
                  className={cn(
                    "py-2.5 px-3 rounded-xl text-xs font-bold border transition-all flex flex-col items-center gap-1",
                    model === "edge-tts"
                      ? "bg-primary/20 border-primary text-primary shadow-[0_0_15px_rgba(124,58,237,0.2)]"
                      : "bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10"
                  )}
                >
                  <CloudLightning className="w-4 h-4" />
                  <span>Edge-TTS</span>
                  <span className="text-[8px] opacity-70 font-normal">Nhiều giọng, Free</span>
                </button>
                <button
                  type="button"
                  onClick={() => setModel("melotts")}
                  className={cn(
                    "py-2.5 px-3 rounded-xl text-xs font-bold border transition-all flex flex-col items-center gap-1",
                    model === "melotts"
                      ? "bg-primary/20 border-primary text-primary shadow-[0_0_15px_rgba(124,58,237,0.2)]"
                      : "bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10"
                  )}
                >
                  <Cpu className="w-4 h-4" />
                  <span>MeloTTS</span>
                  <span className="text-[8px] opacity-70 font-normal">Offline, 1 giọng</span>
                </button>
              </div>
            </div>

            {/* Vietnamese Text Input */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-muted-foreground">Văn bản tiếng Việt (Text)</label>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Nhập đoạn văn bản tiếng Việt bạn muốn chuyển đổi thành giọng nói..."
                className="w-full h-36 bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none font-sans leading-relaxed"
                maxLength={2000}
              />
              <div className="text-right text-[10px] text-muted-foreground">
                {text.length}/2000 ký tự
              </div>
            </div>

            {/* Voice & Speaker (Dynamically render options based on selected model) */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-muted-foreground">Người nói (Speaker)</label>
              {model === "edge-tts" ? (
                <select
                  value={speaker}
                  onChange={(e) => setSpeaker(e.target.value)}
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 font-sans"
                >
                  <option value="vi-VN-HoaiMyNeural" className="bg-zinc-900">Hoài Mỹ (Giọng Nữ Bắc cực hay)</option>
                  <option value="vi-VN-NamMinhNeural" className="bg-zinc-900">Nam Minh (Giọng Nam trầm ấm)</option>
                </select>
              ) : (
                <select
                  value={speaker}
                  onChange={(e) => setSpeaker(e.target.value)}
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 font-sans"
                >
                  <option value="VI-default" className="bg-zinc-900">VI-default (Mặc định)</option>
                </select>
              )}
            </div>

            {/* Speed Option */}
            <div className="space-y-3 pt-1">
              <div className="flex justify-between items-center">
                <label className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-primary" /> Tốc độ đọc (Speed)
                </label>
                <span className="text-xs text-primary font-bold">{speed.toFixed(1)}x</span>
              </div>
              <input
                type="range"
                min="0.5"
                max="2.0"
                step="0.1"
                value={speed}
                onChange={(e) => setSpeed(parseFloat(e.target.value))}
                className="w-full h-1 bg-white/10 rounded-lg appearance-none cursor-pointer accent-primary"
              />
              <div className="flex justify-between text-[10px] text-muted-foreground px-1">
                <span>Chậm (0.5x)</span>
                <span>Bình thường</span>
                <span>Nhanh (2.0x)</span>
              </div>
            </div>

            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl flex items-start gap-3">
                <AlertCircle className="w-4 h-4 text-red-500 mt-0.5" />
                <p className="text-xs text-red-400 leading-relaxed">{error}</p>
              </div>
            )}

            <button
              onClick={handleGenerate}
              disabled={isGenerating || projectsLoading}
              className={cn(
                "w-full py-4 rounded-xl font-bold text-white transition-all flex items-center justify-center gap-3 shadow-lg",
                isGenerating 
                  ? "bg-zinc-800 cursor-not-allowed" 
                  : "bg-gradient-to-r from-violet-600 to-indigo-600 hover:scale-[1.02] active:scale-[0.98] shadow-violet-600/20"
              )}
            >
              {isGenerating ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Đang chuyển đổi giọng nói...
                </>
              ) : (
                <>
                  <Volume2 className="w-5 h-5 animate-pulse" />
                  Generate Speech
                </>
              )}
            </button>
          </div>
        </div>

        <div className="bg-primary/5 border border-primary/20 rounded-2xl p-4 flex items-center gap-3">
          <div className="p-2 bg-primary/20 rounded-lg">
            <Volume2 className="w-4 h-4 text-primary" />
          </div>
          <p className="text-[10px] text-muted-foreground leading-tight">
            {model === "edge-tts" 
              ? "Microsoft Edge-TTS cung cấp giọng Nam/Nữ Bắc vô cùng tự nhiên qua đám mây, hoàn toàn miễn phí."
              : "MeloTTS Vietnamese chạy hoàn toàn offline trên GPU local, được tối ưu hóa cho giọng nói tự nhiên."}
          </p>
        </div>
      </div>

      {/* Right Column: Audio Output Display */}
      <div className="flex-1 flex flex-col gap-4">
        <div className="flex-1 bg-black/40 border border-white/10 rounded-3xl backdrop-blur-xl relative overflow-hidden flex items-center justify-center border-dashed">
          
          {isGenerating ? (
            <div className="text-center space-y-6">
              <div className="relative inline-block">
                <div className="w-24 h-24 rounded-full border-4 border-primary/10 border-t-primary animate-spin" />
                <AudioLines className="w-8 h-8 text-primary absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 animate-pulse" />
              </div>
              <div className="space-y-2">
                <h3 className="text-lg font-medium text-white">Đang xử lý văn bản tiếng Việt...</h3>
                <p className="text-sm text-muted-foreground italic max-w-sm mx-auto">
                  "{text.length > 80 ? text.substring(0, 80) + '...' : text}"
                </p>
                <div className="flex items-center justify-center gap-2 mt-4">
                   <span className="px-2 py-1 bg-white/5 rounded text-[10px] text-primary border border-white/10 uppercase font-bold tracking-wider">
                     {currentJob?.status || "PENDING"}
                   </span>
                </div>
              </div>
            </div>
          ) : currentJob?.url ? (
            <div className="relative group w-full h-full p-8 flex flex-col items-center justify-center space-y-8">
              
              {/* Styled Audio Visualizer mock / premium card */}
              <div className="w-72 h-72 bg-gradient-to-tr from-violet-600/10 to-indigo-600/10 border border-white/10 rounded-full flex items-center justify-center shadow-2xl relative">
                {/* Wave animations when playing */}
                {isPlaying && (
                  <>
                    <div className="absolute inset-0 rounded-full bg-primary/20 animate-ping opacity-70" />
                    <div className="absolute inset-4 rounded-full bg-indigo-500/10 border border-indigo-500/30 animate-pulse" />
                  </>
                )}
                
                <button 
                  onClick={togglePlay}
                  className="w-28 h-28 bg-gradient-to-r from-violet-600 to-indigo-600 rounded-full hover:scale-105 active:scale-95 transition-all shadow-xl flex items-center justify-center text-white z-10"
                >
                  {isPlaying ? (
                    <Pause className="w-12 h-12 fill-white text-white ml-0" />
                  ) : (
                    <Play className="w-12 h-12 fill-white text-white ml-2" />
                  )}
                </button>
              </div>

              <div className="text-center space-y-2">
                <h3 className="text-lg font-bold text-white">Giọng đọc tiếng Việt sẵn sàng</h3>
                <p className="text-xs text-muted-foreground max-w-md line-clamp-2">
                  "{text}"
                </p>
                <div className="flex items-center justify-center gap-4 mt-2">
                  <span className="text-[10px] bg-white/5 border border-white/10 px-2.5 py-1 rounded text-muted-foreground uppercase font-bold">
                    Model: {model.toUpperCase()}
                  </span>
                  <span className="text-[10px] bg-white/5 border border-white/10 px-2.5 py-1 rounded text-muted-foreground uppercase font-bold">
                    Voice: {speaker.replace("vi-VN-", "").replace("Neural", "")}
                  </span>
                  <span className="text-[10px] bg-white/5 border border-white/10 px-2.5 py-1 rounded text-muted-foreground uppercase font-bold">
                    Speed: {speed}x
                  </span>
                </div>
              </div>

              {/* Control Toolbar */}
              <div className="flex items-center gap-4 px-6 py-3 bg-black/60 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl">
                <button 
                  onClick={handleSaveToAssets}
                  disabled={saveStatus !== "idle"}
                  className={cn(
                    "flex items-center gap-2 text-sm font-medium transition-all px-4 py-2 rounded-xl",
                    saveStatus === "success" ? "text-green-400" : "text-white hover:text-primary"
                  )}
                >
                  {saveStatus === "saving" ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : saveStatus === "success" ? (
                    <CheckCircle2 className="w-4 h-4" />
                  ) : (
                    <Save className="w-4 h-4" />
                  )}
                  {saveStatus === "success" ? "Đã lưu vào Assets" : "Lưu vào Assets"}
                </button>
                <div className="w-px h-4 bg-white/10" />
                <a 
                  href={currentJob.url} 
                  download={`tts_${currentJob.jobId}.mp3`}
                  className="flex items-center gap-2 text-sm font-medium text-white hover:text-primary transition-all px-4 py-2"
                >
                  <Download className="w-4 h-4" />
                  Tải về (Download)
                </a>
                <div className="w-px h-4 bg-white/10" />
                <button 
                  onClick={handleGenerate}
                  className="flex items-center gap-2 text-sm font-medium text-white hover:text-primary transition-all px-4 py-2"
                >
                  <RefreshCw className="w-4 h-4" />
                  Thử lại (Regen)
                </button>
              </div>
            </div>
          ) : currentJob?.status === "FAILED" ? (
            <div className="text-center space-y-4 p-8 max-w-md">
              <div className="w-16 h-16 bg-red-500/10 rounded-full flex items-center justify-center mx-auto border border-red-500/20">
                <AlertCircle className="w-8 h-8 text-red-500" />
              </div>
              <div className="space-y-2">
                <h3 className="text-lg font-medium text-white">Chuyển đổi thất bại</h3>
                <p className="text-sm text-red-400/90">{currentJob.error || "Đã xảy ra lỗi khi tạo giọng nói."}</p>
              </div>
              <button 
                onClick={handleGenerate}
                className="px-6 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-sm font-medium text-white transition-all"
              >
                Thử lại lần nữa
              </button>
            </div>
          ) : (
            <div className="text-center space-y-6 opacity-40">
              <div className="w-32 h-32 bg-white/5 rounded-full flex items-center justify-center mx-auto border border-white/10 border-dashed">
                <Music className="w-12 h-12 text-muted-foreground" />
              </div>
              <div className="space-y-2">
                <h3 className="text-xl font-medium text-white tracking-tight">Speech Studio Preview</h3>
                <p className="text-sm text-muted-foreground max-w-xs mx-auto">
                  Nhập văn bản tiếng Việt ở cột trái và nhấn Generate để tạo giọng đọc chất lượng cao.
                </p>
              </div>
            </div>
          )}

          {/* Background patterns */}
          <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 blur-[120px] rounded-full -mr-32 -mt-32" />
          <div className="absolute bottom-0 left-0 w-64 h-64 bg-indigo-500/5 blur-[120px] rounded-full -ml-32 -mb-32" />
        </div>

        {/* Library & Suggestions Tabs Panel */}
        <div className="min-h-[16rem] bg-black/20 border border-white/10 rounded-3xl p-6 flex flex-col gap-4 overflow-hidden relative">
          
          {/* Tab Headers */}
          <div className="flex items-center gap-6 border-b border-white/5 pb-2 shrink-0">
            <button
              onClick={() => setActiveHistoryTab("history")}
              className={cn(
                "pb-2 text-xs font-bold uppercase tracking-widest transition-all cursor-pointer flex items-center gap-2",
                activeHistoryTab === "history" 
                  ? "text-primary border-b-2 border-primary" 
                  : "text-muted-foreground hover:text-white"
              )}
            >
              Lịch sử giọng đọc
              {savedAudioList.length > 0 && (
                <span className="px-1.5 py-0.5 bg-primary/20 border border-primary/30 text-primary text-[9px] rounded-full">
                  {savedAudioList.length}
                </span>
              )}
            </button>
            <button
              onClick={() => setActiveHistoryTab("suggestions")}
              className={cn(
                "pb-2 text-xs font-bold uppercase tracking-widest transition-all cursor-pointer",
                activeHistoryTab === "suggestions" 
                  ? "text-primary border-b-2 border-primary" 
                  : "text-muted-foreground hover:text-white"
              )}
            >
              Mẫu câu gợi ý
            </button>
          </div>

          {/* Tab Contents */}
          <div className="flex-1 overflow-y-auto custom-scrollbar">
            {activeHistoryTab === "history" ? (
              loadingHistory ? (
                <div className="flex items-center justify-center py-10 gap-3">
                  <Loader2 className="w-4 h-4 animate-spin text-primary" />
                  <span className="text-xs text-muted-foreground">Đang tải lịch sử...</span>
                </div>
              ) : savedAudioList.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-center text-muted-foreground select-none">
                  <AudioLines className="w-10 h-10 opacity-20 mb-2 animate-pulse" />
                  <p className="text-xs">Chưa có giọng đọc nào được lưu.</p>
                  <p className="text-[10px] opacity-70 mt-1">Hãy sinh giọng đọc phía trên và bấm "Lưu vào Assets" để lưu trữ.</p>
                </div>
              ) : (
                <div className="space-y-2.5">
                  {savedAudioList.map((asset) => (
                    <div 
                      key={asset.id}
                      className="flex items-center justify-between p-3 bg-white/5 border border-white/5 rounded-2xl hover:bg-white/10 hover:border-white/10 transition-all group"
                    >
                      {/* Left: Info */}
                      <div className="flex items-center gap-3 min-w-0 flex-1">
                        <div className="p-2 bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 rounded-xl shrink-0">
                          <AudioLines className="w-4 h-4" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-xs font-bold text-white truncate max-w-[320px]" title={asset.display_name}>
                            {asset.display_name}
                          </p>
                          <p className="text-[9px] text-muted-foreground mt-0.5">
                            {new Date(asset.created_at).toLocaleString("vi-VN")} | Source: {asset.source}
                          </p>
                        </div>
                      </div>

                      {/* Right: Actions */}
                      <div className="flex items-center gap-2 shrink-0">
                        {/* Play/Pause Button */}
                        <button
                          onClick={() => togglePlayHistory(asset)}
                          className={cn(
                            "p-2 rounded-xl border transition-all cursor-pointer",
                            playingHistoryId === asset.id 
                              ? "bg-primary/20 border-primary text-primary shadow-[0_0_10px_rgba(124,58,237,0.2)]" 
                              : "bg-white/5 border-white/10 text-muted-foreground hover:text-white"
                          )}
                          title={playingHistoryId === asset.id ? "Pause" : "Play"}
                        >
                          {playingHistoryId === asset.id ? (
                            <Pause className="w-3.5 h-3.5" />
                          ) : (
                            <Play className="w-3.5 h-3.5 fill-current" />
                          )}
                        </button>

                        {/* Download link */}
                        <a
                          href={asset.presigned_url || asset.s3_url}
                          download={asset.display_name}
                          className="p-2 bg-white/5 border border-white/10 text-muted-foreground hover:text-white rounded-xl transition-all cursor-pointer"
                          title="Tải tệp âm thanh"
                        >
                          <Download className="w-3.5 h-3.5" />
                        </a>

                        {/* Hard Delete Button */}
                        <button
                          onClick={(e) => handleDeleteHistoryAsset(asset.id, e)}
                          className="p-2 bg-white/5 border border-white/10 text-muted-foreground hover:text-red-400 hover:bg-red-500/10 rounded-xl transition-all cursor-pointer"
                          title="Xóa triệt để"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )
            ) : (
              <div className="flex gap-4 overflow-x-auto pb-2 custom-scrollbar">
                {[
                  { name: "Mở đầu review", text: "Chào mừng các bạn đã quay trở lại với kênh của mình, hôm nay chúng ta sẽ cùng đánh giá một sản phẩm siêu hot nhé." },
                  { name: "Giới thiệu tính năng", text: "Sản phẩm này sở hữu thiết kế vô cùng tinh tế, nhỏ gọn nhưng hiệu năng thì vô cùng đáng kinh ngạc." },
                  { name: "Lời kêu gọi hành động", text: "Nếu các bạn thấy video này hữu ích, đừng quên nhấn Like, Share và Đăng ký kênh để ủng hộ mình nhé." },
                  { name: "Cảm ơn & Tạm biệt", text: "Xin cảm ơn các bạn đã dành thời gian theo dõi, xin chào và hẹn gặp lại trong những video tiếp theo." },
                ].map((sample, i) => (
                  <button 
                    key={i}
                    onClick={() => setText(sample.text)}
                    className="flex-shrink-0 w-52 p-4 bg-white/5 border border-white/5 rounded-2xl hover:bg-white/10 hover:border-white/10 transition-all text-left space-y-1 group cursor-pointer"
                  >
                    <p className="text-xs font-bold text-white group-hover:text-primary transition-colors">{sample.name}</p>
                    <p className="text-[10px] text-muted-foreground line-clamp-2">{sample.text}</p>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
