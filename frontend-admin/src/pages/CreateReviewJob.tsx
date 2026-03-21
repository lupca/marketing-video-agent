import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, Music, Film, Zap, Send, AlertCircle } from "lucide-react";
import api from "../lib/api";
import { cn } from "../lib/utils";
import { useProjects } from "../hooks/useProjects";
import { useAssets } from "../hooks/useAssets";
import type { Segment, UploadedFile } from "../components/features/review/types";
import { ProjectAudioStep } from "../components/features/review/ProjectAudioStep";
import { SegmentEditorStep } from "../components/features/review/SegmentEditorStep";
import { RenderSettingsStep } from "../components/features/review/RenderSettingsStep";
import { ReviewSubmitStep } from "../components/features/review/ReviewSubmitStep";

const STEPS = [
  { id: 1, name: "Âm thanh & Dự án", icon: Music },
  { id: 2, name: "Phân cảnh Video", icon: Film },
  { id: 3, name: "Cài đặt Render", icon: Zap },
  { id: 4, name: "Xem lại & Gửi", icon: Send },
];

export default function CreateReviewJob() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);

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

      setUploadStatus("Đang upload voiceover...");
      const voRes = await uploadAsset(voiceover.file, "voiceover");
      
      setUploadStatus("Đang upload kịch bản...");
      const scriptRes = await uploadAsset(script.file, "script");
      
      let bgmUrl = "";
      let bgmId = "";
      if (bgm) {
        setUploadStatus("Đang upload nhạc nền...");
        const res = await uploadAsset(bgm.file, "bgm");
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
          const res = await uploadAsset(clip.file, "segment_clip", seg.name);
          allAssetIds.push(res.id);
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
        metadata: { project_id: targetProjectId },
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

  const canGoStep2 = (isCreatingProject ? newProjectName.trim() : selectedProjectId) && voiceover && script;
  const canGoStep3 = segments.length > 0 && segments.every(s => s.clips.length > 0);

  return (
    <div className="max-w-5xl mx-auto p-8 lg:p-12 space-y-10">
      <div className="space-y-2">
        <h2 className="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60">
          Tạo Video Review
        </h2>
        <p className="text-muted-foreground text-lg">
          Upload nguyên liệu, lên kịch bản phân cảnh, và dựng video tự động theo phong cách viral.
        </p>
      </div>

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
            onNext={() => setStep(2)}
            canGoNext={!!canGoStep2}
          />
        )}

        {step === 2 && (
          <SegmentEditorStep
            segments={segments} setSegments={setSegments}
            onPrev={() => setStep(1)}
            onNext={() => setStep(3)}
            canGoNext={canGoStep3}
          />
        )}

        {step === 3 && (
          <RenderSettingsStep
            autoSubtitle={autoSubtitle} setAutoSubtitle={setAutoSubtitle}
            priority={priority} setPriority={setPriority}
            fontSize={fontSize} setFontSize={setFontSize}
            textColor={textColor} setTextColor={setTextColor}
            onPrev={() => setStep(2)}
            onNext={() => setStep(4)}
          />
        )}

        {step === 4 && (
          <ReviewSubmitStep
            projects={projects} selectedProjectId={selectedProjectId}
            isCreatingProject={isCreatingProject} newProjectName={newProjectName}
            voiceover={voiceover} script={script} bgm={bgm} language={language}
            segments={segments} autoSubtitle={autoSubtitle} priority={priority}
            loading={loading} uploadStatus={uploadStatus}
            onPrev={() => setStep(3)} onSubmit={handleSubmit}
          />
        )}
      </div>
    </div>
  );
}
