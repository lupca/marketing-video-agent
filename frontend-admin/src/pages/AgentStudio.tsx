import { useState, useEffect } from "react";
import { Bot, Youtube, Plus, Activity, Filter, Target, CalendarDays, RefreshCw } from "lucide-react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { AgentLogsDialog } from "../components/features/agent/AgentLogsDialog";
import type { AgentSession } from "../components/features/agent/AgentLogsDialog";
import { cn } from "../lib/utils";
import api from "../lib/api";

export default function AgentStudio() {
  const [sessions, setSessions] = useState<AgentSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedSession, setSelectedSession] = useState<AgentSession | null>(null);

  // Form states
  const [keyword, setKeyword] = useState("");
  const [videoCount, setVideoCount] = useState(1);
  const [mode, setMode] = useState("full");
  const [submitting, setSubmitting] = useState(false);

  const fetchSessions = async (hideLoading = false) => {
    if (!hideLoading) setLoading(true);
    else setRefreshing(true);
    
    try {
      const resp = await api.get('/api/agent/sessions');
      setSessions(resp.data);
    } catch (e) {
      console.error("Fetch agent sessions error", e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchSessions();
    const interval = setInterval(() => fetchSessions(true), 15000); // 15s refresh
    return () => clearInterval(interval);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!keyword) return;

    setSubmitting(true);
    try {
      const resp = await api.post('/api/agent/sessions', {
        keyword,
        video_count: videoCount,
        config: { mode: mode }
      });
      setKeyword("");
      setVideoCount(1);
      setMode("full");
      // Add the new session directly to top of list
      setSessions((prev) => [resp.data, ...prev]);
    } catch (e: any) {
      alert("Error starting agent session: " + (e.response?.data?.detail || e.message));
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch(status) {
      case "RUNNING": return "bg-blue-500/20 text-blue-400 border-blue-500/30";
      case "COMPLETED": return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
      case "FAILED": return "bg-red-500/20 text-red-400 border-red-500/30";
      default: return "bg-zinc-500/20 text-zinc-400 border-zinc-500/30";
    }
  };

  return (
    <div className="max-w-7xl mx-auto p-8 lg:p-12 space-y-8 animate-in fade-in duration-500">
      
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <h2 className="text-4xl font-extrabold tracking-tight flex items-center gap-3 text-white">
            <div className="p-2.5 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl shadow-[0_0_20px_rgba(99,102,241,0.4)]">
              <Bot className="w-8 h-8 text-white" />
            </div>
            AI Agent Studio
          </h2>
          <p className="text-muted-foreground text-lg ml-1">
            Delegate multi-step video creation pipelines entirely to local LLMs.
          </p>
        </div>
        <Button onClick={() => fetchSessions(true)} variant="secondary" isLoading={refreshing}>
          <RefreshCw className={cn("w-4 h-4 mr-2", refreshing && "animate-spin")} />
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Creation Form */}
        <div className="lg:col-span-1 space-y-6">
          <Card className="p-6 bg-gradient-to-br from-zinc-900/80 to-black/80 border-white/10 relative overflow-hidden group">
            <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/10 rounded-full blur-[80px] -mr-32 -mt-32 pointer-events-none transition-opacity duration-500 opacity-50 group-hover:opacity-100" />
            
            <div className="mb-6">
              <h3 className="text-xl font-bold text-white flex items-center gap-2 mb-2">
                <Target className="w-5 h-5 text-indigo-400" />
                Assign Mission
              </h3>
              <p className="text-sm text-zinc-400">
                Agent will automatically search, analyze, and spawn a rendering job for you.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-sm font-semibold text-zinc-300">Keyword Focus</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Youtube className="w-4 h-4 text-zinc-500" />
                  </div>
                  <input
                    type="text"
                    required
                    value={keyword}
                    onChange={(e) => setKeyword(e.target.value)}
                    placeholder="e.g. #badminton, review iphone"
                    className="w-full pl-10 pr-4 py-2.5 bg-black/40 border border-white/10 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm placeholder:text-zinc-600 transition-all text-white"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-sm font-semibold text-zinc-300">Quantity</label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  required
                  value={videoCount}
                  onChange={(e) => setVideoCount(Number(e.target.value))}
                  className="w-full px-4 py-2.5 bg-black/40 border border-white/10 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm transition-all text-white"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-sm font-semibold text-zinc-300">Mode</label>
                <select
                  value={mode}
                  onChange={(e) => setMode(e.target.value)}
                  className="w-full px-4 py-2.5 bg-black/40 border border-white/10 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm transition-all text-white focus:outline-none"
                >
                  <option value="full" className="bg-zinc-900 text-white">Full Pipeline (Research & Generate)</option>
                  <option value="research_only" className="bg-zinc-900 text-white">Research Only (Download Assets)</option>
                </select>
              </div>

              <Button 
                type="submit" 
                className="w-full py-6 mt-4 bg-indigo-600 hover:bg-indigo-500 text-base shadow-[0_0_20px_rgba(79,70,229,0.3)] transition-all"
                isLoading={submitting}
              >
                Launch Intelligence
                <Plus className="w-5 h-5 ml-2 opacity-70" />
              </Button>
            </form>
          </Card>
        </div>

        {/* Sessions List */}
        <div className="lg:col-span-2">
          <Card className="flex flex-col h-[700px] border-white/10 bg-black/20">
            <div className="p-5 border-b border-white/10 flex items-center justify-between">
              <h3 className="font-semibold text-white flex items-center gap-2">
                <Activity className="w-4 h-4 text-indigo-400" /> 
                Active & History Deployments
              </h3>
              <div className="flex gap-2">
                <span className="text-xs px-2.5 py-1 rounded bg-white/5 border border-white/10 text-zinc-400">
                  Total: {sessions.length}
                </span>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar">
              {loading && sessions.length === 0 ? (
                <div className="flex flex-col h-full items-center justify-center text-zinc-500">
                  <RefreshCw className="w-6 h-6 animate-spin mb-4 text-indigo-500" />
                  Checking orchestrator status...
                </div>
              ) : sessions.length === 0 ? (
                <div className="flex flex-col h-full items-center justify-center text-zinc-500 space-y-4">
                  <Bot className="w-12 h-12 opacity-20" />
                  <p>No agent sessions found.</p>
                </div>
              ) : (
                sessions.map((session) => (
                  <div 
                    key={session.id}
                    onClick={() => setSelectedSession(session)}
                    className="p-4 rounded-xl border border-white/5 bg-white/5 hover:bg-white/10 transition-all cursor-pointer group flex items-start gap-4"
                  >
                    <div className="p-3 bg-black/30 rounded-lg group-hover:scale-110 transition-transform">
                      <Bot className="w-5 h-5 text-indigo-400" />
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <h4 className="font-semibold text-white truncate max-w-[80%] text-lg">
                          "{session.keyword}"
                        </h4>
                        <span className={cn("text-xs px-2.5 py-1 rounded-full font-medium tracking-wide min-w-[80px] text-center border", getStatusColor(session.status))}>
                          {session.status}
                        </span>
                      </div>
                      
                      <div className="flex flex-wrap items-center gap-4 mt-2 text-xs text-zinc-400">
                        <span className="flex items-center gap-1.5 font-mono bg-black/40 px-2 py-0.5 rounded">
                          <Filter className="w-3 h-3 text-emerald-500" /> Count: {session.video_count}
                        </span>
                        <span className="flex items-center gap-1.5 bg-black/40 px-2 py-0.5 rounded">
                          <CalendarDays className="w-3 h-3 text-indigo-500" /> 
                          {new Date(session.created_at).toLocaleString()}
                        </span>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </Card>
        </div>
      </div>

      {selectedSession && (
        <AgentLogsDialog 
          session={selectedSession} 
          onClose={() => setSelectedSession(null)} 
        />
      )}
    </div>
  );
}
