import { useState } from "react"
import api from "../lib/api"
import { useNavigate } from "react-router-dom"
import { UploadCloud, Plus, Trash2, Loader2, ChevronRight, CheckCircle2, Video, FileText, Send } from "lucide-react"
import { cn } from "../lib/utils"

interface TextEvent {
  time: number
  text: string
  effect: "hook" | "feature"
}

export default function CreateUnboxJob() {
  const navigate = useNavigate()
  const [step, setStep] = useState(1)

  // Data State
  const [priority, setPriority] = useState<number>(0)
  const [clips, setClips] = useState<FileList | null>(null)
  const [audio, setAudio] = useState<File | null>(null)
  const [textEvents, setTextEvents] = useState<TextEvent[]>([
    { time: 0.0, text: "Wait till you see this...", effect: "hook" }
  ])

  // UI State
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const uploadFile = async (file: File) => {
    const formData = new FormData()
    formData.append("file", file)
    const res = await api.post("/api/assets/upload", formData)
    return res.data.s3_url
  }

  const handleSubmit = async () => {
    if (!clips || clips.length === 0) return setError("Please select at least 1 video clip")
    if (!audio) return setError("Please select an audio file")

    setLoading(true)
    setError(null)
    try {
      // 1. Upload audio
      const audioUrl = await uploadFile(audio)

      // 2. Upload clips
      const clipUrls: string[] = []
      for (let i = 0; i < clips.length; i++) {
        const url = await uploadFile(clips[i])
        clipUrls.push(url)
      }

      // 3. Create job
      const payload = {
        job_type: "unbox",
        priority,
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
    }
  }

  const steps = [
    { id: 1, name: "Upload Media", icon: Video },
    { id: 2, name: "Script & Timeline", icon: FileText },
    { id: 3, name: "Review & Render", icon: Send }
  ]

  return (
    <div className="max-w-5xl mx-auto p-8 lg:p-12 space-y-10">

      {/* Header */}
      <div className="space-y-2">
        <h2 className="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60">
          Create Viral Unbox
        </h2>
        <p className="text-muted-foreground text-lg">
          Upload raw vertical clips and sync them with trending audio.
        </p>
      </div>

      {/* Main Glass Panel */}
      <div className="glass-panel p-6 lg:p-10 flex flex-col space-y-10">

        {/* Stepper Wizard */}
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

        {/* Step 1: Upload Media */}
        {step === 1 && (
          <div className="space-y-8 animate-in fade-in slide-in-from-right-8 duration-500">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              {/* Video Dropzone */}
              <div className="space-y-3">
                <label className="text-sm font-semibold text-white/90 uppercase tracking-wider">Raw Video Clips</label>
                <div className="flex items-center justify-center w-full">
                  <label className="flex flex-col items-center justify-center w-full h-48 border-2 border-dashed border-white/20 rounded-2xl cursor-pointer hover:bg-white/5 hover:border-primary/50 transition-all duration-300 group">
                    <div className="flex flex-col items-center justify-center pt-5 pb-6 text-center px-4">
                      <div className="p-4 mb-4 rounded-full bg-white/5 group-hover:bg-primary/20 transition-colors">
                        <UploadCloud className="w-8 h-8 text-primary" />
                      </div>
                      <p className="mb-2 text-sm text-white/80"><span className="font-semibold text-primary">Click to browse</span> or drag & drop</p>
                      <p className="text-xs text-muted-foreground">MP4, MOV up to 1080p</p>
                    </div>
                    <input type="file" className="hidden" multiple accept="video/mp4,video/quicktime" onChange={(e) => setClips(e.target.files)} />
                  </label>
                </div>
                {clips && clips.length > 0 && (
                  <div className="flex items-center gap-2 text-sm text-green-400 bg-green-400/10 p-3 rounded-lg border border-green-400/20">
                    <CheckCircle2 className="w-4 h-4" /> Selected {clips.length} video files
                  </div>
                )}
              </div>

              {/* Audio Dropzone */}
              <div className="space-y-3">
                <label className="text-sm font-semibold text-white/90 uppercase tracking-wider">Background Audio</label>
                <div className="flex items-center justify-center w-full">
                  <label className="flex flex-col items-center justify-center w-full h-48 border-2 border-dashed border-white/20 rounded-2xl cursor-pointer hover:bg-white/5 hover:border-primary/50 transition-all duration-300 group">
                    <div className="flex flex-col items-center justify-center pt-5 pb-6 text-center px-4">
                      <div className="p-4 mb-4 rounded-full bg-white/5 group-hover:bg-primary/20 transition-colors">
                        <UploadCloud className="w-8 h-8 text-indigo-400" />
                      </div>
                      <p className="mb-2 text-sm text-white/80"><span className="font-semibold text-indigo-400">Trending TikTok Sound</span></p>
                      <p className="text-xs text-muted-foreground">MP3 format</p>
                    </div>
                    <input type="file" className="hidden" accept="audio/mpeg" onChange={(e) => setAudio(e.target.files?.[0] || null)} />
                  </label>
                </div>
                {audio && (
                  <div className="flex items-center gap-2 text-sm text-green-400 bg-green-400/10 p-3 rounded-lg border border-green-400/20">
                    <CheckCircle2 className="w-4 h-4" /> Selected: {audio.name}
                  </div>
                )}
              </div>
            </div>

            <div className="flex justify-end pt-4">
              <button
                onClick={() => setStep(2)}
                disabled={!clips || clips.length === 0 || !audio}
                className="glowing-button text-white px-8 py-3 rounded-xl font-medium flex items-center gap-2 disabled:opacity-50 disabled:shadow-none"
              >
                Continue to Script <ChevronRight className="w-5 h-5" />
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Script & Timeline */}
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
              <button
                onClick={() => setStep(3)}
                className="glowing-button text-white px-8 py-3 rounded-xl font-medium flex items-center gap-2"
              >
                Review Configuration <ChevronRight className="w-5 h-5" />
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Review & Render */}
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
              <button
                onClick={handleSubmit}
                disabled={loading}
                className="glowing-button text-white px-10 py-3 rounded-xl font-medium flex items-center gap-2 shadow-[0_0_30px_rgba(124,58,237,0.6)]"
              >
                {loading ? <><Loader2 className="mr-2 h-5 w-5 animate-spin" /> Processing GPU Job...</> : <><Send className="w-5 h-5" /> Send to Render Farm</>}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
