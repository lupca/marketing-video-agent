import { useEffect, useState } from "react"
import api from "../lib/api"
import { format } from "date-fns"
import { AlertCircle, Clock, CheckCircle2, LayoutDashboard, RefreshCw, Download, ChevronDown, ChevronUp, Timer, ExternalLink } from "lucide-react"
import { cn } from "../lib/utils"

interface VideoJob {
  id: number
  job_type: string
  status: "PENDING" | "PROCESSING" | "SUCCESS" | "FAILED"
  priority: number
  progress_percent: number
  result_url: string | null
  error_message: string | null
  started_at: string | null
  completed_at: string | null
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
                        {job.result_url ? (
                          <div className="flex items-center justify-end gap-2">
                            <a
                              href={getMinioDownloadUrl(job.result_url)}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center justify-center rounded-full bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 transition-all h-9 w-9 shadow-[0_0_15px_rgba(16,185,129,0.2)] hover:shadow-[0_0_20px_rgba(16,185,129,0.4)] group-hover:scale-110"
                              title="Download video"
                            >
                              <Download className="h-4 w-4" />
                            </a>
                            <a
                              href={getMinioBrowserUrl(job.result_url)}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center justify-center rounded-full bg-white/5 hover:bg-white/10 text-white/60 hover:text-white border border-white/10 transition-all h-9 w-9"
                              title="Open in MinIO Console"
                            >
                              <ExternalLink className="h-4 w-4" />
                            </a>
                          </div>
                        ) : (
                          <span className="text-muted-foreground/50 pr-4">—</span>
                        )}
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
    </div>
  )
}
