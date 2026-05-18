import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { UploadCloud, Folder, Plus, CheckCircle2, Languages, Send, AlertTriangle } from "lucide-react";
import api from "../lib/api";
import { cn } from "../lib/utils";
import { useAssets } from "../hooks/useAssets";
import { useProjects } from "../hooks/useProjects";
import { Button } from "../components/ui/Button";
import { AssetSelector } from "../components/ui/AssetSelector";
import type { UploadedFile } from "../components/features/review/types";

export default function CreateTranslifyJob() {
  const navigate = useNavigate();
  const { uploadAsset } = useAssets();
  const { projects, createProject } = useProjects();

  // Data State
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [newProjectName, setNewProjectName] = useState("");
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [priority, setPriority] = useState<number>(0);
  const [video, setVideo] = useState<UploadedFile | null>(null);
  const [voiceName, setVoiceName] = useState("vi-VN-NamMinhNeural");

  // UI State
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState("");

  useEffect(() => {
    if (projects.length > 0 && !selectedProjectId) setSelectedProjectId(projects[0].id);
    if (projects.length === 0) setIsCreatingProject(true);
  }, [projects, selectedProjectId]);

  const handleSubmit = async () => {
    if (!video) return setError("Vui lòng chọn video tiếng Trung đầu vào.");
    if (!isCreatingProject && !selectedProjectId) return setError("Vui lòng chọn một dự án.");
    if (isCreatingProject && !newProjectName.trim()) return setError("Vui lòng nhập tên dự án mới.");

    setLoading(true);
    setError(null);
    try {
      let targetProjectId = selectedProjectId;
      if (isCreatingProject && newProjectName.trim()) {
        setUploadStatus("Đang tạo dự án...");
        const proj = await createProject(newProjectName.trim());
        targetProjectId = proj.id;
      }

      const allAssetIds: string[] = [];

      setUploadStatus("Đang tải video lên server...");
      let videoUrl = "";
      if (video.file) {
        const res = await uploadAsset(video.file as File, "clip");
        videoUrl = res.s3_url;
        allAssetIds.push(res.id);
      } else {
        videoUrl = video.asset!.s3_url;
        allAssetIds.push(video.asset!.id);
      }

      setUploadStatus("Đang khởi tạo tiến trình dịch thuật...");
      const payload = {
        job_type: "translify",
        priority,
        project_id: targetProjectId,
        asset_ids: allAssetIds,
        config_data: {
          video: videoUrl,
          voice_name: voiceName,
        },
      };

      await api.post("/api/jobs", payload);
      navigate("/projects");
    } catch (err: any) {
      console.error(err);
      setError(err?.response?.data?.detail || err.message || "Không thể tạo job dịch thuật");
    } finally {
      setLoading(false);
      setUploadStatus("");
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-8 lg:p-12 space-y-8">
      {/* Title & Banner */}
      <div className="space-y-2">
        <div className="flex items-center gap-2.5">
          <div className="p-2 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-xl shadow-[0_0_15px_rgba(124,58,237,0.5)]">
            <Languages className="w-6 h-6 text-white" />
          </div>
          <span className="text-xs font-mono uppercase bg-primary/20 text-primary px-2 py-0.5 rounded border border-primary/20 font-semibold tracking-wider">
            Layer A + C
          </span>
        </div>
        <h2 className="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60 mt-2">
          Dịch thuật & Lồng tiếng AI (Translify)
        </h2>
        <p className="text-muted-foreground text-lg">
          Tự động phân tách phân cảnh, Whisper dịch thoại, inpainting xóa chữ cứng Douyin/TikTok và lồng tiếng Việt chuẩn marketing.
        </p>
      </div>

      {error && (
        <div className="p-4 bg-rose-500/10 text-rose-400 rounded-xl border border-rose-500/20 backdrop-blur-sm animate-in fade-in flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Forms & Inputs */}
      <div className="glass-panel p-6 lg:p-10 flex flex-col space-y-8">
        {/* Step 1: Project Selection */}
        <div className="space-y-4">
          <label className="text-sm font-semibold text-white/90 uppercase tracking-wider flex items-center gap-2">
            <Folder className="w-4 h-4 text-primary" /> Dự án liên kết
          </label>
          <div className="flex flex-col sm:flex-row gap-4">
            <button
              type="button"
              onClick={() => setIsCreatingProject(false)}
              className={cn(
                "flex-1 px-4 py-3 rounded-xl border flex items-center gap-2 justify-center transition-all",
                !isCreatingProject
                  ? "bg-primary/20 border-primary text-white shadow-[0_0_15px_rgba(124,58,237,0.3)]"
                  : "bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10"
              )}
            >
              <Folder className="w-4 h-4" /> Chọn dự án có sẵn
            </button>
            <button
              type="button"
              onClick={() => setIsCreatingProject(true)}
              className={cn(
                "flex-1 px-4 py-3 rounded-xl border flex items-center gap-2 justify-center transition-all",
                isCreatingProject
                  ? "bg-primary/20 border-primary text-white shadow-[0_0_15px_rgba(124,58,237,0.3)]"
                  : "bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10"
              )}
            >
              <Plus className="w-4 h-4" /> Tạo dự án mới
            </button>
          </div>

          {isCreatingProject ? (
            <div className="space-y-2 animate-in fade-in">
              <input
                type="text"
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                placeholder="Tên dự án dịch thuật mới..."
                className="flex h-12 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-base text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all placeholder:text-muted-foreground/50"
              />
            </div>
          ) : (
            <div className="space-y-2 animate-in fade-in">
              <select
                value={selectedProjectId}
                onChange={(e) => setSelectedProjectId(e.target.value)}
                className="flex h-12 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-base text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all appearance-none"
              >
                {projects.length === 0 ? (
                  <option disabled value="" className="bg-[#1A1A24]">
                    Bạn chưa có dự án nào
                  </option>
                ) : (
                  projects.map((p) => (
                    <option key={p.id} value={p.id} className="bg-[#1A1A24]">
                      {p.name}
                    </option>
                  ))
                )}
              </select>
            </div>
          )}
        </div>

        {/* Step 2: Upload original Video */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div className="space-y-3">
            <AssetSelector
              label="Chọn video gốc (Tiếng Trung)"
              sublabel="Video Douyin / TikTok cần dịch lồng tiếng"
              icon={<UploadCloud className="w-8 h-8 text-primary" />}
              accept="video/mp4,video/*"
              assetTypeFilter="clip"
              selectedFile={video}
              onSelect={(file, asset) => {
                if (file || asset) {
                  setVideo({
                    file,
                    asset,
                    id: asset?.id || null,
                    s3_url: asset?.s3_url || null,
                    uploading: false,
                    progress: 0,
                  });
                } else {
                  setVideo(null);
                }
              }}
            />
            {video && (
              <div className="flex items-center gap-2 text-sm text-green-400 bg-green-400/10 p-3 rounded-xl border border-green-400/20">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <span>Video đã được cấu hình</span>
              </div>
            )}
          </div>

          {/* Voiceover Voice Selection */}
          <div className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm font-semibold text-white/90">Lựa chọn Giọng đọc mặc định</label>
              <select
                value={voiceName}
                onChange={(e) => setVoiceName(e.target.value)}
                className="flex h-11 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 appearance-none"
              >
                <option value="vi-VN-NamMinhNeural" className="bg-[#1A1A24]">
                  🇻🇳 vi-VN-NamMinh (Giọng nam trầm ấm - Recommend)
                </option>
                <option value="vi-VN-HoaiMyNeural" className="bg-[#1A1A24]">
                  🇻🇳 vi-VN-HoaiMy (Giọng nữ nhẹ nhàng)
                </option>
                <option value="vi-VN-MinhQuanNeural" className="bg-[#1A1A24]">
                  🇻🇳 vi-VN-MinhQuan (Giọng nam năng động)
                </option>
              </select>
              <p className="text-[11px] text-muted-foreground leading-relaxed mt-1">
                Lựa chọn này sẽ áp dụng cho giọng lồng tiếng Việt mặc định trong từng phân cảnh ban đầu. Bạn có thể đổi lại sau tại Editor.
              </p>
            </div>

            {/* Compute Priority Selection */}
            <div className="space-y-2">
              <label className="text-sm font-semibold text-white/90">Độ ưu tiên hàng đợi (Compute Priority)</label>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setPriority(0)}
                  className={cn(
                    "px-4 py-2 rounded-xl transition-all text-xs font-semibold border",
                    priority === 0
                      ? "bg-white/10 border-white/30 text-white shadow-sm"
                      : "border-transparent text-muted-foreground hover:bg-white/5"
                  )}
                >
                  Bình thường
                </button>
                <button
                  type="button"
                  onClick={() => setPriority(1)}
                  className={cn(
                    "px-4 py-2 rounded-xl transition-all text-xs font-semibold border",
                    priority === 1
                      ? "bg-orange-500/20 border-orange-500/50 text-orange-400 shadow-[0_0_15px_rgba(249,115,22,0.2)]"
                      : "border-transparent text-muted-foreground hover:bg-orange-500/10 hover:text-orange-400/70"
                  )}
                >
                  Ưu tiên cao (GPU Priority)
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Action Button */}
        <div className="flex justify-end pt-4 border-t border-white/10">
          <Button
            onClick={handleSubmit}
            isLoading={loading}
            disabled={!video}
            className="glowing-button px-10 py-3 rounded-xl font-bold shadow-[0_0_30px_rgba(124,58,237,0.6)] flex items-center gap-2"
          >
            {!loading && <Send className="w-4 h-4" />}
            {loading ? uploadStatus || "Đang khởi động..." : "Bắt đầu Phân tích Video (Stage 1)"}
          </Button>
        </div>
      </div>
    </div>
  );
}
