import os
import gc
import logging
import asyncio
import subprocess
import shutil
import cv2
import re
import numpy as np
import soundfile as sf
import pyrubberband as pyrb
from PIL import Image
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    from .phase1_extract import clean_gpu_memory
except ImportError:
    from phase1_extract import clean_gpu_memory

logger = logging.getLogger(__name__)


@dataclass
class VoiceoverConfig:
    """Configuration for Edge-TTS voice generation and alignment."""
    sample_rate: int = 16000
    voice_name: str = "vi-VN-NamMinhNeural"
    stretch_min: float = 0.5
    stretch_max: float = 2.0
    stretch_threshold: float = 0.05
    concurrency_limit: int = 5


@dataclass
class InpaintConfig:
    """Configuration for hardcoded text removal."""
    use_iopaint: bool = True
    inpaint_padding: int = 6
    iopaint_device: str = "cuda"


@dataclass
class AssemblyConfig:
    """Configuration for video rendering and audio mixing."""
    bgm_volume: float = 0.25
    video_codec: str = "h264_nvenc"
    video_codec_fallback: str = "libx264"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    audio_channels: int = 2
    audio_samplerate: int = 44100
    h264_preset: str = "p5"
    h264_preset_fallback: str = "veryfast"
    cq_value: int = 20
    crf_fallback: int = 20


@dataclass
class CompositionConfig:
    """Master configuration for the composition engine."""
    voiceover: VoiceoverConfig = field(default_factory=VoiceoverConfig)
    inpaint: InpaintConfig = field(default_factory=InpaintConfig)
    assembly: AssemblyConfig = field(default_factory=AssemblyConfig)


async def tts_generate_segment(text: str, output_path: str, voice: str = "vi-VN-NamMinhNeural") -> bool:
    """Generate audio file for a single segment using edge-tts with resilient retry.
    
    Maintained as a module-level utility for compatibility with other engines (e.g. RenderEngine).
    """
    import edge_tts
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_path)
            return True
        except Exception as e:
            logger.warning(f"Edge-TTS attempt {attempt}/{max_retries} failed for text '{text}': {e}")
            if attempt < max_retries:
                await asyncio.sleep(1.0 * attempt)  # Exponential backoff
            else:
                logger.error(f"Edge-TTS failed completely for text '{text}' after {max_retries} attempts.")
    return False


class VoiceoverGenerator:
    """Synthesizes styled, aligned Vietnamese voiceover tracks using Edge-TTS and Rubberband."""

    def __init__(self, config: Optional[VoiceoverConfig] = None):
        self.config = config or VoiceoverConfig()

    async def _tts_task(self, sem: asyncio.Semaphore, idx: int, text: str, temp_mp3: str) -> Tuple[int, bool]:
        """Runs a single TTS generation task within concurrency limits."""
        async with sem:
            success = await tts_generate_segment(text, temp_mp3, voice=self.config.voice_name)
            return idx, success

    async def generate_all_tts(self, segments: List[Dict[str, Any]], voices_dir: str) -> Dict[int, bool]:
        """Generate all TTS voice segments concurrently using asyncio gather and semaphore control."""
        sem = asyncio.Semaphore(self.config.concurrency_limit)
        tasks = []
        for idx, seg in enumerate(segments):
            text = seg.get("text", "").strip()
            if not text:
                continue

            # Defensive check: skip segments containing Chinese characters
            if re.search(r'[\u4e00-\u9fff]', text):
                logger.warning(f"Skipping Edge-TTS for segment {idx} containing untranslated Chinese characters: '{text}'")
                continue

            temp_mp3 = os.path.join(voices_dir, f"seg_{idx:03d}.mp3")
            tasks.append(self._tts_task(sem, idx, text, temp_mp3))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_map = {}
        for res in results:
            if isinstance(res, Exception):
                logger.error(f"Concurrent TTS generation task failed: {res}")
            elif isinstance(res, tuple):
                idx, success = res
                success_map[idx] = success
        return success_map

    def generate_voiceover(self, segments: List[Dict[str, Any]], work_dir: str) -> str:
        """Stitches and co-stretches generated voice segments to construct the full localized audio track."""
        logger.info("Generating Vietnamese voiceover track via Edge-TTS (Concurrent Batch Mode)...")
        voices_dir = os.path.join(work_dir, "voices")
        os.makedirs(voices_dir, exist_ok=True)

        # 1. Run TTS generation concurrently using a safe event loop runner
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            # If the current thread already has a running event loop, delegate to a separate thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(lambda: asyncio.run(self.generate_all_tts(segments, voices_dir)))
                success_map = future.result()
        else:
            success_map = loop.run_until_complete(self.generate_all_tts(segments, voices_dir))

        # 2. Reconstruct, convert and align/stretch tracks sequentially
        sample_rate = self.config.sample_rate
        total_duration = 5.0
        if segments:
            total_duration = max([seg.get("end", 5.0) for seg in segments]) + 1.0

        full_voice = np.zeros(int(total_duration * sample_rate))
        ffmpeg_bin = shutil.which("ffmpeg")

        for idx, seg in enumerate(segments):
            if idx not in success_map or not success_map[idx]:
                continue

            start = seg.get("start", 0.0)
            end = seg.get("end", 1.0)
            dur = end - start
            if dur <= 0:
                continue

            temp_mp3 = os.path.join(voices_dir, f"seg_{idx:03d}.mp3")
            temp_wav = os.path.join(voices_dir, f"seg_{idx:03d}.wav")

            if not os.path.exists(temp_mp3) or os.path.getsize(temp_mp3) == 0:
                continue

            # Convert mp3 from edge-tts to wav for audio manipulations
            subprocess.run([
                ffmpeg_bin, "-y", "-i", temp_mp3,
                "-ar", str(sample_rate), "-ac", "1", temp_wav
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if not os.path.exists(temp_wav):
                continue

            data, sr = sf.read(temp_wav)
            actual_dur = len(data) / sr

            # Perform co-stretching ratio alignments bounded within safety limits
            ratio = actual_dur / dur
            ratio = max(self.config.stretch_min, min(self.config.stretch_max, ratio))

            if abs(ratio - 1.0) > self.config.stretch_threshold:
                logger.info(f"Stretching vocal segment {idx} by factor {ratio:.2f} to fit {dur:.2f}s")
                try:
                    data_stretched = pyrb.time_stretch(data, sr, ratio)
                except Exception as e:
                    logger.error(f"Rubberband stretch failed: {e}. Falling back to default pitch trim.")
                    data_stretched = data
            else:
                data_stretched = data

            # Pad or truncate to achieve perfect frame duration alignment
            target_len = int(dur * sample_rate)
            if len(data_stretched) > target_len:
                data_stretched = data_stretched[:target_len]
            elif len(data_stretched) < target_len:
                pad = np.zeros(target_len - len(data_stretched))
                data_stretched = np.concatenate([data_stretched, pad])

            start_idx = int(start * sample_rate)
            end_idx = start_idx + len(data_stretched)

            if end_idx > len(full_voice):
                extend_pad = np.zeros(end_idx - len(full_voice) + 1000)
                full_voice = np.concatenate([full_voice, extend_pad])

            full_voice[start_idx:end_idx] = data_stretched

        # Save vocal output track
        output_vocal = os.path.join(work_dir, "voice_viet.wav")
        sf.write(output_vocal, full_voice, sample_rate)
        logger.info(f"Synthesized voiceover track saved to {output_vocal}")
        return output_vocal


class TextInpainter:
    """Removes hardcoded subtitles and texts from video frames via advanced inpainting algorithms."""

    def __init__(self, config: Optional[InpaintConfig] = None):
        self.config = config or InpaintConfig()

    def _create_mask(self, height: int, width: int, active_texts: List[Dict[str, Any]]) -> np.ndarray:
        """Constructs a binary mask over detected textual bounding box regions with edge padding."""
        mask = np.zeros((height, width), dtype=np.uint8)
        for item in active_texts:
            bbox = item["bbox"]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            if not bbox:
                continue
            poly = np.array(bbox, dtype=np.int32)
            poly = poly.reshape((-1, 1, 2))
            
            # Draw the exact slanted polygon, not a straight rectangle
            cv2.fillPoly(mask, [poly], 255)

        # Apply a 3x3 dilation (adds ~1 pixel border) to soften the edge for the inpainting model
        # This prevents the text outline from remaining visible as a "ghost" after removal
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=1)
        return mask

    def clean_frames(self, video_path: str, ocr_results: List[Dict[str, Any]], work_dir: str) -> str:
        """Processes video frame-by-frame, applying AI LaMa or CV2 Telea inpainting on text masks."""
        if not ocr_results:
            logger.info("No on-screen OCR text to remove. Skipping inpainting.")
            return video_path

        logger.info("Starting on-screen text removal (inpainting)...")
        frames_dir = os.path.join(work_dir, "inpainted_frames")
        os.makedirs(frames_dir, exist_ok=True)

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise IOError(f"Failed to open video source: {video_path}")

        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            # Index OCR text events by rounded seconds
            ocr_by_sec = {}
            for res in ocr_results:
                sec = res["time_sec"]
                ocr_by_sec.setdefault(sec, []).append(res)

            temp_raw = os.path.join(work_dir, "inpainted_raw.mp4")
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(temp_raw, fourcc, fps, (width, height))
            if not writer.isOpened():
                logger.warning(f"OpenCV VideoWriter reported not isOpened() for {temp_raw}, proceeding with best effort.")

            # Instantiate Advanced IOPaint LaMa if enabled
            iopaint_model = None
            if self.config.use_iopaint:
                try:
                    logger.info(f"Initializing IOPaint LaMa model on {self.config.iopaint_device}...")
                    from iopaint.model.lama import LaMa
                    iopaint_model = LaMa(device=self.config.iopaint_device)
                    logger.info("IOPaint LaMa loaded successfully.")
                except Exception as e:
                    logger.warning(f"Failed to load IOPaint LaMa model: {e}. Falling back to OpenCV Inpainting.")
                    iopaint_model = None

            try:
                frame_idx = 0
                cleaned_count = 0

                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break

                    sec = int(frame_idx / fps)
                    # Apply text mask for +/- 1 second buffers
                    active_texts = []
                    for delta in (-1, 0, 1):
                        t_sec = sec + delta
                        if t_sec in ocr_by_sec:
                            active_texts.extend(ocr_by_sec[t_sec])

                    if active_texts:
                        mask = self._create_mask(height, width, active_texts)

                        if iopaint_model is not None:
                            try:
                                from iopaint.schema import InpaintRequest
                                img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                                pil_img = Image.fromarray(img_rgb)
                                pil_mask = Image.fromarray(mask)

                                inpainted_rgb = iopaint_model.inpaint(pil_img, pil_mask, InpaintRequest())
                                frame = cv2.cvtColor(np.array(inpainted_rgb), cv2.COLOR_RGB2BGR)
                                cleaned_count += 1
                            except Exception as e:
                                logger.error(f"IOPaint inpaint failed on frame {frame_idx}: {e}. Falling back to CV2.")
                                frame = cv2.inpaint(frame, mask, 5, cv2.INPAINT_TELEA)
                        else:
                            frame = cv2.inpaint(frame, mask, 5, cv2.INPAINT_TELEA)
                            cleaned_count += 1

                    writer.write(frame)
                    frame_idx += 1
            finally:
                writer.release()
                if iopaint_model is not None:
                    del iopaint_model
                    clean_gpu_memory()
        finally:
            cap.release()

        logger.info(f"Cleaned {cleaned_count} frames containing Chinese text.")

        # High quality H264 transcoding via NVENC with robust CPU fallback
        cleaned_video = os.path.join(work_dir, "inpainted_clean.mp4")
        ffmpeg_bin = shutil.which("ffmpeg")
        cmd_gpu = [
            ffmpeg_bin, "-y",
            "-i", temp_raw,
            "-c:v", "h264_nvenc",
            "-preset", "p4",
            "-profile:v", "high",
            "-pix_fmt", "yuv420p",
            cleaned_video
        ]
        try:
            logger.info("Attempting GPU NVENC clean video transcode...")
            subprocess.run(cmd_gpu, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except Exception as e:
            logger.warning(f"GPU NVENC transcode failed: {e}. Falling back to standard CPU x264 encode...")
            cmd_cpu = [
                ffmpeg_bin, "-y",
                "-i", temp_raw,
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "20",
                "-pix_fmt", "yuv420p",
                cleaned_video
            ]
            subprocess.run(cmd_cpu, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return cleaned_video


class VideoAssembler:
    """Handles audio mixing, stylized subtitle burning, and video rendering using FFmpeg."""

    def __init__(self, config: Optional[AssemblyConfig] = None):
        self.config = config or AssemblyConfig()

    def _execute_ffmpeg(self, cmd: List[str]) -> None:
        """Wrapper for subprocess calls with comprehensive error diagnostics."""
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            logger.error(f"FFmpeg execution failed with returncode {proc.returncode}")
            logger.error(f"FFmpeg Output: {proc.stdout}")
            logger.error(f"FFmpeg Error Details: {proc.stderr}")
            raise subprocess.CalledProcessError(proc.returncode, cmd, output=proc.stdout, stderr=proc.stderr)

    def assemble(self, video_clean: str, voice_wav: str, bgm_wav: str, subtitle_ass: str, output_path: str) -> str:
        """Performs multi-track audio multiplexing and subtitle burning under high-speed hardware profiles."""
        logger.info("Assembling final video with audio track and burned subtitles...")
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            raise FileNotFoundError("FFmpeg not found in path")

        filter_complex = (
            f"[1:a]volume={self.config.bgm_volume}[bgm];"
            f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )

        cmd_gpu = [
            ffmpeg_bin, "-y",
            "-i", voice_wav,
            "-i", bgm_wav,
            "-i", video_clean,
            "-filter_complex", filter_complex,
            "-map", "2:v:0",
            "-map", "[aout]",
            "-vf", f"ass={subtitle_ass}",
            "-c:v", self.config.video_codec,
            "-preset", self.config.h264_preset,
            "-profile:v", "high",
            "-rc", "vbr",
            "-cq", str(self.config.cq_value),
            "-pix_fmt", "yuv420p",
            "-c:a", self.config.audio_codec,
            "-ar", str(self.config.audio_samplerate),
            "-ac", str(self.config.audio_channels),
            "-b:a", self.config.audio_bitrate,
            "-movflags", "+faststart",
            output_path
        ]

        try:
            logger.info("Running hardware-accelerated NVENC assemble...")
            self._execute_ffmpeg(cmd_gpu)
        except Exception as e:
            logger.warning(f"GPU assembly failed: {e}. Falling back to standard CPU x264 encode...")
            cmd_cpu = [
                ffmpeg_bin, "-y",
                "-i", voice_wav,
                "-i", bgm_wav,
                "-i", video_clean,
                "-filter_complex", filter_complex,
                "-map", "2:v:0",
                "-map", "[aout]",
                "-vf", f"ass={subtitle_ass}",
                "-c:v", self.config.video_codec_fallback,
                "-preset", self.config.h264_preset_fallback,
                "-crf", str(self.config.crf_fallback),
                "-pix_fmt", "yuv420p",
                "-c:a", self.config.audio_codec,
                "-ar", str(self.config.audio_samplerate),
                "-ac", str(self.config.audio_channels),
                "-b:a", self.config.audio_bitrate,
                "-movflags", "+faststart",
                output_path
            ]
            self._execute_ffmpeg(cmd_cpu)

        logger.info(f"Final video generated successfully at {output_path}")
        return output_path


# --- Backward Compatibility API Adaptors ---

def generate_vietnamese_voiceover(segments: List[Dict[str, Any]], work_dir: str, voice_name: str = "vi-VN-NamMinhNeural") -> str:
    """Backward compatibility wrapper for generating co-stretched voiceover tracks."""
    config = VoiceoverConfig(voice_name=voice_name)
    generator = VoiceoverGenerator(config)
    return generator.generate_voiceover(segments, work_dir)


def clean_chinese_text_frames(video_path: str, ocr_results: List[Dict[str, Any]], work_dir: str, use_iopaint: bool = True) -> str:
    """Backward compatibility wrapper for hard text video frame cleanup."""
    config = InpaintConfig(use_iopaint=use_iopaint)
    inpainter = TextInpainter(config)
    return inpainter.clean_frames(video_path, ocr_results, work_dir)


def assemble_final_video(video_clean: str, voice_wav: str, bgm_wav: str, subtitle_ass: str, output_path: str, work_dir: str) -> str:
    """Backward compatibility wrapper for final video multiplexing and subtitle embedding."""
    config = AssemblyConfig()
    assembler = VideoAssembler(config)
    return assembler.assemble(video_clean, voice_wav, bgm_wav, subtitle_ass, output_path)
