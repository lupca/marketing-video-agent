import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { LayoutDashboard, RefreshCw } from "lucide-react";
import { cn } from "../lib/utils";
import { useJobs } from "../hooks/useJobs";
import type { VideoJob, JobLog } from "../hooks/useJobs";
import { JobTable } from "../components/features/jobs/JobTable";
import { JobDetailsModal } from "../components/features/jobs/JobDetailsModal";
import { VideoPlayerModal } from "../components/features/jobs/VideoPlayerModal";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Pagination } from "../components/ui/Pagination";


export default function Dashboard() {
  const navigate = useNavigate();
  const { jobs, loading, refreshing, fetchJobs, deleteJob, getDownloadUrl, getJobLogs, updateJob, hasProcessing } = useJobs(true, 5000);
  
  const [selectedJob, setSelectedJob] = useState<VideoJob | null>(null);
  const [jobLogs, setJobLogs] = useState<JobLog[]>([]);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [watchUrl, setWatchUrl] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>("all");
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);

  // Sorting state for video jobs
  const [sortField, setSortField] = useState<'id' | 'type' | 'priority' | 'status' | 'duration' | 'created_at'>('created_at');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  const handleSort = (field: 'id' | 'type' | 'priority' | 'status' | 'duration' | 'created_at') => {
    if (sortField === field) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection(field === 'created_at' ? 'desc' : 'asc');
    }
  };

  // Reset page when sorting changes
  useEffect(() => {
    setCurrentPage(1);
  }, [sortField, sortDirection]);

  const handleRefresh = () => fetchJobs(true);
  
  const handleTabChange = (tab: string) => {
    setActiveTab(tab);
    setCurrentPage(1);
  };

  const handleViewDetails = async (job: VideoJob) => {
    setSelectedJob(job);
    setLoadingLogs(true);
    setJobLogs([]);
    try {
      const logs = await getJobLogs(job.id);
      setJobLogs(logs);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingLogs(false);
    }
  };

  useEffect(() => {
    let interval: any;
    if (selectedJob && selectedJob.status === "PROCESSING") {
      interval = setInterval(async () => {
        try {
          const logs = await getJobLogs(selectedJob.id);
          setJobLogs(logs);
        } catch (e) {}
      }, 3000);
    }
    return () => clearInterval(interval);
  }, [selectedJob, getJobLogs]);

  const handleDeleteJob = async (id: number) => {
    if (!confirm("Permanently delete this job and its resources?")) return;
    setDeletingId(id);
    try {
      await deleteJob(id);
    } catch (e) {
      console.error(e);
      alert("Failed to delete job");
    } finally {
      setDeletingId(null);
    }
  };

  const handleDownloadJob = async (id: number) => {
    try {
      const url = await getDownloadUrl(id);
      if (url) window.open(url, "_blank");
    } catch (e: any) {
      console.error(e);
      alert(e?.response?.data?.detail || "Lỗi khi tải URL (Check API/MinIO)");
    }
  };

  const handleWatchJob = async (id: number) => {
    try {
      const url = await getDownloadUrl(id);
      if (url) setWatchUrl(url);
    } catch (e: any) {
      console.error(e);
      alert(e?.response?.data?.detail || "Failed to get watch URL");
    }
  };

  const handleCopyJob = (job: VideoJob) => {
    const path = job.job_type === "unbox_viral" ? "viral" : job.job_type;
    navigate(`/create-${path}?clone=${job.id}`);
  };

  const jobTypes = Array.from(new Set(jobs.map(j => j.job_type))).sort();
  const displayJobs = jobs.filter(job => activeTab === "all" || job.job_type === activeTab);

  const sortedJobs = useMemo(() => {
    const list = [...displayJobs];
    list.sort((a, b) => {
      let compareVal = 0;
      if (sortField === "id") {
        compareVal = a.id - b.id;
      } else if (sortField === "type") {
        compareVal = a.job_type.localeCompare(b.job_type);
      } else if (sortField === "priority") {
        compareVal = a.priority - b.priority;
      } else if (sortField === "status") {
        compareVal = a.status.localeCompare(b.status);
      } else if (sortField === "duration") {
        const getDurationMs = (j: VideoJob) => {
          if (j.started_at && j.completed_at) {
            return new Date(j.completed_at).getTime() - new Date(j.started_at).getTime();
          }
          if (j.started_at) {
            return new Date().getTime() - new Date(j.started_at).getTime(); // Running
          }
          return 0;
        };
        compareVal = getDurationMs(a) - getDurationMs(b);
      } else if (sortField === "created_at") {
        compareVal = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      }
      return sortDirection === "asc" ? compareVal : -compareVal;
    });
    return list;
  }, [displayJobs, sortField, sortDirection]);

  const paginatedJobs = useMemo(() => {
    return sortedJobs.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);
  }, [sortedJobs, currentPage, itemsPerPage]);

  const formatJobType = (type: string) => {
    switch (type) {
      case 'unbox_viral': return "Viral Shorts";
      case 'unbox': return "Unbox Standard";
      case 'review': return "Review Details";
      case 'slideshow': return "Slideshow";
      case 'promotion': return "Viral Promotion";
      case 'capcut': return "CapCut Draft";
      default: return type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }
  };

  const getJobTypeColor = (type: string, isActive: boolean) => {
    if (isActive) {
      switch (type) {
        case 'review': return "bg-indigo-500/20 text-indigo-400 shadow-sm ring-1 ring-indigo-500/30";
        case 'unbox': return "bg-cyan-500/20 text-cyan-400 shadow-sm ring-1 ring-cyan-500/30";
        case 'unbox_viral': return "bg-amber-500/20 text-amber-500 shadow-sm ring-1 ring-amber-500/30";
        case 'slideshow': return "bg-pink-500/20 text-pink-400 shadow-sm ring-1 ring-pink-500/30";
        case 'promotion': return "bg-orange-500/20 text-orange-400 shadow-sm ring-1 ring-orange-500/30";
        case 'capcut': return "bg-rose-500/20 text-rose-400 shadow-sm ring-1 ring-rose-500/30";
        default: return "bg-primary/20 text-primary shadow-sm ring-1 ring-primary/30";
      }
    }
    return "text-muted-foreground hover:text-white hover:bg-white/5";
  };

  const stats = [
    { label: "Total Jobs", value: displayJobs.length, color: "text-white" },
    { label: "Success", value: displayJobs.filter(j => j.status === "SUCCESS").length, color: "text-emerald-400" },
    { label: "Processing", value: displayJobs.filter(j => j.status === "PROCESSING").length, color: "text-blue-400" },
    { label: "Failed", value: displayJobs.filter(j => j.status === "FAILED").length, color: "text-rose-400" },
  ];

  return (
    <div className="max-w-7xl mx-auto p-8 lg:p-12 space-y-10 animate-in fade-in duration-500">
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
          <Button onClick={handleRefresh} variant="secondary" isLoading={refreshing}>
            {!refreshing && <RefreshCw className="w-4 h-4 mr-2" />}
            Refresh
          </Button>
        </div>
      </div>

      {jobs.length > 0 && jobTypes.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 bg-black/20 p-1.5 rounded-2xl w-fit border border-white/5 shadow-inner">
          <button
            onClick={() => handleTabChange("all")}
            className={cn(
              "px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200",
              activeTab === "all" ? "bg-white/15 text-white shadow-sm ring-1 ring-white/20" : "text-muted-foreground hover:text-white hover:bg-white/5"
            )}
          >
            All Types ({jobs.length})
          </button>
          {jobTypes.map(type => (
            <button
              key={type}
              onClick={() => handleTabChange(type)}
              className={cn(
                "px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200",
                getJobTypeColor(type, activeTab === type)
              )}
            >
              {formatJobType(type)} ({jobs.filter(j => j.job_type === type).length})
            </button>
          ))}
        </div>
      )}

      {displayJobs.length > 0 && (
        <div className="grid grid-cols-4 gap-4">
          {stats.map(stat => (
            <Card key={stat.label} className="p-5">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{stat.label}</p>
              <p className={cn("text-3xl font-bold mt-1", stat.color)}>{stat.value}</p>
            </Card>
          ))}
        </div>
      )}

      <div className="space-y-4">
        <Card className="overflow-hidden">
          {loading && jobs.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-12 text-muted-foreground gap-3">
              <RefreshCw className="w-6 h-6 animate-spin text-primary" />
              Connecting to Render Farm...
            </div>
          ) : jobs.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-12 text-muted-foreground gap-2">
              No video jobs found.
            </div>
          ) : displayJobs.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-12 text-muted-foreground gap-2">
              No videos in this format.
            </div>
          ) : (
            <JobTable
              jobs={paginatedJobs}
              deletingId={deletingId}
              onViewDetails={handleViewDetails}
              onDeleteJob={handleDeleteJob}
              onDownloadJob={handleDownloadJob}
              onWatchJob={handleWatchJob}
              onCopyJob={handleCopyJob}
              onUpdateNote={updateJob}
              sortField={sortField}
              sortDirection={sortDirection}
              onSort={handleSort}
            />
          )}
        </Card>

        {displayJobs.length > 0 && (
          <Pagination
            currentPage={currentPage}
            totalItems={displayJobs.length}
            itemsPerPage={itemsPerPage}
            onPageChange={setCurrentPage}
            onItemsPerPageChange={setItemsPerPage}
          />
        )}
      </div>

      {selectedJob && (
        <JobDetailsModal
          job={selectedJob}
          logs={jobLogs}
          loadingLogs={loadingLogs}
          onClose={() => setSelectedJob(null)}
        />
      )}
      
      {watchUrl && (
        <VideoPlayerModal 
          url={watchUrl} 
          onClose={() => setWatchUrl(null)} 
        />
      )}
    </div>
  );
}
