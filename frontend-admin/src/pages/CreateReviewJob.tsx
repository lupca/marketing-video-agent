import { useState, useRef, useEffect } from "react"
import axios from "axios"
import { useNavigate } from "react-router-dom"
import api from "../lib/api"
import {
  Loader2, ChevronRight, CheckCircle2, Upload, Music, FileText,
  Video, Plus, Trash2, Send, Sparkles, AlertCircle, Mic, Film, Zap, Folder
} from "lucide-react"
import { cn } from "../lib/utils"

/* ─── Types ──────────────────────────────────────────────────── */

interface UploadedFile {
  file: File
  id: string | null
  s3_url: string | null
  uploading: boolean
  progress: number
}

interface Project {
  id: string
  name: string
}

interface Segment {
  name: string
  label: string
  timeStart: number
  timeEnd: number
  clips: UploadedFile[]
  textOverlay: string
  highlightWords: string
  effects: string[]
  pacingMin: number
  pacingMax: number
}

/* ─── Constants ──────────────────────────────────────────────── */

const SEGMENT_PRESETS = [
  { name: "01_hook", label: "🎯 Hook — Thu hút trong 3s đầu" },
  { name: "02_pain_point", label: "😤 Pain Point — Đánh vào nỗi đau" },
  { name: "03_reveal", label: "✨ Reveal — Giải pháp/Sản phẩm" },
  { name: "04_educate", label: "📚 Educate — Kiến thức/Chi tiết" },
  { name: "05_proof", label: "🏆 Proof — Bằng chứng" },
  { name: "06_cta", label: "📢 CTA — Kêu gọi hành động" },
]

const EFFECTS_OPTIONS = [
  { value: "camera_shake", label: "📳 Camera Shake" },
  { value: "snap_zoom", label: "🔍 Snap Zoom" },
  { value: "slow_motion_0.5x", label: "🐌 Slow Motion (0.5x)" },
]

const STEPS = [
  { id: 1, name: "Âm thanh & Dự án", icon: Music },
  { id: 2, name: "Phân cảnh Video", icon: Film },
  { id: 3, name: "Cài đặt Render", icon: Zap },
  { id: 4, name: "Xem lại & Gửi", icon: Send },
]

/* ─── Component ──────────────────────────────────────────────── */

export default function CreateReviewJob() {
  const navigate = useNavigate()
  const [step, setStep] = useState(1)

  // Step 1: Project & Audio
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState("")
  const [newProjectName, setNewProjectName] = useState("")
  const [isCreatingProject, setIsCreatingProject] = useState(false)
  const [voiceover, setVoiceover] = useState<UploadedFile | null>(null)
  const [script, setScript] = useState<UploadedFile | null>(null)
  const [bgm, setBgm] = useState<UploadedFile | null>(null)
  const [language, setLanguage] = useState("vi")

  // Load projects on mount
  useEffect(() => {
    api.get("/api/projects").then(res => {
      setProjects(res.data)
      if (res.data.length > 0) setSelectedProjectId(res.data[0].id)
      else setIsCreatingProject(true)
    }).catch(console.error)
  }, [])

  // Step 2: Segments
  const [segments, setSegments] = useState<Segment[]>([
    {
      name: "01_hook", label: "🎯 Hook", timeStart: 0, timeEnd: 5,
      clips: [], textOverlay: "", highlightWords: "",
      effects: ["camera_shake"], pacingMin: 0.5, pacingMax: 1.2,
    }
  ])

  // Step 3: Render Settings
  const [autoSubtitle, setAutoSubtitle] = useState(true)
  const [fontSize, setFontSize] = useState(80)
  const [textColor, setTextColor] = useState("yellow")
  const [priority, setPriority] = useState(0)

  // UI
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [uploadStatus, setUploadStatus] = useState("")

  /* ─── Upload a single file to the API ──────────────────────── */

  const uploadFile = async (
    file: File,
    assetType: string,
    segmentName?: string
  ): Promise<{s3_url: string, id: string}> => {
    const formData = new FormData()
    formData.append("file", file)
    formData.append("asset_type", assetType)
    if (segmentName) formData.append("segment_name", segmentName)

    const res = await api.post(`/api/assets/upload`, formData)
    return { s3_url: res.data.s3_url, id: res.data.id }
  }

  /* ─── Handle file selection for audio ──────────────────────── */

  const handleAudioFile = (
    file: File | undefined,
    setter: (f: UploadedFile | null) => void
  ) => {
    if (!file) return
    setter({ file, id: null, s3_url: null, uploading: false, progress: 0 })
  }

  /* ─── Handle clip files for a segment ──────────────────────── */

  const handleSegmentClips = (index: number, files: FileList | null) => {
    if (!files) return
    const newSegments = [...segments]
    const newClips: UploadedFile[] = Array.from(files).map(f => ({
      file: f, id: null, s3_url: null, uploading: false, progress: 0
    }))
    newSegments[index].clips = [...newSegments[index].clips, ...newClips]
    setSegments(newSegments)
  }

  /* ─── Add / Remove segment ─────────────────────────────────── */

  const addSegment = () => {
    const nextIdx = segments.length
    const preset = SEGMENT_PRESETS[nextIdx] || {
      name: `segment_${nextIdx + 1}`,
      label: `Segment ${nextIdx + 1}`
    }
    const lastEnd = segments.length > 0 ? segments[segments.length - 1].timeEnd : 0
    setSegments([...segments, {
      name: preset.name,
      label: preset.label,
      timeStart: lastEnd,
      timeEnd: lastEnd + 10,
      clips: [],
      textOverlay: "",
      highlightWords: "",
      effects: [],
      pacingMin: 1.0,
      pacingMax: 2.0,
    }])
  }

  const removeSegment = (idx: number) => {
    setSegments(segments.filter((_, i) => i !== idx))
  }

  const updateSegment = (idx: number, field: string, value: any) => {
    const updated = [...segments]
    ;(updated[idx] as any)[field] = value
    setSegments(updated)
  }

  const toggleEffect = (idx: number, effect: string) => {
    const updated = [...segments]
    const fx = updated[idx].effects
    if (fx.includes(effect)) {
      updated[idx].effects = fx.filter(e => e !== effect)
    } else {
      updated[idx].effects = [...fx, effect]
    }
    setSegments(updated)
  }

  /* ─── Submit: Upload all files then create job ─────────────── */

  const handleSubmit = async () => {
    if (!isCreatingProject && !selectedProjectId) return setError("Vui lòng chọn dự án")
    if (isCreatingProject && !newProjectName.trim()) return setError("Vui lòng nhập tên dự án mới")
    if (!voiceover) return setError("Vui lòng chọn file voiceover")
    if (!script) return setError("Vui lòng chọn file kịch bản")

    setLoading(true)
    setError(null)

    try {
      // 0. Create Project if needed
      let targetProjectId = selectedProjectId;
      if (isCreatingProject && newProjectName.trim()) {
        setUploadStatus("Đang tạo dự án...")
        const projRes = await api.post("/api/projects", { name: newProjectName.trim() })
        targetProjectId = projRes.data.id;
      }

      setUploadStatus("Đang upload voiceover...")
      const { s3_url: voUrl, id: voId } = await uploadFile(voiceover.file, "voiceover")
      
      setUploadStatus("Đang upload kịch bản...")
      const { s3_url: scriptUrl, id: scriptId } = await uploadFile(script.file, "script")
      
      let bgmUrl = ""
      let bgmId = ""
      if (bgm) {
        setUploadStatus("Đang upload nhạc nền...")
        const res = await uploadFile(bgm.file, "bgm")
        bgmUrl = res.s3_url
        bgmId = res.id
      }

      const allAssetIds = [voId, scriptId]
      if (bgmId) allAssetIds.push(bgmId)

      // 2. Upload segment clips
      const videoFolders: Record<string, string> = {}
      const timelineScript: any[] = []

      for (let i = 0; i < segments.length; i++) {
        const seg = segments[i]
        setUploadStatus(`Đang upload clips phân cảnh ${i + 1}/${segments.length}...`)

        // Upload each clip
        const clipUrls: string[] = []
        for (const clip of seg.clips) {
          const res = await uploadFile(clip.file, "segment_clip", seg.name)
          clipUrls.push(res.s3_url)
          allAssetIds.push(res.id)
        }

        // The s3 folder prefix for this segment
        // All clips are stored under assets/segments/{segment_name}/
        const folderPrefix = `s3://videos/assets/segments/${seg.name}/`
        videoFolders[seg.name] = folderPrefix

        timelineScript.push({
          segment: seg.name,
          time_range: [seg.timeStart, seg.timeEnd],
          video_source: seg.name,
          text_overlay: seg.textOverlay || undefined,
          highlight_words: seg.highlightWords
            ? seg.highlightWords.split(",").map(w => w.trim()).filter(Boolean)
            : [],
          visual_effects: seg.effects,
          pacing: {
            min_clip_duration: seg.pacingMin,
            max_clip_duration: seg.pacingMax,
          }
        })
      }

      // 3. Build config_data
      setUploadStatus("Đang tạo job...")
      const configData = {
        metadata: { project_id: targetProjectId },
        assets: {
          logo: { width: 160, x: 48, y: 160, opacity: 0.9 },
          audio: {
            voiceover_path: voUrl,
            voiceover_script: scriptUrl,
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
          text_style: {
            position: "center",
            font_size: fontSize,
            color: textColor,
            high_contrast_outline: true,
          },
        },
      }

      // 4. Create job
      await api.post(`/api/jobs`, {
        job_type: "review",
        project_id: targetProjectId,
        priority,
        config_data: configData,
        asset_ids: allAssetIds
      })

      navigate("/")
    } catch (err: any) {
      console.error(err)
      setError(err?.response?.data?.detail || err.message || "Failed to create job")
    } finally {
      setLoading(false)
      setUploadStatus("")
    }
  }

  /* ─── Validation helpers ───────────────────────────────────── */

  const canGoStep2 = (isCreatingProject ? newProjectName.trim() : selectedProjectId) && voiceover && script
  const canGoStep3 = segments.length > 0 && segments.every(s => s.clips.length > 0)

  /* ─── Render ───────────────────────────────────────────────── */

  return (
    <div className="max-w-5xl mx-auto p-8 lg:p-12 space-y-10">

      {/* Header */}
      <div className="space-y-2">
        <h2 className="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60">
          Tạo Video Review
        </h2>
        <p className="text-muted-foreground text-lg">
          Upload nguyên liệu, lên kịch bản phân cảnh, và dựng video tự động theo phong cách viral.
        </p>
      </div>

      <div className="glass-panel p-6 lg:p-10 flex flex-col space-y-10">

        {/* Stepper */}
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

        {/* ═══ STEP 1: Audio & Project ═══ */}
        {step === 1 && (
          <div className="space-y-8 animate-in fade-in slide-in-from-right-8 duration-500">
            {/* Project Selection / Creation */}
            <div className="space-y-4">
              <label className="text-sm font-semibold text-white/90 uppercase tracking-wider flex items-center gap-2">
                <Folder className="w-4 h-4 text-primary" /> Dự án
              </label>

              <div className="flex flex-col sm:flex-row gap-4">
                <button
                  type="button"
                  onClick={() => setIsCreatingProject(false)}
                  className={cn("flex-1 px-4 py-3 rounded-xl border flex items-center gap-2 justify-center transition-all", !isCreatingProject ? "bg-primary/20 border-primary text-white shadow-[0_0_15px_rgba(124,58,237,0.3)]" : "bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10")}
                >
                  <Folder className="w-4 h-4" /> Chọn dự án có sẵn
                </button>
                <button
                  type="button"
                  onClick={() => setIsCreatingProject(true)}
                  className={cn("flex-1 px-4 py-3 rounded-xl border flex items-center gap-2 justify-center transition-all", isCreatingProject ? "bg-primary/20 border-primary text-white shadow-[0_0_15px_rgba(124,58,237,0.3)]" : "bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10")}
                >
                  <Plus className="w-4 h-4" /> Tạo dự án mới
                </button>
              </div>

              {isCreatingProject ? (
                <div className="space-y-2 animate-in fade-in slide-in-from-top-2">
                  <input
                    type="text"
                    value={newProjectName}
                    onChange={e => setNewProjectName(e.target.value)}
                    placeholder="Tên dự án mới..."
                    className="flex h-12 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-base text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all placeholder:text-muted-foreground/50"
                  />
                </div>
              ) : (
                <div className="space-y-2 animate-in fade-in slide-in-from-top-2">
                  <select
                    value={selectedProjectId}
                    onChange={e => setSelectedProjectId(e.target.value)}
                    className="flex h-12 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-base text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all appearance-none"
                  >
                    {projects.length === 0 ? (
                      <option disabled value="" className="bg-[#1A1A24]">Bạn chưa có dự án nào</option>
                    ) : (
                      projects.map(p => (
                        <option key={p.id} value={p.id} className="bg-[#1A1A24]">{p.name}</option>
                      ))
                    )}
                  </select>
                </div>
              )}
            </div>

            {/* Audio Uploads */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Voiceover */}
              <FileDropzone
                label="Giọng đọc (Voiceover)"
                sublabel="MP3 — File thu âm chính"
                icon={<Mic className="w-6 h-6 text-primary" />}
                accept="audio/mpeg,audio/*"
                selectedFile={voiceover}
                onSelect={f => handleAudioFile(f, setVoiceover)}
                required
              />
              {/* Script */}
              <FileDropzone
                label="Kịch bản (Script)"
                sublabel="TXT — Nội dung đọc 100%"
                icon={<FileText className="w-6 h-6 text-indigo-400" />}
                accept=".txt,text/plain"
                selectedFile={script}
                onSelect={f => handleAudioFile(f, setScript)}
                required
              />
              {/* BGM */}
              <FileDropzone
                label="Nhạc nền (BGM)"
                sublabel="MP3 — Tùy chọn"
                icon={<Music className="w-6 h-6 text-cyan-400" />}
                accept="audio/mpeg,audio/*"
                selectedFile={bgm}
                onSelect={f => handleAudioFile(f, setBgm)}
              />
            </div>

            {/* Language */}
            <div className="flex items-center gap-4 bg-white/5 p-4 rounded-xl border border-white/10">
              <label className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Ngôn ngữ</label>
              <select
                value={language}
                onChange={e => setLanguage(e.target.value)}
                className="h-10 rounded-xl border border-white/10 bg-white/5 px-4 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 appearance-none"
              >
                <option value="vi" className="bg-[#1A1A24]">🇻🇳 Tiếng Việt</option>
                <option value="en" className="bg-[#1A1A24]">🇺🇸 English</option>
              </select>
            </div>

            <div className="flex justify-end pt-4">
              <button
                onClick={() => setStep(2)}
                disabled={!canGoStep2}
                className="glowing-button text-white px-8 py-3 rounded-xl font-medium flex items-center gap-2 disabled:opacity-50 disabled:shadow-none"
              >
                Tiếp tục <ChevronRight className="w-5 h-5" />
              </button>
            </div>
          </div>
        )}

        {/* ═══ STEP 2: Video Segments ═══ */}
        {step === 2 && (
          <div className="space-y-6 animate-in fade-in slide-in-from-right-8 duration-500">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xl font-semibold text-white">Phân cảnh Video</h3>
                <p className="text-sm text-muted-foreground">Mỗi phân cảnh = mỗi phần của kịch bản voiceover</p>
              </div>
              <button
                type="button"
                onClick={addSegment}
                className="inline-flex items-center bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-sm font-medium transition-colors h-10 px-4 text-white"
              >
                <Plus className="mr-2 h-4 w-4 text-primary" /> Thêm phân cảnh
              </button>
            </div>

            <div className="space-y-4 max-h-[550px] overflow-y-auto pr-2 custom-scrollbar">
              {segments.map((seg, idx) => (
                <div key={idx} className="p-5 rounded-2xl bg-black/40 border border-white/10 hover:border-white/20 transition-all space-y-4">
                  {/* Segment header */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/20 text-primary font-bold text-sm border border-primary/30">{idx + 1}</div>
                      <select
                        value={seg.name}
                        onChange={e => {
                          const preset = SEGMENT_PRESETS.find(p => p.name === e.target.value)
                          updateSegment(idx, "name", e.target.value)
                          if (preset) updateSegment(idx, "label", preset.label)
                        }}
                        className="h-9 rounded-lg border border-white/10 bg-white/5 px-3 text-sm text-white appearance-none"
                      >
                        {SEGMENT_PRESETS.map(p => (
                          <option key={p.name} value={p.name} className="bg-[#1A1A24]">{p.label}</option>
                        ))}
                      </select>
                    </div>
                    <button onClick={() => removeSegment(idx)} className="p-2 text-muted-foreground hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>

                  {/* Time range */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-muted-foreground uppercase">Bắt đầu (s)</label>
                      <input type="number" step="0.5" min="0"
                        value={seg.timeStart}
                        onChange={e => updateSegment(idx, "timeStart", parseFloat(e.target.value) || 0)}
                        className="flex h-10 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-muted-foreground uppercase">Kết thúc (s)</label>
                      <input type="number" step="0.5" min="0"
                        value={seg.timeEnd}
                        onChange={e => updateSegment(idx, "timeEnd", parseFloat(e.target.value) || 0)}
                        className="flex h-10 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-muted-foreground uppercase">Pacing Min (s)</label>
                      <input type="number" step="0.1" min="0.1"
                        value={seg.pacingMin}
                        onChange={e => updateSegment(idx, "pacingMin", parseFloat(e.target.value) || 0.5)}
                        className="flex h-10 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-muted-foreground uppercase">Pacing Max (s)</label>
                      <input type="number" step="0.1" min="0.1"
                        value={seg.pacingMax}
                        onChange={e => updateSegment(idx, "pacingMax", parseFloat(e.target.value) || 1.5)}
                        className="flex h-10 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50"
                      />
                    </div>
                  </div>

                  {/* Video clip upload */}
                  <div className="space-y-2">
                    <label className="text-xs font-semibold text-muted-foreground uppercase">
                      Video Clips <span className="text-primary">*</span>
                    </label>
                    <div className="flex items-center gap-3">
                      <label className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-dashed border-white/20 cursor-pointer transition-colors text-sm text-white/80">
                        <Upload className="w-4 h-4 text-primary" /> Chọn video clips
                        <input type="file" className="hidden" multiple accept="video/mp4,video/quicktime,.mov"
                          onChange={e => handleSegmentClips(idx, e.target.files)}
                        />
                      </label>
                      {seg.clips.length > 0 && (
                        <span className="text-xs text-green-400 bg-green-400/10 px-3 py-1 rounded-full border border-green-400/20">
                          <CheckCircle2 className="w-3 h-3 inline mr-1" />{seg.clips.length} clip(s)
                        </span>
                      )}
                    </div>
                    {seg.clips.length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-1">
                        {seg.clips.map((c, ci) => (
                          <span key={ci} className="text-xs bg-white/5 text-white/70 px-2 py-1 rounded-lg border border-white/10 flex items-center gap-1">
                            <Video className="w-3 h-3" /> {c.file.name.length > 20 ? c.file.name.slice(0, 20) + "..." : c.file.name}
                            <button onClick={() => {
                              const newSegs = [...segments]
                              newSegs[idx].clips = newSegs[idx].clips.filter((_, i) => i !== ci)
                              setSegments(newSegs)
                            }} className="text-red-400 hover:text-red-300 ml-1">×</button>
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Text overlay & highlight */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-muted-foreground uppercase">Text Overlay (chữ lớn)</label>
                      <input type="text"
                        placeholder="VD: SAI LẦM CHẾT NGƯỜI!"
                        value={seg.textOverlay}
                        onChange={e => updateSegment(idx, "textOverlay", e.target.value)}
                        className="flex h-10 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 placeholder:text-muted-foreground/40"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-muted-foreground uppercase">Highlight Words (phân tách bởi dấu phẩy)</label>
                      <input type="text"
                        placeholder="VD: SAI LẦM, CHẾT NGƯỜI"
                        value={seg.highlightWords}
                        onChange={e => updateSegment(idx, "highlightWords", e.target.value)}
                        className="flex h-10 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 placeholder:text-muted-foreground/40"
                      />
                    </div>
                  </div>

                  {/* Effects */}
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-muted-foreground uppercase">Hiệu ứng</label>
                    <div className="flex gap-2 flex-wrap">
                      {EFFECTS_OPTIONS.map(fx => (
                        <button key={fx.value} type="button"
                          onClick={() => toggleEffect(idx, fx.value)}
                          className={cn(
                            "px-3 py-1.5 rounded-lg text-xs font-medium transition-all border",
                            seg.effects.includes(fx.value)
                              ? "bg-primary/20 border-primary/40 text-primary shadow-[0_0_10px_rgba(124,58,237,0.2)]"
                              : "bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10"
                          )}
                        >
                          {fx.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex justify-between pt-4 border-t border-white/10">
              <button onClick={() => setStep(1)} className="px-6 py-3 rounded-xl font-medium text-white/80 hover:text-white hover:bg-white/5 transition-colors">
                Quay lại
              </button>
              <button onClick={() => setStep(3)} disabled={!canGoStep3}
                className="glowing-button text-white px-8 py-3 rounded-xl font-medium flex items-center gap-2 disabled:opacity-50 disabled:shadow-none"
              >
                Cài đặt Render <ChevronRight className="w-5 h-5" />
              </button>
            </div>
          </div>
        )}

        {/* ═══ STEP 3: Render Settings ═══ */}
        {step === 3 && (
          <div className="space-y-8 animate-in fade-in slide-in-from-right-8 duration-500">
            <h3 className="text-xl font-semibold text-white">Cài đặt Render</h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Auto subtitle */}
              <div className="p-4 rounded-xl bg-white/5 border border-white/10 space-y-3">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-semibold text-white">Phụ đề tự động (WhisperX)</label>
                  <button type="button" onClick={() => setAutoSubtitle(!autoSubtitle)}
                    className={cn("w-12 h-7 rounded-full transition-all relative", autoSubtitle ? "bg-primary" : "bg-white/20")}
                  >
                    <div className={cn("w-5 h-5 rounded-full bg-white absolute top-1 transition-all", autoSubtitle ? "left-6" : "left-1")} />
                  </button>
                </div>
                <p className="text-xs text-muted-foreground">Tự động tạo phụ đề Hormozi-style từ voiceover + script</p>
              </div>

              {/* Priority */}
              <div className="p-4 rounded-xl bg-white/5 border border-white/10 space-y-3">
                <label className="text-sm font-semibold text-white">Độ ưu tiên</label>
                <div className="flex gap-2">
                  <button type="button" onClick={() => setPriority(0)}
                    className={cn("px-4 py-2 rounded-lg text-sm font-medium transition-all", priority === 0 ? "bg-white/10 border border-white/30 text-white" : "border border-transparent text-muted-foreground hover:bg-white/5")}
                  >
                    Normal
                  </button>
                  <button type="button" onClick={() => setPriority(1)}
                    className={cn("px-4 py-2 rounded-lg text-sm font-medium transition-all", priority === 1 ? "bg-orange-500/20 border border-orange-500/50 text-orange-400" : "border border-transparent text-muted-foreground hover:bg-orange-500/10")}
                  >
                    High Priority
                  </button>
                </div>
              </div>

              {/* Font size */}
              <div className="p-4 rounded-xl bg-white/5 border border-white/10 space-y-3">
                <label className="text-sm font-semibold text-white">Cỡ chữ Overlay</label>
                <div className="flex items-center gap-3">
                  <input type="range" min="40" max="120" value={fontSize} onChange={e => setFontSize(parseInt(e.target.value))}
                    className="flex-1 accent-primary"
                  />
                  <span className="text-sm text-white font-mono w-10 text-center">{fontSize}</span>
                </div>
              </div>

              {/* Text color */}
              <div className="p-4 rounded-xl bg-white/5 border border-white/10 space-y-3">
                <label className="text-sm font-semibold text-white">Màu chữ Overlay</label>
                <div className="flex gap-2">
                  {["yellow", "white", "red", "cyan"].map(c => (
                    <button key={c} type="button" onClick={() => setTextColor(c)}
                      className={cn(
                        "w-10 h-10 rounded-lg border-2 transition-all",
                        textColor === c ? "border-primary scale-110 shadow-[0_0_15px_rgba(124,58,237,0.4)]" : "border-white/20"
                      )}
                      style={{ backgroundColor: c }}
                    />
                  ))}
                </div>
              </div>
            </div>

            <div className="flex justify-between pt-4 border-t border-white/10">
              <button onClick={() => setStep(2)} className="px-6 py-3 rounded-xl font-medium text-white/80 hover:text-white hover:bg-white/5 transition-colors">
                Quay lại
              </button>
              <button onClick={() => setStep(4)}
                className="glowing-button text-white px-8 py-3 rounded-xl font-medium flex items-center gap-2"
              >
                Xem lại & Gửi <ChevronRight className="w-5 h-5" />
              </button>
            </div>
          </div>
        )}

        {/* ═══ STEP 4: Review & Submit ═══ */}
        {step === 4 && (
          <div className="space-y-8 animate-in fade-in slide-in-from-right-8 duration-500">
            <div className="rounded-2xl bg-black/40 border border-white/10 p-8 space-y-6">
              <h3 className="text-2xl font-bold text-white flex items-center gap-3">
                <CheckCircle2 className="w-8 h-8 text-green-400" /> Xem lại trước khi gửi
              </h3>

              <div className="grid grid-cols-2 gap-8 text-sm">
                <div className="space-y-3">
                  <p className="text-muted-foreground font-semibold uppercase text-xs tracking-wider">Dự án & Âm thanh</p>
                  <div className="space-y-2">
                    <p className="text-white flex justify-between border-b border-white/10 pb-2"><span>Dự án:</span> <span className="font-medium">{isCreatingProject ? newProjectName : projects.find(p => p.id === selectedProjectId)?.name || "Chưa chọn"}</span></p>
                    <p className="text-white flex justify-between border-b border-white/10 pb-2"><span>Voiceover:</span> <span className="font-medium text-green-400">{voiceover?.file.name || "—"}</span></p>
                    <p className="text-white flex justify-between border-b border-white/10 pb-2"><span>Kịch bản:</span> <span className="font-medium text-green-400">{script?.file.name || "—"}</span></p>
                    <p className="text-white flex justify-between border-b border-white/10 pb-2"><span>Nhạc nền:</span> <span className="font-medium">{bgm?.file.name || "Không có"}</span></p>
                    <p className="text-white flex justify-between border-b border-white/10 pb-2"><span>Ngôn ngữ:</span> <span>{language === "vi" ? "🇻🇳 Tiếng Việt" : "🇺🇸 English"}</span></p>
                  </div>
                </div>
                <div className="space-y-3">
                  <p className="text-muted-foreground font-semibold uppercase text-xs tracking-wider">Cài đặt Render</p>
                  <div className="space-y-2">
                    <p className="text-white flex justify-between border-b border-white/10 pb-2"><span>Phân cảnh:</span> <span className="font-medium">{segments.length} segments</span></p>
                    <p className="text-white flex justify-between border-b border-white/10 pb-2"><span>Tổng clips:</span> <span className="font-medium">{segments.reduce((a, s) => a + s.clips.length, 0)} files</span></p>
                    <p className="text-white flex justify-between border-b border-white/10 pb-2"><span>Phụ đề tự động:</span> <span className={autoSubtitle ? "text-green-400" : "text-muted-foreground"}>{autoSubtitle ? "Bật" : "Tắt"}</span></p>
                    <p className="text-white flex justify-between border-b border-white/10 pb-2"><span>Độ phân giải:</span> <span>1080×1920</span></p>
                    <p className="text-white flex justify-between border-b border-white/10 pb-2"><span>Ưu tiên:</span> <span className={priority > 0 ? "text-orange-400 font-semibold" : ""}>{priority > 0 ? "High" : "Normal"}</span></p>
                  </div>
                </div>
              </div>

              {/* Segment summary */}
              <div className="space-y-2">
                <p className="text-muted-foreground font-semibold uppercase text-xs tracking-wider">Timeline phân cảnh</p>
                <div className="grid gap-2">
                  {segments.map((seg, i) => (
                    <div key={i} className="flex items-center gap-3 text-sm bg-white/5 p-3 rounded-lg border border-white/10">
                      <span className="w-6 h-6 rounded-full bg-primary/20 text-primary text-xs flex items-center justify-center font-bold">{i + 1}</span>
                      <span className="text-white font-medium flex-1">{seg.label || seg.name}</span>
                      <span className="text-muted-foreground font-mono text-xs">{seg.timeStart}s – {seg.timeEnd}s</span>
                      <span className="text-xs text-green-400">{seg.clips.length} clip(s)</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex justify-between pt-4">
              <button onClick={() => setStep(3)} className="px-6 py-3 rounded-xl font-medium text-white/80 hover:text-white hover:bg-white/5 transition-colors" disabled={loading}>
                Quay lại
              </button>
              <button
                onClick={handleSubmit}
                disabled={loading}
                className="glowing-button text-white px-10 py-3 rounded-xl font-medium flex items-center gap-2 shadow-[0_0_30px_rgba(124,58,237,0.6)]"
              >
                {loading ? (
                  <><Loader2 className="mr-2 h-5 w-5 animate-spin" /> {uploadStatus || "Đang xử lý..."}</>
                ) : (
                  <><Send className="w-5 h-5" /> Gửi Render Video</>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}


/* ─── Reusable File Dropzone Component ───────────────────────── */

function FileDropzone({
  label, sublabel, icon, accept, selectedFile, onSelect, required
}: {
  label: string
  sublabel: string
  icon: React.ReactNode
  accept: string
  selectedFile: UploadedFile | null
  onSelect: (file: File | undefined) => void
  required?: boolean
}) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-semibold text-white/90 uppercase tracking-wider flex items-center gap-1">
        {label} {required && <span className="text-primary">*</span>}
      </label>
      <label className="flex flex-col items-center justify-center w-full h-36 border-2 border-dashed border-white/20 rounded-2xl cursor-pointer hover:bg-white/5 hover:border-primary/50 transition-all duration-300 group">
        <div className="flex flex-col items-center justify-center py-4 text-center px-4">
          <div className="p-3 mb-2 rounded-full bg-white/5 group-hover:bg-primary/20 transition-colors">
            {icon}
          </div>
          <p className="text-xs text-muted-foreground">{sublabel}</p>
        </div>
        <input type="file" className="hidden" accept={accept} onChange={e => onSelect(e.target.files?.[0])} />
      </label>
      {selectedFile && (
        <div className="flex items-center gap-2 text-xs text-green-400 bg-green-400/10 p-2 rounded-lg border border-green-400/20">
          <CheckCircle2 className="w-3.5 h-3.5" /> {selectedFile.file.name}
        </div>
      )}
    </div>
  )
}
