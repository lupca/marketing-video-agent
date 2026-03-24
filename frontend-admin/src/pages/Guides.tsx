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

const ContentUnboxWorker = () => (
  <div className="space-y-6 text-gray-300 leading-relaxed font-light">
    <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-6 shadow-sm shadow-cyan-900/20">
      <h1 className="flex items-center gap-3 text-3xl font-bold bg-gradient-to-r from-cyan-400 to-emerald-400 bg-clip-text text-transparent mb-4">
        <Zap className="w-8 h-8 text-cyan-400" />
        Hướng Dẫn: Plugin Video Unbox
      </h1>
      <p className="text-lg text-white/80">
        Công cụ <strong className="font-semibold text-white">Worker Unbox</strong> là giải pháp tối ưu cho dạng Video Viral không lời, tập trung vào hình ảnh và âm nhạc. Với cơ chế <strong className="text-cyan-400">Beat-drop Sync</strong>, nó có thể tạo ra nhiều loại nội dung triệu view chứ không chỉ dừng lại ở việc mở hộp sản phẩm.
      </p>
    </div>

    <div className="pl-2">
      <SectionHeading icon={Target}>1. Các loại Video Viral phù hợp nhất</SectionHeading>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        {[
          { title: "📦 Product Unboxing", desc: "Mở hộp, bóc seal, khám phá phụ kiện với âm nhạc percussive (như EDM, Phonk)." },
          { title: "✨ Lifestyle Showcase", desc: "Quay sản phẩm/trang phục ở nhiều góc độ nghệ thuật trong bối cảnh thực tế (Cinematic B-roll)." },
          { title: "🔄 Transformation / BTS", desc: "Video Before/After, quá trình hoàn thiện sản phẩm hoặc dọn dẹp setup cực nhanh." },
          { title: "🏖️ Recap & Highlights", desc: "Tóm tắt chuyến đi, sự kiện hoặc các khoảnh khắc ấn tượng bám nhịp theo bài hát sôi động." },
          { title: "🛠️ Workflow / ASMR", desc: "Các bước thực hiện một quy trình (nấu ăn, DIY) với các cú máy cận cảnh sắc nét." },
          { title: "🔥 Action / Sports", desc: "Những pha Highlight thể thao, tập luyện phối hợp với hiệu ứng Zoom mạnh trên từng nhịp drop." },
        ].map((item, idx) => (
          <div key={idx} className="p-4 rounded-xl bg-white/5 border border-white/10 flex flex-col gap-1">
            <h4 className="font-bold text-white text-base">{item.title}</h4>
            <p className="text-xs text-muted-foreground">{item.desc}</p>
          </div>
        ))}
      </div>
      <SectionHeading icon={Settings}>2. Cơ chế Hoạt Động Kỹ Thuật</SectionHeading>
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

      <SectionHeading icon={Target}>3. Dữ liệu Input & Config</SectionHeading>
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

      <SectionHeading icon={CodeIcon}>4. Tinh Chỉnh Nâng Cao (Dành cho Developer)</SectionHeading>
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

      <div className="my-8 h-px bg-white/10" />

      <SectionHeading icon={Bot}>5. Universal AI Prompt (Dành cho Content Marketing)</SectionHeading>
      <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-4 mb-4 flex gap-3">
        <Info className="w-6 h-6 text-cyan-500 flex-shrink-0" />
        <p className="text-sm text-cyan-200/80">
          Hãy copy prompt dưới đây và dán vào ChatGPT / Claude. Bạn chỉ cần thay đổi <strong>MỤC TIÊU</strong> (Unboxing, Lookbook, Travel, ...) để AI tạo ra kịch bản quay và text overlay phù hợp nhất:
        </p>
      </div>

      <CodeBlock 
        language="text" 
        title="Universal Scripting Prompt"
        code={`Bạn là chuyên gia sáng tạo nội dung Video Viral (TikTok/Reels/Shorts). Bạn giỏi trong việc lên ý tưởng hình ảnh bám theo nhịp điệu âm nhạc (Beat-sync).

Nhiệm vụ: Lên kịch bản quay B-roll và nội dung Text Overlay cho Video.
- LOẠI VIDEO: [ĐIỀN VÀO: Unboxing / Showcase / Transformation / Travel Recap / Workout / ASMR]
- CHỦ ĐỀ SẢN PHẨM: [ĐIỀN VÀO, VÍ DỤ: "Bàn phím cơ Custom"]

Hệ thống render tự động của tôi sẽ cắt đoạn thô và chèn chữ theo 2 kiểu:
1. "hook": Hiện to, nổi bật ngay giây đầu tiên (giây 0.0).
2. "feature": Chữ hiện ở góc dưới trái, trượt vào màn hình (slide-in), thường dùng để giới thiệu điểm mạnh hoặc lợi ích.

Hãy đưa ra kịch bản theo yêu cầu sau:

### PHẦN 1: Ý TƯỞNG QUAY PHIM (Dành cho Producer)
Tư vấn 15-20 cảnh quay cực ngắn (1.5s - 2.5s mỗi cảnh) phù hợp với LOẠI VIDEO đã chọn. Hãy tập trung vào các góc máy sáng tạo, ánh sáng tốt và hành động dứt khoát.
(Vd: Cú máy trượt (Slide), máy xoay (Rotate), cận cảnh macro (Close-up), quay POV người dùng).

### PHẦN 2: CHUỖI TEXT OVERLAY (JSON Format)
Dựa trên mood của LOẠI VIDEO, hãy ghi ra các dòng text ngắn gọn, punchy (dưới 5 từ). Sắp xếp mốc thời gian (time) nối tiếp nhau khoảng mỗi 3-4 giây.
In kết quả JSON đúng mẫu dưới đây (In duy nhất block JSON này, không giải thích thêm ở phần này):

{
  "text_events": [
    {"time": 0.0, "text": "HOOK GÂY TÒ MÒ 🔥", "effect": "hook"},
    {"time": 3.0, "text": "Key Feature 1", "effect": "feature"},
    {"time": 6.5, "text": "Key Feature 2", "effect": "feature"},
    {"time": 9.5, "text": "Lợi ích / Call To Action", "effect": "feature"}
  ]
}`} 
      />

      <div className="mt-8 rounded-xl bg-cyan-500/10 border border-cyan-500/20 p-5 items-center flex gap-4">
        <Sparkles className="w-8 h-8 text-cyan-400 flex-shrink-0" />
        <div>
          <h4 className="font-semibold text-white mb-1">Mẹo đa năng</h4>
          <p className="text-sm text-cyan-50">
            Đừng chỉ nghĩ Link Bio là CTA duy nhất. Hãy dùng Text Feature để đặt câu hỏi tương tác (Vd: "Cmt số 1 nếu bạn thích màu này") để tăng engagement cho video!
          </p>
        </div>
      </div>
    </div>
  </div>
);

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
