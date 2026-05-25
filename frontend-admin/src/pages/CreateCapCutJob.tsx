import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Folder, Plus, Bot, Send, AlertTriangle, FileText, Clock, Copy, Music, Film, Trash2, FileJson } from "lucide-react";
import api from "../lib/api";
import { cn } from "../lib/utils";
import { useProjects } from "../hooks/useProjects";
import { Button } from "../components/ui/Button";

interface Segment {
  segment: string;
  video_source: string;
  time_start: number;
  time_end: number;
  text_overlay: string;
  transition: string;
  visual_effects: string[];
}

export default function CreateCapCutJob() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const cloneJobId = searchParams.get("clone");
  const { projects, createProject } = useProjects();

  // Project State
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [newProjectName, setNewProjectName] = useState("");
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [priority, setPriority] = useState(0);

  // Audio Assets
  const [bgmPath, setBgmPath] = useState("");
  const [voiceoverPath, setVoiceoverPath] = useState("");

  // Video Folders Map
  const [videoFolders, setVideoFolders] = useState<Record<string, string>>({});
  const [newFolderKey, setNewFolderKey] = useState("");
  const [newFolderVal, setNewFolderVal] = useState("");

  // Timeline Script
  const [segments, setSegments] = useState<Segment[]>([]);

  // Raw JSON Mode
  const [isJsonMode, setIsJsonMode] = useState(false);
  const [jsonText, setJsonText] = useState("");

  // UI State
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState("");
  const [cloneLoading, setCloneLoading] = useState(!!cloneJobId);

  useEffect(() => {
    if (projects.length > 0 && !selectedProjectId) setSelectedProjectId(projects[0].id);
    if (projects.length === 0) setIsCreatingProject(true);
  }, [projects, selectedProjectId]);

  // Clone pre-fill: fetch original job data and populate form
  useEffect(() => {
    if (!cloneJobId) return;
    let cancelled = false;
    const loadClone = async () => {
      try {
        setCloneLoading(true);
        const res = await api.get(`/api/jobs/${cloneJobId}`);
        const job = res.data;
        if (cancelled) return;

        // Pre-fill project
        if (job.project_id) {
          setSelectedProjectId(job.project_id);
          setIsCreatingProject(false);
        }
        if (job.priority !== undefined) setPriority(job.priority);

        const cfg = job.config_data || {};
        
        // Audio
        if (cfg.assets?.audio) {
          setBgmPath(cfg.assets.audio.bgm_path || "");
          setVoiceoverPath(cfg.assets.audio.voiceover_path || "");
        }

        // Video folders
        if (cfg.assets?.video_folders) {
          setVideoFolders(cfg.assets.video_folders);
        }

        // Segments
        if (cfg.timeline_script && Array.isArray(cfg.timeline_script)) {
          const parsedSegs: Segment[] = cfg.timeline_script.map((ts: any) => ({
            segment: ts.segment || ts.video_source || "segment",
            video_source: ts.video_source || ts.segment || "segment",
            time_start: ts.time_range?.[0] || 0,
            time_end: ts.time_range?.[1] || 5,
            text_overlay: ts.text_overlay || "",
            transition: ts.transition || "",
            visual_effects: ts.visual_effects || [],
          }));
          setSegments(parsedSegs);
        }

        // Set json text
        setJsonText(JSON.stringify(cfg, null, 2));

      } catch (err) {
        console.error("Failed to load cloned capcut job:", err);
        setError("Không thể tải thông tin Job sao chép.");
      } finally {
        if (!cancelled) setCloneLoading(false);
      }
    };
    loadClone();
    return () => {
      cancelled = true;
    };
  }, [cloneJobId]);

  // Handle building config payload
  const buildConfigPayload = () => {
    if (isJsonMode) {
      try {
        return JSON.parse(jsonText);
      } catch (e) {
        throw new Error("Cấu trúc JSON cấu hình không hợp lệ. Vui lòng kiểm tra lại cú pháp.");
      }
    }

    const timelineScript = segments.map(s => {
      const item: any = {
        segment: s.segment,
        time_range: [Number(s.time_start), Number(s.time_end)],
        video_source: s.video_source,
      };
      if (s.text_overlay) item.text_overlay = s.text_overlay;
      if (s.transition) item.transition = s.transition;
      if (s.visual_effects && s.visual_effects.length > 0) {
        item.visual_effects = s.visual_effects.filter(Boolean);
      }
      return item;
    });

    return {
      metadata: {
        project_id: selectedProjectId || "default"
      },
      assets: {
        audio: {
          bgm_path: bgmPath.trim() || undefined,
          voiceover_path: voiceoverPath.trim() || undefined
        },
        video_folders: videoFolders
      },
      timeline_script: timelineScript
    };
  };

  // Sync JSON text when forms change (if not in JSON mode)
  useEffect(() => {
    if (!isJsonMode) {
      try {
        const payload = buildConfigPayload();
        setJsonText(JSON.stringify(payload, null, 2));
      } catch (e) {}
    }
  }, [bgmPath, voiceoverPath, videoFolders, segments, selectedProjectId, isJsonMode]);

  const addSegment = () => {
    const nextStart = segments.length > 0 ? segments[segments.length - 1].time_end : 0;
    setSegments([
      ...segments,
      {
        segment: `segment_${segments.length + 1}`,
        video_source: `segment_${segments.length + 1}`,
        time_start: nextStart,
        time_end: nextStart + 5,
        text_overlay: "",
        transition: "",
        visual_effects: [],
      }
    ]);
  };

  const removeSegment = (idx: number) => {
    setSegments(segments.filter((_, i) => i !== idx));
  };

  const updateSegment = (idx: number, fields: Partial<Segment>) => {
    setSegments(segments.map((s, i) => i === idx ? { ...s, ...fields } : s));
  };

  const addVideoFolder = () => {
    if (!newFolderKey.trim() || !newFolderVal.trim()) return;
    setVideoFolders({
      ...videoFolders,
      [newFolderKey.trim()]: newFolderVal.trim()
    });
    setNewFolderKey("");
    setNewFolderVal("");
  };

  const removeVideoFolder = (key: string) => {
    const updated = { ...videoFolders };
    delete updated[key];
    setVideoFolders(updated);
  };

  const handleSubmit = async () => {
    if (!isCreatingProject && !selectedProjectId) return setError("Vui lòng chọn một dự án.");
    if (isCreatingProject && !newProjectName.trim()) return setError("Vui lòng nhập tên dự án mới.");

    setLoading(true);
    setError(null);
    try {
      let targetProjectId = selectedProjectId;
      if (isCreatingProject && newProjectName.trim()) {
        setStatusMessage("Đang tạo dự án mới...");
        const proj = await createProject(newProjectName.trim());
        targetProjectId = proj.id;
      }

      setStatusMessage("Đang gửi lệnh dựng bản nháp CapCut...");

      const payloadConfig = buildConfigPayload();
      // Ensure project_id matches
      if (payloadConfig.metadata) {
        payloadConfig.metadata.project_id = targetProjectId;
      } else {
        payloadConfig.metadata = { project_id: targetProjectId };
      }

      const payload = {
        job_type: "capcut",
        project_id: targetProjectId,
        priority: Number(priority),
        config_data: payloadConfig,
      };

      await api.post("/api/jobs", payload);
      navigate("/");
    } catch (err: any) {
      console.error(err);
      const detail = err?.response?.data?.detail;
      const msg = Array.isArray(detail)
        ? detail.map((e: any) => e.msg || JSON.stringify(e)).join("; ")
        : typeof detail === "string" ? detail : err.message || "Không thể tạo Job dựng CapCut.";
      setError(msg);
    } finally {
      setLoading(false);
      setStatusMessage("");
    }
  };

  return (
    <div className="max-w-7xl mx-auto p-8 lg:p-12 space-y-10 animate-in fade-in duration-300">
      {/* Header section */}
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-2xl shadow-[0_0_20px_rgba(124,58,237,0.4)]">
            <Film className="w-7 h-7 text-white" />
          </div>
          <span className="text-xs font-mono uppercase bg-primary/20 text-primary px-3 py-1 rounded-md border border-primary/20 font-bold tracking-wider">
            CapCut Draft Generator
          </span>
        </div>
        <h2 className="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60">
          Dựng Bản Nháp CapCut (CapCut Draft Factory)
        </h2>
        <p className="text-muted-foreground text-lg max-w-3xl">
          Tạo và điều chỉnh timeline kịch bản, cấu hình BGM/Voiceover để tự động kết xuất dự án nháp sang máy tính Windows chạy CapCut của bạn.
        </p>
      </div>

      {error && (
        <div className="p-4 bg-rose-500/10 text-rose-400 rounded-2xl border border-rose-500/20 backdrop-blur-sm flex items-center gap-3 animate-in slide-in-from-top-2">
          <AlertTriangle className="w-5 h-5 shrink-0" />
          <span className="font-medium">{error}</span>
        </div>
      )}

      {cloneJobId && (
        <div className="glass-panel p-4 flex items-center gap-3 bg-amber-500/10 border border-amber-500/20 rounded-xl animate-in fade-in">
          <Copy className="w-5 h-5 text-amber-400 shrink-0" />
          <div>
            <p className="text-sm font-medium text-amber-300">Bản sao từ Job #{cloneJobId}</p>
            <p className="text-xs text-amber-400/70">Chỉnh sửa timeline và nguồn tư liệu bên dưới rồi gửi để tạo bản nháp CapCut mới.</p>
          </div>
        </div>
      )}

      {cloneLoading ? (
        <div className="glass-panel p-16 flex flex-col items-center justify-center gap-4 text-muted-foreground">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
          <p>Đang tải dữ liệu từ Job #{cloneJobId}...</p>
        </div>
      ) : (
        <div className="space-y-8">
          {/* Mode Switcher */}
          <div className="flex items-center gap-2 bg-black/20 p-1 rounded-xl w-fit border border-white/5">
            <button
              onClick={() => setIsJsonMode(false)}
              className={cn(
                "px-4 py-2 rounded-lg text-xs font-semibold transition-all",
                !isJsonMode ? "bg-white/10 text-white" : "text-muted-foreground hover:text-white"
              )}
            >
              <Film className="w-3.5 h-3.5 inline mr-1.5" /> Giao diện Timeline
            </button>
            <button
              onClick={() => setIsJsonMode(true)}
              className={cn(
                "px-4 py-2 rounded-lg text-xs font-semibold transition-all",
                isJsonMode ? "bg-white/10 text-white" : "text-muted-foreground hover:text-white"
              )}
            >
              <FileJson className="w-3.5 h-3.5 inline mr-1.5" /> Chỉnh sửa JSON thô
            </button>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
            
            {/* Left Column: Project & Assets (Forms) */}
            <div className="xl:col-span-1 space-y-8">
              
              {/* Project Selection Card */}
              <div className="glass-panel p-6 space-y-6">
                <label className="text-xs font-bold text-white/95 uppercase tracking-widest flex items-center gap-2">
                  <Folder className="w-4 h-4 text-primary" /> Dự án liên kết
                </label>
                
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setIsCreatingProject(false)}
                    className={cn(
                      "flex-1 py-2 rounded-lg border text-xs font-semibold transition-all",
                      !isCreatingProject ? "bg-primary/20 border-primary text-white" : "bg-white/5 border-white/10 text-muted-foreground"
                    )}
                  >
                    Chọn dự án có sẵn
                  </button>
                  <button
                    type="button"
                    onClick={() => setIsCreatingProject(true)}
                    className={cn(
                      "flex-1 py-2 rounded-lg border text-xs font-semibold transition-all",
                      isCreatingProject ? "bg-primary/20 border-primary text-white" : "bg-white/5 border-white/10 text-muted-foreground"
                    )}
                  >
                    Tạo dự án mới
                  </button>
                </div>

                {isCreatingProject ? (
                  <input
                    type="text"
                    value={newProjectName}
                    onChange={(e) => setNewProjectName(e.target.value)}
                    placeholder="Tên dự án mới..."
                    className="flex h-11 w-full rounded-xl border border-white/10 bg-white/5 px-4 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all"
                  />
                ) : (
                  <select
                    value={selectedProjectId}
                    onChange={(e) => setSelectedProjectId(e.target.value)}
                    className="flex h-11 w-full rounded-xl border border-white/10 bg-white/5 px-4 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all appearance-none"
                  >
                    {projects.map((p) => (
                      <option key={p.id} value={p.id} className="bg-[#1A1A24]">
                        {p.name}
                      </option>
                    ))}
                  </select>
                )}

                <div className="space-y-2 border-t border-white/5 pt-4">
                  <label className="text-xs font-semibold text-muted-foreground">Độ ưu tiên Job (Priority)</label>
                  <select
                    value={priority}
                    onChange={(e) => setPriority(Number(e.target.value))}
                    className="flex h-10 w-full rounded-xl border border-white/10 bg-white/5 px-4 text-xs text-white focus:outline-none focus:ring-2 focus:ring-primary/50"
                  >
                    <option value={0} className="bg-[#1A1A24]">Normal</option>
                    <option value={10} className="bg-[#1A1A24]">High</option>
                  </select>
                </div>
              </div>

              {!isJsonMode && (
                <>
                  {/* Audio Assets Card */}
                  <div className="glass-panel p-6 space-y-5">
                    <h3 className="text-sm font-bold text-white flex items-center gap-2.5">
                      <Music className="w-5 h-5 text-indigo-400" />
                      Âm thanh (Audio Assets)
                    </h3>
                    
                    <div className="space-y-4">
                      <div className="space-y-2">
                        <label className="text-[11px] font-semibold text-muted-foreground">S3/Local Path Nhạc Nền (BGM)</label>
                        <input
                          type="text"
                          value={bgmPath}
                          onChange={(e) => setBgmPath(e.target.value)}
                          placeholder="Ví dụ: s3://videos/assets/bgm/victory.mp3"
                          className="flex h-10 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-xs text-white font-mono focus:outline-none focus:ring-1 focus:ring-primary"
                        />
                      </div>

                      <div className="space-y-2">
                        <label className="text-[11px] font-semibold text-muted-foreground">S3/Local Path Giọng Đọc (Voiceover)</label>
                        <input
                          type="text"
                          value={voiceoverPath}
                          onChange={(e) => setVoiceoverPath(e.target.value)}
                          placeholder="Ví dụ: s3://videos/outputs/voiceover_267.mp3"
                          className="flex h-10 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-xs text-white font-mono focus:outline-none focus:ring-1 focus:ring-primary"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Video Folders Card */}
                  <div className="glass-panel p-6 space-y-4">
                    <h3 className="text-sm font-bold text-white flex items-center gap-2.5">
                      <Film className="w-5 h-5 text-cyan-400" />
                      Thư mục Video Phân Cảnh (Video Folders)
                    </h3>
                    
                    {/* Add Custom video folder mapping */}
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={newFolderKey}
                        onChange={(e) => setNewFolderKey(e.target.value)}
                        placeholder="Key (e.g. hook)"
                        className="w-1/3 h-9 rounded-lg border border-white/10 bg-white/5 px-2 text-xs text-white"
                      />
                      <input
                        type="text"
                        value={newFolderVal}
                        onChange={(e) => setNewFolderVal(e.target.value)}
                        placeholder="S3 Folder hoặc Local Path"
                        className="flex-1 h-9 rounded-lg border border-white/10 bg-white/5 px-2 text-xs text-white font-mono"
                      />
                      <button
                        onClick={addVideoFolder}
                        className="px-3 bg-primary text-white rounded-lg text-xs font-semibold"
                      >
                        Thêm
                      </button>
                    </div>

                    <div className="space-y-2 border-t border-white/5 pt-3 max-h-48 overflow-y-auto custom-scrollbar">
                      {Object.keys(videoFolders).length === 0 ? (
                        <p className="text-xs text-muted-foreground/60 italic text-center py-2">Chưa cấu hình thư mục video phân cảnh nào.</p>
                      ) : (
                        Object.entries(videoFolders).map(([k, v]) => (
                          <div key={k} className="flex items-center justify-between bg-white/[0.02] border border-white/5 p-2 rounded-lg">
                            <div className="flex flex-col truncate max-w-[80%]">
                              <span className="text-xs font-bold text-white font-mono">{k}</span>
                              <span className="text-[10px] text-muted-foreground truncate font-mono">{v}</span>
                            </div>
                            <button
                              onClick={() => removeVideoFolder(k)}
                              className="p-1 hover:text-rose-400"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </>
              )}

            </div>

            {/* Right Column: Timeline segments (or raw JSON editor) */}
            <div className="xl:col-span-2 space-y-6">
              {isJsonMode ? (
                /* RAW JSON EDITOR PANEL */
                <div className="glass-panel p-6 lg:p-8 space-y-5 h-full min-h-[500px] flex flex-col">
                  <h3 className="text-base font-bold text-white flex items-center gap-2.5">
                    <FileJson className="w-5 h-5 text-amber-400" />
                    Cấu hình JSON thô (config_data)
                  </h3>
                  
                  <textarea
                    value={jsonText}
                    onChange={(e) => setJsonText(e.target.value)}
                    rows={20}
                    className="flex-1 w-full bg-black/40 border border-white/10 rounded-xl p-4 font-mono text-xs text-white/95 focus:outline-none focus:ring-1 focus:ring-primary custom-scrollbar resize-none"
                    placeholder="Dán cấu hình config_data JSON ở đây..."
                  />
                  <div className="text-[10px] text-muted-foreground italic flex items-center justify-between">
                    <span>* Vui lòng đảm bảo cấu trúc JSON hợp lệ trước khi gửi.</span>
                    <button
                      onClick={() => {
                        try {
                          const pretty = JSON.stringify(JSON.parse(jsonText), null, 2);
                          setJsonText(pretty);
                        } catch (e) {
                          alert("JSON không hợp lệ để định dạng đẹp.");
                        }
                      }}
                      className="text-primary hover:underline"
                    >
                      Định dạng đẹp JSON
                    </button>
                  </div>
                </div>
              ) : (
                /* INTERACTIVE TIMELINE SCRIPT PANEL */
                <div className="glass-panel p-6 lg:p-8 space-y-6">
                  <div className="flex items-center justify-between border-b border-white/5 pb-4">
                    <h3 className="text-base font-bold text-white flex items-center gap-2.5">
                      <Film className="w-5 h-5 text-violet-400" />
                      Kịch bản phân cảnh (Timeline Script)
                    </h3>
                    <button
                      onClick={addSegment}
                      className="px-4 py-2 bg-primary/20 hover:bg-primary/30 text-primary border border-primary/30 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5"
                    >
                      <Plus className="w-4 h-4" /> Thêm Phân Cảnh
                    </button>
                  </div>

                  <div className="space-y-4 max-h-[600px] overflow-y-auto custom-scrollbar pr-2">
                    {segments.length === 0 ? (
                      <div className="flex flex-col items-center justify-center p-12 text-muted-foreground/60 border border-dashed border-white/10 rounded-2xl gap-2">
                        <Clock className="w-8 h-8 text-muted-foreground/30 animate-pulse" />
                        Ttimeline rỗng. Hãy bấm "Thêm Phân Cảnh" để bắt đầu thiết kế kịch bản.
                      </div>
                    ) : (
                      segments.map((seg, idx) => (
                        <div key={idx} className="bg-white/[0.015] border border-white/5 p-4 rounded-xl space-y-4 relative group/segment">
                          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 pb-2">
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-extrabold text-primary font-mono bg-primary/10 px-2 py-0.5 rounded">
                                #{idx + 1}
                              </span>
                              <input
                                type="text"
                                value={seg.segment}
                                onChange={(e) => updateSegment(idx, { segment: e.target.value })}
                                className="bg-transparent border-b border-transparent focus:border-white/20 text-xs font-bold text-white focus:outline-none font-mono"
                                placeholder="Tên phân cảnh..."
                              />
                            </div>
                            
                            <div className="flex items-center gap-4">
                              <div className="flex items-center gap-1 text-[11px] text-muted-foreground font-mono">
                                <span>Time (s):</span>
                                <input
                                  type="number"
                                  value={seg.time_start}
                                  onChange={(e) => updateSegment(idx, { time_start: parseFloat(e.target.value) || 0 })}
                                  className="w-12 h-6 bg-white/5 border border-white/10 rounded px-1 text-center text-white"
                                  step="0.5"
                                />
                                <span>to</span>
                                <input
                                  type="number"
                                  value={seg.time_end}
                                  onChange={(e) => updateSegment(idx, { time_end: parseFloat(e.target.value) || 0 })}
                                  className="w-12 h-6 bg-white/5 border border-white/10 rounded px-1 text-center text-white"
                                  step="0.5"
                                />
                              </div>
                              
                              <button
                                onClick={() => removeSegment(idx)}
                                className="p-1 hover:text-rose-400 opacity-60 hover:opacity-100 transition-opacity"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-2">
                              <label className="text-[10px] font-semibold text-muted-foreground">Nguồn Video (video_source)</label>
                              <input
                                type="text"
                                value={seg.video_source}
                                onChange={(e) => updateSegment(idx, { video_source: e.target.value })}
                                placeholder="e.g. hook"
                                className="flex h-9 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-xs text-white font-mono"
                              />
                            </div>

                            <div className="space-y-2">
                              <label className="text-[10px] font-semibold text-muted-foreground">Hiệu ứng chuyển cảnh (Transition)</label>
                              <input
                                type="text"
                                value={seg.transition}
                                onChange={(e) => updateSegment(idx, { transition: e.target.value })}
                                placeholder="e.g. crossfade"
                                className="flex h-9 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-xs text-white"
                              />
                            </div>

                            <div className="md:col-span-2 space-y-2">
                              <label className="text-[10px] font-semibold text-muted-foreground">Phụ đề On-Screen (Text Overlay)</label>
                              <input
                                type="text"
                                value={seg.text_overlay}
                                onChange={(e) => updateSegment(idx, { text_overlay: e.target.value })}
                                placeholder="Nhập text chạy hiển thị trên màn hình phân cảnh này..."
                                className="flex h-9 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-xs text-white"
                              />
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

          </div>

          {/* Action Footer */}
          <div className="flex justify-end pt-6 border-t border-white/10">
            <Button
              onClick={handleSubmit}
              isLoading={loading}
              disabled={isJsonMode ? !jsonText : false}
              className="glowing-button px-10 py-4.5 rounded-xl font-bold shadow-[0_0_30px_rgba(124,58,237,0.5)] flex items-center gap-2.5 text-sm hover:scale-[1.02] active:scale-[0.98] transition-all"
            >
              {!loading && <Send className="w-4.5 h-4.5" />}
              {loading ? statusMessage || "Đang xử lý..." : "Khởi tạo Draft CapCut"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
