# Video Creator — Slideshow Worker

The `worker_slideshow` is a Celery-based backend worker that automatically transforms a list of product images and text into a high-quality vertical promotional video (9:16). It leverages `moviepy`, `edge-tts` (for AI voiceover), and robust transitions.

## Architecture

The worker listens to the `slideshow_queue` in Redis/RabbitMQ. When a job is received, it executes `process_video` (via `shared_core.worker_base`):
1. **Asset preparation**: Downloads all MinIO paths (product images, custom `bg_music`, custom `logo`) into a temporary isolated `work_dir`.
2. **Rendering**: Configures `RenderContext` with the temp folder and executes the MoviePy rendering pipeline.
3. **Upload**: Pushes the generated `.mp4` and `.ass` (captions) back to MinIO and marks the DB job as `SUCCESS`.

## Rendering Variants

The AI engine supports multiple variant profiles that control the overall vibe, speed, and motion:

| Variant | Style | Pacing | Best For |
|---------|-------|--------|----------|
| **A** | Energetic | Fast, snappy cuts | Flash sales, trending TikToks, young audience |
| **B** | Smooth | Medium | Standard product showcases, steady rhythm |
| **C** | Dramatic | Slow, cinematic | Premium items, luxury branding, deep focus |

## Hardware Acceleration

The worker intelligently detects Apple Silicon environments:
- **VideoToolbox (`h264_videotoolbox`)**: Automatically chosen on macOS/M-series chips. Reduces CPU usage dramatically and increases export speed by up to 3x.
- **Software Encoding (`libx264`)**: Used as a fallback on standard Linux/Docker environments.

## File Structure

```text
worker_slideshow/
├── celery_worker.py      # Entry point for the Celery consumer
├── requirements.txt      # Infrastructure & Video Engine dependencies
├── slideshow_engine/     # Core rendering engine
│   ├── config.py         # Hardware detection and RenderContext
│   ├── pipeline.py       # Main orchestration (render_single_variant)
│   ├── data_input.py     # Schema validation and parsing
│   ├── hook_outro.py     # Intro pop-up animations & Outro CTA
│   ├── audio_sync.py     # Librosa beat detection & timing alignment
│   ├── visuals.py        # Image transformations (blur backgrounds, scaling)
│   └── tts.py            # edge-tts voiceover generation
├── assets/fonts/         # Default Fonts (e.g., BeVietnamPro)
├── bg_music.mp3          # Default background music fallback
├── logo.webp             # Default watermark logo fallback
├── arrow.png             # UI element for the outro scene
└── docs/                 # Documentation folder
```
