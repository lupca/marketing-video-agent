import React, { useState } from 'react';
import { Check, Copy, Sparkles, Zap, AlignLeft, Info, Code as CodeIcon, Settings, Target, Bot, Layout } from 'lucide-react';
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

const ContentUnboxWorker = () => {
  const [unboxType, setUnboxType] = useState<'compare' | 'basic' | 'viral'>('compare');

  return (
    <div className="space-y-6 text-gray-300 leading-relaxed font-light">
      <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-6 shadow-sm shadow-cyan-900/20">
        <h1 className="flex items-center gap-3 text-3xl font-bold bg-gradient-to-r from-cyan-400 to-emerald-400 bg-clip-text text-transparent mb-4">
          <Zap className="w-8 h-8 text-cyan-400" />
          Hướng Dẫn: Plugin Video Unbox
        </h1>
        <p className="text-lg text-white/80">
          Công cụ <strong className="font-semibold text-white">Worker Unbox</strong> cung cấp 2 chế độ tạo Video Viral không lời cực mạnh bám theo nhạc percussive sôi động (EDM, Phonk). Hãy chọn chế độ phù hợp với nguyên liệu video của bạn:
        </p>
        
        {/* Sub-tabs for Unbox Mode selector */}
        <div className="flex flex-wrap gap-3 mt-6">
          <button
            onClick={() => setUnboxType('compare')}
            className={cn(
              "px-4 py-2 rounded-xl text-xs font-bold border transition-all duration-200",
              unboxType === 'compare'
                ? "bg-cyan-500/20 border-cyan-500/50 text-cyan-300 shadow-lg shadow-cyan-500/10"
                : "bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10 hover:text-white"
            )}
          >
            📊 So sánh 2 chế độ
          </button>
          <button
            onClick={() => setUnboxType('basic')}
            className={cn(
              "px-4 py-2 rounded-xl text-xs font-bold border transition-all duration-200",
              unboxType === 'basic'
                ? "bg-cyan-500/20 border-cyan-500/50 text-cyan-300 shadow-lg shadow-cyan-500/10"
                : "bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10 hover:text-white"
            )}
          >
            📦 1. Basic Unbox (Cơ Bản)
          </button>
          <button
            onClick={() => setUnboxType('viral')}
            className={cn(
              "px-4 py-2 rounded-xl text-xs font-bold border transition-all duration-200",
              unboxType === 'viral'
                ? "bg-cyan-500/20 border-cyan-500/50 text-cyan-300 shadow-lg shadow-cyan-500/10"
                : "bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10 hover:text-white"
            )}
          >
            ⚡ 2. Viral Unbox (AI Nâng Cao)
          </button>
        </div>
      </div>

      {unboxType === 'compare' && (
        <div className="space-y-6 animate-in fade-in duration-300">
          <SectionHeading icon={Target}>So sánh Basic Unbox vs Viral Unbox</SectionHeading>
          
          <div className="overflow-x-auto rounded-xl border border-white/10 bg-[#0f1117]">
            <table className="min-w-full divide-y divide-white/5 text-left text-sm text-gray-300">
              <thead className="bg-white/5 text-xs uppercase tracking-wider text-white">
                <tr>
                  <th className="px-6 py-4 font-semibold">Tính năng</th>
                  <th className="px-6 py-4 font-semibold text-cyan-400">📦 Basic Unbox (Cơ Bản)</th>
                  <th className="px-6 py-4 font-semibold text-emerald-400">⚡ Viral Unbox (AI Nâng Cao)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                <tr>
                  <td className="px-6 py-4 font-medium text-white">Nguyên liệu đầu vào (Input)</td>
                  <td className="px-6 py-4">Nhiều clip ngắn đã được quay hoặc cắt thô sẵn.</td>
                  <td className="px-6 py-4"><strong className="text-white">1 Clip dài duy nhất</strong> (1.5 - 3 phút) chứa trọn vẹn quá trình unbox có âm thanh ASMR tự nhiên.</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 font-medium text-white">Cắt ghép (Scene Cutting)</td>
                  <td className="px-6 py-4">Nối các clip ngắn lại với nhau. Chuyển cảnh trúng chính xác vào nhịp beat nhạc (Beat-sync).</td>
                  <td className="px-6 py-4">Tự động phân tích chuyển động trong clip để cắt bỏ phần tĩnh (boring frame) và giữ lại phân cảnh hành động hấp dẫn.</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 font-medium text-white">Tăng giảm tốc độ (Speed Ramp)</td>
                  <td className="px-6 py-4">Tốc độ bình thường (1x).</td>
                  <td className="px-6 py-4"><strong className="text-white">Optical-Flow Speed Ramping:</strong> Tự động tua nhanh lúc chuẩn bị/không có hành động, và làm chậm (Slow-motion) mượt mà vào lúc mở hộp, bóc seal.</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 font-medium text-white">Căn giữa khung dọc (Crop 9:16)</td>
                  <td className="px-6 py-4">Center-crop tĩnh (cắt chính giữa khung hình).</td>
                  <td className="px-6 py-4"><strong className="text-white">YOLO Smart Crop:</strong> Nhận diện sản phẩm, tay người và hộp quà để dịch chuyển camera theo vùng chuyển động, luôn giữ vật thể ở trung tâm khung dọc.</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 font-medium text-white">Xử lý âm thanh (Audio Mix)</td>
                  <td className="px-6 py-4">Chèn nhạc nền (BGM) lồng ghép đè lên video.</td>
                  <td className="px-6 py-4"><strong className="text-white">ASMR + Music Mix:</strong> Tách tiếng ASMR gốc (tiếng bóc seal, tiếng động vật lý) và trộn hoàn hảo bám theo beat nhạc nền.</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 font-medium text-white">Chèn Chữ (Text Overlays)</td>
                  <td className="px-6 py-4">Phải tự điền chính xác <strong className="text-pink-400">Timestamp (giây)</strong> chữ xuất hiện.</td>
                  <td className="px-6 py-4"><strong className="text-emerald-400">Auto Beat-Snapped:</strong> Không cần điền thời gian! Hệ thống tự động đẩy chữ nhảy ra trúng các nhịp Drop mạnh của nhạc.</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 font-medium text-white">Mục đích sử dụng tối ưu</td>
                  <td className="px-6 py-4">Làm video tổng hợp nhanh, lookbook, các clip dựng từ nhiều nguồn khác nhau.</td>
                  <td className="px-6 py-4">Làm video mở hộp sản phẩm cận cảnh cực kỳ nghệ thuật, sang xịn mịn, giữ chân người xem cao nhờ nhịp điệu dồn dập.</td>
                </tr>
              </tbody>
            </table>
          </div>
          
          <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-5 flex gap-4">
            <Sparkles className="w-8 h-8 text-cyan-400 flex-shrink-0" />
            <div>
              <h4 className="font-semibold text-white mb-1">Lời khuyên của chuyên gia Content</h4>
              <p className="text-sm text-cyan-100/90">
                Nếu bạn chỉ quay 1 cú bấm máy dài cảnh bóc hộp từ đầu tới cuối, hãy sử dụng ngay <strong className="text-cyan-300">Viral Unbox</strong>. Nếu bạn có sẵn nhiều clip khác nhau muốn ghép lại thành một video bám nhịp, hãy chọn <strong className="text-cyan-300">Basic Unbox</strong>!
              </p>
            </div>
          </div>
        </div>
      )}

      {unboxType === 'basic' && (
        <div className="space-y-6 animate-in fade-in duration-300">
          <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-6">
            <h2 className="text-2xl font-bold text-white mb-3">📦 Basic Unbox - Cắt Ghép Nhịp Beat Cổ Điển</h2>
            <p className="text-gray-300">
              Công cụ tự động cắt và chuyển đổi giữa nhiều clip ngắn của bạn khớp với các mốc Beat-drop mạnh mẽ của bài hát. Chế độ này yêu cầu bạn nhập chính xác mốc thời gian hiển thị text để video có nội dung đồng bộ nhất.
            </p>
          </div>

          <SectionHeading icon={Settings}>Cách Sử Dụng trên UI</SectionHeading>
          <ul className="space-y-3 list-decimal pl-5">
            <li>Tải lên danh sách các <strong className="text-white">Clips ngắn thô</strong> (Nhiều file khác nhau).</li>
            <li>Tải lên <strong className="text-white">Background Audio</strong> (Mặc định sẽ được phân tích beat tự động).</li>
            <li>Thêm các dòng <strong className="text-white">Text Overlay</strong> và bắt buộc điền <strong className="text-cyan-400">Timestamp (giây)</strong> để chữ xuất hiện đúng phân đoạn.</li>
            <li>Bấm <strong className="text-white">Send to Render Farm</strong> để hoàn thành.</li>
          </ul>

          <SectionHeading icon={Bot}>AI Prompt tạo kịch bản Basic Unbox (Có Giây)</SectionHeading>
          <p className="text-sm text-muted-foreground">
            Hãy copy prompt này gửi cho ChatGPT/Claude để AI tự lên danh sách text overlay kèm số giây chính xác bám theo nhịp video:
          </p>
          
          <CodeBlock
            language="text"
            title="Prompt AI cho Basic Unbox"
            code={`Bạn là chuyên gia kịch bản video TikTok. Hãy viết kịch bản video ngắn dạng beat-sync cho sản phẩm: [ĐIỀN TÊN SẢN PHẨM].
Tôi sẽ cắt video bám theo nhịp beat nhạc sôi động. Tôi cần bạn tạo chuỗi Text Overlay kèm theo giây chính xác (thường mỗi 3-4 giây xuất hiện một câu ngắn gọn dưới 5 từ).

Đầu ra in định dạng JSON chuẩn sau:
{
  "text_events": [
    {"time": 0.0, "text": "HOOK BẮT MẮT 🔥", "effect": "hook"},
    {"time": 3.0, "text": "Đặc điểm nổi bật 1", "effect": "feature"},
    {"time": 6.5, "text": "Đặc điểm nổi bật 2", "effect": "feature"},
    {"time": 9.5, "text": "Call to action mua ngay", "effect": "feature"}
  ]
}`}
          />
        </div>
      )}

      {unboxType === 'viral' && (
        <div className="space-y-6 animate-in fade-in duration-300">
          <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-6">
            <h2 className="text-2xl font-bold text-white mb-3">⚡ Viral Unbox - AI Smart Editor</h2>
            <p className="text-gray-300">
              Trải nghiệm công nghệ dựng phim tự động đỉnh cao. Hệ thống sử dụng mô hình học sâu <strong className="text-emerald-400">YOLOv8</strong> để tự động bám theo sản phẩm, tự động tua nhanh/tua chậm thông minh thông qua luồng chuyển động, và tự động trộn tiếng động ASMR thực tế vào nhạc.
            </p>
          </div>

          <SectionHeading icon={Settings}>Cách Sử Dụng trên UI</SectionHeading>
          <ul className="space-y-3 list-decimal pl-5">
            <li>Tải lên <strong className="text-white">1 Video Clip dài duy nhất</strong> (Khuyên dùng video quay quá trình mở hộp từ đầu tới cuối dài từ 1 - 3 phút, có âm thanh bóc hộp rõ nét).</li>
            <li>Tải lên <strong className="text-white">Background Audio</strong> (Bài nhạc trending bạn muốn lồng ghép).</li>
            <li>Thêm các dòng <strong className="text-white">Text Overlay</strong>. <strong className="text-emerald-400">Cực kỳ đặc biệt:</strong> Bạn KHÔNG cần điền số giây. Chỉ cần sắp xếp thứ tự các câu text, AI sẽ tự chọn các nhịp drop hay nhất để tung chữ ra màn hình!</li>
            <li>Bấm <strong className="text-white">Send to Render Farm</strong> để bắt đầu render GPU.</li>
          </ul>

          <SectionHeading icon={Bot}>AI Prompt tạo kịch bản Viral Unbox (Không Cần Giây)</SectionHeading>
          <p className="text-sm text-muted-foreground">
            Sử dụng prompt này để AI tự viết ra những câu giật tít, giới thiệu tính năng cực ngắn gọn mà không cần lo về việc tính toán số giây hiển thị:
          </p>

          <CodeBlock
            language="text"
            title="Prompt AI cho Viral Unbox"
            code={`Bạn là một bậc thầy làm video TikTok triệu view. Hãy viết nội dung chữ chèn màn hình cho video Viral Unbox sản phẩm: [ĐIỀN TÊN SẢN PHẨM].
Do hệ thống AI của tôi tự động bắt nhịp beat nhạc để chèn chữ, bạn không cần chèn giây (time). Hãy viết các câu thật ngắn gọn, punchy, đậm chất Gen Z để kích thích sự tò mò.

In kết quả theo định dạng JSON sau:
{
  "text_events": [
    {"text": "ĐẬP HỘP SIÊU PHẨM MỚI 📦", "effect": "hook"},
    {"text": "Bóc seal cực đã tay", "effect": "feature"},
    {"text": "Khung nhôm nguyên khối", "effect": "feature"},
    {"text": "Giá cực hời trong bio!", "effect": "feature"}
  ]
}`}
          />
        </div>
      )}
    </div>
  );
};

const ContentSlideshowWorker = () => (
  <div className="space-y-6 text-gray-300 leading-relaxed font-light">
    <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-6 shadow-sm shadow-amber-900/20">
      <h1 className="flex items-center gap-3 text-3xl font-bold bg-gradient-to-r from-amber-400 to-orange-400 bg-clip-text text-transparent mb-4">
        <Sparkles className="w-8 h-8 text-amber-400" />
        Hướng Dẫn: Slideshow Form Automation
      </h1>
      <p className="text-lg text-white/80">
        Công cụ <strong className="font-semibold text-white">Worker Slideshow</strong> giúp bạn tạo video quảng cáo sản phẩm nhanh chóng từ danh sách ảnh. Dưới đây là cách sử dụng AI để viết kịch bản tối ưu nhất cho công cụ này.
      </p>
    </div>

    <div className="pl-2">
      <SectionHeading icon={Bot}>1. Prompt AI Tạo Kịch Bản Điền Form Tự Động</SectionHeading>
      <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 mb-4 flex gap-3">
        <Info className="w-6 h-6 text-amber-500 flex-shrink-0" />
        <p className="text-sm text-amber-200/80">
          <strong>Cách dùng:</strong> Copy đoạn mẫu dưới đây, điền thông tin nguyên liệu thô của bạn vào phần trong ngoặc vuông <code className="bg-black/30 px-1 rounded text-amber-300">[...]</code> và gửi cho AI. AI sẽ trả về kết quả chuẩn để bạn copy thẳng vào từng ô trên giao diện phần mềm.
        </p>
      </div>

      <CodeBlock 
        language="text" 
        title="Prompt dành cho ChatGPT/Claude"
        code={`Đóng vai: Bạn là một content creator mảng cầu lông tại Hà Nội, chuyên làm nội dung review đồ "ngon-bổ-rẻ" hướng tới đối tượng Học sinh - Sinh viên.

Nhiệm vụ: Viết kịch bản video ngắn dạng Infographic. Trình bày kết quả thật rõ ràng để tôi có thể copy và dán trực tiếp vào các ô nhập liệu trên phần mềm tạo video.

Thông tin chiến dịch:
- Chủ đề/Sản phẩm: [Điền chủ đề. Ví dụ: Combo Vợt Astrox 88 Play + Cước Kizuna Z61 + Căng 11kg]
- Đặc điểm nổi bật: [Ví dụ: Vợt dễ thuần, cước nổ to, phù hợp người mới, có quà tặng kèm]

Cấu trúc khung hình (Tổng cộng [Điền số lượng ảnh] ảnh):
Ảnh 1: [Ý tưởng cho ảnh 1 - VD: Vợt Astrox 88 Play]
Ảnh 2: [Ý tưởng cho ảnh 2 - VD: Cước Kizuna Z61]
Ảnh 3: [Ý tưởng cho ảnh 3 - VD: Mức căng 11kg]
Ảnh 4: [Ý tưởng cho ảnh 4 - VD: Quà tặng kèm]

Yêu cầu đầu ra (Format Output):
Hãy xuất kết quả theo đúng cấu trúc dưới đây, ngôn từ giật tít, đậm chất Gen Z:

[CÀI ĐẶT CHUNG]
Intro Text (Mở đầu): [1 câu giật tít ngắn gọn khơi gợi sự tò mò, tối đa 15 chữ]
Outro Text (Kết thúc): [1 câu kêu gọi hành động mua hàng/click link khẩn cấp]

[DANH SÁCH SẢN PHẨM]
Ảnh 1:
Tên / Mô tả: [Mô tả lợi ích cốt lõi, ngắn gọn, súc tích]
Hook Badge: [Tối đa 3 từ, ví dụ: Vợt Quốc Dân, Siêu Bền...]

Ảnh 2:
Tên / Mô tả: [...]
Hook Badge: [...]

(Lặp lại tương tự cho đến hết số lượng ảnh)`} 
      />

      <div className="mt-8 rounded-xl bg-amber-500/10 border border-amber-500/20 p-5 items-center flex gap-4">
        <Target className="w-8 h-8 text-amber-400 flex-shrink-0" />
        <div>
          <h4 className="font-semibold text-white mb-1">Tại sao nên dùng Prompt này?</h4>
          <p className="text-sm text-amber-50">
            Prompt này giúp AI hiểu rõ <strong>đối tượng mục tiêu</strong> và <strong>văn phong</strong> mong muốn. Kết quả trả về được chia theo từng Slide, tương ứng chính xác với các ô nhập liệu giúp bạn tiết kiệm 90% thời gian lên kịch bản.
          </p>
        </div>
      </div>
    </div>
  </div>
);

export default function Guides() {
  const [activeTab, setActiveTab] = useState<'review' | 'unbox' | 'slideshow'>('review');

  const renderContent = () => {
    switch (activeTab) {
      case 'review': return <ContentReviewWorker />;
      case 'unbox': return <ContentUnboxWorker />;
      case 'slideshow': return <ContentSlideshowWorker />;
      default: return <ContentReviewWorker />;
    }
  };

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
        <button
          onClick={() => setActiveTab('slideshow')}
          className={cn(
            "pb-4 px-2 text-sm font-semibold transition-all relative",
            activeTab === 'slideshow' 
              ? "text-amber-400" 
              : "text-muted-foreground hover:text-white"
          )}
        >
          <div className="flex items-center gap-2">
            <Layout className="w-4 h-4" />
            Slideshow Video Guide
          </div>
          {activeTab === 'slideshow' && (
            <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-amber-400 rounded-t-full shadow-[0_-2px_8px_rgba(245,158,11,0.5)]" />
          )}
        </button>
      </div>

      <div className="transition-all duration-300">
        {renderContent()}
      </div>
    </div>
  );
}
