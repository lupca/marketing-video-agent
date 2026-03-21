import React, { useState } from 'react';
import { Check, Copy, Sparkles, Zap, AlignLeft, Info, Code as CodeIcon, Settings, Target, Bot } from 'lucide-react';
import { cn } from '../lib/utils';

// Helper component for Code Block with Copy capability
const CodeBlock = ({ code, language, title }: { code: string; language?: string; title?: string }) => {
  const [copied, setCopied] = useState(false);

  const copyToClipboard = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-6 overflow-hidden rounded-xl border border-white/10 bg-[#0f1117] shadow-lg">
      <div className="flex items-center justify-between border-b border-white/5 bg-white/5 px-4 py-2">
        <div className="flex items-center gap-2">
          {language === 'json' ? <CodeIcon className="w-4 h-4 text-emerald-400" /> : <AlignLeft className="w-4 h-4 text-amber-400" />}
          <span className="text-xs font-mono text-muted-foreground">{title || language?.toUpperCase() || 'CODE'}</span>
        </div>
        <button
          onClick={copyToClipboard}
          className="flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-white/10 hover:text-white"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <div className="p-4 overflow-x-auto text-sm font-mono text-gray-300">
        <pre className="whitespace-pre-wrap"><code>{code}</code></pre>
      </div>
    </div>
  );
};

const SectionHeading = ({ children, icon: Icon }: { children: React.ReactNode; icon: React.ElementType }) => (
  <h2 className="mt-8 mb-4 flex items-center gap-2 text-xl font-semibold text-white">
    <Icon className="w-6 h-6 text-primary" />
    {children}
  </h2>
);

const ContentReviewWorker = () => (
  <div className="space-y-6 text-gray-300 leading-relaxed font-light">
    <div className="rounded-xl border border-primary/20 bg-primary/5 p-6 shadow-sm">
      <h1 className="flex items-center gap-3 text-3xl font-bold bg-gradient-to-r from-violet-400 to-fuchsia-400 bg-clip-text text-transparent mb-4">
        <Sparkles className="w-8 h-8 text-violet-400" />
        Hướng Dẫn: Plugin Video Review
      </h1>
      <p className="text-lg text-white/80">
        Công cụ <strong className="font-semibold text-white">Worker Review</strong> giúp bạn tạo nội dung Viral mang tính kể chuyện / thuyết minh. Hệ thống tự động nối Clip B-Roll theo ngữ cảnh Voiceover, chèn hiệu ứng (Shake, Zoom) và Auto Subtitle nổi bật Key Words theo phong cách Alex Hormozi.
      </p>
    </div>

    <div className="pl-2">
      <SectionHeading icon={Target}>1. Yêu cầu Input & File Kịch Bản</SectionHeading>
      <p>
        Để Worker dựng video thành công, cấu hình Input API cần truyền cấu trúc <code className="text-pink-400 bg-pink-400/10 px-1.5 py-0.5 rounded">config_data</code> chi tiết:
      </p>

      <div className="mt-6 mb-4">
        <h3 className="text-lg font-medium text-white">A. Cấu trúc Metadata & Assets</h3>
        <p className="text-sm text-muted-foreground mt-1">
          Tham khảo cơ bản nội dung Payload gọi xuống hệ thống. Thông thường API từ form tạo Job sẽ gửi.
        </p>
        <CodeBlock 
          language="json" 
          title="JSON Payload"
          code={`{
  "project_id": "review_vot_caulong",
  "assets": {
    "logo": { "width": 160, "opacity": 0.9 }, // Có thể ko gửi param này
    "audio": { 
      "voiceover_path": "s3://videos/assets/audio/voice.mp3", 
      "voiceover_script": "s3://videos/assets/audio/voice.txt" // <-- CỰC KỲ QUAN TRỌNG CHO AUTO SUBTITLE CHUẨN XÁC
    },
    "video_folders": { 
      "01_hook": "s3://videos/assets/segments/hook/", // URL Folder B-Roll Raw lưu tại hệ thống Minio 
      "02_body": "s3://videos/assets/segments/body/"
    }
  },
  "timeline_script": [ ... ]
}`} 
        />
      </div>

      <div className="mt-8 mb-4">
        <h3 className="text-lg font-medium text-white mb-2">B. Mẹo Cấu Hình Phân Đoạn (Timeline Script) Cực Cháy</h3>
        <p>
          <code className="text-pink-400 bg-pink-400/10 px-1.5 py-0.5 rounded">timeline_script</code> chứa các cụm (hook, body, cta). Nhịp độ cực quan trọng giữ chân Viewer:
        </p>
        <CodeBlock 
          language="json" 
          title="Timeline Element Script"
          code={`{
  "segment": "Hook",
  "time_range": [0, 2.5],  // Giây từ 0 đến 2.5 theo Voice
  "video_source": "01_hook", 
  "text_overlay": "MUA VỢT SAI = MẤT CẢ MÙA GIẢI?", // Text nổi làm nổi bật chính
  "highlight_words": ["SAI", "MẤT CẢ MÙA GIẢI"], // Bôi vàng text nổi
  "visual_effects": ["slow_motion_0.5x", "snap_zoom"], // Phóng to tạo ấn tượng
  "pacing": { "min_clip_duration": 0.5, "max_clip_duration": 0.8 } // Chuyển cảnh nhanh để dồn dập
}`} 
        />
      </div>

      <div className="my-8 h-px bg-white/10" />

      <SectionHeading icon={Bot}>2. Prompt Nhờ AI Tạo Kịch Bản Review Cực Tốc Độ</SectionHeading>
      <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 mb-4 flex gap-3">
        <Info className="w-6 h-6 text-amber-500 flex-shrink-0" />
        <p className="text-sm text-amber-200/80">
          Hãy copy toàn bộ đoạn text dưới đây, điền chủ đề và gửi vào ChatGPT / Claude để AI tự xuất Kịch bản Voiceover, File hướng dẫn Quay Video & Cấu hình JSON cho hệ thống gọi API:
        </p>
      </div>

      <CodeBlock 
        language="text" 
        title="Prompt dành cho ChatGPT/Claude"
        code={`Bạn là chuyên gia kịch bản video TikTok viral, retention rate cao với pacing liên tục. 
Nhiệm vụ: Viết kịch bản video review (dưới 60s) về: [ĐIỀN CHỦ ĐỀ VÀO ĐÂY, VÍ DỤ: "Review vợt Astrox Lite"].

Hệ thống render tự động của tôi dùng phân đoạn để ghép Source broll với Voiceover, có hiệu ứng giật camera (camera_shake), zoom (snap_zoom), Auto Subtitles bôi vàng keywords (highlight_words). Phân chia output làm 3 phần RÕ RÀNG:

### PHẦN 1: FILE GIỌNG ĐỌC (vo.txt)
Viết phần voiceover kịch bản, lời văn Gen Z tự nhiên. Có ngắt nghỉ chấm, phẩy đàng hoàng (Không tự nghĩ chèn emoji hay action). Hook nói cực bắt tai.

### PHẦN 2: HƯỚNG DẪN QUAY B-ROLL 
Tư vấn quay các góc máy điện thoại phân chia vào các thư mục:
- 01_hook: Góc sốc / tò mò.
- 02_problem: Vấn đề đau đớn người mua hay gặp.
- 03_solution: Lợi ích cực mạnh.
- 04_demo: Quay test đập góc thực tế.
- 05_cta: Front Camera hô hào cta.

### PHẦN 3: FILE CẤU HÌNH INPUT JSON
Dựa trên vo.txt, nhắm khoảng timeline. Người VN đọc trung bình 4 từ/s. 
Format JSON cho một phần tử mảng timeline_script hệ thống là:
{
  "segment": "Tên",
  "time_range": [giây bắt đầu, giây kết thúc],
  "video_source": "tên_thư_mục_broll",
  "text_overlay": "Dòng Text ngắn gọn hiện giữa màn",
  "highlight_words": ["TỪ BÔI VÀNG"],
  "visual_effects": ["camera_shake", "snap_zoom"], // Không bắt buộc, có thể trống
  "pacing": {"min_clip_duration": 0.5, "max_clip_duration": 1.5}
}
Lưu ý: Pacing đoạn quan trọng cao trào hãy rát cực ngắn (0.4-0.9), text_overlay móc trộm CTA thôi. In đúng JSON, nối tiếp time_range không thủng thời gian!`} 
      />

      <div className="mt-8 rounded-xl bg-primary/10 border border-primary/20 p-5 items-center flex gap-4">
        <Sparkles className="w-8 h-8 text-primary flex-shrink-0" />
        <div>
          <h4 className="font-semibold text-white mb-1">Mẹo sử dụng kết quả</h4>
          <p className="text-sm text-primary-50">
            Chỉ cần đọc thu phần Voiceover (<code className="bg-black/30 px-1 rounded">.mp3</code>), lưu nội dung Text ra file txt. Quay B-roll quăng tất vào theo list AI gợi ý, ghép cái JSON API và nhấn <strong>Render!</strong>
          </p>
        </div>
      </div>
    </div>
  </div>
);

// We need an icon for Bot (missing from imports). I'll use FileText or replace it. I'll import Bot at the top actually in the final code.
// Replacing Bot with Zap above.

const ContentUnboxWorker = () => (
  <div className="space-y-6 text-gray-300 leading-relaxed font-light">
    <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-6 shadow-sm shadow-cyan-900/20">
      <h1 className="flex items-center gap-3 text-3xl font-bold bg-gradient-to-r from-cyan-400 to-emerald-400 bg-clip-text text-transparent mb-4">
        <Zap className="w-8 h-8 text-cyan-400" />
        Hướng Dẫn: Plugin Video Unbox
      </h1>
      <p className="text-lg text-white/80">
        Công cụ <strong className="font-semibold text-white">Worker Unbox</strong> được thiết kế đặc biệt cho dạng Video Viral, Music Sync. Hệ thống sẽ tự động bắt cảnh quay cắt ghép nối tiếp nhau khớp từng nhịp đập âm nhạc (Beat-drop sync).
      </p>
    </div>

    <div className="pl-2">
      <SectionHeading icon={Settings}>1. Cơ chế Hoạt Động Kỹ Thuật</SectionHeading>
      <p className="mb-4">
        Đây là một Engine render sử dụng <strong className="text-white">FFmpeg</strong> xử lý luồng Video kết hợp thư viện <code className="text-cyan-400 bg-cyan-400/10 px-1.5 py-0.5 rounded">librosa</code> xử lý Audio.
      </p>

      <ul className="space-y-4 mb-8">
        {[
          { title: "Phát hiện Beat (Beat-drop detect)", desc: "librosa phân tích File âm thanh MP3 đầu vào để tạo danh sách mốc thời gian beat-drop mạnh." },
          { title: "Cắt mượt & Loại bỏ Silence", desc: "Tìm ngưỡng im lặng silence_db trong các File Clip thô .mov, auto cắt bỏ đoạn chết (Trim đầu/cuối), và chuẩn hóa khung hình dọc 1080x1920@30fps." },
          { title: "Lên Kế Hoạch Scene (Scene Planning)", desc: "Cắt scene (cảnh) bám theo Beat hoặc Random planning trong khoảng Min/Max [scene_min_seconds, scene_max_seconds]." },
          { title: "Nối Scene bằng Hiệu Ứng", desc: "xfade để thay đổi qua lại giữa cảnh. Hỗ trợ luân phiên hiệu ứng như fade, slideleft liên tục. Hiệu ứng Ken Burns (Zoom trượt êm ái x/y) chạy mặc định tạo nhịp độ sống động." },
          { title: "Overlay Text (Chữ Tốc Độ)", desc: "Render nội dung chữ (Hook, Lợi ích Feature) bằng FFmpeg drawtext đè nháy ngay điểm quan trọng." },
        ].map((item, idx) => (
          <li key={idx} className="flex gap-4 p-4 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors">
            <div className="flex items-center justify-center w-8 h-8 rounded-full bg-cyan-500/20 text-cyan-400 font-bold flex-shrink-0">
              {idx + 1}
            </div>
            <div>
              <h4 className="font-semibold text-white mb-1">{item.title}</h4>
              <p className="text-sm text-gray-400">{item.desc}</p>
            </div>
          </li>
        ))}
      </ul>

      <div className="my-8 h-px bg-white/10" />

      <SectionHeading icon={Target}>2. Dữ liệu Input & Config</SectionHeading>
      <p>
        Dữ liệu do API truyền xuống là mảng <code className="text-cyan-400 bg-cyan-400/10 px-1.5 py-0.5 rounded">config_data</code>:
      </p>
      <CodeBlock 
        language="json" 
        title="Unbox Config Data"
        code={`{
  "clips": [
    "s3://videos/assets/unbox/clip1.mov",
    "s3://videos/assets/unbox/clip2.mov"
  ],
  "audio": "s3://videos/assets/audio/the_mountain-tiktok.mp3",
  "text_events": [
    {"time": 0.0, "text": "VỢT CẦU LÔNG SIÊU ĐỈNH", "effect": "hook"},
    {"time": 3.2, "text": "Cuốn cán chính hãng", "effect": "feature"}
  ]
}`} 
      />

      <div className="my-8 h-px bg-white/10" />

      <SectionHeading icon={CodeIcon}>3. Tinh Chỉnh Nâng Cao (Dành cho Developer)</SectionHeading>
      <div className="rounded-xl border-l-4 border-red-500 bg-red-500/10 p-5 mt-4 text-sm">
        <p className="font-bold text-red-400 mb-3 uppercase tracking-wider text-xs">Phần cấu hình hệ thống Core</p>
        <p className="mb-4">Khi điều chỉnh Source hệ thống trong <code className="bg-black/30 px-1.5 py-0.5 rounded font-mono text-red-300">make_viral.py</code>:</p>
        <ul className="space-y-3 list-disc pl-5 marker:text-red-500/50">
          <li>
            <strong className="text-white">Tăng tốc độ luân chuyển Scene:</strong> Giảm <code className="text-red-300 bg-black/20 px-1">xfade_duration</code> (Mặc định 0.5s) xuống <code className="text-red-300 bg-black/20 px-1">0.2s - 0.4s</code> tạo nét cắt gắt. Hoặc giảm biến thời gian <code className="text-red-300 bg-black/20 px-1">scene_max_seconds</code>.
          </li>
          <li>
            <strong className="text-white">Thay Tốc Độ Zoom (Ken Burns):</strong> Bên trong hàm <code className="text-red-300 bg-black/20 px-1">_render_scene()</code>, thay đổi hệ số trượt <code className="text-red-300 bg-black/20 px-1">z='min(zoom+0.0015,1.15)'</code>. Phóng to <code className="text-red-300 bg-black/20 px-1">0.0018</code> dồn dập, <code className="text-red-300 bg-black/20 px-1">0.0012</code> êm trôi.
          </li>
          <li>
            <strong className="text-white">Render Output Bị Lỗi (Giật Lag):</strong> Có thể do Drop Rate khung hình ảo khi FFmpeg scale. Giữ nguyên force Output Filter: <code className="text-red-300 bg-black/20 px-1">s=1080x1920:fps=30</code> trước khi qua Zoompan.
          </li>
          <li>
            <strong className="text-white">Thiếu FFmpeg Drawtext Backend:</strong> Module tự bắt <code className="text-red-300 bg-black/20 px-1">OverlayError</code> để đổi qua Fallback chạy MoviePy/Pillow Render Text dán đè thay nếu OS Developer không build bản có Drawtext.
          </li>
        </ul>
      </div>
    </div>
  </div>
);

export default function Guides() {
  const [activeTab, setActiveTab] = useState<'review' | 'unbox'>('review');

  return (
    <div className="p-8 max-w-5xl mx-auto pb-24 animate-in fade-in duration-500">
      <div className="mb-10">
        <h1 className="text-4xl font-extrabold text-white tracking-tight mb-3">Content Marketing Guides</h1>
        <p className="text-muted-foreground text-lg">
          Hướng dẫn chi tiết cách thức cấu hình và tạo prompt kịch bản cho các Plugin tạo Video của VidGenius.
        </p>
      </div>

      <div className="flex gap-4 mb-8 border-b border-white/10 pb-px">
        <button
          onClick={() => setActiveTab('review')}
          className={cn(
            "pb-4 px-2 text-sm font-semibold transition-all relative",
            activeTab === 'review' 
              ? "text-primary" 
              : "text-muted-foreground hover:text-white"
          )}
        >
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4" />
            Review Video Guide
          </div>
          {activeTab === 'review' && (
            <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary rounded-t-full shadow-[0_-2px_8px_rgba(124,58,237,0.5)]" />
          )}
        </button>
        <button
          onClick={() => setActiveTab('unbox')}
          className={cn(
            "pb-4 px-2 text-sm font-semibold transition-all relative",
            activeTab === 'unbox' 
              ? "text-cyan-400" 
              : "text-muted-foreground hover:text-white"
          )}
        >
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4" />
            Unbox Video Guide
          </div>
          {activeTab === 'unbox' && (
            <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-cyan-400 rounded-t-full shadow-[0_-2px_8px_rgba(34,211,238,0.5)]" />
          )}
        </button>
      </div>

      <div className="transition-all duration-300">
        {activeTab === 'review' ? <ContentReviewWorker /> : <ContentUnboxWorker />}
      </div>
    </div>
  );
}
