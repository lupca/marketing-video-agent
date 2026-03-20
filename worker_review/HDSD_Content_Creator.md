# Hướng dẫn tạo Video Viral (TikTok, Reels, Shorts) với Video Builder

Chào bạn (Content Creator)! Công cụ **Video Builder** này được thiết kế để tự động hóa quá trình dựng video ngắn tỷ lệ 9:16 (1080x1920) chuẩn TikTok, YouTube Shorts, và Instagram Reels.

Thay vì phải ngồi chắp vá từng đoạn clip, thêm hiệu ứng, chỉnh phụ đề bằng tay trên CapCut hay Premiere, hệ thống này giúp bạn chỉ cần **chuẩn bị nguyên liệu (quay clip, thu âm)** và **lên kịch bản (file JSON)**. Hệ thống sẽ tự động ghép nối, thêm hiệu ứng, phụ đề Hormozi-style (chữ to, nổi bật từ khóa), và xuất ra video hoàn chỉnh.

---

## 1. Công cụ này phù hợp làm thể loại video gì?

Công cụ cực kỳ mạnh mẽ cho các dạng video có cấu trúc rõ ràng và nhịp độ nhanh (pacing):
- **Video Review Sản Phẩm / Đập Hộp:** (Ví dụ: Review vợt cầu lông, đồ công nghệ, mỹ phẩm...)
- **Video Kể Chuyện / Chia sẻ kiến thức (Talking Head kết hợp b-roll):** Một người nói/thu âm, hình ảnh minh họa thay đổi liên tục.
- **Video "Faceless" (Không lộ mặt):** Dùng giọng đọc (Voiceover/AI Voice) ghép với các video stock hoặc b-roll có sẵn.

---

## 2. Hệ thống cần những Input (Nguyên liệu) gì?

Để công cụ hoạt động mượt mà, bạn cần chuẩn bị 3 thành phần chính:

1. **Âm thanh (Audio):**
   - File Voiceover (ví dụ: `vo_58s.mp3`): Giọng đọc chính của video.
   - File Text kịch bản (ví dụ: `vo_58s.txt`): Kịch bản dạng chữ khớp 100% với giọng đọc. Hệ thống dùng nó để căn chỉnh phụ đề cực kỳ chuẩn xác (không bị sai lỗi chính tả).
   - Nhạc nền (BGM - Background Music).

2. **Hình ảnh/Video nguyên liệu (B-roll/Footage):**
   - Các đoạn clip thô (đã quay) được chia vào các thư mục theo **từng phần của kịch bản** (Ví dụ: `01_hook/`, `02_reveal/`, `03_pain_point/`...). 
   - *Lưu ý: Không cần cắt sẵn độ dài, hệ thống sẽ tự động bắt cảnh ngẫu nhiên (hoặc đầu clip) dựa theo cấu hình.*

3. **File Kịch Bản Điều Khiển (`input.json`):**
   - Đây là "bộ não" hướng dẫn tool cách ghép các nguyên liệu trên.

---

## 3. Hướng dẫn cấu hình `input.json` để tạo video Viral

Một video nghìn view/triệu view cần có nhịp điệu (pacing) tốt, hiệu ứng thị giác (visual effects) giữ chân người xem, và phụ đề thu hút. Dưới đây là cách bạn cấu hình file `input.json`:

### A. Cấu trúc cơ bản
File JSON chia làm 3 phần: `metadata` (tên dự án), `assets` (đường dẫn file/thư mục), và `timeline_script` (kịch bản chi tiết).

### B. Mẹo cấu hình `timeline_script` cực cháy

Kịch bản được chia thành các "Segment" (phân đoạn) tương ứng với thời gian của Voiceover.

**1. Tối ưu Hook (3-5 giây đầu tiên) - Quan trọng nhất!**
Người xem quyết định lướt qua hay ở lại trong 3 giây đầu.
- **`time_range`**: Đặt `[0, 2.0]` hoặc độ dài vừa đủ câu Hook.
- **`text_overlay`**: Thêm dòng text thật giật gân (ví dụ: *"MUA VỢT SAI = MẤT CẢ MÙA GIẢI?"*).
- **`highlight_words`**: Chèn các từ khóa kích thích vào mảng này (ví dụ: `["SAI", "MẤT CẢ MÙA GIẢI"]`) để chữ sáng màu vàng dạ quang (Hormozi style).
- **`visual_effects`**: Thêm `"slow_motion_0.5x"` hoặc fast forward để tạo ấn tượng thị giác mạnh từ giây đầu.
- **Ví dụ JSON:**
```json
{
  "segment": "Hook",
  "time_range": [0, 2.0],
  "video_source": "01_hook",
  "text_overlay": "MUA VỢT SAI = MẤT CẢ MÙA GIẢI?",
  "highlight_words": ["SAI", "MẤT CẢ MÙA GIẢI"],
  "visual_effects": ["slow_motion_0.5x"],
  "pacing": { "min_clip_duration": 0.5, "max_clip_duration": 0.8 } 
}
```

**2. Nhịp độ (Pacing) - Bí quyết giữ chân người xem**
Đừng để một khung hình tồn tại quá lâu. Hãy lợi dụng thuộc tính `pacing`.
- Nếu đoạn video đang nói về chi tiết sản phẩm: Hãy để chuyển cảnh chậm lại một chút để người xem kịp nhìn `{"min_clip_duration": 1.5, "max_clip_duration": 2.5}`.
- Nếu đoạn cao trào, nhịp độ cần dồn dập: Hạ duration xuống thấp `{"min_clip_duration": 0.4, "max_clip_duration": 0.9}`. Cảnh sẽ giật liên tục, tạo cảm giác gấp gáp.

**3. Hiệu ứng thị giác (Visual Effects)**
Để tránh nhàm chán khi chuyển cảnh, bạn có thể trigger hiệu ứng:
- `"snap_zoom"`: Phóng to đột ngột vào trọng tâm (thích hợp nhân mạnh ý quan trọng).
- `"camera_shake"`: Rung camera (phù hợp khi nói về thất vọng, bực tức, hoặc một cú đập "smash" uy lực).
- Lên lịch chính xác hiệu ứng:
```json
"visual_effects": [
  { "type": "snap_zoom", "trigger_at": 3.0, "intensity": 1.3 },
  { "type": "camera_shake", "start_time": 6.6, "duration": 0.3, "amplitude": 15 }
]
```

**4. Kêu gọi hành động (CTA)**
Ở những giây cuối, bạn cần điều hướng người xem (Comment, Like, Đón xem phần 2).
- Sử dụng `text_overlay` để in to chỉ dẫn.
- Bôi phủ (`highlight_words`) từ khóa chính như `"PART 2"`, `"COMMENT"`.

### C. Cơ chế Auto Subtitle (Phụ đề tự động)
Hệ thống sử dụng công nghệ WhisperX để căn chỉnh phụ đề chuẩn xác tới từng miligiây. 
- Hãy bật `"auto_subtitle": true` trong `render_settings`.
- **CỰC KỲ QUAN TRỌNG:** Kịch bản `.txt` phải viết CHÍNH XÁC 100% những gì bạn đọc trong Voiceover. Đừng viết tắt nếu bạn đọc đầy đủ. Tool sẽ không tự dịch hay tự nghe (tránh lỗi chính tả ngớ ngẩn), nó chỉ lấy chữ bạn đưa chắp với âm thanh bạn đọc.

---

## 4. Tóm lại Quy trình chạy chuẩn

1. Soạn kịch bản, thu âm giọng đọc và lưu thành `vo.mp3` và `vo.txt`.
2. Quay các đoạn b-roll tương ứng và vứt vào các thư mục `01_hook`, `02_reveal`, v.v...
3. Viết file `input.json` phân bổ từng mốc thời gian (vd: giây 0 đến giây 3 là thư mục `01_hook`...).
4. Mở Terminal / CMD lên và chạy lệnh:
   ```bash
   python video_builder.py path/to/input.json
   ```
5. Đợi vài phút và nhận siêu phẩm `.mp4` đầy đủ hiệu ứng, nhạc, phụ đề tại thư mục `output/`. Đi uống cafe và post video lên Top Trending thôi!
