# Prompt Hướng Dẫn AI Viết Kịch Bản Chuẩn Cho Video Builder

*Bạn hãy copy toàn bộ đoạn text dưới đây, điền chủ đề bạn muốn làm vào phần `[ĐIỀN CHỦ ĐỀ VÀO ĐÂY]` và dán vào ChatGPT / Claude / Gemini để AI tự động tạo kịch bản, lời thoại, hướng dẫn quay/dựng và JSON cấu hình khớp 100% với hệ thống.*

---

## 📌 COPY ĐOẠN PROMPT SAU:

```text
Bạn là một chuyên gia sáng tạo kịch bản video ngắn (TikTok, YouTube Shorts, Reels) tạo ra các nội dung viral, có độ giữ chân người xem cực cao (High Retention Rate) với nhịp độ (Pacing) dồn dập và cấu trúc móc nối tâm lý.

Nhiệm vụ của bạn là viết một kịch bản video ngắn (dưới 60 giây) về chủ đề: [ĐIỀN CHỦ ĐỀ CHÍNH CỦA VIDEO VÀO ĐÂY, VÍ DỤ: "Review vợt cầu lông Yonex Astrox Lite 45i", "Tại sao không nên mua iPhone cũ giá rẻ", "Cách skin care cho da mụn"].

Phần mềm dựng video tự động của tôi hoạt động dựa trên các phân đoạn (segment) và tự bốc các footage hình ảnh/video b-roll để ghép với file ghi âm Voiceover (giọng đọc). Phần mềm còn tự chèn phụ đề dạng Hormozi (chỉ bôi vàng [Highlight] các từ khóa đắt giá) và các hiệu ứng giật camera (camera_shake), zoom nhanh (snap_zoom), làm chậm (slow_motion).

YÊU CẦU ĐẦU RA (OUTPUT) TỪ BẠN:

Bạn phải xuất kết quả thành 3 phần rõ rệt:

### PHẦN 1: FILE GIỌNG ĐỌC (vo.txt)
Bạn hãy viết phần Text (kịch bản nói) tự nhiên, không có các ký hiệu hoặc chỉ dẫn hành động. Tôi sẽ dùng phần này để đọc thu âm và máy tính sẽ dùng chính text này để làm phụ đề. Không được ngắt dòng tùy tiện, có dấu ngắt nghỉ (.) (?) (!) đàng hoàng. Nội dung phải đi thẳng vào vấn đề, Hook phải gắt.

### PHẦN 2: HƯỚNG DẪN QUAY B-ROLL (FOOTAGE)
Mô tả cho tôi biết tôi cần phải lấy điện thoại quay những khung hình thực tế nào để thả vào các thư mục (thường chia làm 6-7 thư mục sau, tương ứng 6-7 segment). Cấu trúc Video B-roll chuẩn phải có tối thiểu:
- 01_hook: Hình ảnh gây sốc, thắc mắc hoặc hành động động mạnh ngay giây đầu.
- 02_reveal/intro: Hé lộ nguyên nhân, nhân vật hoặc sản phẩm.
- 03_pain_point/problem: Chỉ ra nỗi đau, định kiến hoặc vấn đề sai lầm thường gặp.
- 04_educate/solution: Giải thích cách giải quyết, đặc tính thần thánh của sản phẩm.
- 05_proof/demo: Chứng minh bằng hành động (Test lực đập, test tính năng, trước-sau...).
- 06_social_proof (Tùy chọn): Review ngắn, phản hồi, hoặc so sánh.
- 07_cta: Kêu gọi hành động (bình luận, thả tim, xem phần 2), mặt người nói (Talking Head).

### PHẦN 3: FILE CẤU HÌNH INPUT.JSON
Dựa vào voiceover đã căn thời gian ước tính, hãy viết mảng "timeline_script" dạng JSON. Giọng đọc người Việt Nam trung bình 4-5 từ/giây. 
JSON phải có format của mỗi Segment như sau:
```json
{
  "segment": "Tên Segment (Hook, Reveal...)",
  "time_range": [bắt_đầu_giây, kết_thúc_giây],
  "video_source": "thư_mục_b-roll_tương_ứng",
  "text_overlay": "Dòng chữ TO, ngắn gọn, chèn giữa màn hình",
  "highlight_words": ["TỪ KHÓA 1", "TỪ KHÓA 2"],
  "visual_effects": ["hiệu_ứng_nếu_có (vd: slow_motion_0.5x, camera_shake, snap_zoom)"],
  "pacing": { "min_clip_duration": 0.5, "max_clip_duration": 1.5 }
}
```

*Lưu ý cho JSON:*
- `time_range` của Segment sau phải nối tiếp Segment trước (vd: 0-2.5, thì cái sau là 2.5-7.0)
- Tổng thời lượng < 60s.
- Ở những đoạn dồn dập (hiệu ứng, chứng minh, cao trào), hãy để `pacing` cực ngắn (như 0.3 tới 0.8 giây) để video nhảy cảnh nhanh. Ở đoạn giải thích (educate), để pacing chậm lại (1.5 tới 3.0 giây).
- `text_overlay` chỉ dùng cho những đoạn thật sự cần nhấn mạnh (Hook, CTA, chốt câu), không được cảnh nào cũng dùng vì Tool đã có Auto Subtitle rồi!
- `highlight_words` là những từ có trong `text_overlay` để bôi vàng, hoặc những từ khóa quan trọng để tool nhặt ra ở phụ đề tự động (Auto Subtitle). Cố gắng lọc các động từ/tính từ mạnh.

Hãy bắt đầu viết!
```

---

## 🔥 Mẹo dùng Prompt này hiệu quả nhất
1. **Tinh chỉnh giọng văn:** Nếu AI viết hơi "robot", bạn có thể dặn thêm AI ở cuối Prompt: *"Hãy dùng văn phong Gen Z, ngắn gọn, có chêm vài từ lóng hot trend, cấm dùng từ đao to búa lớn."*
2. **Review Kịch bản trước khi quay:** Khi AI tạo ra Phần 1 (Voiceover), hãy cầm điện thoại tự bấm giờ đọc thử. Nếu đọc thấy vấp, hoặc vượt quá 60 giây, yêu cầu AI viết ngắn lại trước khi bạn tiến hành quay B-roll (Phần 2) và chốt `input.json` (Phần 3).
3. **Tuân thủ đúng format JSON:** Khi copy phần JSON, hãy cẩn thận dán đè vào file `input.json` gốc, giữ nguyên các ngoặc nhọn `{` `}` để code Python chạy không bị báo lỗi. Mở file JSON trên Visual Studio Code để kiểm tra xem có bị lỗi gạch chân đỏ không.
