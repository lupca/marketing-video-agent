import { useEffect, useRef, useState } from "react";
import { X, Terminal, Loader2 } from "lucide-react";
import { cn } from "../../../lib/utils";
import api from "../../../lib/api";

export interface AgentLog {
  id: number;
  session_id: string;
  step: string;
  tool_name?: string;
  input_data?: any;
  output_data?: any;
  llm_reasoning?: string;
  log_level: string;
  created_at: string;
}

export interface AgentSession {
  id: string;
  user_id: string;
  keyword: string;
  video_count: number;
  status: string;
  summary?: string;
  config?: any;
  created_at: string;
  completed_at?: string;
}

interface AgentLogsDialogProps {
  session: AgentSession;
  onClose: () => void;
}

export function AgentLogsDialog({ session, onClose }: AgentLogsDialogProps) {
  const [logs, setLogs] = useState<AgentLog[]>([]);
  const [loading, setLoading] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  const fetchLogs = async () => {
    try {
      const resp = await api.get(`/api/agent/sessions/${session.id}/logs`);
      setLogs(resp.data);
    } catch (e) {
      console.error("Failed to fetch agent logs", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
    
    // Auto refresh if running
    let interval: any;
    if (session.status === "RUNNING" || session.status === "PENDING") {
      interval = setInterval(fetchLogs, 3000);
    }
    return () => clearInterval(interval);
  }, [session.id, session.status]);

  useEffect(() => {
    // Auto scroll to bottom
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  // Format JSON to string
  const formatJSON = (data: any) => {
    if (!data) return "";
    try {
      if (typeof data === "string") return data;
      return JSON.stringify(data, null, 2);
    } catch {
      return String(data);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 sm:p-6 lg:p-8">
      <div 
        className="bg-zinc-950 w-full max-w-5xl max-h-[90vh] rounded-2xl border border-zinc-800 shadow-2xl flex flex-col overflow-hidden animate-in zoom-in-95 duration-200"
      >
        <div className="flex items-center justify-between p-4 sm:p-6 border-b border-zinc-900 bg-zinc-950">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-500/10 rounded-xl">
              <Terminal className="w-6 h-6 text-emerald-500" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                Agent Console <span className="text-zinc-500 text-sm">#{session.id.substring(0, 8)}</span>
              </h2>
              <p className="text-zinc-400 text-sm flex gap-2">
                Target: <span className="text-emerald-400">{session.keyword}</span>
                Count: <span className="text-emerald-400">{session.video_count}</span>
              </p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            {session.status === "RUNNING" && (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
                <Loader2 className="w-4 h-4 text-emerald-400 animate-spin" />
                <span className="text-xs text-emerald-400 font-medium tracking-wide">EXECUTING</span>
              </div>
            )}
            <button 
              onClick={onClose}
              className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-900 rounded-xl transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="flex-1 p-6 overflow-y-auto bg-black font-mono text-sm leading-relaxed" ref={scrollRef}>
          {loading && logs.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
            </div>
          ) : logs.length === 0 ? (
            <div className="flex items-center justify-center h-full text-zinc-600">
              [ Agent is thinking... ]
            </div>
          ) : (
            <div className="space-y-4">
              {logs.map((log) => (
                <div key={log.id} className="border-l-2 pl-4 border-zinc-800 pb-2">
                  <div className="flex items-center gap-2 text-xs text-zinc-500 mb-1">
                    <span className="text-blue-400">[{new Date(log.created_at).toLocaleTimeString()}]</span>
                    <span className={cn(
                      "px-1.5 py-0.5 rounded uppercase tracking-wider font-bold text-[10px]",
                      log.log_level === "INFO" ? "bg-blue-500/20 text-blue-400" :
                      log.log_level === "ERROR" ? "bg-red-500/20 text-red-400" :
                      log.log_level === "WARNING" ? "bg-amber-500/20 text-amber-400" :
                      "bg-zinc-800 text-zinc-300"
                    )}>
                      {log.log_level}
                    </span>
                    <span className="text-zinc-300 font-semibold">{log.step}</span>
                    {log.tool_name && (
                      <span className="text-purple-400">→ {log.tool_name}</span>
                    )}
                  </div>
                  
                  {log.llm_reasoning && (
                    <div className="text-emerald-400 whitespace-pre-wrap mt-1 opacity-90 italic">
                      # {log.llm_reasoning}
                    </div>
                  )}
                  
                  {log.input_data && (
                    <div className="mt-2 text-zinc-400">
                      <span className="text-zinc-600">Input: </span>
                      <span className="break-all">{formatJSON(log.input_data)}</span>
                    </div>
                  )}
                  
                  {log.output_data && (
                    <div className="mt-1 text-zinc-300">
                      <span className="text-zinc-600">Output: </span>
                      <span className="break-all">{formatJSON(log.output_data)}</span>
                    </div>
                  )}
                </div>
              ))}
              
              {session.status === "RUNNING" && (
                <div className="flex items-center gap-2 text-zinc-500 animate-pulse mt-4">
                  <span className="w-2 h-4 bg-emerald-500 block"></span>
                  Agent is processing...
                </div>
              )}
              
              {session.summary && (
                <div className="mt-6 p-4 rounded-lg border border-purple-500/30 bg-purple-500/10">
                  <div className="text-purple-400 font-bold mb-1">AGENT SUMMARY</div>
                  <div className="text-purple-200 whitespace-pre-wrap">{session.summary}</div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
