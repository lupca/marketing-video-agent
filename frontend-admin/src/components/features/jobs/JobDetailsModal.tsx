import { useState, useEffect } from "react";
import { format } from "date-fns";
import {
  Terminal,
  Code2,
  RefreshCw,
  Cpu,
  CheckCircle2,
  AlertTriangle,
  Play,
  HelpCircle,
  FileText,
  Settings,
  ShieldAlert,
  Database,
  Eye,
  Brackets,
  Brain
} from "lucide-react";
import { Modal } from "../../ui/Modal";
import { cn } from "../../../lib/utils";
import api from "../../../lib/api";
import type { VideoJob, JobLog, AgentLog } from "../../../hooks/useJobs";

interface JobDetailsModalProps {
  job: VideoJob;
  logs: JobLog[];
  loadingLogs: boolean;
  onClose: () => void;
}

export function JobDetailsModal({ job, logs, loadingLogs, onClose }: JobDetailsModalProps) {
  const isLeader = job.job_type === "leader";
  const [activeTab, setActiveTab] = useState<"logs" | "trace" | "config">(
    isLeader ? "trace" : "logs"
  );
  
  const [traceLogs, setTraceLogs] = useState<AgentLog[]>([]);
  const [loadingTrace, setLoadingTrace] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<number | null>(null);
  const [activeInspectorTab, setActiveInspectorTab] = useState<"io" | "thought">("io");

  // Fetch real-time LangGraph Traces
  useEffect(() => {
    if (!isLeader) return;

    let isMounted = true;
    const fetchTrace = async () => {
      try {
        const res = await api.get(`/api/jobs/${job.id}/trace`);
        if (isMounted) {
          setTraceLogs(res.data);
          // Auto-select first node if none is selected
          if (res.data.length > 0 && selectedNodeId === null) {
            setSelectedNodeId(res.data[res.data.length - 1].id); // select latest by default
          }
        }
      } catch (err) {
        console.error("Failed to fetch LangGraph trace:", err);
      }
    };

    // First fetch
    setLoadingTrace(true);
    fetchTrace().finally(() => {
      if (isMounted) setLoadingTrace(false);
    });

    let interval: any;
    if (job.status === "PROCESSING") {
      interval = setInterval(fetchTrace, 3000);
    }

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [job.id, job.status, isLeader, selectedNodeId]);

  // Node helper functions
  const getNodeLabel = (log: AgentLog, index: number, allLogs: AgentLog[]) => {
    switch (log.node_name) {
      case "extract":
        return "Extract Context Payload";
      case "router":
        return "Creative Routing Node";
      case "generator": {
        const attempt = allLogs.slice(0, index + 1).filter(l => l.node_name === "generator").length;
        return `Draft Generation (Attempt ${attempt})`;
      }
      case "validator": {
        const attempt = allLogs.slice(0, index + 1).filter(l => l.node_name === "validator").length;
        return `Pacing Validation (Attempt ${attempt})`;
      }
      case "healing":
        return "Defensive Structure Healer";
      case "persistence":
        return "DB Persistence Engine";
      default:
        return log.node_name || "Unknown Graph Node";
    }
  };

  const getNodeIcon = (nodeName: string | null) => {
    switch (nodeName) {
      case "extract": return FileText;
      case "router": return Settings;
      case "generator": return Cpu;
      case "validator": return ShieldAlert;
      case "healing": return Play;
      case "persistence": return Database;
      default: return HelpCircle;
    }
  };

  const activeLog = traceLogs.find(l => l.id === selectedNodeId);

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      maxWidth={isLeader ? "6xl" : "4xl"}
      title={
        <div className="flex items-center gap-3">
          <div className="px-3 py-1 rounded bg-white/5 border border-white/10 font-mono text-sm font-semibold text-primary">
            JOB #{job.id}
          </div>
          <div className="flex gap-1">
            {isLeader && (
              <button
                onClick={() => setActiveTab("trace")}
                className={cn(
                  "px-4 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2",
                  activeTab === "trace" ? "bg-white/10 text-white shadow-sm ring-1 ring-white/15" : "text-muted-foreground hover:text-white hover:bg-white/5"
                )}
              >
                <Brain className="w-4 h-4 text-purple-400" /> Mindmap Tracing
              </button>
            )}
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
      <div className="h-[70vh] relative bg-[#09090E]/90">
        {activeTab === "trace" ? (
          <div className="absolute inset-0 flex divide-x divide-white/5">
            {/* LEFT COLUMN: Node Execution Flowchart */}
            <div className="w-2/5 overflow-y-auto p-5 custom-scrollbar space-y-4">
              <div className="flex items-center justify-between border-b border-white/5 pb-3">
                <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">LangGraph Execution Steps</span>
                {job.status === "PROCESSING" && (
                  <span className="flex items-center gap-1.5 text-[10px] text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded-full border border-purple-500/20 animate-pulse font-medium">
                    <RefreshCw className="w-2.5 h-2.5 animate-spin" /> Stream Active
                  </span>
                )}
              </div>

              {loadingTrace && traceLogs.length === 0 ? (
                <div className="flex flex-col items-center justify-center p-12 text-muted-foreground gap-2">
                  <RefreshCw className="w-5 h-5 animate-spin text-primary" />
                  Connecting to Tracing Pipeline...
                </div>
              ) : traceLogs.length === 0 ? (
                <div className="p-8 text-center text-muted-foreground/40 italic text-sm">
                  LangGraph has not initialized tracing buffers for this job yet.
                </div>
              ) : (
                <div className="relative pl-6 border-l border-white/5 space-y-6">
                  {traceLogs.map((log, index) => {
                    const NodeIcon = getNodeIcon(log.node_name);
                    const isSelected = selectedNodeId === log.id;
                    const hasError = log.log_level === "ERROR" || (log.output_data && log.output_data.error) || (log.output_data && log.output_data.pacing_errors && log.output_data.pacing_errors.length > 0);
                    
                    return (
                      <div
                        key={log.id}
                        onClick={() => setSelectedNodeId(log.id)}
                        className={cn(
                          "relative p-3.5 rounded-xl border transition-all duration-200 cursor-pointer group hover:-translate-y-0.5",
                          isSelected
                            ? "bg-white/10 border-white/15 shadow-lg shadow-black/20"
                            : "bg-white/5 border-white/5 hover:bg-white/10 hover:border-white/10"
                        )}
                      >
                        {/* Timeline node marker */}
                        <div className={cn(
                          "absolute -left-[31px] top-4.5 w-4.5 h-4.5 rounded-full border flex items-center justify-center transition-all duration-300",
                          hasError
                            ? "bg-rose-950 border-rose-500 text-rose-400"
                            : log.log_level === "WARNING"
                            ? "bg-amber-950 border-amber-500 text-amber-400"
                            : "bg-emerald-950 border-emerald-500 text-emerald-400"
                        )}>
                          {hasError ? (
                            <AlertTriangle className="w-2.5 h-2.5" />
                          ) : (
                            <CheckCircle2 className="w-2.5 h-2.5" />
                          )}
                        </div>

                        {/* Node content */}
                        <div className="space-y-1.5">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-mono text-muted-foreground/60">
                              [{format(new Date(log.created_at), "HH:mm:ss")}]
                            </span>
                            <span className={cn(
                              "text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border",
                              log.step === "generate" ? "text-blue-400 bg-blue-500/5 border-blue-500/10" :
                              log.step === "validate" ? "text-purple-400 bg-purple-500/5 border-purple-500/10" :
                              log.step === "decide" ? "text-amber-400 bg-amber-500/5 border-amber-500/10" :
                              log.step === "heal" ? "text-cyan-400 bg-cyan-500/5 border-cyan-500/10" :
                              "text-emerald-400 bg-emerald-500/5 border-emerald-500/10"
                            )}>
                              {log.step || "node"}
                            </span>
                          </div>

                          <h4 className="text-sm font-bold text-white flex items-center gap-2">
                            <NodeIcon className={cn("w-4 h-4", isSelected ? "text-primary" : "text-muted-foreground")} />
                            {getNodeLabel(log, index, traceLogs)}
                          </h4>

                          {/* Preview snippet of output */}
                          {hasError && (
                            <div className="text-[10px] font-semibold text-rose-400 flex items-center gap-1 bg-rose-500/10 p-1.5 rounded border border-rose-500/20">
                              <AlertTriangle className="w-3 h-3 shrink-0" />
                              <span className="truncate">
                                {log.output_data?.error || (log.output_data?.pacing_errors && `${log.output_data.pacing_errors.length} pacing violations detected.`)}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* RIGHT COLUMN: Node Inspector Panel */}
            <div className="w-3/5 overflow-y-auto p-6 custom-scrollbar bg-black/20 flex flex-col h-full">
              {activeLog ? (
                <div className="space-y-6 flex-1 flex flex-col">
                  {/* Inspector Header */}
                  <div className="border-b border-white/5 pb-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <h3 className="text-lg font-bold text-white tracking-wide">
                        Inspector: <span className="font-mono text-primary">{activeLog.node_name}</span>
                      </h3>
                      <span className="text-[11px] font-mono text-muted-foreground bg-white/5 border border-white/5 px-2 py-0.5 rounded">
                        UUID: {activeLog.id}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed italic">
                      {activeLog.llm_reasoning ? "LLM executed logical inference step. Review thoughts below." : "Static Python validation or persistent database sync operations."}
                    </p>
                  </div>

                  {/* Tabs: Inputs/Outputs vs LLM reasoning */}
                  <div className="flex border-b border-white/5">
                    <button
                      onClick={() => setActiveInspectorTab("io")}
                      className={cn(
                        "px-4 py-2 border-b-2 text-xs font-bold tracking-wider uppercase transition-colors flex items-center gap-1.5",
                        activeInspectorTab === "io" ? "border-primary text-white" : "border-transparent text-muted-foreground hover:text-white"
                      )}
                    >
                      <Brackets className="w-3.5 h-3.5" /> Inputs & Outputs
                    </button>
                    {activeLog.llm_reasoning && (
                      <button
                        onClick={() => setActiveInspectorTab("thought")}
                        className={cn(
                          "px-4 py-2 border-b-2 text-xs font-bold tracking-wider uppercase transition-colors flex items-center gap-1.5",
                          activeInspectorTab === "thought" ? "border-purple-500 text-white" : "border-transparent text-muted-foreground hover:text-purple-400"
                        )}
                      >
                        <Brain className="w-3.5 h-3.5 text-purple-400" /> Thinking Trace
                      </button>
                    )}
                  </div>

                  {/* Inspector Body */}
                  <div className="flex-1 flex flex-col">
                    {activeInspectorTab === "io" ? (
                      <div className="space-y-6 flex-1">
                        {/* INPUTS CONTAINER */}
                        <div className="space-y-2">
                          <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                            <Eye className="w-3.5 h-3.5 text-blue-400" /> Node Inputs
                          </h4>
                          {activeLog.node_name === "generator" && activeLog.input_data?.prompt ? (
                            <div className="p-3 bg-black/40 rounded-xl border border-white/5 text-xs text-white/90 leading-relaxed font-mono whitespace-pre-wrap max-h-[25vh] overflow-y-auto custom-scrollbar shadow-inner">
                              {activeLog.input_data.prompt}
                            </div>
                          ) : (
                            <pre className="text-xs text-blue-300 font-mono whitespace-pre-wrap max-h-[20vh] overflow-y-auto bg-black/40 p-3.5 rounded-xl border border-white/5 custom-scrollbar shadow-inner">
                              <code>{JSON.stringify(activeLog.input_data, null, 2)}</code>
                            </pre>
                          )}
                        </div>

                        {/* OUTPUTS CONTAINER */}
                        <div className="space-y-2">
                          <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                            <Brackets className="w-3.5 h-3.5 text-emerald-400" /> Node Outputs
                          </h4>
                          {activeLog.node_name === "validator" && activeLog.output_data?.pacing_errors ? (
                            <div className="space-y-2 max-h-[30vh] overflow-y-auto custom-scrollbar">
                              {activeLog.output_data.pacing_errors.length === 0 ? (
                                <div className="text-xs text-emerald-400 font-semibold bg-emerald-500/5 border border-emerald-500/10 p-3 rounded-xl flex items-center gap-2">
                                  <CheckCircle2 className="w-4 h-4" /> All segments satisfy optimal pacing thresholds (&lt; 4.5 words/sec).
                                </div>
                              ) : (
                                <div className="space-y-1.5">
                                  <div className="text-xs text-rose-400 font-semibold bg-rose-500/5 border border-rose-500/10 p-3 rounded-xl flex items-center gap-2">
                                    <AlertTriangle className="w-4 h-4" /> Detected {activeLog.output_data.pacing_errors.length} timeline pace violations.
                                  </div>
                                  <div className="space-y-1">
                                    {activeLog.output_data.pacing_errors.map((err: string, i: number) => (
                                      <div key={i} className="text-xs bg-rose-500/5 border border-rose-500/10 p-2.5 rounded-lg text-rose-300/90 font-mono">
                                        {err}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          ) : (
                            <pre className="text-xs text-emerald-300 font-mono whitespace-pre-wrap max-h-[30vh] overflow-y-auto bg-black/40 p-3.5 rounded-xl border border-white/5 custom-scrollbar shadow-inner">
                              <code>{JSON.stringify(activeLog.output_data, null, 2)}</code>
                            </pre>
                          )}
                        </div>
                      </div>
                    ) : (
                      /* LLM THINKING TRACE */
                      <div className="flex-1 flex flex-col">
                        <div className="p-4 bg-purple-500/5 border border-purple-500/10 rounded-xl leading-relaxed text-xs text-purple-200/90 font-mono whitespace-pre-wrap overflow-y-auto max-h-[50vh] custom-scrollbar flex-1 shadow-inner">
                          {activeLog.llm_reasoning}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center flex-1 text-muted-foreground/30 italic text-sm">
                  Select a LangGraph Execution Step to Inspect Data Nodes.
                </div>
              )}
            </div>
          </div>
        ) : activeTab === "logs" ? (
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
