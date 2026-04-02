import { Plus, Trash2, Upload, CheckCircle2, Video, ChevronRight, Folder } from "lucide-react";
import { cn } from "../../../lib/utils";
import { Button } from "../../ui/Button";
import { AssetSelectModal } from "../../ui/AssetSelectModal";
import type { Asset } from "../../../hooks/useAssets";
import type { Segment, UploadedFile } from "./types";
import { useState } from "react";

const SEGMENT_PRESETS = [
  { name: "01_hook", label: "🎯 Hook — Thu hút trong 3s đầu" },
  { name: "02_pain_point", label: "😤 Pain Point — Đánh vào nỗi đau" },
  { name: "03_reveal", label: "✨ Reveal — Giải pháp/Sản phẩm" },
  { name: "04_educate", label: "📚 Educate — Kiến thức/Chi tiết" },
  { name: "05_proof", label: "🏆 Proof — Bằng chứng" },
  { name: "06_cta", label: "📢 CTA — Kêu gọi hành động" },
];

const EFFECTS_OPTIONS = [
  { value: "camera_shake", label: "📳 Camera Shake" },
  { value: "snap_zoom", label: "🔍 Snap Zoom" },
  { value: "slow_motion_0.5x", label: "🐌 Slow Motion (0.5x)" },
  { value: "warp_slide", label: "⚡ Warp Slide" }, // Added based on recent feature
];

interface SegmentEditorStepProps {
  segments: Segment[];
  setSegments: (segments: Segment[]) => void;
  onPrev: () => void;
  onNext: () => void;
  canGoNext: boolean;
}

export function SegmentEditorStep({ segments, setSegments, onPrev, onNext, canGoNext }: SegmentEditorStepProps) {
  const [modalOpenIdx, setModalOpenIdx] = useState<number | null>(null);

  const handleSegmentClips = (index: number, files: FileList | null) => {
    if (!files) return;
    const newSegments = [...segments];
    const newClips: UploadedFile[] = Array.from(files).map((f) => ({
      file: f, id: null, s3_url: null, uploading: false, progress: 0
    }));
    newSegments[index].clips = [...newSegments[index].clips, ...newClips];
    setSegments(newSegments);
  };

  const handleAssetSelectMultiple = (index: number, assets: Asset[]) => {
    const newSegments = [...segments];
    const newClips: UploadedFile[] = assets.map(asset => ({
      asset, id: asset.id, s3_url: asset.s3_url, uploading: false, progress: 0
    }));
    newSegments[index].clips = [...newSegments[index].clips, ...newClips];
    setSegments(newSegments);
  };

  const addSegment = () => {
    const nextIdx = segments.length;
    const preset = SEGMENT_PRESETS[nextIdx] || { name: `segment_${nextIdx + 1}`, label: `Segment ${nextIdx + 1}` };
    const lastEnd = segments.length > 0 ? segments[segments.length - 1].timeEnd : 0;
    setSegments([...segments, {
      name: preset.name, label: preset.label, timeStart: lastEnd, timeEnd: lastEnd + 10,
      clips: [], textOverlay: "", highlightWords: "", effects: [], pacingMin: 1.0, pacingMax: 2.0,
    }]);
  };

  const removeSegment = (idx: number) => setSegments(segments.filter((_, i) => i !== idx));

  const updateSegment = (idx: number, field: keyof Segment, value: any) => {
    const updated = [...segments];
    (updated[idx] as any)[field] = value;
    setSegments(updated);
  };

  const toggleEffect = (idx: number, effect: string) => {
    const updated = [...segments];
    const fx = updated[idx].effects;
    updated[idx].effects = fx.includes(effect) ? fx.filter(e => e !== effect) : [...fx, effect];
    setSegments(updated);
  };

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-right-8 duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xl font-semibold text-white">Phân cảnh Video</h3>
          <p className="text-sm text-muted-foreground">Mỗi phân cảnh = mỗi phần của kịch bản voiceover</p>
        </div>
        <button
          type="button"
          onClick={addSegment}
          className="inline-flex items-center bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-sm font-medium transition-colors h-10 px-4 text-white"
        >
          <Plus className="mr-2 h-4 w-4 text-primary" /> Thêm phân cảnh
        </button>
      </div>

      <div className="space-y-4 max-h-[550px] overflow-y-auto pr-2 custom-scrollbar">
        {segments.map((seg, idx) => (
          <div key={idx} className="p-5 rounded-2xl bg-black/40 border border-white/10 hover:border-white/20 transition-all space-y-4">
            {/* Segment header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/20 text-primary font-bold text-sm border border-primary/30">{idx + 1}</div>
                <select
                  value={seg.name}
                  onChange={e => {
                    const preset = SEGMENT_PRESETS.find(p => p.name === e.target.value);
                    updateSegment(idx, "name", e.target.value);
                    if (preset) updateSegment(idx, "label", preset.label);
                  }}
                  className="h-9 rounded-lg border border-white/10 bg-white/5 px-3 text-sm text-white appearance-none"
                >
                  {SEGMENT_PRESETS.map(p => (
                    <option key={p.name} value={p.name} className="bg-[#1A1A24]">{p.label}</option>
                  ))}
                </select>
              </div>
              <button onClick={() => removeSegment(idx)} className="p-2 text-muted-foreground hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors">
                <Trash2 className="h-4 w-4" />
              </button>
            </div>

            {/* Time range */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-muted-foreground uppercase">Bắt đầu (s)</label>
                <input type="number" step="0.5" min="0" value={seg.timeStart}
                  onChange={e => updateSegment(idx, "timeStart", parseFloat(e.target.value) || 0)}
                  className="flex h-10 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-muted-foreground uppercase">Kết thúc (s)</label>
                <input type="number" step="0.5" min="0" value={seg.timeEnd}
                  onChange={e => updateSegment(idx, "timeEnd", parseFloat(e.target.value) || 0)}
                  className="flex h-10 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-muted-foreground uppercase">Pacing Min (s)</label>
                <input type="number" step="0.1" min="0.1" value={seg.pacingMin}
                  onChange={e => updateSegment(idx, "pacingMin", parseFloat(e.target.value) || 0.5)}
                  className="flex h-10 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-muted-foreground uppercase">Pacing Max (s)</label>
                <input type="number" step="0.1" min="0.1" value={seg.pacingMax}
                  onChange={e => updateSegment(idx, "pacingMax", parseFloat(e.target.value) || 1.5)}
                  className="flex h-10 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50"
                />
              </div>
            </div>

            {/* Video clip upload */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-muted-foreground uppercase">
                Video Clips <span className="text-primary">*</span>
              </label>
              <div className="flex items-center gap-3">
                <label className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-dashed border-white/20 cursor-pointer transition-colors text-sm text-white/80">
                  <Upload className="w-4 h-4 text-primary" /> Từ Máy Tính
                  <input type="file" className="hidden" multiple accept="video/mp4,video/quicktime,.mov"
                    onChange={e => handleSegmentClips(idx, e.target.files)} />
                </label>
                <button
                  type="button"
                  onClick={() => setModalOpenIdx(idx)}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/20 transition-colors text-sm text-white/80"
                >
                  <Folder className="w-4 h-4 text-indigo-400" /> Thư Viện
                </button>
                {seg.clips.length > 0 && (
                  <span className="text-xs text-green-400 bg-green-400/10 px-3 py-1 rounded-full border border-green-400/20">
                    <CheckCircle2 className="w-3 h-3 inline mr-1" />{seg.clips.length} clip(s)
                  </span>
                )}
              </div>
              {seg.clips.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-1">
                  {seg.clips.map((c, ci) => (
                    <span key={ci} className="text-xs bg-white/5 text-white/70 px-2 py-1 rounded-lg border border-white/10 flex items-center gap-1">
                      <Video className="w-3 h-3" /> 
                      {c.file?.name 
                        ? (c.file.name.length > 20 ? c.file.name.slice(0, 20) + "..." : c.file.name) 
                        : (c.asset?.file_name && c.asset.file_name.length > 20 ? c.asset.file_name.slice(0, 20) + "..." : c.asset?.file_name)}
                      <button type="button" onClick={() => {
                        const newSegs = [...segments];
                        newSegs[idx].clips = newSegs[idx].clips.filter((_, i) => i !== ci);
                        setSegments(newSegs);
                      }} className="text-red-400 hover:text-red-300 ml-1">×</button>
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Text overlay & highlight */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-muted-foreground uppercase">Text Overlay (chữ lớn)</label>
                <input type="text" placeholder="VD: SAI LẦM CHẾT NGƯỜI!" value={seg.textOverlay}
                  onChange={e => updateSegment(idx, "textOverlay", e.target.value)}
                  className="flex h-10 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 placeholder:text-muted-foreground/40"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-muted-foreground uppercase">Highlight Words (phân tách bởi dấu phẩy)</label>
                <input type="text" placeholder="VD: SAI LẦM, CHẾT NGƯỜI" value={seg.highlightWords}
                  onChange={e => updateSegment(idx, "highlightWords", e.target.value)}
                  className="flex h-10 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary/50 placeholder:text-muted-foreground/40"
                />
              </div>
            </div>

            {/* Effects */}
            <div className="space-y-1">
              <label className="text-xs font-semibold text-muted-foreground uppercase">Hiệu ứng</label>
              <div className="flex gap-2 flex-wrap">
                {EFFECTS_OPTIONS.map(fx => (
                  <button key={fx.value} type="button" onClick={() => toggleEffect(idx, fx.value)}
                    className={cn(
                      "px-3 py-1.5 rounded-lg text-xs font-medium transition-all border",
                      seg.effects.includes(fx.value)
                        ? "bg-primary/20 border-primary/40 text-primary shadow-[0_0_10px_rgba(124,58,237,0.2)]"
                        : "bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10"
                    )}
                  >
                    {fx.label}
                  </button>
                ))}
              </div>
            </div>
            
            <AssetSelectModal
              isOpen={modalOpenIdx === idx}
              onClose={() => setModalOpenIdx(null)}
              assetTypeFilter="clip"
              multiple={true}
              onSelectMultiple={(assets) => handleAssetSelectMultiple(idx, assets)}
            />
          </div>
        ))}
      </div>

      <div className="flex justify-between pt-4 border-t border-white/10">
        <button onClick={onPrev} className="px-6 py-3 rounded-xl font-medium text-white/80 hover:text-white hover:bg-white/5 transition-colors">
          Quay lại
        </button>
        <Button onClick={onNext} disabled={!canGoNext} className="glowing-button px-8 py-3 rounded-xl font-medium">
          Cài đặt Render <ChevronRight className="w-5 h-5 ml-2" />
        </Button>
      </div>
    </div>
  );
}
