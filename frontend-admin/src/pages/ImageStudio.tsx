import { useState, useEffect } from "react";
import { 
  Sparkles, 
  Image as ImageIcon, 
  Download, 
  Save, 
  RefreshCw, 
  Layout, 
  Maximize2,
  AlertCircle,
  Loader2,
  CheckCircle2,
  ChevronRight
} from "lucide-react";
import api from "../lib/api";
import { cn } from "../lib/utils";
import { useProjects } from "../hooks/useProjects";

interface GenerationResult {
  jobId: number;
  status: string;
  url?: string;
  error?: string;
}

export default function ImageStudio() {
  const { projects, loading: projectsLoading } = useProjects();
  
  // Form State
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [aspectRatio, setAspectRatio] = useState("1:1");
  const [width, setWidth] = useState(1024);
  const [height, setHeight] = useState(1024);
  const [seed, setSeed] = useState<number | "">("");

  // UI State
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentJob, setCurrentJob] = useState<GenerationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "success" | "error">("idle");

  // Set default project
  useEffect(() => {
    if (projects.length > 0 && !selectedProjectId) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  // Adjust width/height based on aspect ratio
  useEffect(() => {
    if (aspectRatio === "1:1") { setWidth(1024); setHeight(1024); }
    else if (aspectRatio === "16:9") { setWidth(1280); setHeight(720); }
    else if (aspectRatio === "9:16") { setWidth(720); setHeight(1280); }
  }, [aspectRatio]);

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      setError("Vui lòng nhập prompt để bắt đầu.");
      return;
    }
    if (!selectedProjectId) {
      setError("Vui lòng chọn hoặc tạo một Project.");
      return;
    }

    setError(null);
    setIsGenerating(true);
    setSaveStatus("idle");

    try {
      const response = await api.post("/api/jobs", {
        job_type: "text2img",
        project_id: selectedProjectId,
        config_data: {
          prompt: prompt,
          width: width,
          height: height,
          seed: seed === "" ? null : seed
        }
      });

      const jobId = response.data.id;
      setCurrentJob({ jobId, status: "PENDING" });
      startPolling(jobId);
    } catch (err: any) {
      console.error("Failed to start generation:", err);
      setError(err.response?.data?.detail || "Không thể khởi động tiến trình gen ảnh.");
      setIsGenerating(false);
    }
  };

  const startPolling = (jobId: number) => {
    const interval = setInterval(async () => {
      try {
        const res = await api.get(`/api/jobs/${jobId}`);
        const job = res.data;

        if (job.status === "SUCCESS") {
          setCurrentJob({ jobId, status: "SUCCESS", url: job.result_url });
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

    // Safety timeout after 5 minutes
    setTimeout(() => {
      clearInterval(interval);
      if (isGenerating) {
        setIsGenerating(false);
        setError("Quá thời gian chờ (Timeout). Vui lòng kiểm tra lại sau.");
      }
    }, 300000);
  };

  const handleSaveToAssets = async () => {
    if (!currentJob?.url) return;
    
    setSaveStatus("saving");
    try {
      // Logic để lưu vào bảng assets
      // Thông thường worker đã lưu vào MinIO, ta chỉ cần tạo record asset
      await api.post("/api/assets", {
        project_id: selectedProjectId,
        s3_url: currentJob.url,
        asset_type: "image",
        file_name: `flux_gen_${currentJob.jobId}.png`,
        mime_type: "image/png"
      });
      setSaveStatus("success");
      setTimeout(() => setSaveStatus("idle"), 3000);
    } catch (err) {
      console.error("Failed to save asset:", err);
      setSaveStatus("error");
    }
  };

  return (
    <div className="flex h-[calc(100vh-2rem)] gap-6 p-2 overflow-hidden">
      {/* Cột Trái: Cấu hình */}
      <div className="w-96 flex flex-col gap-4 overflow-y-auto pr-2 custom-scrollbar">
        <div className="bg-black/40 border border-white/10 rounded-2xl p-6 backdrop-blur-xl">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 bg-primary/20 rounded-lg">
              <Sparkles className="w-5 h-5 text-primary" />
            </div>
            <h2 className="text-xl font-bold text-white">Image Studio</h2>
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

            {/* Prompt Input */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-muted-foreground">Miêu tả ảnh (Prompt)</label>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Ví dụ: Một thành phố tương lai trên mây, phong cách cyberpunk, ánh sáng neon rực rỡ..."
                className="w-full h-40 bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none"
              />
            </div>

            {/* Aspect Ratio */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-muted-foreground">Tỷ lệ khung hình</label>
              <div className="grid grid-cols-3 gap-2">
                {["1:1", "16:9", "9:16"].map((ratio) => (
                  <button
                    key={ratio}
                    onClick={() => setAspectRatio(ratio)}
                    className={cn(
                      "py-2 px-3 rounded-lg text-xs font-medium border transition-all",
                      aspectRatio === ratio
                        ? "bg-primary/20 border-primary text-primary shadow-[0_0_15px_rgba(124,58,237,0.2)]"
                        : "bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10"
                    )}
                  >
                    {ratio}
                  </button>
                ))}
              </div>
            </div>

            {/* Advanced Settings */}
            <div className="pt-4 border-t border-white/5 space-y-4">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-muted-foreground">Seed (Tùy chọn)</label>
                <button 
                  onClick={() => setSeed(Math.floor(Math.random() * 1000000))}
                  className="text-[10px] text-primary hover:underline"
                >
                  Randomize
                </button>
              </div>
              <input
                type="number"
                value={seed}
                onChange={(e) => setSeed(e.target.value ? parseInt(e.target.value) : "")}
                placeholder="Để trống để lấy ngẫu nhiên"
                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
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
                  Đang tạo ảnh...
                </>
              ) : (
                <>
                  <Sparkles className="w-5 h-5" />
                  Generate with FLUX
                </>
              )}
            </button>
          </div>
        </div>

        <div className="bg-primary/5 border border-primary/20 rounded-2xl p-4 flex items-center gap-3">
          <div className="p-2 bg-primary/20 rounded-lg">
            <AlertCircle className="w-4 h-4 text-primary" />
          </div>
          <p className="text-[10px] text-muted-foreground leading-tight">
            Mô hình FLUX.1 [schnell] được tối ưu hóa cho tốc độ. Ảnh thường hoàn thành trong 5-15 giây.
          </p>
        </div>
      </div>

      {/* Cột Phải: Preview */}
      <div className="flex-1 flex flex-col gap-4">
        <div className="flex-1 bg-black/40 border border-white/10 rounded-3xl backdrop-blur-xl relative overflow-hidden flex items-center justify-center border-dashed">
          
          {isGenerating ? (
            <div className="text-center space-y-6">
              <div className="relative inline-block">
                <div className="w-24 h-24 rounded-full border-4 border-primary/10 border-t-primary animate-spin" />
                <Sparkles className="w-8 h-8 text-primary absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
              </div>
              <div className="space-y-2">
                <h3 className="text-lg font-medium text-white">AI đang vẽ ảnh cho bạn</h3>
                <p className="text-sm text-muted-foreground italic">"{prompt.length > 50 ? prompt.substring(0, 50) + '...' : prompt}"</p>
                <div className="flex items-center justify-center gap-2 mt-4">
                   <span className="px-2 py-1 bg-white/5 rounded text-[10px] text-primary border border-white/10 uppercase font-bold tracking-wider">
                     {currentJob?.status || "PENDING"}
                   </span>
                </div>
              </div>
            </div>
          ) : currentJob?.url ? (
            <div className="relative group w-full h-full p-8 flex items-center justify-center">
              <img 
                src={currentJob.url} 
                alt="AI Generated" 
                className="max-w-full max-h-full rounded-2xl shadow-2xl object-contain animate-in fade-in zoom-in duration-500"
              />
              
              <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-center justify-center gap-4">
                <button 
                  onClick={() => window.open(currentJob.url, '_blank')}
                  className="p-4 bg-white/10 hover:bg-white/20 backdrop-blur-md rounded-full text-white transition-all transform translate-y-4 group-hover:translate-y-0"
                  title="Mở ảnh kích thước lớn"
                >
                  <Maximize2 className="w-6 h-6" />
                </button>
                <a 
                  href={currentJob.url} 
                  download 
                  className="p-4 bg-white/10 hover:bg-white/20 backdrop-blur-md rounded-full text-white transition-all transform translate-y-4 group-hover:translate-y-0 delay-75"
                  title="Tải ảnh về máy"
                >
                  <Download className="w-6 h-6" />
                </a>
              </div>

              {/* Toolbar dưới ảnh */}
              <div className="absolute bottom-12 left-1/2 -translate-x-1/2 flex items-center gap-4 px-6 py-3 bg-black/60 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl">
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
                <h3 className="text-lg font-medium text-white">Tạo ảnh thất bại</h3>
                <p className="text-sm text-muted-foreground">{currentJob.error || "Đã có lỗi xảy ra trong quá trình gen ảnh."}</p>
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
                <ImageIcon className="w-12 h-12 text-muted-foreground" />
              </div>
              <div className="space-y-2">
                <h3 className="text-xl font-medium text-white tracking-tight">Image Studio Canvas</h3>
                <p className="text-sm text-muted-foreground max-w-xs mx-auto">
                  Nhập mô tả ở cột trái và nhấn Generate để bắt đầu sáng tạo ảnh nghệ thuật với FLUX AI.
                </p>
              </div>
            </div>
          )}

          {/* Background patterns */}
          <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 blur-[120px] rounded-full -mr-32 -mt-32" />
          <div className="absolute bottom-0 left-0 w-64 h-64 bg-indigo-500/5 blur-[120px] rounded-full -ml-32 -mb-32" />
        </div>

        {/* Recent Creations (Placeholder) */}
        <div className="h-48 bg-black/20 border border-white/10 rounded-3xl p-6 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-widest">Gợi ý phong cách</h4>
            <button className="text-[10px] text-primary hover:underline flex items-center gap-1">
              Xem tất cả <ChevronRight className="w-3 h-3" />
            </button>
          </div>
          <div className="flex gap-4 overflow-x-auto pb-2 custom-scrollbar">
            {[
              { name: "Cyberpunk Night", prompt: "Cyberpunk city, neon lights, rainy street, highly detailed" },
              { name: "Ghibli Style", prompt: "Lush green valley, small cottage, Studio Ghibli art style, watercolor" },
              { name: "3D Render", prompt: "Cute 3D character, octane render, soft lighting, pastel colors" },
              { name: "Abstract Oil", prompt: "Abstract oil painting, heavy brushstrokes, vibrant colors, expressionism" },
            ].map((style, i) => (
              <button 
                key={i}
                onClick={() => setPrompt(style.prompt)}
                className="flex-shrink-0 w-40 p-4 bg-white/5 border border-white/5 rounded-2xl hover:bg-white/10 hover:border-white/10 transition-all text-left space-y-1 group"
              >
                <p className="text-xs font-bold text-white group-hover:text-primary transition-colors">{style.name}</p>
                <p className="text-[10px] text-muted-foreground line-clamp-2">{style.prompt}</p>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
