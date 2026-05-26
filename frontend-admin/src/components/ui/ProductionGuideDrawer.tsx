import { useState, useEffect } from "react";
import { BookOpen, X, FileText } from "lucide-react";
import { cn } from "../../lib/utils";
import { ContentReviewWorker, ContentUnboxWorker, ContentSlideshowWorker } from "../../pages/Guides";

interface ProductionGuideDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  jobType: string;
  tmcpContext?: any;
}

export function ProductionGuideDrawer({ isOpen, onClose, jobType, tmcpContext }: ProductionGuideDrawerProps) {
  const [activeTab, setActiveTab] = useState<"guide" | "tmcp">(tmcpContext ? "tmcp" : "guide");

  // Sync tab active when open or context changes
  useEffect(() => {
    if (isOpen) {
      if (tmcpContext) {
        setActiveTab("tmcp");
      } else {
        setActiveTab("guide");
      }
    }
  }, [tmcpContext, isOpen]);

  // Handle backdrop transition class
  const [showBackdrop, setShowBackdrop] = useState(false);
  useEffect(() => {
    if (isOpen) {
      setShowBackdrop(true);
    } else {
      const timer = setTimeout(() => setShowBackdrop(false), 500);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  return (
    <div
      className={cn(
        "fixed inset-y-0 right-0 z-50 flex pl-10 transition-transform duration-500 ease-out",
        isOpen ? "translate-x-0" : "translate-x-full"
      )}
    >
      {/* Glassmorphism Backdrop with smooth opacity transition */}
      {showBackdrop && (
        <div
          className={cn(
            "fixed inset-0 -z-10 bg-black/40 backdrop-blur-sm transition-opacity duration-500 ease-out",
            isOpen ? "opacity-100" : "opacity-0"
          )}
          onClick={onClose}
        />
      )}

      {/* Main Drawer Body */}
      <div className="w-screen max-w-2xl border-l border-white/10 bg-[#0f111a]/95 p-6 shadow-2xl backdrop-blur-md flex flex-col h-full text-white">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/10 pb-4">
          <div>
            <h3 className="text-xl font-bold text-white flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-violet-400 animate-pulse" />
              Tài Liệu Hỗ Trợ Biên Tập
            </h3>
            <p className="text-xs text-muted-foreground mt-0.5">Bản hướng dẫn và yêu cầu kịch bản tích hợp</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-2 hover:bg-white/5 text-muted-foreground hover:text-white transition-colors focus:outline-none"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Dynamic Navigation Tabs */}
        <div className="flex gap-2 border-b border-white/5 my-4">
          {tmcpContext && (
            <button
              onClick={() => setActiveTab("tmcp")}
              className={cn(
                "pb-3 px-4 text-sm font-semibold transition-all relative focus:outline-none",
                activeTab === "tmcp" ? "text-cyan-400" : "text-muted-foreground hover:text-white"
              )}
            >
              📋 Kịch Bản Gốc TMCP
              {activeTab === "tmcp" && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-cyan-400 rounded-t-full shadow-[0_0_10px_rgba(34,211,238,0.5)]" />
              )}
            </button>
          )}
          <button
            onClick={() => setActiveTab("guide")}
            className={cn(
              "pb-3 px-4 text-sm font-semibold transition-all relative focus:outline-none",
              activeTab === "guide" ? "text-violet-400" : "text-muted-foreground hover:text-white"
            )}
          >
            💡 Hướng Dẫn Kỹ Thuật (Worker)
            {activeTab === "guide" && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-violet-400 rounded-t-full shadow-[0_0_10px_rgba(124,58,237,0.5)]" />
            )}
          </button>
        </div>

        {/* Tab Content Panels */}
        <div className="flex-1 overflow-y-auto pr-2 space-y-6">
          {activeTab === "tmcp" && tmcpContext && (
            <div className="space-y-6 animate-in fade-in duration-300">
              {/* Campaign & Brand contexts */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4 hover:border-cyan-500/30 transition-all">
                  <h4 className="text-xs font-bold text-cyan-400 uppercase tracking-wider mb-2">Chiến Dịch</h4>
                  <p className="text-sm font-semibold text-white">
                    {tmcpContext.campaign_context?.campaign_name || "N/A"}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Đối tượng: {tmcpContext.campaign_context?.target_audience || "Mọi người"}
                  </p>
                </div>
                <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4 hover:border-emerald-500/30 transition-all">
                  <h4 className="text-xs font-bold text-emerald-400 uppercase tracking-wider mb-2">Thương Hiệu</h4>
                  <p className="text-sm font-semibold text-white">
                    {tmcpContext.brand_context?.brand_name || "N/A"}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Tone giọng: {tmcpContext.brand_context?.tone_of_voice || "Tự nhiên"}
                  </p>
                </div>
              </div>

              {/* Master Contents Brief from TMCP */}
              {(tmcpContext.master_contents_brief || tmcpContext.variant_data?.master_contents_brief) && (
                <div className="rounded-xl border border-violet-500/20 bg-violet-500/5 p-5 animate-in fade-in duration-300">
                  <h4 className="text-sm font-bold text-white flex items-center gap-2 mb-3">
                    <FileText className="w-4 h-4 text-violet-400" />
                    Tóm Tắt Nội Dung Chính (Master Brief)
                  </h4>
                  <div className="bg-black/30 rounded-lg p-4 font-mono text-xs text-gray-300 leading-relaxed max-h-48 overflow-y-auto whitespace-pre-line border border-white/5 shadow-inner">
                    {tmcpContext.master_contents_brief || tmcpContext.variant_data?.master_contents_brief}
                  </div>
                </div>
              )}

              {/* Detailed Script from TMCP */}
              <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-5">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-sm font-bold text-white flex items-center gap-2">
                    <FileText className="w-4 h-4 text-cyan-400" />
                    Kịch Bản Chi Tiết (Video Script)
                  </h4>
                  {tmcpContext.variant_data?.suggested_duration && (
                    <span className="text-[10px] bg-cyan-400/20 text-cyan-300 px-2 py-0.5 rounded font-mono">
                      {tmcpContext.variant_data.suggested_duration}s
                    </span>
                  )}
                </div>
                <div className="bg-black/30 rounded-lg p-4 font-mono text-xs text-gray-300 leading-relaxed max-h-96 overflow-y-auto whitespace-pre-line border border-white/5 shadow-inner">
                  {tmcpContext.variant_data?.script_content || "Không tìm thấy nội dung kịch bản gốc."}
                </div>
              </div>
            </div>
          )}

          {activeTab === "guide" && (
            <div className="animate-in fade-in duration-300">
              {/* Integrates existing worker guides */}
              {jobType === "review" && <ContentReviewWorker />}
              {jobType === "unbox" && <ContentUnboxWorker />}
              {jobType === "unbox_viral" && <ContentUnboxWorker />}
              {jobType === "slideshow" && <ContentSlideshowWorker />}
              {!["review", "unbox", "unbox_viral", "slideshow"].includes(jobType) && (
                <div className="text-muted-foreground text-sm flex items-center justify-center p-12 border border-white/5 rounded-xl bg-white/[0.01]">
                  Hướng dẫn của định dạng "{jobType}" đang được cập nhật...
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
