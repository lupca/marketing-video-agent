import { ChevronRight } from "lucide-react";
import { cn } from "../../../lib/utils";
import { Button } from "../../ui/Button";

interface RenderSettingsStepProps {
  autoSubtitle: boolean;
  setAutoSubtitle: (val: boolean) => void;
  priority: number;
  setPriority: (val: number) => void;
  fontSize: number;
  setFontSize: (val: number) => void;
  textColor: string;
  setTextColor: (val: string) => void;
}

export function RenderSettingsStep(props: RenderSettingsStepProps) {
  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-right-8 duration-500">
      <h3 className="text-xl font-semibold text-white">Cài đặt Render</h3>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="p-4 rounded-xl bg-white/5 border border-white/10 space-y-3">
          <div className="flex items-center justify-between">
            <label className="text-sm font-semibold text-white">Phụ đề tự động (WhisperX)</label>
            <button type="button" onClick={() => props.setAutoSubtitle(!props.autoSubtitle)}
              className={cn("w-12 h-7 rounded-full transition-all relative", props.autoSubtitle ? "bg-primary" : "bg-white/20")}
            >
              <div className={cn("w-5 h-5 rounded-full bg-white absolute top-1 transition-all", props.autoSubtitle ? "left-6" : "left-1")} />
            </button>
          </div>
          <p className="text-xs text-muted-foreground">Tự động tạo phụ đề Hormozi-style từ voiceover + script</p>
        </div>

        <div className="p-4 rounded-xl bg-white/5 border border-white/10 space-y-3">
          <label className="text-sm font-semibold text-white">Độ ưu tiên</label>
          <div className="flex gap-2">
            <button type="button" onClick={() => props.setPriority(0)}
              className={cn("px-4 py-2 rounded-lg text-sm font-medium transition-all", props.priority === 0 ? "bg-white/10 border border-white/30 text-white" : "border border-transparent text-muted-foreground hover:bg-white/5")}
            >
              Normal
            </button>
            <button type="button" onClick={() => props.setPriority(1)}
              className={cn("px-4 py-2 rounded-lg text-sm font-medium transition-all", props.priority === 1 ? "bg-orange-500/20 border border-orange-500/50 text-orange-400" : "border border-transparent text-muted-foreground hover:bg-orange-500/10")}
            >
              High Priority
            </button>
          </div>
        </div>

        <div className="p-4 rounded-xl bg-white/5 border border-white/10 space-y-3">
          <label className="text-sm font-semibold text-white">Cỡ chữ Overlay</label>
          <div className="flex items-center gap-3">
            <input type="range" min="40" max="120" value={props.fontSize} onChange={e => props.setFontSize(parseInt(e.target.value))}
              className="flex-1 accent-primary"
            />
            <span className="text-sm text-white font-mono w-10 text-center">{props.fontSize}</span>
          </div>
        </div>

        <div className="p-4 rounded-xl bg-white/5 border border-white/10 space-y-3">
          <label className="text-sm font-semibold text-white">Màu chữ Overlay</label>
          <div className="flex gap-2">
            {["yellow", "white", "red", "cyan"].map(c => (
              <button key={c} type="button" onClick={() => props.setTextColor(c)}
                className={cn(
                  "w-10 h-10 rounded-lg border-2 transition-all",
                  props.textColor === c ? "border-primary scale-110 shadow-[0_0_15px_rgba(124,58,237,0.4)]" : "border-white/20"
                )}
                style={{ backgroundColor: c }}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
