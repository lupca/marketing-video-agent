import React, { useState } from "react";
import { CheckCircle2, Clock, AlertCircle, ChevronDown, ChevronUp, Timer, Download, ExternalLink, Eye, Trash2, Play, Copy } from "lucide-react";
import { cn } from "../../../lib/utils";
import { formatDuration, formatDate } from "../../../lib/format";
import type { VideoJob } from "../../../hooks/useJobs";

export function getMinioBrowserUrl(s3Url: string): string {
  // s3://videos/outputs/review_job_4.mp4 → http://localhost:9001/browser/videos/outputs/review_job_4.mp4
  // We keep this purely for linking directly to minio console.
  return s3Url.replace("s3://", "http://localhost:9001/browser/");
}

interface JobTableProps {
  jobs: VideoJob[];
  onViewDetails: (job: VideoJob) => void;
  onDeleteJob: (id: number) => void;
  onDownloadJob: (id: number) => void;
  onWatchJob?: (id: number) => void;
  onCopyJob?: (job: VideoJob) => void;
  deletingId: number | null;
}

export function JobTable({ jobs, onViewDetails, onDeleteJob, onDownloadJob, onWatchJob, onCopyJob, deletingId }: JobTableProps) {
  const [expandedError, setExpandedError] = useState<number | null>(null);

  if (jobs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-muted-foreground gap-2">
        <AlertCircle className="w-6 h-6 text-muted-foreground/50" />
        No video jobs found. Create your first job!
      </div>
    );
  }

  return (
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
          {jobs.map((job) => (
            <React.Fragment key={job.id}>
              <tr className="hover:bg-white/[0.02] transition-colors group">
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
                    {/* Progress bar */}
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
                  {formatDate(job.created_at)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right">
                  <div className="flex items-center justify-end gap-2 text-muted-foreground">
                    {job.result_url && (
                      <>
                        <button
                          onClick={() => onDownloadJob(job.id)}
                          className="inline-flex items-center justify-center rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white border border-white/10 transition-all h-8 w-8"
                          title="Download video"
                        >
                          <Download className="h-4 w-4" />
                        </button>
                        {onWatchJob && (
                          <button
                            onClick={() => onWatchJob(job.id)}
                            className="inline-flex items-center justify-center rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 transition-all h-8 w-8 hover:shadow-[0_0_15px_rgba(16,185,129,0.3)]"
                            title="Watch Video"
                          >
                            <Play className="h-4 w-4" />
                          </button>
                        )}
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
                    {onCopyJob && (
                      <button
                        onClick={() => onCopyJob(job)}
                        className="p-1.5 rounded-lg hover:bg-amber-500/10 hover:text-amber-400 transition-colors"
                        title="Sao chép & Chỉnh sửa"
                      >
                        <Copy className="h-4 w-4" />
                      </button>
                    )}
                    <button
                      onClick={() => onViewDetails(job)}
                      className="p-1.5 rounded-lg hover:bg-indigo-500/10 hover:text-indigo-400 transition-colors"
                      title="View Terminal Logs & Config"
                    >
                      <Eye className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => onDeleteJob(job.id)}
                      disabled={deletingId === job.id}
                      className="p-1.5 rounded-lg hover:bg-rose-500/10 hover:text-rose-400 transition-colors disabled:opacity-50"
                      title="Delete Job"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
              {/* Error Detail Row */}
              {job.status === "FAILED" && expandedError === job.id && job.error_message && (
                <tr className="border-0">
                  <td colSpan={7} className="px-6 py-3 bg-rose-500/5 border-l-2 border-rose-500/40">
                    <p className="text-xs text-rose-300 font-mono break-all whitespace-pre-wrap">{job.error_message}</p>
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
