import { useEffect, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { UploadCloud, Plus, Folder, Trash2, ChevronRight, CheckCircle2, Video, FileText, Send, Copy } from "lucide-react"
import api from "../lib/api"
import { cn } from "../lib/utils"
import { useAssets } from "../hooks/useAssets"
import { useProjects } from "../hooks/useProjects"
import { Button } from "../components/ui/Button"
import { AssetSelector } from "../components/ui/AssetSelector"
import { AssetSelectModal } from "../components/ui/AssetSelectModal"
import type { UploadedFile } from "../components/features/review/types"

interface TextEvent {
  time: number
  text: string
  effect: "hook" | "feature"
}

export default function CreateUnboxViralJob() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const cloneJobId = searchParams.get("clone")
  const { uploadAsset } = useAssets()
  const { projects, createProject } = useProjects()
  const [step, setStep] = useState(1)
  const [cloneLoading, setCloneLoading] = useState(!!cloneJobId)
  const clonedFromId = cloneJobId

  // Data State
  const [selectedProjectId, setSelectedProjectId] = useState("")
  const [newProjectName, setNewProjectName] = useState("")
  const [isCreatingProject, setIsCreatingProject] = useState(false)
  const [priority, setPriority] = useState<number>(0)
  const [clips, setClips] = useState<UploadedFile[]>([])
  const [audio, setAudio] = useState<UploadedFile | null>(null)
  
  useEffect(() => {
    if (projects.length > 0 && !selectedProjectId) setSelectedProjectId(projects[0].id)
    if (projects.length === 0) setIsCreatingProject(true)
  }, [projects, selectedProjectId])
  
  const [modalOpen, setModalOpen] = useState(false)
  const [textEvents, setTextEvents] = useState<TextEvent[]>([
    { time: 0.0, text: "Wait till you see this...", effect: "hook" }
  ])

  // UI State
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [uploadStatus, setUploadStatus] = useState("")

  // Clone pre-fill: fetch original job data and populate form
  useEffect(() => {
    if (!cloneJobId) return
    let cancelled = false
    const loadClone = async () => {
      try {
        setCloneLoading(true)
        const res = await api.get(`/api/jobs/${cloneJobId}`)
        const job = res.data
        if (cancelled) return

        // Pre-fill project
        if (job.project_id) setSelectedProjectId(job.project_id)
        if (job.priority !== undefined) setPriority(job.priority)

        const cfg = job.config_data || {}

        // Pre-fill clips as asset references (s3_url only, no File object)
        if (cfg.clips && Array.isArray(cfg.clips)) {
          const clonedClips: UploadedFile[] = cfg.clips.map((url: string) => ({
            file: undefined,
            id: null,
            s3_url: url,
            asset: { id: "", s3_url: url, file_name: url.split("/").pop() || "clip", file_size_bytes: 0, asset_type: "clip", mime_type: "video/mp4", created_at: "" },
            uploading: false,
            progress: 0,
          }))
          setClips(clonedClips)
        }

        // Pre-fill audio
        if (cfg.audio) {
          const audioUrl = cfg.audio as string
          setAudio({
            file: undefined,
            id: null,
            s3_url: audioUrl,
            asset: { id: "", s3_url: audioUrl, file_name: audioUrl.split("/").pop() || "audio", file_size_bytes: 0, asset_type: "audio", mime_type: "audio/mpeg", created_at: "" },
            uploading: false,
            progress: 0,
          })
        }

        // Pre-fill text events
        if (cfg.text_events && Array.isArray(cfg.text_events)) {
          setTextEvents(cfg.text_events)
        }
      } catch (err) {
        console.error("Failed to load cloned job:", err)
      } finally {
        if (!cancelled) setCloneLoading(false)
      }
    }
    loadClone()
    return () => { cancelled = true }
  }, [cloneJobId])

  const handleSubmit = async () => {
    if (!clips || clips.length === 0) return setError("Please select at least 1 video clip")
    if (!audio) return setError("Please select an audio file")
    if (!isCreatingProject && !selectedProjectId) return setError("Please select a project")
    if (isCreatingProject && !newProjectName.trim()) return setError("Please enter a new project name")

    setLoading(true)
    setError(null)
    try {
      let targetProjectId = selectedProjectId
      if (isCreatingProject && newProjectName.trim()) {
        setUploadStatus("Creating project...")
        const proj = await createProject(newProjectName.trim())
        targetProjectId = proj.id
      }

      const allAssetIds: string[] = []

      setUploadStatus("Uploading audio...")
      let audioUrl = "";
      if (audio.file) {
        const res = await uploadAsset(audio.file as File, "audio")
        audioUrl = res.s3_url
        allAssetIds.push(res.id)
      } else {
        audioUrl = audio.asset!.s3_url
        allAssetIds.push(audio.asset!.id)
      }

      const clipUrls: string[] = []
      for (let i = 0; i < clips.length; i++) {
        setUploadStatus(`Uploading clip ${i + 1} of ${clips.length}...`)
        if (clips[i].file) {
          const res = await uploadAsset(clips[i].file as File, "clip")
          clipUrls.push(res.s3_url)
          allAssetIds.push(res.id)
        } else {
          clipUrls.push(clips[i].asset!.s3_url)
          allAssetIds.push(clips[i].asset!.id)
        }
      }

      setUploadStatus("Committing job...")
      const payload = {
        job_type: "unbox_viral",
        priority,
        project_id: targetProjectId,
        asset_ids: allAssetIds,
        config_data: {
          clips: clipUrls,
          audio: audioUrl,
          text_events: textEvents
        }
      }

      await api.post("/api/jobs", payload)
      navigate("/")
    } catch (err: any) {
      console.error(err)
      setError(err?.response?.data?.detail || err.message || "Failed to create job")
    } finally {
      setLoading(false)
      setUploadStatus("")
    }
  }

  const steps = [
    { id: 1, name: "Upload Media", icon: Video },
    { id: 2, name: "Script & Timeline", icon: FileText },
    { id: 3, name: "Review & Render", icon: Send }
  ]

  return (
    <div className="max-w-5xl mx-auto p-8 lg:p-12 space-y-10">
      <div className="space-y-2">
        <h2 className="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-violet-400 to-indigo-400">
          Create Viral Unbox ⚡
        </h2>
      <p className="text-muted-foreground text-lg">
          Upload raw vertical clips. Our AI will automatically track products (YOLO), cut static scenes, speed-ramp repetitive actions, and sync with trending audio!
        </p>
      </div>

      {clonedFromId && (
        <div className="glass-panel p-4 flex items-center gap-3 bg-amber-500/10 border border-amber-500/20 rounded-xl animate-in fade-in">
          <Copy className="w-5 h-5 text-amber-400 shrink-0" />
          <div>
            <p className="text-sm font-medium text-amber-300">Bản sao từ Job #{clonedFromId}</p>
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
          {steps.map((s, idx) => (
            <div key={s.id} className="flex items-center">
              <div className={cn(
                "flex items-center gap-3 transition-all duration-300",
                step >= s.id ? "text-primary" : "text-muted-foreground"
              )}>
                <div className={cn(
                  "flex items-center justify-center w-10 h-10 rounded-full border-2 transition-all duration-300",
                  step > s.id ? "bg-primary border-primary text-white" :
                    step === s.id ? "border-primary bg-primary/20 shadow-[0_0_15px_rgba(124,58,237,0.4)]" : "border-muted-foreground/30"
                )}>
                  {step > s.id ? <CheckCircle2 className="w-5 h-5" /> : <s.icon className="w-5 h-5" />}
                </div>
                <span className={cn(
                  "font-medium text-sm hidden md:block",
                  step >= s.id ? "text-white" : "text-muted-foreground"
                )}>
                  {s.name}
                </span>
              </div>
              {idx < steps.length - 1 && (
                <div className="w-12 md:w-24 h-px bg-white/10 mx-4"></div>
              )}
            </div>
          ))}
        </div>

        {error && (
          <div className="p-4 bg-red-500/10 text-red-400 rounded-xl border border-red-500/20 backdrop-blur-sm animate-in fade-in slide-in-from-top-4">
            {error}
          </div>
        )}

        {step === 1 && (
          <div className="space-y-8 animate-in fade-in slide-in-from-right-8 duration-500">
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
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-semibold text-white/90 uppercase tracking-wider">Raw Video Clip (1 is best)</label>
                  <button
                    type="button"
                    onClick={() => setModalOpen(true)}
                    className="text-xs text-primary hover:bg-primary/10 px-2 py-1 rounded-md transition-colors flex items-center gap-1"
                  >
                    Thư viện
                  </button>
                </div>
                <div className="flex items-center justify-center w-full">
                  <label className="flex flex-col items-center justify-center w-full h-48 border-2 border-dashed border-white/20 rounded-2xl cursor-pointer hover:bg-white/5 hover:border-primary/50 transition-all duration-300 group">
                    <div className="flex flex-col items-center justify-center pt-5 pb-6 text-center px-4">
                      <div className="p-4 mb-4 rounded-full bg-white/5 group-hover:bg-primary/20 transition-colors">
                        <UploadCloud className="w-8 h-8 text-primary" />
                      </div>
                      <p className="mb-2 text-sm text-white/80"><span className="font-semibold text-primary">Click to browse</span> or drag & drop</p>
                      <p className="text-xs text-muted-foreground">MP4, MOV up to 1080p</p>
                    </div>
                    <input type="file" className="hidden" multiple accept="video/mp4,video/quicktime" onChange={(e) => {
                      if (e.target.files) {
                        const newFiles = Array.from(e.target.files).map(f => ({ file: f, id: null, s3_url: null, uploading: false, progress: 0 }))
                        setClips([...clips, ...newFiles])
                      }
                    }} />
                  </label>
                </div>
                {clips.length > 0 && (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 text-sm text-green-400 bg-green-400/10 p-3 rounded-xl border border-green-400/20">
                      <CheckCircle2 className="w-4 h-4" /> Selected {clips.length} video files
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {clips.map((c, idx) => (
                        <span key={idx} className="text-sm bg-white/5 text-white/80 px-3 py-1.5 rounded-lg border border-white/10 flex items-center gap-2 shadow-sm">
                          <Video className="w-4 h-4 text-primary/70" /> 
                          {c.file?.name 
                            ? (c.file.name.length > 25 ? c.file.name.slice(0, 25) + "..." : c.file.name) 
                            : (c.asset?.file_name && c.asset.file_name.length > 25 ? c.asset.file_name.slice(0, 25) + "..." : c.asset?.file_name)}
                          <button type="button" onClick={() => setClips(clips.filter((_, i) => i !== idx))} className="text-red-400 hover:text-red-300 ml-1 hover:bg-red-400/10 p-0.5 rounded transition-colors">
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                <AssetSelectModal
                  isOpen={modalOpen}
                  onClose={() => setModalOpen(false)}
                  assetTypeFilter="clip"
                  multiple={true}
                  onSelectMultiple={(assets) => {
                    const newClips = assets.map(asset => ({ asset, id: asset.id, s3_url: asset.s3_url, uploading: false, progress: 0 }));
                    setClips([...clips, ...newClips]);
                  }}
                />
              </div>

              <AssetSelector
                label="Background Audio"
                sublabel="Trending TikTok Sound"
                icon={<UploadCloud className="w-8 h-8 text-indigo-400" />}
                accept="audio/mpeg"
                assetTypeFilter="audio"
                selectedFile={audio}
                onSelect={(file, asset) => {
                  if (file || asset) {
                    setAudio({ file, asset, id: asset?.id || null, s3_url: asset?.s3_url || null, uploading: false, progress: 0 })
                  }
                }}
              />
            </div>

            <div className="flex justify-end pt-4">
              <Button
                onClick={() => setStep(2)}
                disabled={!clips || clips.length === 0 || !audio}
                className="glowing-button px-8 py-3 rounded-xl font-medium"
              >
                Continue to Script <ChevronRight className="w-5 h-5 ml-2" />
              </Button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-8 animate-in fade-in slide-in-from-right-8 duration-500">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xl font-semibold text-white">Visual Overlays</h3>
                <p className="text-sm text-muted-foreground">Add hooks and feature callouts synced to audio time.</p>
              </div>
              <button
                type="button"
                onClick={() => setTextEvents([...textEvents, { time: 0, text: "", effect: "feature" }])}
                className="inline-flex items-center bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-sm font-medium transition-colors h-10 px-4 text-white"
              >
                <Plus className="mr-2 h-4 w-4 text-primary" /> Add Overlay
              </button>
            </div>

            <div className="space-y-4 max-h-[450px] overflow-y-auto pr-2 custom-scrollbar">
              {textEvents.map((ev, idx) => (
                <div key={idx} className="flex items-start gap-4 p-5 rounded-2xl bg-black/40 border border-white/10 hover:border-white/20 transition-all duration-300">
                  <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/20 text-primary font-bold text-sm shrink-0 border border-primary/30">
                    {idx + 1}
                  </div>

                  <div className="flex-1 space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Timestamp (sec)</label>
                        <input
                          type="number" step="0.1" min="0" required
                          className="flex h-11 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all"
                          value={ev.time}
                          onChange={(e) => {
                            const newEvents = [...textEvents];
                            newEvents[idx].time = parseFloat(e.target.value);
                            setTextEvents(newEvents);
                          }}
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Effect Style</label>
                        <select
                          className="flex h-11 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all appearance-none"
                          value={ev.effect}
                          onChange={(e) => {
                            const newEvents = [...textEvents];
                            newEvents[idx].effect = e.target.value as "hook" | "feature";
                            setTextEvents(newEvents);
                          }}
                        >
                          <option value="hook" className="bg-[#1A1A24]">🎯 Hook (Center Large)</option>
                          <option value="feature" className="bg-[#1A1A24]">✨ Feature (Slide-in)</option>
                        </select>
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Overlay Text</label>
                      <input
                        type="text" required
                        placeholder="e.g., You won't believe what happened next!"
                        className="flex h-11 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all placeholder:text-muted-foreground/50"
                        value={ev.text}
                        onChange={(e) => {
                          const newEvents = [...textEvents];
                          newEvents[idx].text = e.target.value;
                          setTextEvents(newEvents);
                        }}
                      />
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => setTextEvents(textEvents.filter((_, i) => i !== idx))}
                    className="p-2 text-muted-foreground hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors mt-8"
                  >
                    <Trash2 className="h-5 w-5" />
                  </button>
                </div>
              ))}
            </div>

            <div className="flex justify-between pt-4 border-t border-white/10">
              <button
                onClick={() => setStep(1)}
                className="px-6 py-3 rounded-xl font-medium text-white/80 hover:text-white hover:bg-white/5 transition-colors"
              >
                Back
              </button>
              <Button
                onClick={() => setStep(3)}
                className="glowing-button px-8 py-3 rounded-xl font-medium"
              >
                Review Configuration <ChevronRight className="w-5 h-5 ml-2" />
              </Button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-8 animate-in fade-in slide-in-from-right-8 duration-500">
            <div className="rounded-2xl bg-black/40 border border-white/10 p-8 space-y-6">
              <h3 className="text-2xl font-bold text-white flex items-center gap-3">
                <CheckCircle2 className="w-8 h-8 text-green-400" /> Ready to Render
              </h3>

              <div className="flex items-center gap-4 bg-white/5 p-4 rounded-xl border border-white/10">
                <label className="text-white text-sm font-semibold uppercase tracking-wider text-muted-foreground mr-4">Compute Priority</label>
                <button
                  type="button"
                  onClick={() => setPriority(0)}
                  className={cn("px-5 py-2 rounded-xl transition-all text-sm font-medium", priority === 0 ? "bg-white/10 border border-white/30 text-white shadow-sm" : "border border-transparent text-muted-foreground hover:bg-white/5")}
                >
                  Normal
                </button>
                <button
                  type="button"
                  onClick={() => setPriority(1)}
                  className={cn("px-5 py-2 rounded-xl transition-all text-sm font-medium", priority === 1 ? "bg-orange-500/20 border border-orange-500/50 text-orange-400 shadow-[0_0_15px_rgba(249,115,22,0.2)]" : "border border-transparent text-muted-foreground hover:bg-orange-500/10 hover:text-orange-400/70")}
                >
                  High Priority
                </button>
              </div>

              <div className="grid grid-cols-2 gap-8 text-sm">
                <div className="space-y-2">
                  <p className="text-muted-foreground">Media Inputs</p>
                  <p className="text-white font-medium flex justify-between border-b border-white/10 pb-2">
                    <span>Clips Selected:</span> <span>{clips?.length || 0} files</span>
                  </p>
                  <p className="text-white font-medium flex justify-between border-b border-white/10 pb-2">
                    <span>Audio Track:</span> <span>Yes</span>
                  </p>
                </div>
                <div className="space-y-2">
                  <p className="text-muted-foreground">Timeline Settings</p>
                  <p className="text-white font-medium flex justify-between border-b border-white/10 pb-2">
                    <span>Text Overlays:</span> <span>{textEvents.length} events</span>
                  </p>
                  <p className="text-white font-medium flex justify-between border-b border-white/10 pb-2">
                    <span>Export Format:</span> <span>Vertical 9:16 MP4</span>
                  </p>
                </div>
              </div>
            </div>

            <div className="flex justify-between pt-4">
              <button
                onClick={() => setStep(2)}
                className="px-6 py-3 rounded-xl font-medium text-white/80 hover:text-white hover:bg-white/5 transition-colors"
                disabled={loading}
              >
                Back to Script
              </button>
              <Button
                onClick={handleSubmit}
                isLoading={loading}
                className="glowing-button px-10 py-3 rounded-xl font-medium shadow-[0_0_30px_rgba(124,58,237,0.6)]"
              >
                {!loading && <Send className="w-5 h-5 mr-2" />}
                {loading ? (uploadStatus || "Processing GPU Job...") : "Send to Render Farm"}
              </Button>
            </div>
          </div>
        )}
      </div>
      )}
    </div>
  )
}
