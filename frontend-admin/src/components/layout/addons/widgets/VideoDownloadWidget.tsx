import { useState } from "react";
import { DownloadCloud, Film, Music, AlertCircle, Loader2, CheckCircle2, Send } from "lucide-react";
import api from "../../../../lib/api";
import { cn } from "../../../../lib/utils";

export default function VideoDownloadWidget() {
  const [url, setUrl] = useState("");
  const [downloadFormat, setDownloadFormat] = useState<"video" | "audio">("video");
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState<"idle" | "downloading" | "success" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!url.trim()) {
      setError("Vui lòng nhập đường dẫn video.");
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      setStatus("downloading");

      await api.post("/api/downloads", {
        url: url.trim(),
        format: downloadFormat
      });

      setUrl("");
      setStatus("success");
      setTimeout(() => setStatus("idle"), 4000);
    } catch (err: any) {
      console.error("Failed to trigger download in addon:", err);
      setStatus("error");
      setError(err?.response?.data?.detail || err.message || "Đã xảy ra lỗi khi tạo yêu cầu tải.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Khung trạng thái tải */}
      {status === "downloading" || status === "success" || status === "error" ? (
        <div className="bg-black/30 border border-white/10 rounded-2xl p-5 text-center min-h-[140px] flex flex-col items-center justify-center">
          {status === "downloading" ? (
            <div className="space-y-3">
              <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto" />
              <div>
                <p className="text-xs font-bold text-white">Render Farm đang tải video...</p>
                <p className="text-[10px] text-muted-foreground">Tiến trình đang chạy ngầm trong cơ sở dữ liệu.</p>
              </div>
            </div>
          ) : status === "success" ? (
            <div className="space-y-3 animate-in fade-in duration-300">
              <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto" />
              <div>
                <p className="text-xs font-bold text-white">Yêu cầu tải thành công!</p>
                <p className="text-[10px] text-muted-foreground leading-relaxed max-w-[200px] mx-auto">
                  Video đang được lưu trữ vào kho của hệ thống. Bạn có thể kiểm tra ở mục **Sưu tầm Video** chính.
                </p>
              </div>
              <button
                onClick={() => setStatus("idle")}
                className="text-[10px] text-primary hover:underline font-bold uppercase tracking-wider cursor-pointer"
              >
                Tải thêm video khác
              </button>
            </div>
          ) : (
            <div className="space-y-3 p-2">
              <AlertCircle className="w-8 h-8 text-red-500 mx-auto" />
              <p className="text-xs font-bold text-white">Lỗi tải xuống</p>
              <p className="text-[10px] text-red-400 leading-tight line-clamp-2">{error || "Vui lòng kiểm tra lại liên kết."}</p>
              <button
                onClick={() => setStatus("idle")}
                className="px-3.5 py-1.5 bg-white/5 border border-white/10 rounded-xl text-[10px] font-bold text-white hover:bg-white/10 cursor-pointer"
              >
                Thử lại
              </button>
            </div>
          )}
        </div>
      ) : (
        /* Trạng thái trống */
        <div className="bg-black/30 border border-dashed border-white/10 rounded-2xl p-6 text-center text-muted-foreground/60 select-none">
          <DownloadCloud className="w-10 h-10 mx-auto opacity-30 mb-2" />
          <p className="text-[11px] font-medium leading-relaxed max-w-[200px] mx-auto">
            Hỗ trợ tải video chất lượng gốc từ Youtube, Tiktok, v.v. và chuyển đổi nhạc MP3.
          </p>
        </div>
      )}

      {/* Form Nhập Liệu */}
      <div className="space-y-4 pt-2">
        {/* Định dạng tải */}
        <div className="space-y-1.5">
          <label className="text-[11px] font-semibold text-muted-foreground">Định dạng file cần tải</label>
          <div className="flex gap-2">
            {[
              { id: "video", name: "Tải Video", icon: Film, desc: "Định dạng MP4" },
              { id: "audio", name: "Tải Nhạc", icon: Music, desc: "Định dạng MP3" }
            ].map((f) => {
              const Icon = f.icon;
              const isSelected = downloadFormat === f.id;
              return (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => setDownloadFormat(f.id as any)}
                  disabled={submitting}
                  className={cn(
                    "flex-1 p-2.5 rounded-xl text-[10px] font-bold border transition-all cursor-pointer text-center flex flex-col items-center gap-1",
                    isSelected
                      ? "bg-primary/20 border-primary text-primary"
                      : "bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10"
                  )}
                >
                  <Icon className="w-4 h-4" />
                  <span>{f.name}</span>
                  <span className="text-[7.5px] opacity-60 font-normal">{f.desc}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Nhập URL */}
        <div className="space-y-1.5">
          <label className="text-[11px] font-semibold text-muted-foreground">Đường dẫn Video (URL)</label>
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={submitting}
            placeholder="Dán liên kết YouTube Shorts, TikTok..."
            className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-xs text-white placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>

        {error && status !== "error" && (
          <div className="p-2.5 bg-red-500/10 border border-red-500/20 rounded-xl text-[10px] text-red-400 flex items-center gap-2">
            <AlertCircle className="w-3.5 h-3.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Nút gửi */}
        <button
          onClick={handleSubmit}
          disabled={submitting || !url.trim()}
          className={cn(
            "w-full py-3 bg-gradient-to-r from-violet-600 to-indigo-600 hover:scale-[1.01] text-white rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2 shadow-lg cursor-pointer",
            (submitting || !url.trim()) && "opacity-50 cursor-not-allowed hover:scale-100"
          )}
        >
          {submitting ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Đang tạo yêu cầu tải...
            </>
          ) : (
            <>
              <Send className="w-4 h-4" />
              Bắt đầu tải về
            </>
          )}
        </button>
      </div>
    </div>
  );
}
