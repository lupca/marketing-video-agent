import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { CheckCircle2, Music, Film, Zap, Send, AlertCircle, Copy } from "lucide-react";
import api from "../lib/api";
import { cn } from "../lib/utils";
import { useProjects } from "../hooks/useProjects";
import { useAssets } from "../hooks/useAssets";
import type { Segment, UploadedFile } from "../components/features/review/types";
import { ProjectAudioStep } from "../components/features/review/ProjectAudioStep";
import { SegmentEditorStep } from "../components/features/review/SegmentEditorStep";
import { RenderSettingsStep } from "../components/features/review/RenderSettingsStep";
import { ReviewSubmitStep } from "../components/features/review/ReviewSubmitStep";
import { JobCreationLayout } from "../components/ui/JobCreationLayout";
import { JobActionButtons } from "../components/ui/JobActionButtons";
import { useAIDraft } from "../hooks/useAIDraft";
import { AIDraftPanel } from "../components/ui/AIDraftPanel";

const STEPS = [
  { id: 1, name: "Âm thanh & Dự án", icon: Music },
  { id: 2, name: "Phân cảnh Video", icon: Film },
  { id: 3, name: "Cài đặt Render", icon: Zap },
  { id: 4, name: "Xem lại & Gửi", icon: Send },
];

export default function CreateReviewJob() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const cloneJobId = searchParams.get("clone");
  const [step, setStep] = useState(1);
  const [cloneLoading, setCloneLoading] = useState(!!cloneJobId);
  const [tmcpContext, setTmcpContext] = useState<any>(null);

  // Raw job data for toggle
  const [rawJob, setRawJob] = useState<any>(null);
  const { hasDrafts, activeMode, setActiveMode, aiMetadata } = useAIDraft(rawJob);

  // Custom Hooks
  const { projects, createProject } = useProjects();
  const { uploadAsset } = useAssets();

  // Step 1: Project & Audio
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [newProjectName, setNewProjectName] = useState("");
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [voiceover, setVoiceover] = useState<UploadedFile | null>(null);
  const [script, setScript] = useState<UploadedFile | null>(null);
  const [bgm, setBgm] = useState<UploadedFile | null>(null);
  const [language, setLanguage] = useState("vi");

  useEffect(() => {
    if (projects.length > 0 && !selectedProjectId) setSelectedProjectId(projects[0].id);
    if (projects.length === 0) setIsCreatingProject(true);
  }, [projects, selectedProjectId]);

  // Step 2: Segments
  const [segments, setSegments] = useState<Segment[]>([
    {
      name: "01_hook", label: "🎯 Hook", timeStart: 0, timeEnd: 5,
      clips: [], textOverlay: "", highlightWords: "",
      effects: ["camera_shake"], pacingMin: 0.5, pacingMax: 1.2,
    }
  ]);

  // Step 3: Render Settings
  const [autoSubtitle, setAutoSubtitle] = useState(true);
  const [fontSize, setFontSize] = useState(80);
  const [textColor, setTextColor] = useState("yellow");
  const [priority, setPriority] = useState(0);

  // UI
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState("");

  const applyConfig = (cfg: any) => {
    if (!cfg) return;

    // Extract and set tmcp_context
    if (cfg.metadata?.tmcp_context) {
      setTmcpContext(cfg.metadata.tmcp_context);
    }

    // Pre-fill audio assets
    if (cfg.assets?.audio) {
      const audio = cfg.assets.audio;
      if (audio.voiceover_path) {
        setVoiceover({
          id: null, s3_url: audio.voiceover_path, uploading: false, progress: 0,
          asset: { id: "", s3_url: audio.voiceover_path, file_name: audio.voiceover_path.split("/").pop() || "voiceover", file_size_bytes: 0, asset_type: "voiceover", mime_type: "audio/mpeg", created_at: "" },
        });
      } else {
        setVoiceover(null);
      }
      if (audio.voiceover_script) {
        setScript({
          id: null, s3_url: audio.voiceover_script, uploading: false, progress: 0,
          asset: { id: "", s3_url: audio.voiceover_script, file_name: audio.voiceover_script.split("/").pop() || "script", file_size_bytes: 0, asset_type: "script", mime_type: "text/plain", created_at: "" },
        });
      } else {
        setScript(null);
      }
      if (audio.voiceover_lang) setLanguage(audio.voiceover_lang);
      if (audio.bgm_path) {
        setBgm({
          id: null, s3_url: audio.bgm_path, uploading: false, progress: 0,
          asset: { id: "", s3_url: audio.bgm_path, file_name: audio.bgm_path.split("/").pop() || "bgm", file_size_bytes: 0, asset_type: "bgm", mime_type: "audio/mpeg", created_at: "" },
        });
      } else {
        setBgm(null);
      }
    }

    // Pre-fill segments from timeline_script
    if (cfg.timeline_script && Array.isArray(cfg.timeline_script)) {
      const clonedSegments: Segment[] = cfg.timeline_script.map((ts: any) => ({
        name: ts.segment || ts.video_source || "segment",
        label: ts.segment || "Segment",
        timeStart: ts.time_range?.[0] || 0,
        timeEnd: ts.time_range?.[1] || 5,
        clips: [], // Clips need to be re-selected
        textOverlay: ts.text_overlay || "",
        highlightWords: (ts.highlight_words || []).join(", "),
        effects: ts.visual_effects || [],
        pacingMin: ts.pacing?.min_clip_duration || 0.5,
        pacingMax: ts.pacing?.max_clip_duration || 1.2,
      }));
      setSegments(clonedSegments);
    }

    // Pre-fill render settings
    if (cfg.render_settings) {
      const rs = cfg.render_settings;
      if (rs.auto_subtitle !== undefined) setAutoSubtitle(rs.auto_subtitle);
      if (rs.text_style?.font_size) setFontSize(rs.text_style.font_size);
      if (rs.text_style?.color) setTextColor(rs.text_style.color);
    }
  };

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

        setRawJob(job);

        // Pre-fill project
        if (job.project_id) {
          setSelectedProjectId(job.project_id);
          setIsCreatingProject(false);
        }
        if (job.priority !== undefined) setPriority(job.priority);

        if (job.draft_variants) {
          applyConfig(job.draft_variants.original);
        } else {
          applyConfig(job.config_data || {});
        }
      } catch (err) {
        console.error("Failed to load cloned job:", err);
      } finally {
        if (!cancelled) setCloneLoading(false);
      }
    };
    loadClone();
    return () => { cancelled = true; };
  }, [cloneJobId]);

  const handleModeToggle = (mode: "original" | "viral_optimized") => {
    setActiveMode(mode);
    if (rawJob && rawJob.draft_variants) {
      applyConfig(rawJob.draft_variants[mode]);
    }
  };

  const handleSubmit = async () => {
    if (!isCreatingProject && !selectedProjectId) return setError("Vui lòng chọn dự án");
    if (isCreatingProject && !newProjectName.trim()) return setError("Vui lòng nhập tên dự án mới");
    if (!voiceover) return setError("Vui lòng chọn file voiceover");
    if (!script) return setError("Vui lòng chọn file kịch bản");

    setLoading(true);
    setError(null);

    try {
      let targetProjectId = selectedProjectId;
      if (isCreatingProject && newProjectName.trim()) {
        setUploadStatus("Đang tạo dự án...");
        const proj = await createProject(newProjectName.trim());
        targetProjectId = proj.id;
      }

      const getAssetRef = async (uf: UploadedFile, type: string) => {
        if (uf.file) return await uploadAsset(uf.file, type);
        return { id: uf.id!, s3_url: uf.s3_url! };
      };

      setUploadStatus("Đang xử lý voiceover...");
      const voRes = await getAssetRef(voiceover, "voiceover");
      
      setUploadStatus("Đang xử lý kịch bản...");
      const scriptRes = await getAssetRef(script, "script");
      
      let bgmUrl = "";
      let bgmId = "";
      if (bgm) {
        setUploadStatus("Đang xử lý nhạc nền...");
        const res = await getAssetRef(bgm, "bgm");
        bgmUrl = res.s3_url;
        bgmId = res.id;
      }

      const allAssetIds = [voRes.id, scriptRes.id];
      if (bgmId) allAssetIds.push(bgmId);

      const videoFolders: Record<string, string> = {};
      const timelineScript: any[] = [];

      for (let i = 0; i < segments.length; i++) {
        const seg = segments[i];
        setUploadStatus(`Đang upload clips phân cảnh ${i + 1}/${segments.length}...`);

        for (const clip of seg.clips) {
          let resId = clip.id;
          if (clip.file) {
            const res = await uploadAsset(clip.file, "segment_clip", seg.name);
            resId = res.id;
          }
          if (resId) allAssetIds.push(resId);
        }

        const folderPrefix = `s3://videos/assets/segments/${seg.name}/`;
        videoFolders[seg.name] = folderPrefix;

        timelineScript.push({
          segment: seg.name,
          time_range: [seg.timeStart, seg.timeEnd],
          video_source: seg.name,
          text_overlay: seg.textOverlay || undefined,
          highlight_words: seg.highlightWords ? seg.highlightWords.split(",").map(w => w.trim()).filter(Boolean) : [],
          visual_effects: seg.effects,
          pacing: { min_clip_duration: seg.pacingMin, max_clip_duration: seg.pacingMax }
        });
      }

      setUploadStatus("Đang tạo job...");
      const configData = {
        metadata: {
          project_id: targetProjectId,
          ...(tmcpContext ? { tmcp_context: tmcpContext } : {})
        },
        assets: {
          logo: { width: 160, x: 48, y: 160, opacity: 0.9 },
          audio: {
            voiceover_path: voRes.s3_url,
            voiceover_script: scriptRes.s3_url,
            voiceover_lang: language,
            whisper_device: "cpu",
            ...(bgmUrl ? { bgm_path: bgmUrl } : {}),
          },
          video_folders: videoFolders,
        },
        timeline_script: timelineScript,
        render_settings: {
          resolution: [1080, 1920],
          auto_subtitle: autoSubtitle,
          pacing: { min_clip_duration: 1.2, max_clip_duration: 1.8 },
          text_style: { position: "center", font_size: fontSize, color: textColor, high_contrast_outline: true },
        },
      };

      await api.post(`/api/jobs`, {
        job_type: "review", project_id: targetProjectId, priority, config_data: configData, asset_ids: allAssetIds
      });

      navigate("/");
    } catch (err: any) {
      console.error(err);
      setError(err?.response?.data?.detail || err.message || "Failed to create job");
    } finally {
      setLoading(false);
      setUploadStatus("");
    }
  };

  const handleCapCutSubmit = async () => {
    if (!isCreatingProject && !selectedProjectId) return setError("Vui lòng chọn dự án");
    if (isCreatingProject && !newProjectName.trim()) return setError("Vui lòng nhập tên dự án mới");
    if (!voiceover) return setError("Vui lòng chọn file voiceover");
    if (!script) return setError("Vui lòng chọn file kịch bản");

    setLoading(true);
    setError(null);

    try {
      let targetProjectId = selectedProjectId;
      if (isCreatingProject && newProjectName.trim()) {
        setUploadStatus("Đang tạo dự án...");
        const proj = await createProject(newProjectName.trim());
        targetProjectId = proj.id;
      }

      const getAssetRef = async (uf: UploadedFile, type: string) => {
        if (uf.file) return await uploadAsset(uf.file, type);
        return { id: uf.id!, s3_url: uf.s3_url! };
      };

      setUploadStatus("Đang xử lý voiceover...");
      const voRes = await getAssetRef(voiceover, "voiceover");
      
      setUploadStatus("Đang xử lý kịch bản...");
      const scriptRes = await getAssetRef(script, "script");
      
      let bgmUrl = "";
      let bgmId = "";
      if (bgm) {
        setUploadStatus("Đang xử lý nhạc nền...");
        const res = await getAssetRef(bgm, "bgm");
        bgmUrl = res.s3_url;
        bgmId = res.id;
      }

      const allAssetIds = [voRes.id, scriptRes.id];
      if (bgmId) allAssetIds.push(bgmId);

      const videoFolders: Record<string, string> = {};
      const timelineScript: any[] = [];

      for (let i = 0; i < segments.length; i++) {
        const seg = segments[i];
        setUploadStatus(`Đang upload clips phân cảnh ${i + 1}/${segments.length}...`);

        for (const clip of seg.clips) {
          let resId = clip.id;
          if (clip.file) {
            const res = await uploadAsset(clip.file, "segment_clip", seg.name);
            resId = res.id;
          }
          if (resId) allAssetIds.push(resId);
        }

        const folderPrefix = `s3://videos/assets/segments/${seg.name}/`;
        videoFolders[seg.name] = folderPrefix;

        timelineScript.push({
          segment: seg.name,
          time_range: [seg.timeStart, seg.timeEnd],
          video_source: seg.name,
          text_overlay: seg.textOverlay || undefined,
          highlight_words: seg.highlightWords ? seg.highlightWords.split(",").map(w => w.trim()).filter(Boolean) : [],
          visual_effects: seg.effects,
          pacing: { min_clip_duration: seg.pacingMin, max_clip_duration: seg.pacingMax }
        });
      }

      setUploadStatus("Đang lưu dữ liệu...");
      const configData = {
        metadata: {
          project_id: targetProjectId,
          ...(tmcpContext ? { tmcp_context: tmcpContext } : {})
        },
        assets: {
          logo: { width: 160, x: 48, y: 160, opacity: 0.9 },
          audio: {
            voiceover_path: voRes.s3_url,
            voiceover_script: scriptRes.s3_url,
            voiceover_lang: language,
            whisper_device: "cpu",
            ...(bgmUrl ? { bgm_path: bgmUrl } : {}),
          },
          video_folders: videoFolders,
        },
        timeline_script: timelineScript,
        render_settings: {
          resolution: [1080, 1920],
          auto_subtitle: autoSubtitle,
          pacing: { min_clip_duration: 1.2, max_clip_duration: 1.8 },
          text_style: { position: "center", font_size: fontSize, color: textColor, high_contrast_outline: true },
        },
      };

      // 1. Bypass auto-deletion of draft job by removing delete_draft parameter from browser URL
      const url = new URL(window.location.href);
      url.searchParams.delete('delete_draft');
      window.history.replaceState({}, '', url.toString());

      // 2. Save the updated manual changes into the original review job as DRAFT
      if (cloneJobId) {
        await api.patch(`/api/jobs/${cloneJobId}`, {
          config_data: configData,
          status: "DRAFT"
        });
      }

      // 3. Create a brand new CapCut Job with the exact same updated configuration!
      await api.post(`/api/jobs`, {
        job_type: "capcut",
        project_id: targetProjectId,
        priority,
        config_data: configData,
        asset_ids: allAssetIds
      });

      navigate("/");
    } catch (err: any) {
      console.error(err);
      setError(err?.response?.data?.detail || err.message || "Failed to create CapCut job");
    } finally {
      setLoading(false);
      setUploadStatus("");
    }
  };

  const handleSaveDraft = async () => {
    if (!cloneJobId) {
      setError("Không thể lưu nháp cho job mới. Chức năng lưu nháp chỉ áp dụng cho job được tạo từ AI Leader hoặc chỉnh sửa Draft.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      let targetProjectId = selectedProjectId;
      if (isCreatingProject && newProjectName.trim()) {
        setUploadStatus("Đang tạo dự án...");
        const proj = await createProject(newProjectName.trim());
        targetProjectId = proj.id;
      }

      const getAssetRefDefensive = async (uf: UploadedFile | null, type: string) => {
        if (!uf) return { id: "", s3_url: "" };
        if (uf.file) {
          const res = await uploadAsset(uf.file, type);
          return { id: res.id, s3_url: res.s3_url };
        }
        return { id: uf.id || "", s3_url: uf.s3_url || "" };
      };

      setUploadStatus("Đang xử lý voiceover...");
      const voRes = await getAssetRefDefensive(voiceover, "voiceover");
      
      setUploadStatus("Đang xử lý kịch bản...");
      const scriptRes = await getAssetRefDefensive(script, "script");
      
      let bgmUrl = "";
      let bgmId = "";
      if (bgm) {
        setUploadStatus("Đang xử lý nhạc nền...");
        const res = await getAssetRefDefensive(bgm, "bgm");
        bgmUrl = res.s3_url;
        bgmId = res.id;
      }

      const allAssetIds: string[] = [];
      if (voRes.id) allAssetIds.push(voRes.id);
      if (scriptRes.id) allAssetIds.push(scriptRes.id);
      if (bgmId) allAssetIds.push(bgmId);

      const videoFolders: Record<string, string> = {};
      const timelineScript: any[] = [];

      for (let i = 0; i < segments.length; i++) {
        const seg = segments[i];
        setUploadStatus(`Đang upload clips phân cảnh ${i + 1}/${segments.length}...`);

        for (const clip of seg.clips) {
          let resId = clip.id;
          if (clip.file) {
            const res = await uploadAsset(clip.file, "segment_clip", seg.name);
            resId = res.id;
          }
          if (resId) allAssetIds.push(resId);
        }

        const folderPrefix = `s3://videos/assets/segments/${seg.name}/`;
        videoFolders[seg.name] = folderPrefix;

        timelineScript.push({
          segment: seg.name,
          time_range: [seg.timeStart, seg.timeEnd],
          video_source: seg.name,
          text_overlay: seg.textOverlay || undefined,
          highlight_words: seg.highlightWords ? seg.highlightWords.split(",").map(w => w.trim()).filter(Boolean) : [],
          visual_effects: seg.effects,
          pacing: { min_clip_duration: seg.pacingMin, max_clip_duration: seg.pacingMax }
        });
      }

      setUploadStatus("Đang lưu bản nháp...");
      const configData = {
        metadata: {
          project_id: targetProjectId || undefined,
          ...(tmcpContext ? { tmcp_context: tmcpContext } : {})
        },
        assets: {
          logo: { width: 160, x: 48, y: 160, opacity: 0.9 },
          audio: {
            voiceover_path: voRes.s3_url || "",
            voiceover_script: scriptRes.s3_url || "",
            voiceover_lang: language,
            whisper_device: "cpu",
            ...(bgmUrl ? { bgm_path: bgmUrl } : {}),
          },
          video_folders: videoFolders,
        },
        timeline_script: timelineScript,
        render_settings: {
          resolution: [1080, 1920],
          auto_subtitle: autoSubtitle,
          pacing: { min_clip_duration: 1.2, max_clip_duration: 1.8 },
          text_style: { position: "center", font_size: fontSize, color: textColor, high_contrast_outline: true },
        },
      };

      await api.patch(`/api/jobs/${cloneJobId}`, {
        project_id: targetProjectId || null,
        priority,
        config_data: configData,
        asset_ids: allAssetIds,
        status: "DRAFT"
      });

    } catch (err: any) {
      console.error("Lỗi khi lưu nháp:", err);
      setError(err?.response?.data?.detail || err.message || "Không thể lưu nháp");
      throw err;
    } finally {
      setLoading(false);
      setUploadStatus("");
    }
  };

  const canGoStep2 = (isCreatingProject ? newProjectName.trim() : selectedProjectId) && voiceover && script;
  const canGoStep3 = segments.length > 0 && segments.every(s => s.clips.length > 0);

  return (
    <JobCreationLayout jobType="review" tmcpContext={tmcpContext}>
      <div className="max-w-5xl mx-auto p-8 lg:p-12 space-y-10">
        <div className="space-y-2">
          <h2 className="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60">
            Tạo Video Review
          </h2>
          <p className="text-muted-foreground text-lg">
            Upload nguyên liệu, lên kịch bản phân cảnh, và dựng video tự động theo phong cách viral.
          </p>
        </div>

        {/* AI Draft Selection Panel */}
        <AIDraftPanel
          hasDrafts={hasDrafts}
          activeMode={activeMode}
          onToggle={handleModeToggle}
          metadata={aiMetadata}
        />

        {cloneJobId && (
          <div className="glass-panel p-4 flex items-center gap-3 bg-amber-500/10 border border-amber-500/20 rounded-xl animate-in fade-in">
            <Copy className="w-5 h-5 text-amber-400 shrink-0" />
            <div>
              <p className="text-sm font-medium text-amber-300">Bản sao từ Job #{cloneJobId}</p>
              <p className="text-xs text-amber-400/70">Chỉnh sửa nội dung bên dưới rồi gửi để tạo video mới.</p>
            </div>
          </div>
        )}

        {cloneLoading ? (
          <div className="glass-panel p-16 flex flex-col items-center justify-center gap-4 text-muted-foreground">
            <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
            <p>Đang tải dữ liệu từ Job #{cloneJobId}...</p>
          </div>
        ) : (

        <div className="glass-panel p-6 lg:p-10 flex flex-col space-y-10">
          <div className="flex items-center justify-between w-full border-b border-white/10 pb-8">
            {STEPS.map((s, idx) => (
              <div key={s.id} className="flex items-center">
                <div className={cn("flex items-center gap-3 transition-all duration-300", step >= s.id ? "text-primary" : "text-muted-foreground")}>
                  <div className={cn(
                    "flex items-center justify-center w-10 h-10 rounded-full border-2 transition-all duration-300",
                    step > s.id ? "bg-primary border-primary text-white" :
                      step === s.id ? "border-primary bg-primary/20 shadow-[0_0_15px_rgba(124,58,237,0.4)]" : "border-muted-foreground/30"
                  )}>
                    {step > s.id ? <CheckCircle2 className="w-5 h-5" /> : <s.icon className="w-5 h-5" />}
                  </div>
                  <span className={cn("font-medium text-sm hidden lg:block", step >= s.id ? "text-white" : "text-muted-foreground")}>{s.name}</span>
                </div>
                {idx < STEPS.length - 1 && <div className="w-8 lg:w-16 h-px bg-white/10 mx-3"></div>}
              </div>
            ))}
          </div>

          {error && (
            <div className="p-4 bg-red-500/10 text-red-400 rounded-xl border border-red-500/20 flex items-start gap-3 animate-in fade-in">
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
              <p>{error}</p>
            </div>
          )}

          {step === 1 && (
            <ProjectAudioStep
              projects={projects}
              selectedProjectId={selectedProjectId}
              setSelectedProjectId={setSelectedProjectId}
              isCreatingProject={isCreatingProject}
              setIsCreatingProject={setIsCreatingProject}
              newProjectName={newProjectName}
              setNewProjectName={setNewProjectName}
              voiceover={voiceover} setVoiceover={setVoiceover}
              script={script} setScript={setScript}
              bgm={bgm} setBgm={setBgm}
              language={language} setLanguage={setLanguage}
            />
          )}

          {step === 2 && (
            <SegmentEditorStep
              segments={segments} setSegments={setSegments}
            />
          )}

          {step === 3 && (
            <RenderSettingsStep
              autoSubtitle={autoSubtitle} setAutoSubtitle={setAutoSubtitle}
              priority={priority} setPriority={setPriority}
              fontSize={fontSize} setFontSize={setFontSize}
              textColor={textColor} setTextColor={setTextColor}
            />
          )}

          {step === 4 && (
            <ReviewSubmitStep
              projects={projects} selectedProjectId={selectedProjectId}
              isCreatingProject={isCreatingProject} newProjectName={newProjectName}
              voiceover={voiceover} script={script} bgm={bgm} language={language}
              segments={segments} autoSubtitle={autoSubtitle} priority={priority}
            />
          )}

          <JobActionButtons
            currentStep={step}
            totalSteps={4}
            loading={loading}
            uploadStatus={uploadStatus}
            isDraft={!!cloneJobId}
            canGoNext={step === 1 ? !!canGoStep2 : step === 2 ? canGoStep3 : true}
            onPrev={() => setStep(prev => prev - 1)}
            onNext={() => setStep(prev => prev + 1)}
            onSubmit={handleSubmit}
            onCapCutSubmit={handleCapCutSubmit}
            onSaveDraft={cloneJobId ? handleSaveDraft : undefined}
          />
        </div>
        )}
      </div>
    </JobCreationLayout>
  );
}
