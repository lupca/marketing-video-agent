# Hướng Dẫn: Plugin Video Review

Công cụ **Worker Review** giúp bạn tạo nội dung Viral mang tính kể chuyện / thuyết minh. 
Hệ thống tự động nối Clip B-Roll theo ngữ cảnh Voiceover, chèn hiệu ứng (Shake, Zoom) và Auto Subtitle nổi bật Key Words theo phong cách Alex Hormozi.

---

## 1. Yêu cầu Input & File Kịch Bản (JSON)

Để Worker dựng video thành công, cấu hình Input API cần truyền cấu trúc `config_data` chi tiết:

### A. Cấu trúc Metadata & Assets
Tham khảo cơ bản nội dung Payload:
```json
{
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
}
```

### B. Mẹo Cấu Hình Phân Đoạn (Timeline Script) Cực Cháy
`timeline_script` chứa các cụm (hook, body, cta). Nhịp độ cực quan trọng giữ chân Viewer:

```json
{
  "segment": "Hook",
  "time_range": [0, 2.5],  // Giây từ 0 đến 2.5 theo Voice
  "video_source": "01_hook", 
  "text_overlay": "MUA VỢT SAI = MẤT CẢ MÙA GIẢI?", // Text nổi làm nổi bật chính
  "highlight_words": ["SAI", "MẤT CẢ MÙA GIẢI"], // Bôi vàng text nổi
  "visual_effects": ["slow_motion_0.5x", "snap_zoom"], // Phóng to tạo ấn tượng
  "pacing": { "min_clip_duration": 0.5, "max_clip_duration": 0.8 } // Chuyển cảnh nhanh để dồn dập
}
```

---

## 2. Prompt Nhờ AI Tạo Kịch Bản Review Cực Tốc Độ

*Hãy copy toàn bộ đoạn text dưới đây, điền chủ đề và gửi vào ChatGPT / Claude để AI tự xuất Kịch bản Voiceover, File hướng dẫn Quay Video & Cấu hình JSON cho hệ thống gọi API:*

```text
Bạn là chuyên gia kịch bản video TikTok viral, retention rate cao với pacing liên tục. 
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
Lưu ý: Pacing đoạn quan trọng cao trào hãy rát cực ngắn (0.4-0.9), text_overlay móc trộm CTA thôi. In đúng JSON, nối tiếp time_range không thủng thời gian!
```

**Mẹo sử dụng kết quả:** 
Chỉ cần đọc thu phần Voiceover (`.mp3`), lưu nội dung Text ra file txt. Quay B-roll quăng tất vào theo list AI gợi ý, ghép cái JSON API và nhấn Render!
