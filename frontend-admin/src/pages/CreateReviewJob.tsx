import { useState } from "react"
import axios from "axios"
import { useNavigate } from "react-router-dom"
import { Loader2, Code2, Play, Settings2, FileJson, AlertCircle } from "lucide-react"
import { cn } from "../lib/utils"

export default function CreateReviewJob() {
  const navigate = useNavigate()
  const [jsonConfig, setJsonConfig] = useState<string>("{\n  \"metadata\": {\n    \"project_id\": \"review_\"\n  }\n}")
  const [priority, setPriority] = useState<number>(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    
    try {
      const configData = JSON.parse(jsonConfig)
      
      const payload = {
        job_type: "review",
        priority,
        config_data: configData
      }

      await axios.post("http://localhost:8000/api/jobs", payload)
      navigate("/")
    } catch (err: any) {
      console.error(err)
      if (err instanceof SyntaxError) {
        setError("Invalid JSON format. Please check your configuration.")
      } else {
        setError(err?.response?.data?.detail || err.message || "Failed to create job")
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-5xl mx-auto p-8 lg:p-12 space-y-10">
      
      {/* Header */}
      <div className="space-y-2">
        <h2 className="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60">
          Create Review Video
        </h2>
        <p className="text-muted-foreground text-lg">
          Advanced JSON builder to orchestrate complex tech review videos using timeline scripting.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="glass-panel p-6 lg:p-10 flex flex-col space-y-8 min-h-[600px] animate-in fade-in slide-in-from-bottom-8 duration-700">
        
        <div className="flex items-center gap-3 border-b border-white/10 pb-4">
          <div className="p-2.5 rounded-xl bg-primary/20 text-primary border border-primary/30 shadow-[0_0_15px_rgba(124,58,237,0.3)]">
            <Code2 className="w-5 h-5" />
          </div>
          <h3 className="text-xl font-semibold text-white">Blueprint Configuration</h3>
        </div>

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

        {error && (
          <div className="p-4 bg-red-500/10 text-red-400 rounded-xl border border-red-500/20 backdrop-blur-sm flex items-start gap-3">
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
            <p>{error}</p>
          </div>
        )}

        <div className="flex-1 flex flex-col space-y-4">
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
              <FileJson className="w-4 h-4" /> JSON Payload
            </label>
            <div className="flex items-center gap-2">
              <span className="flex items-center rounded-full bg-green-400/10 px-2.5 py-0.5 text-xs font-medium text-green-400 border border-green-400/20">
                <Settings2 className="w-3 h-3 mr-1" /> MinIO / S3 Ready
              </span>
            </div>
          </div>
          
          <div className="relative group flex-1 flex flex-col">
            <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-xl pointer-events-none"></div>
            <textarea 
              className="flex-1 min-h-[400px] w-full rounded-xl border border-white/10 bg-[#0c0c14] font-mono text-sm sm:text-[15px] p-6 text-indigo-100 focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all custom-scrollbar placeholder:text-muted-foreground/30 shadow-inner"
              value={jsonConfig}
              onChange={(e) => setJsonConfig(e.target.value)}
              spellCheck={false}
              placeholder={'{\n  "metadata": {\n     "title": "Review"\n  }\n}'}
            />
          </div>
          <p className="text-xs text-muted-foreground/60">
            S3 object URLs must be provided in the assets directory mapped configuration.
          </p>
        </div>

        <div className="pt-6 border-t border-white/10 flex justify-end">
          <button 
            type="submit" 
            disabled={loading}
            className="glowing-button text-white px-10 py-3 rounded-xl font-medium flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? <><Loader2 className="mr-2 h-5 w-5 animate-spin"/> Validating...</> : <><Play className="w-5 h-5"/> Execute Job Blueprint</>}
          </button>
        </div>
      </form>
    </div>
  )
}
