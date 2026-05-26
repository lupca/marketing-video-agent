import { Sparkles, AlertTriangle, CheckCircle } from "lucide-react";
import type { AIMetadata } from "../../hooks/useAIDraft";

interface AIDraftPanelProps {
  hasDrafts: boolean;
  activeMode: "original" | "viral_optimized";
  onToggle: (mode: "original" | "viral_optimized") => void;
  metadata?: AIMetadata;
}

export function AIDraftPanel({
  hasDrafts,
  activeMode,
  onToggle,
  metadata,
}: AIDraftPanelProps) {
  if (!hasDrafts || !metadata) return null;

  const hookScore = metadata.hook_score || 0;
  const isGoodHook = hookScore >= 8;

  return (
    <div className="glass-panel p-6 mb-8 rounded-2xl border border-white/10 bg-white/[0.02] backdrop-blur-md flex flex-col gap-6 animate-in fade-in slide-in-from-top-4 duration-300">
      {/* Panel Title & Status */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/5 pb-4">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 bg-gradient-to-r from-violet-500 to-fuchsia-500 rounded-lg shadow-[0_0_15px_rgba(168,85,247,0.3)]">
            <Sparkles className="w-5 h-5 text-white animate-pulse" />
          </div>
          <div>
            <h4 className="text-md font-bold text-white flex items-center gap-2">
              Bản Nháp AI Leader (AI Draft Panel)
            </h4>
            <p className="text-xs text-muted-foreground">
              Định tuyến phân tách & Bơm cảm xúc theo Phễu Marketing TMCP
            </p>
          </div>
        </div>

        {/* Funnel Badges */}
        <div className="flex flex-wrap gap-2 items-center">
          {(metadata?.content_brief_context?.funnel_stage || metadata?.funnel_stage) && (
            <span className="text-[10px] font-bold tracking-widest uppercase bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 px-2.5 py-1 rounded-md">
              Stage: {metadata?.content_brief_context?.funnel_stage || metadata?.funnel_stage}
            </span>
          )}
          {(metadata?.content_brief_context?.psychological_angle || metadata?.psych_angle) && (
            <span className="text-[10px] font-bold tracking-widest uppercase bg-fuchsia-500/10 text-fuchsia-300 border border-fuchsia-500/20 px-2.5 py-1 rounded-md">
              Angle: {metadata?.content_brief_context?.psychological_angle || metadata?.psych_angle}
            </span>
          )}
        </div>
      </div>

      {/* Main Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Hook Score */}
        <div className="space-y-2.5">
          <div className="flex justify-between items-center text-sm font-semibold">
            <span className="text-white/80">Điểm Thu Hút (Hook Score):</span>
            <span className={isGoodHook ? "text-emerald-400 font-bold" : "text-amber-400 font-bold"}>
              {hookScore}/10
            </span>
          </div>
          <div className="w-full bg-white/10 rounded-full h-2 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-1000 ${
                isGoodHook
                  ? "bg-gradient-to-r from-emerald-500 to-teal-400 shadow-[0_0_10px_rgba(16,185,129,0.3)]"
                  : "bg-gradient-to-r from-amber-500 to-orange-400"
              }`}
              style={{ width: `${hookScore * 10}%` }}
            />
          </div>
          <p className="text-[11px] text-muted-foreground">
            {isGoodHook
              ? "Hook cực kỳ mạnh mẽ, đánh trực diện vào nỗi đau khách hàng."
              : "Hook mức độ bình thường, có thể cải thiện bằng cách giật tít sốc ở 3s đầu."}
          </p>
        </div>

        {/* SEO Panel */}
        {metadata.seo_titles && metadata.seo_titles.length > 0 && (
          <div className="space-y-1.5">
            <span className="text-sm font-semibold text-white/80 block">Đề Xuất Tiêu Đề SEO:</span>
            <div className="flex flex-col gap-1 text-xs text-muted-foreground">
              {metadata.seo_titles.map((title, i) => (
                <div key={i} className="flex items-center gap-1.5 text-white/70">
                  <CheckCircle className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                  <span>{title}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* QA Warnings */}
      {metadata.qa_warnings && metadata.qa_warnings.length > 0 && (
        <div className="p-3.5 bg-rose-500/5 border border-rose-500/10 rounded-xl flex items-start gap-2.5">
          <AlertTriangle className="w-4.5 h-4.5 text-rose-400 shrink-0 mt-0.5" />
          <div className="space-y-1 text-xs text-rose-400">
            <span className="font-bold">Cảnh báo Pacing / QA:</span>
            <ul className="list-disc pl-4 space-y-0.5">
              {metadata.qa_warnings.map((warn, idx) => (
                <li key={idx}>{warn}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Switch Toggle Tab-style for Sleek UX */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 bg-white/[0.01] border border-white/5 p-3 rounded-xl mt-2">
        <span className="text-xs font-semibold text-muted-foreground">
          Chọn phiên bản cấu hình để duyệt hoặc sửa đổi:
        </span>
        
        <div className="flex bg-black/40 p-1 rounded-xl border border-white/10 w-full sm:w-auto">
          <button
            type="button"
            onClick={() => onToggle("original")}
            className={`flex-1 sm:flex-none px-5 py-2 text-xs font-bold rounded-lg transition-all duration-300 ${
              activeMode === "original"
                ? "bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-lg"
                : "text-muted-foreground hover:text-white"
            }`}
          >
            Bản Gốc (TMCP)
          </button>
          <button
            type="button"
            onClick={() => onToggle("viral_optimized")}
            className={`flex-1 sm:flex-none px-5 py-2 text-xs font-bold rounded-lg transition-all duration-300 flex items-center justify-center gap-1.5 ${
              activeMode === "viral_optimized"
                ? "bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-lg"
                : "text-muted-foreground hover:text-white"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-300" />
            AI Viral (Phễu)
          </button>
        </div>
      </div>
    </div>
  );
}
