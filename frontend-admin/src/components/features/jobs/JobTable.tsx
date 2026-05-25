import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CheckCircle2, Clock, AlertCircle, ChevronDown, ChevronUp, Timer, Download, ExternalLink, Eye, Trash2, Play, Copy, Wand2, FileText } from "lucide-react";
import { cn } from "../../../lib/utils";
import { formatDuration, formatDate } from "../../../lib/format";
import type { VideoJob } from "../../../hooks/useJobs";
import api from "../../../lib/api";


function getCreatePath(jobType: string): string {
  if (jobType === "unbox_viral") return "viral";
  return jobType;
}

function getMinioBrowserUrl(s3Url: string): string {
  // s3://videos/outputs/review_job_4.mp4 → http://localhost:9001/browser/videos/outputs/review_job_4.mp4
  // We keep this purely for linking directly to minio console.
  return s3Url.replace("s3://", "http://localhost:9001/browser/");
}

interface JobTableProps {
  jobs: VideoJob[];
  onViewDetails: (job: VideoJob) => void;
  onDeleteJob: (id: number) => void;
  onDownloadJob: (id: number) => void;
  onUpdateNote?: (id: number, note: string) => void;
  onWatchJob?: (id: number) => void;
  onCopyJob?: (job: VideoJob) => void;
  deletingId: number | null;

  // Sorting props
  sortField?: 'id' | 'type' | 'priority' | 'status' | 'duration' | 'created_at';
  sortDirection?: 'asc' | 'desc';
  onSort?: (field: 'id' | 'type' | 'priority' | 'status' | 'duration' | 'created_at') => void;
}

export function JobTable({ 
  jobs, 
  onViewDetails, 
  onDeleteJob, 
  onDownloadJob, 
  onUpdateNote, 
  onWatchJob, 
  onCopyJob, 
  deletingId,
  sortField,
  sortDirection,
  onSort
}: JobTableProps) {
  const [expandedError, setExpandedError] = useState<number | null>(null);
  const navigate = useNavigate();
  const [reopeningId, setReopeningId] = useState<number | null>(null);

  const handleReopen = async (jobId: number) => {
    setReopeningId(jobId);
    try {
      await api.post(`/api/translify/projects/${jobId}/reopen`);
      navigate(`/translify/editor/${jobId}`);
    } catch (e: any) {
      console.error(e);
      alert("Không thể mở lại kịch bản: " + (e?.response?.data?.detail || e.message));
    } finally {
      setReopeningId(null);
    }
  };

  const renderSortIcon = (field: 'id' | 'type' | 'priority' | 'status' | 'duration' | 'created_at') => {
    const isActive = sortField === field;
    if (!isActive) {
      return (
        <span className="inline-flex flex-col ml-1.5 opacity-30 group-hover:opacity-75 transition-opacity">
          <ChevronUp className="w-2.5 h-2.5 -mb-0.5" />
          <ChevronDown className="w-2.5 h-2.5" />
        </span>
      );
    }
    return (
      <span className="inline-flex ml-1.5 text-primary">
        {sortDirection === 'asc' ? (
          <ChevronUp className="w-3.5 h-3.5 drop-shadow-[0_0_8px_rgba(238,76,124,0.5)]" />
        ) : (
          <ChevronDown className="w-3.5 h-3.5 drop-shadow-[0_0_8px_rgba(238,76,124,0.5)]" />
        )}
      </span>
    );
  };

  if (jobs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-muted-foreground gap-2">
        <AlertCircle className="w-6 h-6 text-muted-foreground/50" />
        No video jobs found. Create your first job!
      </div>
    );
  }

  return (
    <div className="w-full overflow-x-auto custom-scrollbar">
      <table className="w-full text-sm text-left border-collapse">
        <thead className="bg-black/40 text-xs uppercase text-muted-foreground border-b border-white/10 select-none">
          <tr>
            <th 
              onClick={() => onSort?.('id')}
              className="px-4 py-4 font-semibold tracking-wider cursor-pointer group hover:text-white transition-colors"
            >
              <div className="flex items-center">
                <span>Job ID</span>
                {renderSortIcon('id')}
              </div>
            </th>
            <th 
              onClick={() => onSort?.('type')}
              className="px-4 py-4 font-semibold tracking-wider cursor-pointer group hover:text-white transition-colors"
            >
              <div className="flex items-center">
                <span>Type</span>
                {renderSortIcon('type')}
              </div>
            </th>
            <th 
              onClick={() => onSort?.('priority')}
              className="px-4 py-4 font-semibold tracking-wider cursor-pointer group hover:text-white transition-colors hidden sm:table-cell"
            >
              <div className="flex items-center">
                <span>Priority</span>
                {renderSortIcon('priority')}
              </div>
            </th>
            <th 
              onClick={() => onSort?.('status')}
              className="px-4 py-4 font-semibold tracking-wider cursor-pointer group hover:text-white transition-colors"
            >
              <div className="flex items-center">
                <span>Status & Progress</span>
                {renderSortIcon('status')}
              </div>
            </th>
            <th 
              onClick={() => onSort?.('duration')}
              className="px-4 py-4 font-semibold tracking-wider cursor-pointer group hover:text-white transition-colors hidden md:table-cell"
            >
              <div className="flex items-center">
                <span>Duration</span>
                {renderSortIcon('duration')}
              </div>
            </th>
            <th 
              onClick={() => onSort?.('created_at')}
              className="px-4 py-4 font-semibold tracking-wider cursor-pointer group hover:text-white transition-colors hidden lg:table-cell"
            >
              <div className="flex items-center">
                <span>Created</span>
                {renderSortIcon('created_at')}
              </div>
            </th>
            <th className="px-4 py-4 font-semibold tracking-wider hidden xl:table-cell">Note</th>
            <th className="px-4 py-4 font-semibold tracking-wider text-right">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5">
          {jobs.map((job) => (
            <React.Fragment key={job.id}>
              <tr className="hover:bg-white/[0.015] transition-colors group">
                <td className="px-4 py-3 whitespace-nowrap font-medium text-white/90">
                  #{job.id}
                </td>
                <td className="px-4 py-3 whitespace-nowrap">
                  <span className={cn(
                    "inline-flex items-center px-2 py-0.5 rounded-md bg-white/5 border border-white/10 text-[10px] font-bold capitalize tracking-wide",
                    job.job_type === "review" ? "text-indigo-300 border-indigo-500/20" :
                    job.job_type === "leader" ? "text-violet-300 border-violet-500/20 bg-violet-500/5 shadow-[0_0_8px_rgba(139,92,246,0.15)]" :
                    job.job_type === "translify" ? "text-emerald-300 border-emerald-500/20" :
                    job.job_type === "slideshow" ? "text-amber-300 border-amber-500/20" :
                    job.job_type === "capcut" ? "text-rose-300 border-rose-500/20 bg-rose-500/5 shadow-[0_0_8px_rgba(244,63,94,0.15)]" :
                    "text-cyan-300"
                  )}>
                    {job.job_type === "leader" ? "AI Leader" : job.job_type === "capcut" ? "CapCut Draft" : job.job_type}
                  </span>
                </td>
                <td className="px-4 py-3 whitespace-nowrap hidden sm:table-cell">
                  {job.priority > 0 ? (
                    <span className="inline-flex items-center px-2 py-0.5 rounded border border-orange-500/30 text-[9px] font-bold text-orange-400 uppercase">
                      High
                    </span>
                  ) : (
                    <span className="inline-flex items-center px-2 py-0.5 rounded border border-white/10 text-[9px] font-medium text-muted-foreground uppercase">
                      Normal
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 whitespace-nowrap min-w-[180px] sm:min-w-[220px]">
                  <div className="flex flex-col gap-1.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        {job.status === "SUCCESS" && (
                          <span className="inline-flex items-center rounded-full border border-emerald-500/30 px-2 py-0.5 text-[10px] font-bold bg-emerald-500/10 text-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.2)]">
                            <CheckCircle2 className="mr-1 h-3 w-3" /> SUCCESS
                          </span>
                        )}
                        {job.status === "PROCESSING" && (
                          <span className="inline-flex items-center rounded-full border border-blue-500/30 px-2 py-0.5 text-[10px] font-bold bg-blue-500/10 text-blue-400 shadow-[0_0_10px_rgba(59,130,246,0.2)]">
                            <Clock className="mr-1 h-3 w-3 animate-spin" /> RENDERING
                          </span>
                        )}
                        {job.status === "PENDING" && (
                          <span className="inline-flex items-center rounded-full border border-gray-500/30 px-2 py-0.5 text-[10px] font-bold bg-gray-500/10 text-gray-400">
                            QUEUED
                          </span>
                        )}
                        {job.status === "DRAFT" && (
                          <span className="inline-flex items-center rounded-full border border-yellow-500/30 px-2 py-0.5 text-[10px] font-bold bg-yellow-500/10 text-yellow-400 shadow-[0_0_10px_rgba(234,179,8,0.2)]">
                            <FileText className="mr-1 h-3 w-3" /> DRAFT
                          </span>
                        )}
                        {job.status === "DRAFT" && (
                          <Link
                            to={`/create-${getCreatePath(job.job_type)}?clone=${job.id}&delete_draft=${job.id}`}
                            className="inline-flex items-center justify-center rounded bg-yellow-500/10 hover:bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 transition-all h-6 px-2 text-[9px] uppercase font-bold hover:shadow-[0_0_15px_rgba(234,179,8,0.3)] gap-0.5 shrink-0"
                            title="Edit and Publish Draft"
                          >
                            <Wand2 className="h-3 w-3" /> Edit & Publish
                          </Link>
                        )}
                        {job.status === "WAITING_FOR_REVIEW" && (
                          <span className="inline-flex items-center rounded-full border border-amber-500/30 px-2 py-0.5 text-[10px] font-bold bg-amber-500/10 text-amber-400 shadow-[0_0_10px_rgba(245,158,11,0.2)]">
                            <Eye className="mr-1 h-3 w-3" /> REVIEW NEEDED
                          </span>
                        )}
                        {job.status === "FAILED" && (
                          <button
                            onClick={() => setExpandedError(expandedError === job.id ? null : job.id)}
                            className="inline-flex items-center rounded-full border border-rose-500/30 px-2 py-0.5 text-[10px] font-bold bg-rose-500/10 text-rose-400 shadow-[0_0_10px_rgba(244,63,94,0.2)] cursor-pointer hover:bg-rose-500/20 transition-colors"
                          >
                            <AlertCircle className="mr-1 h-3 w-3" /> FAILED
                            {expandedError === job.id ? <ChevronUp className="ml-0.5 h-3 w-3" /> : <ChevronDown className="ml-0.5 h-3 w-3" />}
                          </button>
                        )}
                      </div>
                      <span className="text-[10px] text-muted-foreground font-mono">{job.progress_percent || 0}%</span>
                    </div>
                    {/* Progress bar */}
                    {(job.status === "PROCESSING" || job.status === "SUCCESS") && (
                      <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden">
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
                <td className="px-4 py-3 whitespace-nowrap hidden md:table-cell text-muted-foreground/80">
                  {job.started_at && job.completed_at ? (
                    <div className="flex items-center gap-1.5 text-[11px]">
                      <Timer className="w-3 h-3 text-emerald-400" />
                      <span className="text-white font-medium">{formatDuration(job.started_at, job.completed_at)}</span>
                    </div>
                  ) : job.started_at ? (
                    <div className="flex items-center gap-1.5 text-[11px]">
                      <Clock className="w-3 h-3 text-blue-400 animate-spin" />
                      <span className="text-blue-400">In progress...</span>
                    </div>
                  ) : (
                    <span className="text-[11px] text-muted-foreground/50">—</span>
                  )}
                </td>
                <td className="px-4 py-3 whitespace-nowrap hidden lg:table-cell text-muted-foreground/80 text-xs">
                  {formatDate(job.created_at)}
                </td>
                <td className="px-4 py-3 hidden xl:table-cell max-w-[140px]">
                  <input
                    type="text"
                    defaultValue={job.note || ""}
                    placeholder="Ghi chú..."
                    className="w-full max-w-[130px] bg-white/5 border border-white/10 rounded px-2 py-0.5 text-xs text-white/80 focus:outline-none focus:border-primary/50 transition-colors truncate"
                    onBlur={(e) => {
                      if (onUpdateNote && e.target.value !== (job.note || "")) {
                        onUpdateNote(job.id, e.target.value);
                      }
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.currentTarget.blur();
                      }
                    }}
                  />
                </td>
                <td className="px-4 py-3 whitespace-nowrap text-right">
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
                    {job.status === "WAITING_FOR_REVIEW" && (
                      <Link
                        to={`/translify/editor/${job.id}`}
                        className="inline-flex items-center justify-center rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30 transition-all h-8 px-2.5 text-[10px] uppercase font-bold hover:shadow-[0_0_15px_rgba(245,158,11,0.3)] gap-1 shrink-0"
                        title="Refine Translation"
                      >
                        <Play className="h-3 w-3 fill-current" /> Refine Script
                      </Link>
                    )}
                    {job.job_type === "translify" && job.status === "SUCCESS" && (
                      <button
                        onClick={() => handleReopen(job.id)}
                        disabled={reopeningId === job.id}
                        className="inline-flex items-center justify-center rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 transition-all h-8 px-2.5 text-[10px] uppercase font-bold hover:shadow-[0_0_15px_rgba(16,185,129,0.3)] gap-1 shrink-0 disabled:opacity-50"
                        title="Edit & render again"
                      >
                        {reopeningId === job.id ? <Clock className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3 fill-current" />}
                        Edit & Re-render
                      </button>
                    )}
                    {job.job_type === "translify" && job.status === "FAILED" && (
                      <button
                        onClick={() => handleReopen(job.id)}
                        disabled={reopeningId === job.id}
                        className="inline-flex items-center justify-center rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 transition-all h-8 px-2.5 text-[10px] uppercase font-bold hover:shadow-[0_0_15px_rgba(244,63,94,0.3)] gap-1 shrink-0 disabled:opacity-50"
                        title="Edit script & try again"
                      >
                        {reopeningId === job.id ? <Clock className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3 fill-current" />}
                        Retry
                      </button>
                    )}
                    {job.job_type === "capcut" && (
                      <Link
                        to={`/create-capcut?clone=${job.id}`}
                        className="inline-flex items-center justify-center rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 transition-all h-8 px-2.5 text-[10px] uppercase font-bold hover:shadow-[0_0_15px_rgba(244,63,94,0.3)] gap-1.5 shrink-0"
                        title="Chỉnh sửa dòng thời gian CapCut"
                      >
                        <Wand2 className="h-3 w-3" /> Sửa Draft
                      </Link>
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
                  <td colSpan={8} className="px-4 py-3 bg-rose-500/5 border-l-2 border-rose-500/40">
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
