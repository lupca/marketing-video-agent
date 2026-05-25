import { useState } from "react";
import { ArrowLeft, Save, Send, Film, Check, Loader2 } from "lucide-react";
import { Button } from "./Button";

interface JobActionButtonsProps {
  currentStep: number;
  totalSteps: number;
  loading: boolean;
  uploadStatus: string;
  isDraft: boolean;
  canGoNext?: boolean;
  onPrev?: () => void;
  onNext?: () => void;
  onSubmit: () => Promise<void>;
  onCapCutSubmit?: () => Promise<void>;
  onSaveDraft?: () => Promise<void>;
}

export function JobActionButtons({
  currentStep,
  totalSteps,
  loading,
  uploadStatus,
  isDraft,
  canGoNext = true,
  onPrev,
  onNext,
  onSubmit,
  onCapCutSubmit,
  onSaveDraft
}: JobActionButtonsProps) {
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved">("idle");

  const handleSaveDraft = async () => {
    if (!onSaveDraft) return;
    setSaveState("saving");
    try {
      await onSaveDraft();
      setSaveState("saved");
      setTimeout(() => setSaveState("idle"), 2000);
    } catch (err) {
      console.error(err);
      setSaveState("idle");
    }
  };

  const isLastStep = currentStep === totalSteps;

  return (
    <div className="sticky bottom-0 bg-[#161622]/95 backdrop-blur-md border-t border-white/10 p-6 -mx-6 lg:-mx-10 -mb-6 lg:-mb-10 flex flex-wrap items-center justify-between gap-4 z-20 rounded-b-2xl shadow-[0_-10px_30px_rgba(0,0,0,0.6)] animate-in fade-in duration-300">
      
      {/* Left: Back Button */}
      <div>
        {currentStep > 1 && onPrev && (
          <button
            onClick={onPrev}
            disabled={loading}
            className="inline-flex items-center justify-center px-5 py-2.5 rounded-xl border border-white/10 bg-white/5 text-sm font-semibold text-white/80 hover:text-white hover:bg-white/10 transition-all disabled:opacity-50 gap-1.5 cursor-pointer"
          >
            <ArrowLeft className="w-4 h-4" /> Quay lại
          </button>
        )}
      </div>

      {/* Right controls */}
      <div className="flex items-center gap-3">
        
        {/* Save Draft Button (Available in any step if it's a draft job) */}
        {isDraft && onSaveDraft && (
          <Button
            onClick={handleSaveDraft}
            isLoading={saveState === "saving"}
            disabled={loading || saveState === "saved"}
            variant="secondary"
            className={`px-5 py-2.5 rounded-xl text-sm font-semibold border transition-all gap-1.5 min-w-[130px] ${
              saveState === "saved"
                ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-400"
                : "border-white/10 bg-white/5 text-white/80 hover:text-white hover:bg-white/10"
            }`}
          >
            {saveState === "idle" && <Save className="w-4 h-4" />}
            {saveState === "saving" && <Loader2 className="w-4 h-4 animate-spin" />}
            {saveState === "saved" && <Check className="w-4 h-4 text-emerald-400" />}
            {saveState === "idle" && "Lưu nháp"}
            {saveState === "saving" && "Đang lưu..."}
            {saveState === "saved" && "Đã lưu!"}
          </Button>
        )}

        {/* Step-by-Step Navigation: Next Button */}
        {!isLastStep && onNext && (
          <Button
            onClick={onNext}
            disabled={!canGoNext || loading}
            className="glowing-button px-6 py-2.5 rounded-xl text-sm font-bold shadow-[0_0_15px_rgba(124,58,237,0.4)] flex items-center gap-1.5"
          >
            Tiếp tục
          </Button>
        )}

        {/* Final Step Submission Buttons */}
        {isLastStep && (
          <>
            {onCapCutSubmit && (
              <Button
                onClick={onCapCutSubmit}
                isLoading={loading}
                variant="secondary"
                className="px-6 py-2.5 rounded-xl text-sm font-bold border border-rose-500/30 bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 transition-all hover:shadow-[0_0_20px_rgba(244,63,94,0.4)] flex items-center gap-1.5"
              >
                {!loading && <Film className="w-4 h-4 text-rose-400" />}
                {loading ? (uploadStatus || "Đang xử lý...") : "Dựng với CapCut"}
              </Button>
            )}
            
            <Button
              onClick={onSubmit}
              isLoading={loading}
              className="glowing-button px-8 py-2.5 rounded-xl text-sm font-bold shadow-[0_0_25px_rgba(124,58,237,0.5)] flex items-center gap-1.5"
            >
              {!loading && <Send className="w-4 h-4" />}
              {loading ? (uploadStatus || "Đang xử lý...") : "Gửi Render Video"}
            </Button>
          </>
        )}

      </div>
    </div>
  );
}
