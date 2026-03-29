import { useState, useRef, useEffect } from "react";
import { DownloadCloud, AlertCircle, Send, RefreshCw, Terminal, Code2 } from "lucide-react";
import { format } from "date-fns";
import api from "../lib/api";
import { cn } from "../lib/utils";
import { useDownloadJobs } from "../hooks/useDownloadJobs";
import type { DownloadJob, DownloadJobLog } from "../hooks/useDownloadJobs";
import { DownloadJobTable } from "../components/features/downloads/DownloadJobTable";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Modal } from "../components/ui/Modal";

export default function DownloadVideo() {
  const { jobs, loading, refreshing, fetchJobs, deleteJob, getDownloadUrl, getJobLogs, hasActive } = useDownloadJobs(true, 5000);

  const [url, setUrl] = useState("");
  const [customFilename, setCustomFilename] = useState("");
  const [downloadFormat, setDownloadFormat] = useState<"video" | "audio">("video");
  const [submitting, setSubmitting] = useState(false);
  const [statusMsg, setStatusMsg] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Logs modal state
  const [selectedJob, setSelectedJob] = useState<DownloadJob | null>(null);
  const [jobLogs, setJobLogs] = useState<DownloadJobLog[]>([]);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const tableRef = useRef<HTMLDivElement>(null);

  const handleSubmit = async () => {
    if (!url.trim()) {
      return setError("Vui lòng nhập URL của video.");
    }

    try {
      setSubmitting(true);
      setError(null);
      setStatusMsg("Đang gửi yêu cầu tải video...");

      await api.post("/api/downloads", {
        url: url.trim(),
        format: downloadFormat,
        custom_filename: customFilename.trim() || undefined,
      });

      setUrl("");
      setCustomFilename("");
      // Refresh list and scroll to table
      await fetchJobs(true);
      setTimeout(() => {
        tableRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 200);
    } catch (err: any) {
      console.error(err);
      setError(err?.response?.data?.detail || err.message || "Đã xảy ra lỗi khi tạo yêu cầu.");
    } finally {
      setSubmitting(false);
      setStatusMsg("");
    }
  };

  const handleViewLogs = async (job: DownloadJob) => {
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

  // Auto-refresh logs when viewing a processing job
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
    if (!confirm("Xóa lượt tải này?")) return;
    setDeletingId(id);
    try {
      await deleteJob(id);
    } catch (e) {
      console.error(e);
      alert("Lỗi khi xóa job");
    } finally {
      setDeletingId(null);
    }
  };

  const handleDownloadResult = async (id: number) => {
    try {
      const downloadUrl = await getDownloadUrl(id);
      if (downloadUrl) window.open(downloadUrl, "_blank");
    } catch (e: any) {
      console.error(e);
      alert(e?.response?.data?.detail || "Lỗi khi tải file");
    }
  };

  const isFormValid = url.trim();

  const stats = [
    { label: "Tổng cộng", value: jobs.length, color: "text-white" },
    { label: "Hoàn tất", value: jobs.filter(j => j.status === "SUCCESS").length, color: "text-emerald-400" },
    { label: "Đang tải", value: jobs.filter(j => j.status === "PROCESSING").length, color: "text-blue-400" },
    { label: "Thất bại", value: jobs.filter(j => j.status === "FAILED").length, color: "text-rose-400" },
  ];

  return (
    <div className="max-w-7xl mx-auto p-8 lg:p-12 space-y-10">
      {/* Header */}
      <div className="space-y-2">
        <h2 className="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60">
          Sưu tầm Video
        </h2>
        <p className="text-muted-foreground text-lg">
          Dán đường link từ YouTube, TikTok,... hệ thống sẽ tải và trích xuất nguyên liệu video gốc với chất lượng cao nhất.
        </p>
      </div>

      {/* Form Section */}
      <div className="glass-panel p-6 lg:p-10 flex flex-col space-y-8 animate-in fade-in slide-in-from-bottom-4">
        
        {error && (
          <div className="p-4 bg-red-500/10 text-red-500 rounded-xl border border-red-500/20 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
            <p className="text-sm font-medium">{error}</p>
          </div>
        )}

        {/* Format Selection */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-white">
            <DownloadCloud className="w-5 h-5 text-primary" />
            <h3 className="text-lg font-semibold">1. Định dạng Tải</h3>
          </div>
          <div className="flex gap-4">
            <label className={cn(
              "flex-1 p-4 rounded-xl border cursor-pointer transition-all",
              downloadFormat === "video" 
                ? "bg-primary/20 border-primary/50 shadow-[0_0_15px_rgba(124,58,237,0.3)] ring-1 ring-primary/20" 
                : "bg-white/5 border-white/10 hover:bg-white/10"
            )}>
              <input type="radio" className="hidden" name="format" value="video" checked={downloadFormat === "video"} onChange={() => setDownloadFormat("video")} />
              <div className="font-medium text-white mb-1">Video (MP4)</div>
              <div className="text-xs opacity-70">Tải video độ phân giải cao nhất</div>
            </label>
            
            <label className={cn(
              "flex-1 p-4 rounded-xl border cursor-pointer transition-all",
              downloadFormat === "audio" 
                ? "bg-primary/20 border-primary/50 shadow-[0_0_15px_rgba(124,58,237,0.3)] ring-1 ring-primary/20" 
                : "bg-white/5 border-white/10 hover:bg-white/10"
            )}>
              <input type="radio" className="hidden" name="format" value="audio" checked={downloadFormat === "audio"} onChange={() => setDownloadFormat("audio")} />
              <div className="font-medium text-white mb-1">Chỉ lấy Nhạc (MP3)</div>
              <div className="text-xs opacity-70">Trích xuất âm thanh từ liên kết</div>
            </label>
          </div>
        </div>

        {/* Custom Filename Input */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-white">
            <Code2 className="w-5 h-5 text-primary" />
            <h3 className="text-lg font-semibold">2. Tên file lưu trữ (Tùy chọn)</h3>
          </div>
          <p className="text-sm text-muted-foreground">
            Nếu để trống, hệ thống sẽ tự động lấy tên từ tiêu đề video gốc.
          </p>
          <input
            type="text"
            disabled={submitting}
            placeholder="Ví dụ: video_review_san_pham_A"
            value={customFilename}
            onChange={(e) => setCustomFilename(e.target.value)}
            className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3.5 text-white focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all placeholder:text-muted-foreground/50 font-mono text-sm"
          />
        </div>

        <div className="w-full h-px bg-white/10"></div>

        {/* URL Input */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-white">
            <DownloadCloud className="w-5 h-5 text-primary" />
            <h3 className="text-lg font-semibold">3. Đường dẫn Link</h3>
          </div>
          <p className="text-sm text-muted-foreground">
            Hỗ trợ link từ YouTube, TikTok, Facebook v.v. (Ví dụ: https://www.youtube.com/shorts/...)
          </p>
          <input
            type="url"
            disabled={submitting}
            placeholder="Dán URL video tại đây..."
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && isFormValid && !submitting) handleSubmit(); }}
            className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3.5 text-white focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all placeholder:text-muted-foreground/50"
          />
        </div>

        {/* Action Button */}
        <div>
          <button
            onClick={handleSubmit}
            disabled={!isFormValid || submitting}
            className="w-full py-4 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white rounded-xl font-bold text-lg shadow-[0_0_20px_rgba(124,58,237,0.4)] transition-all flex items-center justify-center gap-3 disabled:opacity-50 disabled:cursor-not-allowed group"
          >
            {submitting ? (
              <>
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>{statusMsg || "Đang xử lý..."}</span>
              </>
            ) : (
              <>
                <Send className="w-5 h-5 group-hover:translate-x-1 group-hover:-translate-y-1 transition-transform" />
                <span>Bắt Đầu Tải</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Download History Section */}
      <div ref={tableRef} className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h3 className="text-2xl font-bold text-white">Lịch sử tải</h3>
            {hasActive && (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-500/10 border border-blue-500/20">
                <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse shadow-[0_0_8px_rgba(59,130,246,0.8)]"></div>
                <span className="text-xs text-blue-400 font-medium">Đang tải</span>
              </div>
            )}
          </div>
          <Button onClick={() => fetchJobs(true)} variant="secondary" isLoading={refreshing}>
            {!refreshing && <RefreshCw className="w-4 h-4 mr-2" />}
            Refresh
          </Button>
        </div>

        {/* Stats */}
        {jobs.length > 0 && (
          <div className="grid grid-cols-4 gap-4">
            {stats.map(stat => (
              <Card key={stat.label} className="p-5">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{stat.label}</p>
                <p className={cn("text-3xl font-bold mt-1", stat.color)}>{stat.value}</p>
              </Card>
            ))}
          </div>
        )}

        {/* Table */}
        <Card className="overflow-hidden">
          {loading && jobs.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-12 text-muted-foreground gap-3">
              <RefreshCw className="w-6 h-6 animate-spin text-primary" />
              Đang tải danh sách...
            </div>
          ) : (
            <DownloadJobTable
              jobs={jobs}
              deletingId={deletingId}
              onViewLogs={handleViewLogs}
              onDeleteJob={handleDeleteJob}
              onDownloadResult={handleDownloadResult}
            />
          )}
        </Card>
      </div>

      {/* Logs Modal */}
      {selectedJob && (
        <Modal
          isOpen={true}
          onClose={() => setSelectedJob(null)}
          maxWidth="4xl"
          title={
            <div className="flex items-center gap-3">
              <div className="px-3 py-1 rounded bg-white/5 border border-white/10 font-mono text-sm font-semibold text-primary">
                DOWNLOAD #{selectedJob.id}
              </div>
              <span className="text-xs text-muted-foreground font-mono truncate max-w-[300px]" title={selectedJob.source_url}>
                {selectedJob.source_url}
              </span>
            </div>
          }
        >
          <div className="h-[60vh] relative bg-black/50">
            <div className="absolute inset-0 bg-[#0D0D12] overflow-y-auto p-4 custom-scrollbar font-mono text-xs">
              {loadingLogs && jobLogs.length === 0 ? (
                <div className="text-muted-foreground flex items-center gap-2">
                  Đang tải logs... <RefreshCw className="w-3 h-3 animate-spin" />
                </div>
              ) : jobLogs.length === 0 ? (
                <div className="text-muted-foreground/50 italic">Chưa có log nào.</div>
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
          </div>
        </Modal>
      )}
    </div>
  );
}
