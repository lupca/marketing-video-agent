import { useState, useEffect } from "react";
import { Sparkles, ImageIcon, Download, Save, RefreshCw, AlertCircle, Loader2, CheckCircle2 } from "lucide-react";
import api from "../../../../lib/api";
import { cn } from "../../../../lib/utils";
import { useProjects } from "../../../../hooks/useProjects";

interface GenerationResult {
  jobId: number;
  status: string;
  url?: string;
  s3Url?: string;
  error?: string;
}

export default function ImageStudioWidget() {
  const { projects, loading: projectsLoading } = useProjects();
  
  // Form state
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [aspectRatio, setAspectRatio] = useState("1:1");
  const [width, setWidth] = useState(1024);
  const [height, setHeight] = useState(1024);

  // Status state
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentJob, setCurrentJob] = useState<GenerationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "success" | "error">("idle");

  // Đặt project mặc định đầu tiên
  useEffect(() => {
    if (projects.length > 0 && !selectedProjectId) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  // Điều chỉnh width/height theo tỉ lệ chọn
  useEffect(() => {
    if (aspectRatio === "1:1") { setWidth(1024); setHeight(1024); }
    else if (aspectRatio === "16:9") { setWidth(1280); setHeight(720); }
    else if (aspectRatio === "9:16") { setWidth(720); setHeight(1280); }
  }, [aspectRatio]);

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      setError("Vui lòng nhập mô tả ảnh.");
      return;
    }
    if (!selectedProjectId) {
      setError("Vui lòng chọn một Dự án để lưu ảnh.");
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
          seed: null
        }
      });

      const jobId = response.data.id;
      setCurrentJob({ jobId, status: "PENDING" });
      startPolling(jobId);
    } catch (err: any) {
      console.error("Failed to start generation:", err);
      setError(err.response?.data?.detail || "Không thể gửi yêu cầu tạo ảnh.");
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
        console.error("Polling error in widget:", err);
      }
    }, 2000);

    // Timeout an toàn sau 5 phút
    setTimeout(() => {
      clearInterval(interval);
      if (isGenerating) {
        setIsGenerating(false);
        setError("Quá thời gian phản hồi từ server.");
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
        asset_type: "image",
        file_name: `flux_addon_${currentJob.jobId}.png`,
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
    <div className="space-y-4">
      {/* Khung Gen ảnh đang chạy hoặc Kết quả */}
      {isGenerating || currentJob?.url || currentJob?.status === "FAILED" ? (
        <div className="bg-black/30 border border-white/10 rounded-2xl p-4 flex flex-col items-center justify-center min-h-[220px] relative overflow-hidden">
          {isGenerating ? (
            <div className="text-center space-y-3">
              <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto" />
              <div className="space-y-1">
                <p className="text-xs font-bold text-white">AI đang vẽ ảnh minh họa...</p>
                <p className="text-[10px] text-muted-foreground animate-pulse">Trạng thái: {currentJob?.status || "PENDING"}</p>
              </div>
            </div>
          ) : currentJob?.url ? (
            <div className="w-full space-y-4 animate-in fade-in zoom-in-95 duration-300">
              <div className="relative group rounded-xl overflow-hidden bg-black/40 border border-white/10 aspect-video flex items-center justify-center">
                <img 
                  src={currentJob.url} 
                  alt="FLUX Gen" 
                  className="max-w-full max-h-[180px] object-contain rounded"
                />
                
                <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                  <a 
                    href={currentJob.url} 
                    target="_blank"
                    rel="noreferrer"
                    className="p-2.5 bg-white/10 hover:bg-white/20 rounded-full text-white transition-all"
                    title="Mở ảnh lớn"
                  >
                    <Download className="w-4 h-4" />
                  </a>
                </div>
              </div>

              {/* Nút lưu */}
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
                    setPrompt("");
                  }}
                  className="px-3.5 py-2.5 bg-white/5 hover:bg-white/10 border border-white/10 text-white rounded-xl text-xs cursor-pointer"
                  title="Tạo ảnh mới"
                >
                  <RefreshCw className="w-4 h-4" />
                </button>
              </div>
            </div>
          ) : (
            <div className="text-center space-y-3 p-4">
              <AlertCircle className="w-8 h-8 text-red-500 mx-auto" />
              <p className="text-xs font-bold text-white">Lỗi tạo hình ảnh</p>
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
          <ImageIcon className="w-10 h-10 mx-auto opacity-30 mb-2" />
          <p className="text-[11px] font-medium leading-relaxed max-w-[200px] mx-auto">
            Nhập prompt mô tả và nhấn nút tạo để vẽ hình ảnh AI bằng FLUX AI.
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

        {/* Soạn prompt */}
        <div className="space-y-1.5">
          <label className="text-[11px] font-semibold text-muted-foreground">Mô tả bức ảnh (Prompt)</label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            disabled={isGenerating}
            placeholder="Ví dụ: Một chiếc ly thủy tinh chứa nước ép cam đặt trên bãi cát vàng biển xanh, ánh nắng hè rực rỡ..."
            className="w-full h-24 bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-xs text-white placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-primary resize-none"
          />
        </div>

        {/* Tỉ lệ ảnh */}
        <div className="space-y-1.5">
          <label className="text-[11px] font-semibold text-muted-foreground">Tỉ lệ khung hình</label>
          <div className="grid grid-cols-3 gap-2">
            {["1:1", "16:9", "9:16"].map((ratio) => (
              <button
                key={ratio}
                onClick={() => setAspectRatio(ratio)}
                disabled={isGenerating}
                className={cn(
                  "py-1.5 rounded-lg text-[10px] font-bold border transition-all cursor-pointer",
                  aspectRatio === ratio
                    ? "bg-primary/20 border-primary text-primary"
                    : "bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10"
                )}
              >
                {ratio}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div className="p-2.5 bg-red-500/10 border border-red-500/20 rounded-xl text-[10px] text-red-400 flex items-center gap-2">
            <AlertCircle className="w-3.5 h-3.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Nút Gen */}
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
              Đang tạo ảnh FLUX...
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              Tạo ảnh nhanh (FLUX)
            </>
          )}
        </button>
      </div>
    </div>
  );
}
