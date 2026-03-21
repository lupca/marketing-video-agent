import { useState, useEffect } from "react";
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

export default function Dashboard() {
  const navigate = useNavigate();
  const { jobs, loading, refreshing, fetchJobs, deleteJob, getDownloadUrl, getJobLogs, hasProcessing } = useJobs(true, 5000);
  
  const [selectedJob, setSelectedJob] = useState<VideoJob | null>(null);
  const [jobLogs, setJobLogs] = useState<JobLog[]>([]);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [watchUrl, setWatchUrl] = useState<string | null>(null);

  const handleRefresh = () => fetchJobs(true);

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
    navigate(`/create-${job.job_type}?clone=${job.id}`);
  };

  const stats = [
    { label: "Total Jobs", value: jobs.length, color: "text-white" },
    { label: "Success", value: jobs.filter(j => j.status === "SUCCESS").length, color: "text-emerald-400" },
    { label: "Processing", value: jobs.filter(j => j.status === "PROCESSING").length, color: "text-blue-400" },
    { label: "Failed", value: jobs.filter(j => j.status === "FAILED").length, color: "text-rose-400" },
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

      <div className="grid grid-cols-4 gap-4">
        {stats.map(stat => (
          <Card key={stat.label} className="p-5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{stat.label}</p>
            <p className={cn("text-3xl font-bold mt-1", stat.color)}>{stat.value}</p>
          </Card>
        ))}
      </div>

      <Card className="overflow-hidden">
        {loading && jobs.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-12 text-muted-foreground gap-3">
            <RefreshCw className="w-6 h-6 animate-spin text-primary" />
            Connecting to Render Farm...
          </div>
        ) : (
          <JobTable
            jobs={jobs}
            deletingId={deletingId}
            onViewDetails={handleViewDetails}
            onDeleteJob={handleDeleteJob}
            onDownloadJob={handleDownloadJob}
            onWatchJob={handleWatchJob}
            onCopyJob={handleCopyJob}
          />
        )}
      </Card>

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
