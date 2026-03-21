import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { DownloadCloud, AlertCircle, Send, Plus, FolderHeart } from "lucide-react";
import api from "../lib/api";
import { cn } from "../lib/utils";
import { useProjects } from "../hooks/useProjects";

export default function DownloadVideo() {
  const navigate = useNavigate();
  const { projects, createProject } = useProjects();

  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [newProjectName, setNewProjectName] = useState("");
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [url, setUrl] = useState("");
  const [downloadFormat, setDownloadFormat] = useState<"video" | "audio">("video");

  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (projects.length > 0 && !selectedProjectId) {
      setSelectedProjectId(projects[0].id);
    }
    if (projects.length === 0) {
      setIsCreatingProject(true);
    }
  }, [projects, selectedProjectId]);

  const handleSubmit = async () => {
    if (!isCreatingProject && !selectedProjectId) {
      return setError("Vui lòng chọn hoặc tạo dự án mới.");
    }
    if (isCreatingProject && !newProjectName.trim()) {
      return setError("Vui lòng nhập tên dự án mới.");
    }
    if (!url.trim()) {
      return setError("Vui lòng nhập URL của video.");
    }

    try {
      setLoading(true);
      setError(null);
      
      let targetProjectId = selectedProjectId;

      if (isCreatingProject && newProjectName.trim()) {
        setStatusMsg("Đang tạo dự án...");
        const newProj = await createProject(newProjectName.trim());
        targetProjectId = newProj.id;
      }

      setStatusMsg("Đang gửi yêu cầu tải video...");

      await api.post("/api/jobs", {
        job_type: "download",
        project_id: targetProjectId,
        config_data: { url: url.trim(), format: downloadFormat },
      });

      // Redirect to dashboard to see the job progress
      navigate("/");
    } catch (err: any) {
      console.error(err);
      setError(err?.response?.data?.detail || err.message || "Đã xảy ra lỗi khi tạo yêu cầu.");
    } finally {
      setLoading(false);
      setStatusMsg("");
    }
  };

  const isFormValid = (isCreatingProject ? newProjectName.trim() : selectedProjectId) && url.trim();

  return (
    <div className="max-w-4xl mx-auto p-8 lg:p-12 space-y-10">
      <div className="space-y-2">
        <h2 className="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60">
          Tải Video
        </h2>
        <p className="text-muted-foreground text-lg">
          Dán đường link từ YouTube, TikTok,... hệ thống sẽ tải và trích xuất nguyên liệu video gốc với chất lượng cao nhất.
        </p>
      </div>

      <div className="glass-panel p-6 lg:p-10 flex flex-col space-y-8 animate-in fade-in slide-in-from-bottom-4">
        
        {error && (
          <div className="p-4 bg-red-500/10 text-red-500 rounded-xl border border-red-500/20 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
            <p className="text-sm font-medium">{error}</p>
          </div>
        )}

        {/* Project Selection */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-white">
            <FolderHeart className="w-5 h-5 text-primary" />
            <h3 className="text-lg font-semibold">1. Chọn Dự án</h3>
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            <button
              onClick={() => setIsCreatingProject(false)}
              className={cn(
                "p-4 rounded-xl border text-left transition-all duration-300",
                !isCreatingProject
                  ? "bg-primary/20 border-primary/50 shadow-[0_0_15px_rgba(124,58,237,0.3)] ring-1 ring-primary/20"
                  : "bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10"
              )}
            >
              <div className="font-medium text-white mb-1">Dự án có sẵn</div>
              <div className="text-xs opacity-70">Thêm vào dự án hiện tại</div>
            </button>
            <button
              onClick={() => setIsCreatingProject(true)}
              className={cn(
                "p-4 rounded-xl border text-left transition-all duration-300",
                isCreatingProject
                  ? "bg-primary/20 border-primary/50 shadow-[0_0_15px_rgba(124,58,237,0.3)] ring-1 ring-primary/20"
                  : "bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10"
              )}
            >
              <div className="font-medium text-white mb-1 flex items-center gap-2">
                <Plus className="w-4 h-4" /> Tạo dự án mới
              </div>
              <div className="text-xs opacity-70">Khởi tạo không gian riêng</div>
            </button>
          </div>

          <div className="pt-2">
            {!isCreatingProject ? (
              <select
                value={selectedProjectId}
                onChange={(e) => setSelectedProjectId(e.target.value)}
                className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3.5 text-white focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all appearance-none"
              >
                {projects.length === 0 ? (
                  <option value="" disabled>Chưa có dự án nào</option>
                ) : (
                  projects.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))
                )}
              </select>
            ) : (
              <input
                type="text"
                placeholder="Ví dụ: Review Sản Phẩm X"
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3.5 text-white focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all placeholder:text-muted-foreground/50"
              />
            )}
          </div>
        </div>

        <div className="w-full h-px bg-white/10"></div>

        {/* Format Selection */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-white">
            <DownloadCloud className="w-5 h-5 text-primary" />
            <h3 className="text-lg font-semibold">2. Định dạng Tải</h3>
          </div>
          <div className="flex gap-4">
            <label className={cn(
              "flex-1 p-4 rounded-xl border cursor-pointer transition-all",
              downloadFormat === "video" 
                ? "bg-primary/20 border-primary/50 shadow-[0_0_15px_rgba(124,58,237,0.3)] ring-1 ring-primary/20" 
                : "bg-white/5 border-white/10 hover:bg-white/10"
            )}>
              <input type="radio" className="hidden" name="format" value="video" checked={downloadFormat === "video"} onChange={() => setDownloadFormat("video")} />
              <div className="font-medium text-white mb-1">Video (MP4)</div>
              <div className="text-xs opacity-70">Tải video độ phân giải cao nhất</div>
            </label>
            
            <label className={cn(
              "flex-1 p-4 rounded-xl border cursor-pointer transition-all",
              downloadFormat === "audio" 
                ? "bg-primary/20 border-primary/50 shadow-[0_0_15px_rgba(124,58,237,0.3)] ring-1 ring-primary/20" 
                : "bg-white/5 border-white/10 hover:bg-white/10"
            )}>
              <input type="radio" className="hidden" name="format" value="audio" checked={downloadFormat === "audio"} onChange={() => setDownloadFormat("audio")} />
              <div className="font-medium text-white mb-1">Chỉ lấy Nhạc (MP3)</div>
              <div className="text-xs opacity-70">Trích xuất âm thanh từ liên kết</div>
            </label>
          </div>
        </div>

        <div className="w-full h-px bg-white/10"></div>

        {/* URL Input */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-white">
            <DownloadCloud className="w-5 h-5 text-primary" />
            <h3 className="text-lg font-semibold">3. Đường dẫn Link</h3>
          </div>
          <p className="text-sm text-muted-foreground">
            Hỗ trợ link từ YouTube, TikTok, Facebook v.v. (Ví dụ: https://www.youtube.com/shorts/...)
          </p>
          <input
            type="url"
            disabled={loading}
            placeholder="Dán URL video tại đây..."
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3.5 text-white focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all placeholder:text-muted-foreground/50"
          />
        </div>

        {/* Action Button */}
        <div className="pt-6">
          <button
            onClick={handleSubmit}
            disabled={!isFormValid || loading}
            className="w-full py-4 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white rounded-xl font-bold text-lg shadow-[0_0_20px_rgba(124,58,237,0.4)] transition-all flex items-center justify-center gap-3 disabled:opacity-50 disabled:cursor-not-allowed group"
          >
            {loading ? (
              <>
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>{statusMsg || "Đang xử lý..."}</span>
              </>
            ) : (
              <>
                <Send className="w-5 h-5 group-hover:translate-x-1 group-hover:-translate-y-1 transition-transform" />
                <span>Bắt Đầu Tải Video</span>
              </>
            )}
          </button>
        </div>

      </div>
    </div>
  );
}
