import { useEffect, useState } from "react"
import axios from "axios"
import { format } from "date-fns"
import { PlayCircle, AlertCircle, Clock, CheckCircle2, LayoutDashboard, RefreshCw } from "lucide-react"
import { cn } from "../lib/utils"

interface VideoJob {
  id: number
  job_type: string
  status: "PENDING" | "PROCESSING" | "SUCCESS" | "FAILED"
  priority: number
  progress_percent: number
  result_url: string | null
  error_message: string | null
  created_at: string
}

export default function Dashboard() {
  const [jobs, setJobs] = useState<VideoJob[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const fetchJobs = async () => {
    try {
      const res = await axios.get("http://localhost:8000/api/jobs")
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
    const interval = setInterval(fetchJobs, 10000)
    return () => clearInterval(interval)
  }, [])

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
        
        <button 
          onClick={handleRefresh}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-white transition-all text-sm font-medium"
        >
          <RefreshCw className={cn("w-4 h-4", refreshing && "animate-spin")} /> 
          Refresh status
        </button>
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
                <th className="px-6 py-5 font-semibold tracking-wider">Created At</th>
                <th className="px-6 py-5 font-semibold tracking-wider text-right">Result</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {loading && jobs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-3">
                      <RefreshCw className="w-6 h-6 animate-spin text-primary" />
                      Connecting to Render Farm...
                    </div>
                  </td>
                </tr>
              ) : jobs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <AlertCircle className="w-6 h-6 text-muted-foreground/50" />
                      No video jobs found in the queue.
                    </div>
                  </td>
                </tr>
              ) : (
                jobs.map((job) => (
                  <tr key={job.id} className="hover:bg-white/[0.02] transition-colors group">
                    <td className="px-6 py-4 whitespace-nowrap font-medium text-white/90">
                      #{job.id}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="inline-flex items-center px-2.5 py-1 rounded-md bg-white/5 border border-white/10 text-xs font-medium text-indigo-300 capitalize tracking-wide">
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
                    <td className="px-6 py-4 whitespace-nowrap min-w-[200px]">
                      <div className="flex flex-col gap-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            {job.status === "SUCCESS" && (
                              <span className="inline-flex items-center rounded-full border border-emerald-500/30 px-3 py-1 text-xs font-semibold bg-emerald-500/10 text-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.2)]">
                                <CheckCircle2 className="mr-1.5 h-3.5 w-3.5"/> SUCCESS
                              </span>
                            )}
                            {job.status === "PROCESSING" && (
                              <span className="inline-flex items-center rounded-full border border-blue-500/30 px-3 py-1 text-xs font-semibold bg-blue-500/10 text-blue-400 shadow-[0_0_10px_rgba(59,130,246,0.2)]">
                                <Clock className="mr-1.5 h-3.5 w-3.5 animate-spin"/> {job.status}
                              </span>
                            )}
                            {job.status === "PENDING" && (
                              <span className="inline-flex items-center rounded-full border border-gray-500/30 px-3 py-1 text-xs font-semibold bg-gray-500/10 text-gray-400">
                                PENDING
                              </span>
                            )}
                            {job.status === "FAILED" && (
                              <span className="inline-flex items-center rounded-full border border-rose-500/30 px-3 py-1 text-xs font-semibold bg-rose-500/10 text-rose-400 shadow-[0_0_10px_rgba(244,63,94,0.2)]" title={job.error_message || "Error"}>
                                <AlertCircle className="mr-1.5 h-3.5 w-3.5"/> FAILED
                              </span>
                            )}
                          </div>
                          <span className="text-xs text-muted-foreground font-mono">{job.progress_percent || 0}%</span>
                        </div>
                        {job.status === "PROCESSING" && (
                          <div className="w-full h-1.5 bg-white/5 rounded-full overflow-hidden">
                            <div className="h-full bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.8)] transition-all duration-1000" style={{ width: `${job.progress_percent || 0}%` }}></div>
                          </div>
                        )}
                        {job.status === "SUCCESS" && (
                          <div className="w-full h-1.5 bg-white/5 rounded-full overflow-hidden">
                            <div className="h-full bg-emerald-500 transition-all duration-1000" style={{ width: '100%' }}></div>
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-muted-foreground/80">
                      {format(new Date(job.created_at), "yyyy-MM-dd HH:mm")}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      {job.result_url ? (
                        <a 
                          href={job.result_url.replace("s3://videos/", "http://localhost:9001/browser/videos/")} 
                          target="_blank" 
                          rel="noreferrer" 
                          className="inline-flex items-center justify-center rounded-full bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 transition-all h-9 w-9 shadow-[0_0_15px_rgba(16,185,129,0.2)] hover:shadow-[0_0_20px_rgba(16,185,129,0.4)] group-hover:scale-110"
                        >
                          <PlayCircle className="h-5 w-5" />
                        </a>
                      ) : (
                        <span className="text-muted-foreground/50 pr-4">-</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
