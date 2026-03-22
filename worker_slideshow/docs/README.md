# Video Creator — Automatic Product Video Generator

Tạo video sản phẩm 1080×1920 (9:16 vertical) tự động từ ảnh, text, nhạc nền.





| Variant | Style | Speed | Motion |
|---------|-------|-------|--------|
| **A** | Energetic | Fast cuts | High |
| **B** | Smooth | Medium | Gentle |
| **C** | Dramatic | Slow reveal | Cinematic |

## Hardware Encoder

Worker tự động detect `h264_videotoolbox` (Apple Silicon HW encoder).
Nếu không có, fallback sang `libx264` (software).

- **VideoToolbox**: Nhanh hơn ~3x, dùng ít CPU → chạy được 3 workers
- **libx264**: Chậm hơn, CPU-bound → max 2 workers

## File Structure

```
video-creater/
├── requirements.txt      # Python dependencies
├── slideshow_engine/     # Core rendering engine
│   ├── config.py         # RenderContext, encoder detection
│   ├── pipeline.py       # render_single_variant()
│   ├── data_input.py     # Content parsing + validation
│   ├── visuals.py        # Image processing (blur, motion)
│   ├── tts.py            # Text-to-speech (edge-tts)
│   └── hook_outro.py     # Intro/outro animations
├── slideshow_moviepy.py  # CLI entry point (standalone)
├── assets/fonts/         # BeVietnamPro-Bold.ttf
├── bg_music.mp3          # Default background music
├── logo.webp             # Default logo
└── docs/
    ├── agent_integration.md  
    └── README.md             
```

```json
{

  "input_json": {
    "intro_text": "Top sản phẩm",
    "outro_text": "Mua ngay!",
    "products": [
      {"image": "p1.jpg", "text": "SP 1", "hook": "Giảm 50%"},
      {"image": "p2.jpg", "text": "SP 2", "hook": "Mới"}
    ]
  }
}
```

