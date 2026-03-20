import { useEffect, useState } from "react"
import api from "../lib/api"
import { format } from "date-fns"
import { AlertCircle, Clock, CheckCircle2, LayoutDashboard, RefreshCw, Download, ChevronDown, ChevronUp, Timer, ExternalLink, Trash2, Eye, Terminal, Code2 } from "lucide-react"
import { cn } from "../lib/utils"

interface VideoJob {
  id: number
  job_type: string
  status: "PENDING" | "PROCESSING" | "SUCCESS" | "FAILED"
  priority: number
  progress_percent: number
  config_data: any
  result_url: string | null
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

interface JobLog {
  id: number
  job_id: number
  log_level: string
  message: string
  created_at: string
}

function formatDuration(start: string, end: string): string {
  const ms = new Date(end).getTime() - new Date(start).getTime()
  const secs = Math.floor(ms / 1000)
  if (secs < 60) return `${secs}s`
  const mins = Math.floor(secs / 60)
  const remainSecs = secs % 60
  return `${mins}m ${remainSecs}s`
}

function getMinioDownloadUrl(s3Url: string): string {
  // s3://videos/outputs/review_job_4.mp4 → http://localhost:9000/videos/outputs/review_job_4.mp4
  return s3Url.replace("s3://", "http://localhost:9000/")
}

function getMinioBrowserUrl(s3Url: string): string {
  // s3://videos/outputs/review_job_4.mp4 → http://localhost:9001/browser/videos/outputs/review_job_4.mp4
  return s3Url.replace("s3://", "http://localhost:9001/browser/")
}

export default function Dashboard() {
  const [jobs, setJobs] = useState<VideoJob[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [expandedError, setExpandedError] = useState<number | null>(null)
  
  // Job Actions State
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [selectedJob, setSelectedJob] = useState<VideoJob | null>(null)
  const [jobLogs, setJobLogs] = useState<JobLog[]>([])
  const [loadingLogs, setLoadingLogs] = useState(false)
  const [activeTab, setActiveTab] = useState<"logs" | "config">("logs")

  const fetchJobs = async () => {
    try {
      const res = await api.get("/api/jobs")
      setJobs(res.data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  const handleRefresh = () => {
    setRefreshing(true)
    fetchJobs()
  }

  const handleDeleteJob = async (id: number) => {
    if (!confirm("Permanently delete this job and its resources?")) return
    setDeletingId(id)
    try {
      await api.delete(`/api/jobs/${id}`)
      setJobs(jobs.filter(j => j.id !== id))
    } catch (e) {
      console.error(e)
      alert("Failed to delete job")
    } finally {
      setDeletingId(null)
    }
  }

  const handleViewDetails = async (job: VideoJob) => {
    setSelectedJob(job)
    setActiveTab("logs")
    setLoadingLogs(true)
    setJobLogs([])
    try {
      const res = await api.get(`/api/jobs/${job.id}/logs`)
      setJobLogs(res.data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoadingLogs(false)
    }
  }

  // Effect to auto-refresh logs if viewing a processing job
  useEffect(() => {
    let interval: any;
    if (selectedJob && selectedJob.status === "PROCESSING" && activeTab === "logs") {
      interval = setInterval(async () => {
        try {
          const res = await api.get(`/api/jobs/${selectedJob.id}/logs`)
          setJobLogs(res.data)
        } catch (e) {}
      }, 3000)
    }
    return () => clearInterval(interval)
  }, [selectedJob, activeTab])

  useEffect(() => {
    fetchJobs()
    const interval = setInterval(fetchJobs, 5000)
    return () => clearInterval(interval)
  }, [])

  const hasProcessing = jobs.some(j => j.status === "PROCESSING")

  return (
    <div className="max-w-7xl mx-auto p-8 lg:p-12 space-y-10">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <h2 className="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60 flex items-center gap-3">
            <LayoutDashboard className="w-8 h-8 text-primary" /> Command Center
          </h2>
          <p className="text-muted-foreground text-lg">
            Monitor rendering farm clusters and automated video generation queues.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {hasProcessing && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-500/10 border border-blue-500/20">
              <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse shadow-[0_0_8px_rgba(59,130,246,0.8)]"></div>
              <span className="text-xs text-blue-400 font-medium">Rendering</span>
            </div>
          )}
          <button
            onClick={handleRefresh}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-white transition-all text-sm font-medium"
          >
            <RefreshCw className={cn("w-4 h-4", refreshing && "animate-spin")} />
            Refresh
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Total Jobs", value: jobs.length, color: "text-white" },
          { label: "Success", value: jobs.filter(j => j.status === "SUCCESS").length, color: "text-emerald-400" },
          { label: "Processing", value: jobs.filter(j => j.status === "PROCESSING").length, color: "text-blue-400" },
          { label: "Failed", value: jobs.filter(j => j.status === "FAILED").length, color: "text-rose-400" },
        ].map(stat => (
          <div key={stat.label} className="glass-panel p-5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{stat.label}</p>
            <p className={cn("text-3xl font-bold mt-1", stat.color)}>{stat.value}</p>
          </div>
        ))}
      </div>

      <div className="glass-panel overflow-hidden animate-in fade-in slide-in-from-bottom-8 duration-700">
        <div className="w-full overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-black/40 text-xs uppercase text-muted-foreground border-b border-white/10">
              <tr>
                <th className="px-6 py-5 font-semibold tracking-wider">Job ID</th>
                <th className="px-6 py-5 font-semibold tracking-wider">Type</th>
                <th className="px-6 py-5 font-semibold tracking-wider">Priority</th>
                <th className="px-6 py-5 font-semibold tracking-wider">Status & Progress</th>
                <th className="px-6 py-5 font-semibold tracking-wider">Duration</th>
                <th className="px-6 py-5 font-semibold tracking-wider">Created</th>
                <th className="px-6 py-5 font-semibold tracking-wider text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {loading && jobs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-3">
                      <RefreshCw className="w-6 h-6 animate-spin text-primary" />
                      Connecting to Render Farm...
                    </div>
                  </td>
                </tr>
              ) : jobs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <AlertCircle className="w-6 h-6 text-muted-foreground/50" />
                      No video jobs found. Create your first job!
                    </div>
                  </td>
                </tr>
              ) : (
                jobs.map((job) => (
                  <>
                    <tr key={job.id} className="hover:bg-white/[0.02] transition-colors group">
                      <td className="px-6 py-4 whitespace-nowrap font-medium text-white/90">
                        #{job.id}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={cn(
                          "inline-flex items-center px-2.5 py-1 rounded-md bg-white/5 border border-white/10 text-xs font-medium capitalize tracking-wide",
                          job.job_type === "review" ? "text-indigo-300" : "text-cyan-300"
                        )}>
                          {job.job_type}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {job.priority > 0 ? (
                          <span className="inline-flex items-center px-2 py-1 rounded border border-orange-500/30 text-[10px] font-bold text-orange-400 uppercase">
                            High
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-1 rounded border border-white/10 text-[10px] font-medium text-muted-foreground uppercase">
                            Normal
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap min-w-[220px]">
                        <div className="flex flex-col gap-2">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              {job.status === "SUCCESS" && (
                                <span className="inline-flex items-center rounded-full border border-emerald-500/30 px-3 py-1 text-xs font-semibold bg-emerald-500/10 text-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.2)]">
                                  <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" /> SUCCESS
                                </span>
                              )}
                              {job.status === "PROCESSING" && (
                                <span className="inline-flex items-center rounded-full border border-blue-500/30 px-3 py-1 text-xs font-semibold bg-blue-500/10 text-blue-400 shadow-[0_0_10px_rgba(59,130,246,0.2)]">
                                  <Clock className="mr-1.5 h-3.5 w-3.5 animate-spin" /> RENDERING
                                </span>
                              )}
                              {job.status === "PENDING" && (
                                <span className="inline-flex items-center rounded-full border border-gray-500/30 px-3 py-1 text-xs font-semibold bg-gray-500/10 text-gray-400">
                                  QUEUED
                                </span>
                              )}
                              {job.status === "FAILED" && (
                                <button
                                  onClick={() => setExpandedError(expandedError === job.id ? null : job.id)}
                                  className="inline-flex items-center rounded-full border border-rose-500/30 px-3 py-1 text-xs font-semibold bg-rose-500/10 text-rose-400 shadow-[0_0_10px_rgba(244,63,94,0.2)] cursor-pointer hover:bg-rose-500/20 transition-colors"
                                >
                                  <AlertCircle className="mr-1.5 h-3.5 w-3.5" /> FAILED
                                  {expandedError === job.id ? <ChevronUp className="ml-1 h-3 w-3" /> : <ChevronDown className="ml-1 h-3 w-3" />}
                                </button>
                              )}
                            </div>
                            <span className="text-xs text-muted-foreground font-mono">{job.progress_percent || 0}%</span>
                          </div>
                          {(job.status === "PROCESSING" || job.status === "SUCCESS") && (
                            <div className="w-full h-1.5 bg-white/5 rounded-full overflow-hidden">
                              <div
                                className={cn(
                                  "h-full transition-all duration-1000",
                                  job.status === "SUCCESS" ? "bg-emerald-500" : "bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.8)]"
                                )}
                                style={{ width: `${job.status === "SUCCESS" ? 100 : job.progress_percent || 0}%` }}
                              ></div>
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-muted-foreground/80">
                        {job.started_at && job.completed_at ? (
                          <div className="flex items-center gap-1.5 text-xs">
                            <Timer className="w-3.5 h-3.5 text-emerald-400" />
                            <span className="text-white font-medium">{formatDuration(job.started_at, job.completed_at)}</span>
                          </div>
                        ) : job.started_at ? (
                          <div className="flex items-center gap-1.5 text-xs">
                            <Clock className="w-3.5 h-3.5 text-blue-400 animate-spin" />
                            <span className="text-blue-400">In progress...</span>
                          </div>
                        ) : (
                          <span className="text-xs text-muted-foreground/50">—</span>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-muted-foreground/80 text-xs">
                        {format(new Date(job.created_at), "MMM dd, HH:mm")}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right">
                        <div className="flex items-center justify-end gap-2 text-muted-foreground">
                          {job.result_url && (
                            <>
                              <a
                                href={getMinioDownloadUrl(job.result_url)}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center justify-center rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 transition-all h-8 w-8 hover:shadow-[0_0_15px_rgba(16,185,129,0.3)]"
                                title="Download video"
                              >
                                <Download className="h-4 w-4" />
                              </a>
                              <a
                                href={getMinioBrowserUrl(job.result_url)}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center justify-center rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white border border-white/10 transition-all h-8 w-8"
                                title="Open in MinIO"
                              >
                                <ExternalLink className="h-4 w-4" />
                              </a>
                            </>
                          )}
                          <div className="w-px h-4 bg-white/10 mx-1"></div>
                          <button
                            onClick={() => handleViewDetails(job)}
                            className="p-1.5 rounded-lg hover:bg-indigo-500/10 hover:text-indigo-400 transition-colors"
                            title="View Terminal Logs & Config"
                          >
                            <Eye className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => handleDeleteJob(job.id)}
                            disabled={deletingId === job.id}
                            className="p-1.5 rounded-lg hover:bg-rose-500/10 hover:text-rose-400 transition-colors disabled:opacity-50"
                            title="Delete Job"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                    {/* Error detail row */}
                    {job.status === "FAILED" && expandedError === job.id && job.error_message && (
                      <tr key={`err-${job.id}`}>
                        <td colSpan={7} className="px-6 py-3 bg-rose-500/5 border-l-2 border-rose-500/40">
                          <p className="text-xs text-rose-300 font-mono break-all">{job.error_message}</p>
                        </td>
                      </tr>
                    )}
                  </>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Details Modal */}
      {selectedJob && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="glass-panel p-1 max-w-4xl w-full h-[80vh] flex flex-col animate-in zoom-in-95 duration-200 overflow-hidden border border-white/10 shadow-[0_0_40px_rgba(0,0,0,0.5)] rounded-2xl">
            <div className="flex items-center justify-between p-4 border-b border-white/10 bg-black/20">
              <div className="flex items-center gap-3">
                <div className="px-3 py-1 rounded bg-white/5 border border-white/10 font-mono text-sm font-semibold text-primary">
                  JOB #{selectedJob.id}
                </div>
                <div className="flex gap-1">
                  <button 
                    onClick={() => setActiveTab("logs")}
                    className={cn("px-4 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2", activeTab === "logs" ? "bg-white/10 text-white" : "text-muted-foreground hover:text-white hover:bg-white/5")}
                  >
                    <Terminal className="w-4 h-4" /> Terminal Logs
                  </button>
                  <button 
                    onClick={() => setActiveTab("config")}
                    className={cn("px-4 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2", activeTab === "config" ? "bg-white/10 text-white" : "text-muted-foreground hover:text-white hover:bg-white/5")}
                  >
                    <Code2 className="w-4 h-4" /> JSON Config
                  </button>
                </div>
              </div>
              <button onClick={() => setSelectedJob(null)} className="text-muted-foreground hover:text-white p-2 rounded-lg hover:bg-white/5 transition-colors">
                ✕
              </button>
            </div>
            
            <div className="flex-1 overflow-hidden relative">
              {activeTab === "logs" ? (
                <div className="absolute inset-0 bg-[#0D0D12] overflow-y-auto p-4 custom-scrollbar font-mono text-xs">
                  {loadingLogs && jobLogs.length === 0 ? (
                    <div className="text-muted-foreground flex items-center gap-2">Scanning terminal logs... <RefreshCw className="w-3 h-3 animate-spin" /></div>
                  ) : jobLogs.length === 0 ? (
                    <div className="text-muted-foreground/50 italic">No logs generated for this operation yet.</div>
                  ) : (
                    <div className="space-y-1.5">
                      {jobLogs.map((log, i) => (
                        <div key={i} className="flex gap-3 hover:bg-white/5 px-2 py-0.5 rounded transition-colors group">
                          <span className="text-emerald-500/50 shrink-0 select-none">[{format(new Date(log.created_at), "HH:mm:ss")}]</span>
                          <span className={cn(
                            "shrink-0 font-bold select-none",
                            log.log_level === "INFO" ? "text-blue-400" : log.log_level === "ERROR" ? "text-rose-400" : "text-amber-400"
                          )}>[{log.log_level}]</span>
                          <span className={cn("text-white/80 whitespace-pre-wrap break-all", log.log_level === "ERROR" && "text-rose-300 font-semibold")}>{log.message}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <div className="absolute inset-0 bg-[#1E1E2E] overflow-y-auto p-6 custom-scrollbar text-sm">
                  <pre className="text-[#a6accd] font-mono whitespace-pre-wrap">
                    <code dangerouslySetInnerHTML={{ __html: JSON.stringify(selectedJob.config_data, null, 2).replace(/"(.*?)"/g, '<span class="text-[#addb67]">"$1"</span>').replace(/(\d+)/g, '<span class="text-[#f78c6c]">$1</span>').replace(/(true|false|null)/g, '<span class="text-[#ff5874]">$1</span>') }} />
                  </pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
