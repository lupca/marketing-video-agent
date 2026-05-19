import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { 
  ArrowLeft, Save, Sparkles, Music, Loader2, Play, AlertTriangle, 
  CheckCircle2, Sliders, Languages, Film, Clock, HelpCircle, Download
} from "lucide-react";
import api from "../lib/api";
import { cn } from "../lib/utils";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { AssetSelector } from "../components/ui/AssetSelector";
import type { UploadedFile } from "../components/features/review/types";

interface OcrItem {
  text_zh: string;
  text_vi: string | null;
  bbox: number[][];
  confidence?: number;
}

interface AudioSegment {
  zh_text: string;
  vi_text: string;
  duration: number;
}

interface VisualSegment {
  ocr_text: OcrItem[];
}

interface Scene {
  id: string;
  start: number;
  end: number;
  speaker: string;
  audio: AudioSegment;
  visual: VisualSegment;
}

interface VideoProject {
  video_id: string;
  scenes: Scene[];
}

const TONES = [
  { id: "hào hứng", name: "🔥 Hào hứng, năng động" },
  { id: "bán hàng", name: "💰 Thúc đẩy bán hàng" },
  { id: "tâm sự", name: "❤️ Kể chuyện, tâm sự" },
  { id: "hài hước", name: "🤡 Hài hước, vui vẻ" },
  { id: "trang trọng", name: "👔 Trang trọng, thuyết phục" },
];

export default function TranslifyEditor() {
  const { id } = useParams<{ id: string }>();
  
  // State
  const [projectData, setProjectData] = useState<VideoProject | null>(null);
  const [bgm, setBgm] = useState<UploadedFile | null>(null);
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null);
  
  // Settings & Tones
  const [voiceName, setVoiceName] = useState("vi-VN-NamMinhNeural");
  const [selectedTone, setSelectedTone] = useState("hào hứng");
  const [ctaText, setCtaText] = useState("");
  
  // UX states
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [rewriting, setRewriting] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);

  // Polling & Render Monitor states
  const [jobStatus, setJobStatus] = useState<string>("WAITING_FOR_REVIEW");
  const [jobProgress, setJobProgress] = useState<number>(100);
  const [jobError, setJobError] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [jobLogs, setJobLogs] = useState<any[]>([]);

  // Load project details
  useEffect(() => {
    if (!id) return;
    const fetchProject = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await api.get(`/api/translify/projects/${id}`);
        const data = res.data;
        setProjectData(data.project_data);
        
        // Load existing custom bgm if set
        if (data.bgm) {
          setBgm({
            id: null,
            s3_url: data.bgm,
            uploading: false,
            progress: 0,
            asset: {
              id: "",
              s3_url: data.bgm,
              file_name: data.bgm.split("/").pop() || "bgm",
              file_size_bytes: 0,
              asset_type: "bgm",
              mime_type: "audio/mpeg",
              created_at: "",
            }
          });
        }
        
        // Select first scene
        if (data.project_data?.scenes?.length > 0) {
          setSelectedSceneId(data.project_data.scenes[0].id);
        }

        // Fetch current job status to sync
        const jobRes = await api.get(`/api/jobs/${id}`);
        setJobStatus(jobRes.data.status);
        setJobProgress(jobRes.data.progress_percent || 0);
        setJobError(jobRes.data.error_message || null);
      } catch (err: any) {
        console.error(err);
        setError(err?.response?.data?.detail || "Không thể tải kịch bản phân tích.");
      } finally {
        setLoading(false);
      }
    };
    fetchProject();
  }, [id]);

  // Polling Effect for Render Monitor
  useEffect(() => {
    if (!id) return;
    
    const checkJobStatus = async () => {
      try {
        const jobRes = await api.get(`/api/jobs/${id}`);
        const status = jobRes.data.status;
        setJobStatus(status);
        setJobProgress(jobRes.data.progress_percent || 0);
        setJobError(jobRes.data.error_message || null);
        
        // Fetch logs
        const logsRes = await api.get(`/api/jobs/${id}/logs`);
        setJobLogs(logsRes.data || []);
        
        if (status === "SUCCESS") {
          const dlRes = await api.get(`/api/jobs/${id}/download`);
          setDownloadUrl(dlRes.data.download_url);
          return true; // completed
        }
        if (status === "FAILED") {
          return true; // failed
        }
      } catch (err) {
        console.error("Error polling job status:", err);
      }
      return false;
    };

    // Run immediately if rendering is active
    if (jobStatus === "PENDING" || jobStatus === "PROCESSING") {
      checkJobStatus();
    }

    let interval: any;
    if (jobStatus === "PENDING" || jobStatus === "PROCESSING") {
      interval = setInterval(async () => {
        const isDone = await checkJobStatus();
        if (isDone) {
          clearInterval(interval);
        }
      }, 3000);
    }
    
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [id, jobStatus]);

  // Handle active scene content edits
  const handleViTextChange = (text: string) => {
    if (!projectData || !selectedSceneId) return;
    const updatedScenes = projectData.scenes.map(scene => {
      if (scene.id === selectedSceneId) {
        return {
          ...scene,
          audio: {
            ...scene.audio,
            vi_text: text
          }
        };
      }
      return scene;
    });
    setProjectData({
      ...projectData,
      scenes: updatedScenes
    });
  };

  // Constraint Rule Formula: Speed calculation (Vietnamese voice speed limit <= 4.0 words/s)
  const getSpeechRate = (scene: Scene) => {
    const text = (scene.audio.vi_text || "").trim();
    if (!text) return 0;
    const wordCount = text.split(/\s+/).length;
    const duration = scene.end - scene.start;
    return duration > 0 ? Number((wordCount / duration).toFixed(2)) : 0;
  };

  const getSyllableCount = (text: string | null | undefined) => {
    return text?.trim() ? text.trim().split(/\s+/).length : 0;
  };

  // API Call: Save project state to PostgreSQL
  const handleSave = async (silent = false) => {
    if (!projectData || !id) return;
    setSaving(true);
    setSaveStatus(null);
    try {
      let bgmS3Url = null;
      if (bgm) {
        if (bgm.file) {
          // Upload local selected bgm file first
          setSaveStatus("Đang upload nhạc nền...");
          const formData = new FormData();
          formData.append("file", bgm.file);
          formData.append("asset_type", "bgm");
          const uploadRes = await api.post("/api/assets", formData);
          bgmS3Url = uploadRes.data.s3_url;
        } else if (bgm.s3_url) {
          bgmS3Url = bgm.s3_url;
        }
      }

      await api.put(`/api/translify/projects/${id}`, {
        project_data: projectData,
        bgm: bgmS3Url
      });
      
      setSaveStatus("Đã lưu tiến trình thành công!");
      setTimeout(() => setSaveStatus(null), 3000);
    } catch (err: any) {
      console.error(err);
      if (!silent) setError("Lỗi khi lưu kịch bản: " + (err.response?.data?.detail || err.message));
    } finally {
      setSaving(false);
    }
  };

  // API Call: AI Rewrite for active scene based on Tone and CTA constraints
  const handleAiRewrite = async () => {
    if (!projectData || !selectedSceneId) return;
    const scene = projectData.scenes.find(s => s.id === selectedSceneId);
    if (!scene) return;

    setRewriting(true);
    setError(null);
    try {
      const res = await api.post("/api/translify/tools/rewrite", {
        zh_text: scene.audio.zh_text,
        original_text: scene.audio.vi_text,
        duration: scene.end - scene.start,
        tone: selectedTone,
        cta: ctaText || null
      });
      
      if (res.data?.rewritten_text) {
        handleViTextChange(res.data.rewritten_text);
      }
    } catch (err: any) {
      console.error(err);
      setError("AI Rewrite thất bại: " + (err.response?.data?.detail || err.message));
    } finally {
      setRewriting(false);
    }
  };

  // API Call: Approve & Trigger rendering stage
  const handleApproveAndRender = async () => {
    if (!projectData || !id) return;
    setRendering(true);
    setError(null);
    try {
      // 1. Save latest state
      await handleSave(true);
      
      // 2. Submit Stage 2 Render Celery Task
      await api.post(`/api/translify/projects/${id}/approve`);
      
      // 3. Instead of navigating away, set status to PENDING so polling takes over
      setJobStatus("PENDING");
      setJobProgress(0);
      setJobLogs([]);
    } catch (err: any) {
      console.error(err);
      setError("Không thể kích hoạt kết xuất video: " + (err.response?.data?.detail || err.message));
    } finally {
      setRendering(false);
    }
  };

  // API Call: Reset/Reopen kịch bản để chỉnh sửa lại
  const handleReopen = async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      await api.post(`/api/translify/projects/${id}/reopen`);
      setJobStatus("WAITING_FOR_REVIEW");
      setDownloadUrl(null);
      setJobProgress(100);
      setJobError(null);
    } catch (err: any) {
      console.error(err);
      setError("Không thể mở lại kịch bản: " + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-[#0B0B0F] text-muted-foreground gap-4">
        <Loader2 className="w-10 h-10 animate-spin text-primary" />
        <p className="text-sm font-medium tracking-wide">Đang phân tích dữ liệu kịch bản...</p>
      </div>
    );
  }

  if (error && !projectData) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-[#0B0B0F] p-6 text-center gap-6">
        <div className="p-4 bg-rose-500/10 rounded-2xl border border-rose-500/20">
          <AlertTriangle className="w-12 h-12 text-rose-500" />
        </div>
        <div>
          <h2 className="text-2xl font-bold text-white mb-2">Đã xảy ra lỗi</h2>
          <p className="text-muted-foreground max-w-sm">{error}</p>
        </div>
        <Link to="/projects">
          <Button variant="secondary">
            <ArrowLeft className="w-4 h-4 mr-2" /> Quay lại dự án
          </Button>
        </Link>
      </div>
    );
  }

  const activeScene = projectData?.scenes.find(s => s.id === selectedSceneId);
  const speechRate = activeScene ? getSpeechRate(activeScene) : 0;
  const isSpeedViolation = speechRate > 4.0;
  const activeDuration = activeScene ? activeScene.end - activeScene.start : 0;
  const maxSafeWords = activeScene ? Math.floor(activeDuration * 4.0) : 0;

  return (
    <div className="min-h-screen bg-[#0B0B0F] text-white flex flex-col font-sans selection:bg-primary/30">
      {/* Premium Header */}
      <header className="border-b border-white/5 bg-black/40 backdrop-blur-md sticky top-0 z-40 px-8 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-6">
          <div className="flex items-center gap-4">
            <Link 
              to="/projects"
              className="p-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-muted-foreground hover:text-white transition-all border border-white/5"
            >
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono uppercase bg-primary/20 text-primary px-2 py-0.5 rounded border border-primary/20 font-semibold tracking-wider">Layer C</span>
                <span className="text-xs text-muted-foreground">Phân dịch video & Kịch bản AI</span>
              </div>
              <h1 className="text-xl font-bold text-white mt-1">Refine Translation Editor (Job #{id})</h1>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {saveStatus && (
              <span className="text-xs text-emerald-400 bg-emerald-400/10 border border-emerald-400/20 px-3 py-1.5 rounded-xl flex items-center gap-1.5 animate-pulse">
                <CheckCircle2 className="w-3.5 h-3.5" /> {saveStatus}
              </span>
            )}
            <Button 
              variant="secondary" 
              onClick={() => handleSave()} 
              disabled={saving}
              className="bg-white/5 hover:bg-white/10 text-white border border-white/10 rounded-xl"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
              Lưu tiến trình
            </Button>
            <Button 
              onClick={handleApproveAndRender} 
              disabled={rendering}
              className="glowing-button bg-gradient-to-r from-violet-600 to-indigo-600 border border-violet-500 hover:shadow-[0_0_20px_rgba(124,58,237,0.5)] rounded-xl"
            >
              {rendering ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Play className="w-4 h-4 mr-2" />}
              Duyệt & Kết xuất Video
            </Button>
          </div>
        </div>
      </header>

      {error && (
        <div className="bg-rose-500/10 border-b border-rose-500/20 px-8 py-3 text-sm text-rose-400 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Workspace Area */}
      <div className="flex-1 max-w-7xl mx-auto w-full p-8 grid grid-cols-1 lg:grid-cols-12 gap-8 overflow-hidden h-[calc(100vh-80px)]">
        {/* Left Column: Vertical Scene Timeline */}
        <div className="lg:col-span-4 flex flex-col h-full overflow-hidden space-y-4">
          <div className="flex items-center justify-between px-2 shrink-0">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <Film className="w-4 h-4 text-primary" /> Phân cảnh Video ({projectData?.scenes.length})
            </h3>
            <span className="text-[10px] bg-white/5 border border-white/10 px-2 py-0.5 rounded text-muted-foreground font-mono">
              Limit: 4.0 words/s
            </span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-3 pr-2 custom-scrollbar pb-8">
            {projectData?.scenes.map((scene, idx) => {
              const isActive = scene.id === selectedSceneId;
              const rate = getSpeechRate(scene);
              const isViolated = rate > 4.0;
              return (
                <button
                  key={scene.id}
                  onClick={() => setSelectedSceneId(scene.id)}
                  className={cn(
                    "w-full text-left p-4 rounded-2xl border transition-all duration-300 flex flex-col gap-2 relative overflow-hidden group",
                    isActive 
                      ? "bg-primary/10 border-primary shadow-[inset_0_0_20px_rgba(124,58,237,0.1)]" 
                      : "bg-white/[0.02] border-white/5 hover:border-white/20 hover:bg-white/[0.04]",
                    isViolated && !isActive && "border-rose-500/20 bg-rose-500/[0.01] hover:border-rose-500/40"
                  )}
                >
                  <div className="flex items-center justify-between w-full">
                    <span className="text-[11px] font-mono text-muted-foreground bg-white/5 px-2 py-0.5 rounded border border-white/5">
                      Cảnh {idx + 1} • {scene.id}
                    </span>
                    <span className="text-[11px] text-muted-foreground flex items-center gap-1 font-mono">
                      <Clock className="w-3.5 h-3.5" />
                      {(scene.end - scene.start).toFixed(2)}s
                    </span>
                  </div>

                  <p className="text-xs text-muted-foreground/80 line-clamp-1 italic font-sans pr-4">
                    🇨🇳 {scene.audio.zh_text || "(Không có giọng nói gốc)"}
                  </p>
                  
                  <p className="text-sm font-semibold text-white/90 line-clamp-2">
                    🇻🇳 {scene.audio.vi_text || <span className="text-muted-foreground/40 font-normal">Chưa dịch</span>}
                  </p>

                  <div className="flex items-center justify-between w-full mt-1 border-t border-white/5 pt-2">
                    <span className="text-[10px] text-muted-foreground/70 font-mono">
                      {getSyllableCount(scene.audio.vi_text)} từ
                    </span>
                    {isViolated ? (
                      <span className="text-[10px] text-rose-400 font-bold bg-rose-500/10 px-2 py-0.5 rounded border border-rose-500/20 animate-pulse flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" /> Quá dài ({rate} từ/s)
                      </span>
                    ) : (
                      <span className="text-[10px] text-emerald-400 font-medium bg-emerald-400/5 px-2 py-0.5 rounded border border-emerald-400/10">
                        Hợp lệ ({rate} từ/s)
                      </span>
                    )}
                  </div>

                  {/* Left indicator line */}
                  <div className={cn(
                    "absolute left-0 top-0 bottom-0 w-1 transition-all",
                    isActive ? "bg-primary" : isViolated ? "bg-rose-500" : "bg-transparent"
                  )}></div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Right Column: Editing Panel OR Rendering Monitor */}
        <div className="lg:col-span-8 flex flex-col h-full overflow-hidden space-y-6">
          {jobStatus !== "WAITING_FOR_REVIEW" ? (
            <div className="flex-1 overflow-y-auto space-y-6 pr-2 custom-scrollbar pb-8 animate-in fade-in duration-500">
              <Card className="p-8 bg-black/40 border border-white/5 shadow-2xl rounded-3xl relative overflow-hidden flex flex-col gap-6">
                
                {/* Visual Status Indicator */}
                <div className="flex flex-col items-center text-center py-6 gap-4">
                  {jobStatus === "PENDING" && (
                    <div className="relative">
                      <div className="w-20 h-20 rounded-full border-4 border-dashed border-indigo-500/30 animate-spin flex items-center justify-center"></div>
                      <Clock className="w-8 h-8 text-indigo-400 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 animate-pulse" />
                    </div>
                  )}
                  {jobStatus === "PROCESSING" && (
                    <div className="relative">
                      <div className="w-20 h-20 rounded-full border-4 border-t-blue-500 border-r-blue-500 border-b-transparent border-l-transparent animate-spin flex items-center justify-center"></div>
                      <Film className="w-8 h-8 text-blue-400 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
                    </div>
                  )}
                  {jobStatus === "SUCCESS" && (
                    <div className="w-20 h-20 rounded-full bg-emerald-500/10 border-4 border-emerald-500/20 flex items-center justify-center shadow-[0_0_30px_rgba(16,185,129,0.2)]">
                      <CheckCircle2 className="w-10 h-10 text-emerald-400" />
                    </div>
                  )}
                  {jobStatus === "FAILED" && (
                    <div className="w-20 h-20 rounded-full bg-rose-500/10 border-4 border-rose-500/20 flex items-center justify-center">
                      <AlertTriangle className="w-10 h-10 text-rose-400" />
                    </div>
                  )}

                  <div>
                    <h2 className="text-2xl font-extrabold tracking-tight text-white mt-2">
                      {jobStatus === "PENDING" && "Đang xếp hàng chờ xử lý..."}
                      {jobStatus === "PROCESSING" && "Đang kết xuất video thành phẩm..."}
                      {jobStatus === "SUCCESS" && "Video của bạn đã sẵn sàng! 🎉"}
                      {jobStatus === "FAILED" && "Kết xuất video thất bại"}
                    </h2>
                    <p className="text-sm text-muted-foreground mt-1 max-w-md mx-auto">
                      {jobStatus === "PENDING" && "Yêu cầu kết xuất đã được gửi lên hàng đợi Celery. Tiến trình sẽ sớm bắt đầu."}
                      {jobStatus === "PROCESSING" && "Hệ thống đang sinh giọng lồng tiếng Việt bằng AI, phối âm thanh môi trường và chèn phụ đề."}
                      {jobStatus === "SUCCESS" && "Chúc mừng! Kịch bản dịch thuật đã được xuất bản thành công vào video."}
                      {jobStatus === "FAILED" && "Đã xảy ra sự cố trong quá trình sinh giọng nói hoặc dựng video."}
                    </p>
                  </div>
                </div>

                {/* Progress Bar */}
                <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-5 space-y-3">
                  <div className="flex justify-between items-center text-xs font-semibold text-zinc-400">
                    <span>TIẾN TRÌNH THỰC HIỆN</span>
                    <span className="font-mono text-white text-sm">{jobProgress}%</span>
                  </div>
                  <div className="w-full h-3 bg-white/5 rounded-full overflow-hidden relative shadow-inner">
                    <div 
                      className={cn(
                        "h-full transition-all duration-1000",
                        jobStatus === "SUCCESS" ? "bg-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.5)]" : 
                        jobStatus === "FAILED" ? "bg-rose-500" : "bg-gradient-to-r from-blue-500 to-indigo-500 shadow-[0_0_15px_rgba(59,130,246,0.5)]"
                      )}
                      style={{ width: `${jobProgress}%` }}
                    ></div>
                  </div>
                </div>

                {/* Video Preview Player (Only on SUCCESS) */}
                {jobStatus === "SUCCESS" && downloadUrl && (
                  <div className="border border-white/5 rounded-2xl overflow-hidden bg-black/40 aspect-video shadow-2xl relative group">
                    <video 
                      src={downloadUrl} 
                      controls 
                      className="w-full h-full object-contain"
                    />
                  </div>
                )}

                {/* Error Banner */}
                {jobStatus === "FAILED" && jobError && (
                  <div className="bg-rose-500/10 border border-rose-500/20 text-rose-400 p-4 rounded-2xl text-sm font-mono whitespace-pre-wrap break-all">
                    {jobError}
                  </div>
                )}

                {/* Real-time Logger Terminal */}
                <div className="flex-1 min-h-[150px] max-h-[250px] bg-black/60 rounded-2xl border border-white/5 p-4 flex flex-col font-mono text-[11px] text-zinc-400 overflow-hidden shadow-inner">
                  <div className="flex items-center justify-between border-b border-white/5 pb-2 mb-2 shrink-0">
                    <span className="text-zinc-500 font-bold uppercase tracking-wider">Terminal Logs</span>
                    <div className="flex gap-1.5">
                      <div className="w-2.5 h-2.5 rounded-full bg-rose-500/40 animate-pulse"></div>
                      <div className="w-2.5 h-2.5 rounded-full bg-amber-500/40 animate-pulse"></div>
                      <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/40 animate-pulse"></div>
                    </div>
                  </div>
                  <div className="flex-1 overflow-y-auto space-y-1.5 custom-scrollbar pr-1 select-text">
                    {jobLogs.length > 0 ? (
                      jobLogs.map((log: any, idx: number) => (
                        <div key={idx} className={cn(
                          "leading-relaxed",
                          log.log_level === "ERROR" ? "text-rose-400" : "text-zinc-300"
                        )}>
                          <span className="text-zinc-600 mr-2">[{new Date(log.created_at).toLocaleTimeString()}]</span>
                          {log.message}
                        </div>
                      ))
                    ) : (
                      <div className="text-zinc-600 italic">Đang tải lịch sử logs...</div>
                    )}
                  </div>
                </div>

                {/* Action Controls */}
                <div className="flex justify-center gap-4 pt-4 border-t border-white/5 shrink-0">
                  {jobStatus === "SUCCESS" && downloadUrl && (
                    <a href={downloadUrl} download={`translated_job_${id}.mp4`}>
                      <Button className="bg-emerald-500 hover:bg-emerald-600 text-black font-bold px-6 py-2.5 rounded-xl flex items-center gap-2">
                        <Download className="w-4 h-4" /> Tải xuống video
                      </Button>
                    </a>
                  )}
                  {(jobStatus === "SUCCESS" || jobStatus === "FAILED") && (
                    <Button 
                      onClick={handleReopen}
                      variant="secondary"
                      className="bg-white/5 hover:bg-white/10 text-white border border-white/10 px-6 py-2.5 rounded-xl flex items-center gap-2"
                    >
                      <Sliders className="w-4 h-4" /> 
                      {jobStatus === "SUCCESS" ? "Chỉnh sửa lại kịch bản" : "Chỉnh sửa & Thử lại"}
                    </Button>
                  )}
                  <Link to="/projects">
                    <Button variant="secondary" className="px-6 py-2.5 rounded-xl">
                      Quay lại dự án
                    </Button>
                  </Link>
                </div>

              </Card>
            </div>
          ) : activeScene ? (
            <div className="flex-1 overflow-y-auto space-y-6 pr-2 custom-scrollbar pb-8">
              {/* Scene Detail Panel */}
              <Card className="p-6 bg-white/[0.02] border-white/5 shadow-xl space-y-5 rounded-2xl">
                <div className="flex items-center justify-between border-b border-white/5 pb-4">
                  <div className="flex items-center gap-2">
                    <Languages className="w-5 h-5 text-primary" />
                    <h3 className="text-lg font-bold text-white">Hiệu chỉnh dịch thuật</h3>
                  </div>
                  <span className="text-xs font-mono text-muted-foreground/80 bg-white/5 border border-white/10 px-3 py-1 rounded-xl">
                    Thời lượng: {activeDuration.toFixed(2)}s (Bắt đầu: {activeScene.start}s - Kết thúc: {activeScene.end}s)
                  </span>
                </div>

                <div className="space-y-4">
                  {/* Original Transcripts */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="bg-black/30 border border-white/5 rounded-2xl p-4 space-y-2">
                      <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Giọng gốc tiếng Trung</label>
                      <p className="text-sm text-white/95 leading-relaxed font-sans min-h-[3rem]">
                        {activeScene.audio.zh_text || <span className="text-muted-foreground/30 italic">Không có âm thanh thoại</span>}
                      </p>
                    </div>

                    <div className="bg-black/30 border border-white/5 rounded-2xl p-4 space-y-2">
                      <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Văn bản OCR trong phân cảnh</label>
                      <div className="text-sm text-white/95 leading-relaxed min-h-[3rem]">
                        {activeScene.visual.ocr_text && activeScene.visual.ocr_text.length > 0 ? (
                          <div className="flex flex-wrap gap-1.5 mt-1">
                            {activeScene.visual.ocr_text.map((ocr, i) => (
                              <span key={i} className="text-xs bg-white/5 border border-white/10 text-muted-foreground px-2 py-0.5 rounded" title={ocr.confidence !== undefined ? `Confidence: ${(ocr.confidence * 100).toFixed(0)}%` : "OCR Detected"}>
                                {ocr.text_zh}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <p className="text-xs text-muted-foreground/30 italic mt-1">Không phát hiện văn bản cứng (OCR)</p>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Script Editor & Constraint Tracker */}
                  <div className="space-y-3 relative">
                    <label className="text-sm font-semibold text-white/90 flex justify-between items-center">
                      <span>Bản dịch giọng đọc tiếng Việt</span>
                      <span className="text-xs font-mono font-medium text-muted-foreground">
                        Syllables: <span className={cn(isSpeedViolation ? "text-rose-400 font-bold" : "text-emerald-400")}>{getSyllableCount(activeScene.audio.vi_text)}</span> / {maxSafeWords} từ an toàn
                      </span>
                    </label>

                    <div className="relative rounded-2xl border border-white/10 bg-black/40 overflow-hidden focus-within:border-primary/50 transition-colors">
                      <textarea
                        value={activeScene.audio.vi_text}
                        onChange={e => handleViTextChange(e.target.value)}
                        placeholder="Nhập bản dịch tiếng Việt tại đây..."
                        rows={4}
                        disabled={rewriting}
                        className="w-full bg-transparent px-4 py-3 text-base text-white focus:outline-none resize-none placeholder:text-muted-foreground/30 min-h-[5rem]"
                      />
                      
                      {rewriting && (
                        <div className="absolute inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center gap-2 animate-in fade-in">
                          <Loader2 className="w-5 h-5 animate-spin text-primary" />
                          <span className="text-xs font-semibold text-primary uppercase tracking-wider">AI đang viết lại kịch bản...</span>
                        </div>
                      )}
                    </div>

                    {/* Constraint Progress Bar */}
                    <div className="bg-black/30 border border-white/5 rounded-2xl p-4 space-y-3">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground flex items-center gap-1 font-semibold">
                          <Sliders className="w-3.5 h-3.5 text-primary" /> Đo lường Ràng buộc thời gian (Constraint Tracker)
                        </span>
                        <span className={cn("font-mono font-bold", isSpeedViolation ? "text-rose-400" : "text-emerald-400")}>
                          Tốc độ đọc: {speechRate} từ/giây (Giới hạn: ≤ 4.0)
                        </span>
                      </div>
                      
                      <div className="w-full h-2.5 bg-white/5 rounded-full overflow-hidden relative">
                        <div
                          className={cn(
                            "h-full transition-all duration-300",
                            isSpeedViolation ? "bg-rose-500" : "bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]"
                          )}
                          style={{ width: `${Math.min(100, (speechRate / 4.0) * 100)}%` }}
                        ></div>
                        <div className="absolute left-[100%] top-0 bottom-0 w-0.5 bg-rose-500 z-10" style={{ left: "100%" }}></div>
                      </div>

                      {isSpeedViolation ? (
                        <div className="bg-rose-500/10 border border-rose-500/20 text-rose-400 p-3 rounded-xl flex items-start gap-2 text-xs">
                          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-rose-400 animate-pulse" />
                          <div>
                            <span className="font-bold">Cảnh báo Vượt thời lượng:</span> Bản dịch quá dài ({getSyllableCount(activeScene.audio.vi_text)} từ) cho thời lượng {activeDuration.toFixed(2)} giây. Giọng đọc AI sẽ bị co-kéo méo tiếng. Vui lòng rút gọn dưới {maxSafeWords} từ hoặc dùng nút "AI Rewrite" bên dưới.
                          </div>
                        </div>
                      ) : (
                        <div className="text-[11px] text-muted-foreground/70">
                          🔥 Độ dài an toàn. Giọng nói AI sẽ khớp hoàn hảo với diễn biến hình ảnh.
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </Card>

              {/* AI Rewrite Assistant Panel */}
              <Card className="p-6 bg-white/[0.02] border-white/5 shadow-xl space-y-4 rounded-2xl">
                <div className="flex items-center gap-2 border-b border-white/5 pb-3">
                  <Sparkles className="w-5 h-5 text-amber-400" />
                  <h3 className="text-md font-bold text-white">Công cụ AI Tinh chỉnh kịch bản (Constraint-Aware)</h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs text-muted-foreground font-semibold">Tông giọng (Tone)</label>
                    <select
                      value={selectedTone}
                      onChange={e => setSelectedTone(e.target.value)}
                      className="w-full h-11 rounded-xl border border-white/10 bg-black/40 px-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-primary/50 appearance-none"
                    >
                      {TONES.map(t => (
                        <option key={t.id} value={t.id} className="bg-[#1A1A24]">{t.name}</option>
                      ))}
                    </select>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs text-muted-foreground font-semibold">Kêu gọi hành động (CTA - Tùy chọn)</label>
                    <input
                      type="text"
                      value={ctaText}
                      onChange={e => setCtaText(e.target.value)}
                      placeholder="Ví dụ: Đăng ký ngay, Click Bio..."
                      className="w-full h-11 rounded-xl border border-white/10 bg-black/40 px-4 text-sm text-white focus:outline-none focus:ring-1 focus:ring-primary/50 placeholder:text-muted-foreground/30"
                    />
                  </div>
                </div>

                <div className="flex justify-end pt-2">
                  <Button 
                    onClick={handleAiRewrite} 
                    disabled={rewriting || !activeScene.audio.zh_text}
                    className="bg-amber-500 hover:bg-amber-600 text-black border-none font-bold rounded-xl flex items-center gap-1.5 hover:shadow-[0_0_15px_rgba(245,158,11,0.3)] shrink-0"
                  >
                    {rewriting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                    Tự động rút gọn & Viết lại bằng AI
                  </Button>
                </div>
              </Card>

              {/* Global Config & BGM Panel */}
              <Card className="p-6 bg-white/[0.02] border-white/5 shadow-xl space-y-4 rounded-2xl">
                <div className="flex items-center gap-2 border-b border-white/5 pb-3">
                  <Sliders className="w-5 h-5 text-indigo-400" />
                  <h3 className="text-md font-bold text-white">Cấu hình Âm thanh & Kết xuất Video</h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-3">
                    <label className="text-sm font-semibold text-white/90">Lựa chọn Giọng đọc AI</label>
                    <select
                      value={voiceName}
                      onChange={e => setVoiceName(e.target.value)}
                      className="w-full h-11 rounded-xl border border-white/10 bg-black/40 px-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-primary/50 appearance-none"
                    >
                      <option value="vi-VN-NamMinhNeural" className="bg-[#1A1A24]">🇻🇳 vi-VN-NamMinh (Giọng nam ấm áp - Tốt nhất)</option>
                      <option value="vi-VN-HoaiMyNeural" className="bg-[#1A1A24]">🇻🇳 vi-VN-HoaiMy (Giọng nữ nhẹ nhàng)</option>
                      <option value="vi-VN-MinhQuanNeural" className="bg-[#1A1A24]">🇻🇳 vi-VN-MinhQuan (Giọng nam trẻ trung)</option>
                    </select>
                    <div className="text-[10px] text-muted-foreground/60 leading-relaxed">
                      Giọng đọc AI được sử dụng trong Stage 2 (Render) để tự động tạo lồng tiếng Việt dựa trên kịch bản từng phân cảnh ở trên.
                    </div>
                  </div>

                  <div className="space-y-1 bg-black/30 p-4 rounded-2xl border border-white/5">
                    <AssetSelector
                      label="Thay thế Nhạc nền (BGM)"
                      sublabel="Click để chọn từ MinIO hoặc Tải lên nhạc nền mới"
                      icon={<Music className="w-5 h-5 text-cyan-400" />}
                      accept="audio/mpeg,audio/*"
                      assetTypeFilter="bgm"
                      selectedFile={bgm}
                      onSelect={(file, asset) => {
                        if (file || asset) {
                          setBgm({
                            file,
                            asset,
                            id: asset?.id || null,
                            s3_url: asset?.s3_url || null,
                            uploading: false,
                            progress: 0
                          });
                        } else {
                          setBgm(null);
                        }
                      }}
                    />
                    <div className="text-[10px] text-muted-foreground/60 leading-relaxed mt-2">
                      Nếu không chọn, hệ thống sẽ tự động trích xuất và phối âm thanh môi trường nguyên bản của video Trung Quốc.
                    </div>
                  </div>
                </div>
              </Card>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center text-muted-foreground bg-white/[0.01] border border-dashed border-white/5 rounded-2xl p-16">
              <div className="text-center space-y-2">
                <HelpCircle className="w-12 h-12 mx-auto text-muted-foreground/30" />
                <p className="text-sm">Hãy chọn một phân cảnh bên trái để bắt đầu hiệu chỉnh.</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
