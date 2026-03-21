import { useState, useEffect } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { FolderHeart, ChevronLeft, RefreshCw, Plus, Activity, AlertCircle, Video } from "lucide-react";
import { useProjects } from "../hooks/useProjects";
import type { Project } from "../hooks/useProjects";
import { useJobs } from "../hooks/useJobs";
import type { VideoJob, JobLog } from "../hooks/useJobs";
import { JobTable } from "../components/features/jobs/JobTable";
import { JobDetailsModal } from "../components/features/jobs/JobDetailsModal";
import { VideoPlayerModal } from "../components/features/jobs/VideoPlayerModal";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";

export default function ProjectDetails() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { getProject } = useProjects();
  const { jobs, loading: jobsLoading, refreshing, fetchJobs, deleteJob, getDownloadUrl, getJobLogs, hasProcessing } = useJobs(true, 5000, id);
  
  const [project, setProject] = useState<Project | null>(null);
  const [loadingProj, setLoadingProj] = useState(true);
  const [errorProj, setErrorProj] = useState("");

  const [selectedJob, setSelectedJob] = useState<VideoJob | null>(null);
  const [jobLogs, setJobLogs] = useState<JobLog[]>([]);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [watchUrl, setWatchUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let isMounted = true;
    const loadProject = async () => {
      try {
        setLoadingProj(true);
        const p = await getProject(id);
        if (isMounted) setProject(p);
      } catch (err: any) {
        if (isMounted) setErrorProj("Project not found or access denied.");
      } finally {
        if (isMounted) setLoadingProj(false);
      }
    };
    loadProject();
    return () => { isMounted = false; };
  }, [id, getProject]);

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

  const handleDeleteJob = async (jobId: number) => {
    if (!confirm("Permanently delete this video job and its resources?")) return;
    setDeletingId(jobId);
    try {
      await deleteJob(jobId);
    } catch (e) {
      console.error(e);
      alert("Failed to delete job");
    } finally {
      setDeletingId(null);
    }
  };

  const handleDownloadJob = async (jobId: number) => {
    try {
      const url = await getDownloadUrl(jobId);
      if (url) window.open(url, "_blank");
    } catch (e: any) {
      console.error(e);
      alert(e?.response?.data?.detail || "Error getting download URL");
    }
  };

  const handleWatchJob = async (jobId: number) => {
    try {
      const url = await getDownloadUrl(jobId);
      if (url) setWatchUrl(url);
    } catch (e: any) {
      console.error(e);
      alert(e?.response?.data?.detail || "Error getting watch URL");
    }
  };

  const handleCopyJob = (job: VideoJob) => {
    navigate(`/create-${job.job_type}?clone=${job.id}`);
  };

  if (loadingProj) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center text-muted-foreground gap-4">
        <RefreshCw className="w-8 h-8 animate-spin text-primary" />
        <p>Loading project workspace...</p>
      </div>
    );
  }

  if (errorProj || !project) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-6">
        <div className="p-4 bg-rose-500/10 rounded-full border border-rose-500/20">
          <AlertCircle className="w-10 h-10 text-rose-400" />
        </div>
        <div className="text-center">
          <h2 className="text-2xl font-bold text-white mb-2">Workspace Not Found</h2>
          <p className="text-muted-foreground max-w-sm">{errorProj || "This project may have been deleted or doesn't exist."}</p>
        </div>
        <Link to="/projects">
          <Button variant="secondary">
            <ChevronLeft className="w-4 h-4 mr-2" /> Return to Projects
          </Button>
        </Link>
      </div>
    );
  }

  const successJobs = jobs.filter(j => j.status === "SUCCESS").length;
  const processingJobs = jobs.filter(j => j.status === "PROCESSING").length;
  const failedJobs = jobs.filter(j => j.status === "FAILED").length;

  return (
    <div className="max-w-7xl mx-auto p-8 lg:p-12 space-y-10 animate-in fade-in duration-500">
      {/* Header and Breadcrumb */}
      <div className="space-y-6">
        <Link 
          to="/projects" 
          className="inline-flex items-center text-sm font-medium text-muted-foreground hover:text-white transition-colors group"
        >
          <div className="p-1 rounded-md bg-white/5 mr-2 group-hover:bg-white/10 transition-colors">
            <ChevronLeft className="w-4 h-4" />
          </div>
          Back to Projects
        </Link>

        <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
          <div className="space-y-3">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-primary/20 to-indigo-500/20 flex items-center justify-center border border-white/10 shadow-[inset_0_0_20px_rgba(124,58,237,0.2)]">
                <FolderHeart className="w-7 h-7 text-primary drop-shadow-[0_0_12px_rgba(124,58,237,0.8)]" />
              </div>
              <div>
                <h1 className="text-4xl font-extrabold tracking-tight text-white line-clamp-1">{project.name}</h1>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-xs font-mono text-muted-foreground/70 bg-white/5 px-2 py-0.5 rounded border border-white/5">
                    ID: {project.id}
                  </span>
                </div>
              </div>
            </div>
            <p className="text-lg text-muted-foreground max-w-3xl leading-relaxed">
              {project.description || "No description provided for this workspace."}
            </p>
          </div>

          <div className="flex flex-col items-end gap-3 shrink-0">
            <div className="flex items-center gap-3">
              {hasProcessing && (
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-blue-500/10 border border-blue-500/20">
                  <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse shadow-[0_0_8px_rgba(59,130,246,0.8)]"></div>
                  <span className="text-xs text-blue-400 font-medium">Rendering Active</span>
                </div>
              )}
              <Button onClick={handleRefresh} variant="secondary" isLoading={refreshing}>
                {!refreshing && <RefreshCw className="w-4 h-4 mr-2" />}
                Refresh
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-5 bg-white/5 border-white/10 backdrop-blur-sm flex flex-col justify-center relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
            <Video className="w-12 h-12 text-white" />
          </div>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider relative z-10">Total Videos</p>
          <p className="text-3xl font-bold mt-1 text-white relative z-10">{jobs.length}</p>
        </Card>
        <Card className="p-5 bg-emerald-500/5 border-emerald-500/10 backdrop-blur-sm flex flex-col justify-center relative overflow-hidden group">
          <p className="text-xs font-semibold text-emerald-500/70 uppercase tracking-wider relative z-10">Success</p>
          <p className="text-3xl font-bold mt-1 text-emerald-400 relative z-10">{successJobs}</p>
        </Card>
        <Card className="p-5 bg-blue-500/5 border-blue-500/10 backdrop-blur-sm flex flex-col justify-center relative overflow-hidden group">
          <p className="text-xs font-semibold text-blue-500/70 uppercase tracking-wider relative z-10">Rendering</p>
          <p className="text-3xl font-bold mt-1 text-blue-400 relative z-10">{processingJobs}</p>
        </Card>
        <Card className="p-5 bg-rose-500/5 border-rose-500/10 backdrop-blur-sm flex flex-col justify-center relative overflow-hidden group">
          <p className="text-xs font-semibold text-rose-500/70 uppercase tracking-wider relative z-10">Failed</p>
          <p className="text-3xl font-bold mt-1 text-rose-400 relative z-10">{failedJobs}</p>
        </Card>
      </div>

      {/* Job Queue Table */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-bold text-white flex items-center gap-2">
            <Activity className="w-5 h-5 text-primary" /> Video Generation Queue
          </h3>
          <div className="flex gap-3">
             <Link to={`/create-unbox?project=${project.id}`}>
               <Button className="glowing-button text-xs py-1.5 h-9">
                 <Plus className="w-3.5 h-3.5 mr-1.5" /> New Unbox
               </Button>
             </Link>
             <Link to={`/create-review?project=${project.id}`}>
               <Button className="glowing-button text-xs py-1.5 h-9">
                 <Plus className="w-3.5 h-3.5 mr-1.5" /> New Review
               </Button>
             </Link>
          </div>
        </div>

        <Card className="overflow-hidden border-white/10 shadow-2xl">
          {jobsLoading && jobs.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-16 text-muted-foreground gap-4">
              <div className="p-4 rounded-full bg-white/5 border border-white/5">
                <RefreshCw className="w-6 h-6 animate-spin text-primary" />
              </div>
              Analyzing Rendering Queue...
            </div>
          ) : jobs.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-16 text-center gap-4 border-dashed border-white/10 m-4 rounded-2xl bg-white/5">
               <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mb-2">
                 <Video className="w-8 h-8 text-primary/60" />
               </div>
               <div>
                 <h4 className="text-lg font-bold text-white mb-1">Queue Empty</h4>
                 <p className="text-sm text-muted-foreground max-w-sm mx-auto">This project has no active or completed videos. Generate your first video to see it here.</p>
               </div>
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
