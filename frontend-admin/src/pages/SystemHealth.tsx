import { useEffect, useState } from "react"
import api from "../lib/api"
import { format } from "date-fns"
import { Activity, Server, FileCode, CheckCircle2, Clock, PlaySquare } from "lucide-react"
import { cn } from "../lib/utils"

interface WorkerNode {
  id: string
  hostname: string
  ip_address: string | null
  status: string
  current_job_id: number | null
  last_heartbeat: string
}

interface Template {
  id: string
  name: string
  job_type: string
  is_active: boolean
}

export default function SystemHealth() {
  const [workers, setWorkers] = useState<WorkerNode[]>([])
  const [templates, setTemplates] = useState<Template[]>([])
  const [loading, setLoading] = useState(true)

  const fetchHealth = async () => {
    try {
      const [workersRes, templatesRes] = await Promise.all([
        api.get("/api/workers"),
        api.get("/api/templates")
      ])
      setWorkers(workersRes.data)
      setTemplates(templatesRes.data)
    } catch (e) {
      console.error("Failed to fetch system data", e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchHealth()
    const interval = setInterval(fetchHealth, 10000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="max-w-7xl mx-auto p-8 lg:p-12 space-y-10 animate-in fade-in duration-700">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <h2 className="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-emerald-400 to-teal-400 flex items-center gap-3">
            <Activity className="w-8 h-8 text-emerald-400" /> System Metrics
          </h2>
          <p className="text-muted-foreground text-lg">
            Monitor API workers and generative templates.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        
        {/* Workers Panel */}
        <div className="glass-panel p-6 flex flex-col h-full border border-emerald-500/10">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 rounded bg-emerald-500/10 text-emerald-400">
              <Server className="w-5 h-5" />
            </div>
            <h3 className="text-xl font-bold text-white">Active Workers</h3>
          </div>
          
          <div className="flex-1">
            {loading && workers.length === 0 ? (
              <div className="text-muted-foreground">Scanning cluster...</div>
            ) : workers.length === 0 ? (
              <div className="text-muted-foreground/50 border border-white/5 rounded-xl p-6 text-center bg-black/20">
                No active workers reported in the database.
              </div>
            ) : (
              <div className="space-y-4">
                {workers.map(w => (
                  <div key={w.id} className="p-4 rounded-xl border border-white/10 bg-white/5 transition-colors hover:bg-white/10">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2 font-mono text-sm text-white/90">
                        {w.hostname} 
                        <span className={cn(
                          "px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider",
                          w.status === "ONLINE" ? "bg-emerald-500/20 text-emerald-400" : "bg-amber-500/20 text-amber-400"
                        )}>
                          {w.status}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <div className="flex items-center gap-1.5"><Clock className="w-3.5 h-3.5"/> Heartbeat: {format(new Date(w.last_heartbeat), "HH:mm:ss")}</div>
                      {w.current_job_id && (
                        <div className="flex items-center gap-1.5 text-indigo-400">
                          <PlaySquare className="w-3.5 h-3.5" /> Working Job #{w.current_job_id}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Templates Panel */}
        <div className="glass-panel p-6 flex flex-col h-full border border-indigo-500/10">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 rounded bg-indigo-500/10 text-indigo-400">
              <FileCode className="w-5 h-5" />
            </div>
            <h3 className="text-xl font-bold text-white">Generative Templates</h3>
          </div>
          
          <div className="flex-1">
            {loading && templates.length === 0 ? (
              <div className="text-muted-foreground">Loading schema registry...</div>
            ) : templates.length === 0 ? (
              <div className="text-muted-foreground/50 border border-white/5 rounded-xl p-6 text-center bg-black/20">
                No templates configured.
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4">
                {templates.map(t => (
                  <div key={t.id} className="p-4 rounded-xl border border-white/10 bg-white/5 flex flex-col gap-3">
                    <div className="flex items-start justify-between">
                      <h4 className="font-bold text-white">{t.name}</h4>
                      {t.is_active && <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
                    </div>
                    <div className="flex gap-2">
                      <span className="px-2 py-1 rounded-md bg-white/5 border border-white/10 text-xs font-mono text-muted-foreground">Type: {t.job_type}</span>
                      <span className="px-2 py-1 rounded-md bg-white/5 border border-white/10 text-xs font-mono text-muted-foreground">ID: {t.id.substring(0,8)}...</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  )
}
