import { useState } from "react";
import { format } from "date-fns";
import { Terminal, Code2, RefreshCw } from "lucide-react";
import { Modal } from "../../ui/Modal";
import { cn } from "../../../lib/utils";
import type { VideoJob, JobLog } from "../../../hooks/useJobs";

interface JobDetailsModalProps {
  job: VideoJob;
  logs: JobLog[];
  loadingLogs: boolean;
  onClose: () => void;
}

export function JobDetailsModal({ job, logs, loadingLogs, onClose }: JobDetailsModalProps) {
  const [activeTab, setActiveTab] = useState<"logs" | "config">("logs");

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      maxWidth="4xl"
      title={
        <div className="flex items-center gap-3">
          <div className="px-3 py-1 rounded bg-white/5 border border-white/10 font-mono text-sm font-semibold text-primary">
            JOB #{job.id}
          </div>
          <div className="flex gap-1">
            <button
              onClick={() => setActiveTab("logs")}
              className={cn(
                "px-4 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2",
                activeTab === "logs" ? "bg-white/10 text-white" : "text-muted-foreground hover:text-white hover:bg-white/5"
              )}
            >
              <Terminal className="w-4 h-4" /> Terminal Logs
            </button>
            <button
              onClick={() => setActiveTab("config")}
              className={cn(
                "px-4 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2",
                activeTab === "config" ? "bg-white/10 text-white" : "text-muted-foreground hover:text-white hover:bg-white/5"
              )}
            >
              <Code2 className="w-4 h-4" /> JSON Config
            </button>
          </div>
        </div>
      }
    >
      <div className="h-[60vh] relative bg-black/50">
        {activeTab === "logs" ? (
          <div className="absolute inset-0 bg-[#0D0D12] overflow-y-auto p-4 custom-scrollbar font-mono text-xs">
            {loadingLogs && logs.length === 0 ? (
              <div className="text-muted-foreground flex items-center gap-2">Scanning terminal logs... <RefreshCw className="w-3 h-3 animate-spin" /></div>
            ) : logs.length === 0 ? (
              <div className="text-muted-foreground/50 italic">No logs generated for this operation yet.</div>
            ) : (
              <div className="space-y-1.5">
                {logs.map((log, i) => (
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
              <code dangerouslySetInnerHTML={{ __html: JSON.stringify(job.config_data, null, 2).replace(/"(.*?)"/g, '<span class="text-[#addb67]">"$1"</span>').replace(/(\d+)/g, '<span class="text-[#f78c6c]">$1</span>').replace(/(true|false|null)/g, '<span class="text-[#ff5874]">$1</span>') }} />
            </pre>
          </div>
        )}
      </div>
    </Modal>
  );
}
