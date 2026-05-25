import { CheckCircle2 } from "lucide-react";
import type { Project } from "../../../hooks/useProjects";
import type { Segment, UploadedFile } from "./types";

interface ReviewSubmitStepProps {
  projects: Project[];
  selectedProjectId: string;
  isCreatingProject: boolean;
  newProjectName: string;
  voiceover: UploadedFile | null;
  script: UploadedFile | null;
  bgm: UploadedFile | null;
  language: string;
  segments: Segment[];
  autoSubtitle: boolean;
  priority: number;
}

export function ReviewSubmitStep(props: ReviewSubmitStepProps) {
  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-right-8 duration-500">
      <div className="rounded-2xl bg-black/40 border border-white/10 p-8 space-y-6">
        <h3 className="text-2xl font-bold text-white flex items-center gap-3">
          <CheckCircle2 className="w-8 h-8 text-green-400" /> Xem lại trước khi gửi
        </h3>

        <div className="grid grid-cols-2 gap-8 text-sm">
          <div className="space-y-3">
            <p className="text-muted-foreground font-semibold uppercase text-xs tracking-wider">Dự án & Âm thanh</p>
            <div className="space-y-2">
              <p className="text-white flex justify-between border-b border-white/10 pb-2"><span>Dự án:</span> <span className="font-medium">{props.isCreatingProject ? props.newProjectName : props.projects.find(p => p.id === props.selectedProjectId)?.name || "Chưa chọn"}</span></p>
              <p className="text-white flex justify-between border-b border-white/10 pb-2"><span>Voiceover:</span> <span className="font-medium text-green-400">{props.voiceover?.file?.name || props.voiceover?.asset?.file_name || "—"}</span></p>
              <p className="text-white flex justify-between border-b border-white/10 pb-2"><span>Kịch bản:</span> <span className="font-medium text-green-400">{props.script?.file?.name || props.script?.asset?.file_name || "—"}</span></p>
              <p className="text-white flex justify-between border-b border-white/10 pb-2"><span>Nhạc nền:</span> <span className="font-medium">{props.bgm?.file?.name || props.bgm?.asset?.file_name || "Không có"}</span></p>
              <p className="text-white flex justify-between border-b border-white/10 pb-2"><span>Ngôn ngữ:</span> <span>{props.language === "vi" ? "🇻🇳 Tiếng Việt" : "🇺🇸 English"}</span></p>
            </div>
          </div>
          <div className="space-y-3">
            <p className="text-muted-foreground font-semibold uppercase text-xs tracking-wider">Cài đặt Render</p>
            <div className="space-y-2">
              <p className="text-white flex justify-between border-b border-white/10 pb-2"><span>Phân cảnh:</span> <span className="font-medium">{props.segments.length} segments</span></p>
              <p className="text-white flex justify-between border-b border-white/10 pb-2"><span>Tổng clips:</span> <span className="font-medium">{props.segments.reduce((a, s) => a + s.clips.length, 0)} files</span></p>
              <p className="text-white flex justify-between border-b border-white/10 pb-2"><span>Phụ đề tự động:</span> <span className={props.autoSubtitle ? "text-green-400" : "text-muted-foreground"}>{props.autoSubtitle ? "Bật" : "Tắt"}</span></p>
              <p className="text-white flex justify-between border-b border-white/10 pb-2"><span>Độ phân giải:</span> <span>1080×1920</span></p>
              <p className="text-white flex justify-between border-b border-white/10 pb-2"><span>Ưu tiên:</span> <span className={props.priority > 0 ? "text-orange-400 font-semibold" : ""}>{props.priority > 0 ? "High" : "Normal"}</span></p>
            </div>
          </div>
        </div>

        {/* Segment summary */}
        <div className="space-y-2">
          <p className="text-muted-foreground font-semibold uppercase text-xs tracking-wider">Timeline phân cảnh</p>
          <div className="grid gap-2">
            {props.segments.map((seg, i) => (
              <div key={i} className="flex items-center gap-3 text-sm bg-white/5 p-3 rounded-lg border border-white/10">
                <span className="w-6 h-6 rounded-full bg-primary/20 text-primary text-xs flex items-center justify-center font-bold">{i + 1}</span>
                <span className="text-white font-medium flex-1">{seg.label || seg.name}</span>
                <span className="text-muted-foreground font-mono text-xs">{seg.timeStart}s – {seg.timeEnd}s</span>
                <span className="text-xs text-green-400">{seg.clips.length} clip(s)</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
