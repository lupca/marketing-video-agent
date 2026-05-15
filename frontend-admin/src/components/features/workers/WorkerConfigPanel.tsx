import { Settings, RefreshCw, Video, Download, Search, Zap, Sparkles, Bot, Terminal } from "lucide-react";
import { useWorkerConfig } from "../../../hooks/useWorkerConfig";
import { Card } from "../../ui/Card";
import { Button } from "../../ui/Button";
import { ToggleSwitch } from "../../ui/ToggleSwitch";
import { cn } from "../../../lib/utils";

const WORKER_ICONS: Record<string, any> = {
  review: Video,
  unbox: Zap,
  research: Search,
  slideshow: Zap,
  download: Download,
  promotion: Sparkles,
  agent: Bot,
};

export function WorkerConfigPanel() {
  const { summary, loading, refreshing, error, fetchConfigs, toggleWorker, batchUpdate } = useWorkerConfig();

  const handleToggleAll = (enabled: boolean) => {
    if (!summary) return;
    
    if (!enabled && !window.confirm("Are you sure you want to disable ALL workers? This will stop all ongoing and future tasks.")) {
      return;
    }

    const updates = summary.configs.reduce((acc, config) => {
      acc[config.worker_type] = enabled;
      return acc;
    }, {} as Record<string, boolean>);
    batchUpdate(updates);
  };

  if (loading && !summary) {
    return (
      <Card className="p-8 flex items-center justify-center border-white/5 bg-black/20">
        <RefreshCw className="w-6 h-6 animate-spin text-primary" />
        <span className="ml-3 text-muted-foreground">Loading worker configuration...</span>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-primary/10 text-primary border border-primary/20">
            <Settings className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-xl font-bold text-white">Worker Configuration</h3>
            <p className="text-xs text-muted-foreground">Manage selective startup and runtime availability</p>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => fetchConfigs(true)} isLoading={refreshing}>
            <RefreshCw className="w-4 h-4 mr-2" /> Refresh
          </Button>
          <div className="flex gap-1">
            <Button variant="outline" size="sm" onClick={() => handleToggleAll(true)} className="text-[10px] uppercase tracking-wider px-3">Enable All</Button>
            <Button variant="outline" size="sm" onClick={() => handleToggleAll(false)} className="text-[10px] uppercase tracking-wider px-3">Disable All</Button>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
          <Terminal className="w-4 h-4" /> {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {summary?.configs.length === 0 ? (
          <div className="col-span-full p-8 text-center border border-dashed border-white/10 rounded-2xl bg-white/5">
            <p className="text-muted-foreground">No worker configurations found in database.</p>
            <p className="text-xs text-muted-foreground/50 mt-1">Run 'python3 init_worker_configs.py --init' to seed data.</p>
          </div>
        ) : (
          summary?.configs.map((config) => {
            const Icon = WORKER_ICONS[config.worker_type] || Terminal;
            const isEnabled = config.is_enabled;
            
            return (
              <Card 
                key={config.id} 
                className={cn(
                  "p-5 transition-all duration-300 border-white/5",
                  isEnabled ? "bg-emerald-500/5 border-emerald-500/20" : "bg-black/40 grayscale-[0.5]"
                )}
              >
                <div className="flex items-start justify-between mb-4">
                  <div className={cn(
                    "p-2.5 rounded-xl transition-colors",
                    isEnabled ? "bg-emerald-500/20 text-emerald-400" : "bg-white/5 text-muted-foreground"
                  )}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <ToggleSwitch 
                    checked={isEnabled} 
                    onChange={(checked) => toggleWorker(config.worker_type, checked)} 
                  />
                </div>
                
                <div className="space-y-1">
                  <h4 className="font-bold text-white capitalize">{config.worker_type} Worker</h4>
                  <div className="flex items-center gap-2">
                    <div className={cn(
                      "w-1.5 h-1.5 rounded-full",
                      isEnabled ? "bg-emerald-400 animate-pulse shadow-[0_0_8px_rgba(52,211,153,0.6)]" : "bg-white/20"
                    )}></div>
                    <span className={cn(
                      "text-[10px] font-bold uppercase tracking-widest",
                      isEnabled ? "text-emerald-400" : "text-muted-foreground"
                    )}>
                      {isEnabled ? "Enabled" : "Disabled"}
                    </span>
                  </div>
                </div>

                <div className="mt-4 pt-4 border-t border-white/5 flex items-center justify-between text-[10px] text-muted-foreground font-mono">
                  <span>Priority: {config.priority}</span>
                  <span>Max: {config.max_replicas}</span>
                </div>
              </Card>
            );
          })
        )}
      </div>

      {summary && (
        <div className="flex items-center gap-4 text-xs text-muted-foreground bg-white/5 p-3 rounded-xl border border-white/5">
           <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
              <span>{summary.enabled_workers} Active</span>
           </div>
           <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-white/20"></span>
              <span>{summary.disabled_workers} Standby</span>
           </div>
           <div className="ml-auto italic">
             * Changes take effect within ~15 seconds
           </div>
        </div>
      )}
    </div>
  );
}
