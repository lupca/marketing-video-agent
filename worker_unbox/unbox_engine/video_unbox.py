"""
unbox_viral specific video processing core.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Union

import cv2
import numpy as np
from moviepy.editor import CompositeVideoClip, ImageClip, VideoFileClip

from worker_unbox.unbox_engine.types import (
    UnboxViralError, SegmentInfo, CropRegion, ProcessedSegment, TextEventUnbox
)
from worker_unbox.unbox_engine.text_overlay import resolve_font, render_text_img

log = logging.getLogger(__name__)

TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
TARGET_FPS = 30
TIKTOK_SAFE_TOP = 0.15
TIKTOK_SAFE_BOTTOM = 0.20
TIKTOK_SAFE_RIGHT = 0.15

STATIC_THRESHOLD = 2.0
REPETITIVE_THRESHOLD = 8.0
MOTION_WINDOW_SEC = 0.5
SPEED_RAMP_FACTOR = 3.5
EMA_ALPHA = 0.15

YOLO_INTEREST_CLASSES = {0, 26, 28, 39, 41, 56, 63, 67, 73, 76}

class VideoProcessor:
    def __init__(
        self,
        yolo_model_name: str = "yolov8n.pt",
        static_threshold: float = STATIC_THRESHOLD,
        repetitive_threshold: float = REPETITIVE_THRESHOLD,
    ):
        self.static_threshold = static_threshold
        self.repetitive_threshold = repetitive_threshold
        self._yolo = None
        self._yolo_model_name = yolo_model_name

    def _get_yolo(self):
        if self._yolo is None:
            try:
                from ultralytics import YOLO
                self._yolo = YOLO(self._yolo_model_name)
                log.info(f"Loaded YOLO model: {self._yolo_model_name}")
            except Exception as e:
                log.warning(f"Failed to load YOLO: {e}. Will use fallback.")
                self._yolo = None
        return self._yolo

    def analyze_motion(
        self,
        video_path: Union[str, Path],
        window_sec: float = MOTION_WINDOW_SEC,
    ) -> List[SegmentInfo]:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise UnboxViralError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or TARGET_FPS
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        window_frames = max(1, int(window_sec * fps))

        sample_step = 2
        prev_gray = None
        flow_scores: List[float] = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % sample_step == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.resize(gray, (320, 180))
                if prev_gray is not None:
                    flow = cv2.calcOpticalFlowFarneback(
                        prev_gray, gray, None,
                        pyr_scale=0.5, levels=3, winsize=15,
                        iterations=3, poly_n=5, poly_sigma=1.2, flags=0,
                    )
                    mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                    score = float(np.mean(mag))
                    flow_scores.append(score)
                else:
                    flow_scores.append(0.0)
                prev_gray = gray
            frame_idx += 1
        cap.release()

        if not flow_scores:
            return []

        scores_per_window = max(1, window_frames // sample_step)
        segments: List[SegmentInfo] = []

        for i in range(0, len(flow_scores), scores_per_window):
            chunk = flow_scores[i : i + scores_per_window]
            avg_score = float(np.mean(chunk))
            std_score = float(np.std(chunk))

            start_time = (i * sample_step) / fps
            end_time = min(((i + len(chunk)) * sample_step) / fps, total_frames / fps)

            if avg_score < self.static_threshold:
                classification = "STATIC"
            elif avg_score < self.repetitive_threshold and std_score < 1.5:
                classification = "REPETITIVE"
            else:
                classification = "DYNAMIC"

            segments.append(SegmentInfo(
                start=round(start_time, 3),
                end=round(end_time, 3),
                motion_score=round(avg_score, 3),
                classification=classification,
            ))

        merged = self._merge_segments(segments)
        return merged

    def _merge_segments(self, segments: List[SegmentInfo]) -> List[SegmentInfo]:
        if not segments:
            return []
        merged: List[SegmentInfo] = [segments[0]]
        for seg in segments[1:]:
            prev = merged[-1]
            if prev.classification == seg.classification:
                avg = (prev.motion_score + seg.motion_score) / 2
                merged[-1] = SegmentInfo(
                    start=prev.start,
                    end=seg.end,
                    motion_score=round(avg, 3),
                    classification=prev.classification,
                )
            else:
                merged.append(seg)
        return merged

    def compute_crop_track(
        self,
        video_path: Union[str, Path],
        sample_interval: int = 5,
    ) -> List[CropRegion]:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise UnboxViralError(f"Cannot open video: {video_path}")

        src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        target_aspect = 9 / 16
        src_aspect = src_w / src_h

        if src_aspect > target_aspect:
            crop_h = src_h
            crop_w = int(src_h * target_aspect)
        else:
            crop_w = src_w
            crop_h = int(src_w / target_aspect)

        center_cx = src_w // 2
        center_cy = src_h // 2
        yolo = self._get_yolo()

        try:
            saliency = cv2.saliency.StaticSaliencySpectralResidual_create()
        except AttributeError:
            saliency = None
            log.warning("OpenCV saliency not available, using center-crop fallback")

        raw_regions: List[CropRegion] = []
        frame_idx = 0
        last_detection: Optional[CropRegion] = None

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % sample_interval == 0:
                region = self._detect_crop_region(
                    frame, src_w, src_h, crop_w, crop_h,
                    center_cx, center_cy, yolo, saliency,
                )
                last_detection = region
            else:
                region = last_detection or CropRegion(center_cx, center_cy, crop_w, crop_h)

            raw_regions.append(region)
            frame_idx += 1
        cap.release()
        return self._smooth_crop_track(raw_regions, crop_w, crop_h, src_w, src_h)

    def _detect_crop_region(
        self,
        frame: np.ndarray,
        src_w: int, src_h: int,
        crop_w: int, crop_h: int,
        center_cx: int, center_cy: int,
        yolo, saliency,
    ) -> CropRegion:
        cx, cy = center_cx, center_cy
        if yolo is not None:
            try:
                results = yolo.predict(
                    frame, conf=0.3, verbose=False,
                    classes=list(YOLO_INTEREST_CLASSES),
                )
                if results and len(results[0].boxes) > 0:
                    boxes = results[0].boxes
                    areas = (boxes.xyxy[:, 2] - boxes.xyxy[:, 0]) * \
                            (boxes.xyxy[:, 3] - boxes.xyxy[:, 1])
                    best_idx = int(areas.argmax())
                    x1, y1, x2, y2 = boxes.xyxy[best_idx].cpu().numpy()
                    cx = int((x1 + x2) / 2)
                    cy = int((y1 + y2) / 2)
                    return CropRegion(cx, cy, crop_w, crop_h)
            except Exception as e:
                log.debug(f"YOLO detection failed: {e}")

        if saliency is not None:
            try:
                success, sal_map = saliency.computeSaliency(frame)
                if success:
                    sal_map = (sal_map * 255).astype(np.uint8)
                    sal_map = cv2.GaussianBlur(sal_map, (25, 25), 0)
                    _, _, _, max_loc = cv2.minMaxLoc(sal_map)
                    cx, cy = max_loc[0], max_loc[1]
                    return CropRegion(cx, cy, crop_w, crop_h)
            except Exception as e:
                log.debug(f"Saliency fallback failed: {e}")
        return CropRegion(center_cx, center_cy, crop_w, crop_h)

    def _smooth_crop_track(
        self,
        regions: List[CropRegion],
        crop_w: int, crop_h: int,
        src_w: int, src_h: int,
    ) -> List[CropRegion]:
        if not regions:
            return []
        smoothed: List[CropRegion] = []
        ema_cx = float(regions[0].cx)
        ema_cy = float(regions[0].cy)
        half_w = crop_w // 2
        half_h = crop_h // 2

        for r in regions:
            ema_cx = EMA_ALPHA * r.cx + (1 - EMA_ALPHA) * ema_cx
            ema_cy = EMA_ALPHA * r.cy + (1 - EMA_ALPHA) * ema_cy
            cx = int(np.clip(ema_cx, half_w, src_w - half_w))
            cy = int(np.clip(ema_cy, half_h, src_h - half_h))
            smoothed.append(CropRegion(cx, cy, crop_w, crop_h))
        return smoothed

    def build_segments(
        self,
        motion_segments: List[SegmentInfo],
        beat_times: List[float],
        min_dynamic_sec: float = 0.3,
    ) -> List[ProcessedSegment]:
        processed: List[ProcessedSegment] = []
        for seg in motion_segments:
            if seg.classification == "STATIC":
                continue
            duration = seg.end - seg.start
            if seg.classification == "DYNAMIC" and duration < min_dynamic_sec:
                continue
            speed = SPEED_RAMP_FACTOR if seg.classification == "REPETITIVE" else 1.0
            is_beat = any(seg.start <= bt <= seg.end for bt in beat_times)
            processed.append(ProcessedSegment(
                start=seg.start,
                end=seg.end,
                speed_factor=speed,
                is_beat_cut=is_beat,
                classification=seg.classification,
            ))
        return processed


class Renderer:
    def __init__(
        self,
        width: int = TARGET_WIDTH,
        height: int = TARGET_HEIGHT,
        fps: int = TARGET_FPS,
        crf: int = 20,
    ):
        self.width = width
        self.height = height
        self.fps = fps
        self.crf = crf
        self._ffmpeg = shutil.which("ffmpeg")
        self._ffprobe = shutil.which("ffprobe")
        if not self._ffmpeg:
            raise UnboxViralError("ffmpeg not found in PATH")
        self._hw_encoder = self._detect_hw_encoder()

    def _detect_hw_encoder(self) -> str:
        try:
            proc = subprocess.run(
                [self._ffmpeg, "-hide_banner", "-encoders"],
                capture_output=True, text=True,
            )
            if "h264_videotoolbox" in proc.stdout:
                return "h264_videotoolbox"
        except Exception:
            pass
        return "libx264"

    def render_segment(
        self,
        video_path: Union[str, Path],
        segment: ProcessedSegment,
        crop_regions: List[CropRegion],
        output_path: Union[str, Path],
        src_fps: float = 30.0,
    ) -> Path:
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        start_frame = int(segment.start * src_fps)
        end_frame = int(segment.end * src_fps)
        duration = segment.end - segment.start

        if crop_regions:
            mid_frame = min((start_frame + end_frame) // 2, len(crop_regions) - 1)
            seg_crops = crop_regions[max(0, start_frame): min(end_frame, len(crop_regions))]
            if seg_crops:
                avg_cx = int(np.mean([c.cx for c in seg_crops]))
                avg_cy = int(np.mean([c.cy for c in seg_crops]))
                crop_w = seg_crops[0].w
                crop_h = seg_crops[0].h
            else:
                c = crop_regions[min(mid_frame, len(crop_regions) - 1)]
                avg_cx, avg_cy, crop_w, crop_h = c.cx, c.cy, c.w, c.h
        else:
            avg_cx, avg_cy = 960, 540
            crop_w, crop_h = 607, 1080

        x = max(0, avg_cx - crop_w // 2)
        y = max(0, avg_cy - crop_h // 2)
        filters = []
        filters.append(f"crop={crop_w}:{crop_h}:{x}:{y}")
        filters.append(f"scale={self.width}:{self.height}")
        if segment.speed_factor > 1.0:
            pts_factor = 1.0 / segment.speed_factor
            filters.append(f"setpts={pts_factor:.4f}*PTS")
        filters.append(f"fps={self.fps}")
        vf = ",".join(filters)

        af_args = []
        if segment.speed_factor > 1.0:
            new_rate = int(44100 * segment.speed_factor)
            af_args = ["-af", f"asetrate={new_rate},aresample=44100"]

        enc_args = self._get_encoder_args()
        cmd = [
            self._ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{segment.start:.3f}",
            "-t", f"{duration:.3f}",
            "-i", str(video_path),
            "-vf", vf,
            *af_args,
            *enc_args,
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(out),
        ]
        self._run(cmd)
        return out

    def concat_with_transitions(
        self,
        segment_files: List[Path],
        segments: List[ProcessedSegment],
        beat_times: List[float],
        output_path: Union[str, Path],
    ) -> Path:
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        if not segment_files:
            raise UnboxViralError("No segment files to concatenate")
        if len(segment_files) == 1:
            shutil.copy2(segment_files[0], out)
            return out

        inputs = []
        for f in segment_files:
            inputs.extend(["-i", str(f)])

        n = len(segment_files)
        filter_parts = []
        concat_inputs = []
        main_drop_applied = False

        for i in range(n):
            seg = segments[i] if i < len(segments) else None
            next_seg = segments[i+1] if i + 1 < len(segments) else None
            is_pre_beat = next_seg and next_seg.is_beat_cut

            if is_pre_beat and not main_drop_applied:
                dur = (seg.end - seg.start) / seg.speed_factor if seg else 0.0
                fade_start = max(0.0, dur - 0.15)
                filter_parts.append(f"[{i}:v]fade=t=out:st={fade_start:.3f}:d=0.15:color=black[v{i}]")
                concat_inputs.append(f"[v{i}][{i}:a]")
            elif seg and seg.is_beat_cut:
                if not main_drop_applied:
                    filter_parts.append(
                        f"[{i}:v]fade=t=in:st=0:d=0.15:color=white,"
                        f"zoompan=z='if(lt(time,0.25), 1.3 - (time/0.25)*0.2, 1.1)'"
                        f":d=1:x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2'"
                        f":s={self.width}x{self.height}:fps={self.fps}[v{i}]"
                    )
                    concat_inputs.append(f"[v{i}][{i}:a]")
                    main_drop_applied = True
                else:
                    filter_parts.append(
                        f"[{i}:v]zoompan=z='1.05'"
                        f":d=1:x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2'"
                        f":s={self.width}x{self.height}:fps={self.fps}[v{i}]"
                    )
                    concat_inputs.append(f"[v{i}][{i}:a]")
            else:
                concat_inputs.append(f"[{i}:v][{i}:a]")

        concat_input_str = "".join(concat_inputs)
        filter_parts.append(f"{concat_input_str}concat=n={n}:v=1:a=1[vout][aout]")
        filter_complex = ";".join(filter_parts)
        enc_args = self._get_encoder_args()

        cmd = [
            self._ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[vout]", "-map", "[aout]",
            *enc_args,
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            "-r", str(self.fps),
            "-movflags", "+faststart",
            str(out),
        ]
        self._run(cmd)
        return out

    def overlay_text(
        self,
        video_path: Union[str, Path],
        text_events: List[TextEventUnbox],
        output_path: Union[str, Path],
        font_path: Optional[Union[str, Path]] = None,
        font_size_hook: int = 84,
        font_size_feature: int = 64,
    ) -> Path:
        out = Path(output_path).resolve()
        src = Path(video_path).resolve()
        font = resolve_font(font_path)
        base = VideoFileClip(str(src))
        overlays: list = []
        tmp_imgs: List[Path] = []
        tmp_dir = Path(tempfile.mkdtemp(prefix="unbox_text_"))

        try:
            for ev in text_events:
                if ev.event_type == "hook":
                    img = render_text_img(
                        ev.text, font, font_size_hook,
                        max_width=int(self.width * 0.70),
                        effect="hook",
                    )
                    p = tmp_dir / f"hook_{len(tmp_imgs):03d}.png"
                    img.save(str(p))
                    tmp_imgs.append(p)
                    clip = ImageClip(str(p), transparent=True)
                    slam_dur = 0.25
                    def slam_scale(t, sd=slam_dur):
                        if t < sd:
                            progress = t / sd
                            return 2.5 - 1.5 * progress
                        return 1.0

                    safe_y = int(self.height * TIKTOK_SAFE_TOP)
                    safe_bottom = int(self.height * (1 - TIKTOK_SAFE_BOTTOM))
                    center_y = (safe_y + safe_bottom) // 2 - clip.h // 2
                    center_x = (self.width - clip.w) // 2

                    clip = (clip.set_start(0.0)
                                .set_duration(min(2.5, base.duration))
                                .set_position((center_x, center_y))
                                .resize(lambda t: slam_scale(t)))
                    overlays.append(clip)
                    continue

                start = max(0.0, ev.start)
                if start >= base.duration:
                    continue

                img = render_text_img(
                    ev.text, font, font_size_feature,
                    max_width=int(self.width * 0.70),
                    effect="feature",
                )
                p = tmp_dir / f"feat_{len(tmp_imgs):03d}.png"
                img.save(str(p))
                tmp_imgs.append(p)
                clip = ImageClip(str(p), transparent=True).rotate(-3.5, expand=True)

                dur = min(2.5, base.duration - start)
                safe_top = int(self.height * TIKTOK_SAFE_TOP)
                safe_bottom = int(self.height * (1 - TIKTOK_SAFE_BOTTOM))
                feat_x = max(0, (self.width - clip.w) // 2)
                feat_y = int((safe_top + safe_bottom) / 2 + 80)

                def feat_pos(t, fx=feat_x, fy=feat_y, cw=clip.w):
                    if t < 0:
                        return (-cw - 80, fy)
                    progress = min(t / 0.35, 1.0)
                    ease = Renderer._ease_out_back(progress)
                    target_x = fx
                    x = int(target_x + (1 - ease) * 60)
                    y_bounce = int(fy - (1 - ease) * 40)
                    return (x, y_bounce)

                overlays.append(clip.set_start(start).set_duration(dur).set_position(feat_pos))

            comp = CompositeVideoClip([base, *overlays], size=base.size).set_duration(base.duration)
            comp.write_videofile(
                str(out), fps=self.fps, codec="libx264",
                audio_codec="aac", preset="veryfast",
                ffmpeg_params=["-crf", str(self.crf), "-movflags", "+faststart"],
                threads=max(1, (os.cpu_count() or 4) // 2),
                verbose=False, logger=None,
            )
        finally:
            for c in overlays:
                try:
                    c.close()
                except Exception:
                    pass
            base.close()
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return out

    def mux_final(
        self,
        video_path: Union[str, Path],
        audio_path: Union[str, Path],
        output_path: Union[str, Path],
    ) -> Path:
        out = Path(output_path).resolve()
        dur = self._probe_duration(video_path)
        enc_args = self._get_encoder_args()

        self._run([
            self._ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(video_path), "-i", str(audio_path),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac",
            "-ar", "48000", "-ac", "2", "-b:a", "192k",
            "-t", f"{dur:.3f}",
            "-movflags", "+faststart",
            str(out),
        ])
        return out

    @staticmethod
    def _ease_out_back(t: float, s: float = 1.70158) -> float:
        t = max(0.0, min(1.0, t))
        t_rev = t - 1.0
        return 1.0 + t_rev * t_rev * ((s + 1) * t_rev + s)

    def _get_encoder_args(self) -> List[str]:
        if self._hw_encoder == "h264_videotoolbox":
            return [
                "-c:v", "h264_videotoolbox",
                "-q:v", "65",
                "-profile:v", "high",
                "-level", "4.1",
            ]
        return [
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", str(self.crf),
        ]

    def _probe_duration(self, video_path: Union[str, Path]) -> float:
        proc = subprocess.run([
            self._ffprobe, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ], capture_output=True, text=True)
        if proc.returncode != 0:
            raise UnboxViralError(f"ffprobe failed for {video_path}")
        return float(proc.stdout.strip())

    @staticmethod
    def _run(cmd: List[str]) -> subprocess.CompletedProcess:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise UnboxViralError(
                f"Command failed: {' '.join(cmd[:8])}...\n{proc.stderr.strip()[:500]}"
            )
        return proc

def probe_fps(video_path: Union[str, Path]) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return float(TARGET_FPS)
    try:
        proc = subprocess.run([
            ffprobe, "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=r_frame_rate",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ], capture_output=True, text=True)
        if proc.returncode == 0:
            rate = proc.stdout.strip()
            if "/" in rate:
                num, den = rate.split("/")
                return float(num) / float(den)
            return float(rate)
    except Exception:
        pass
    return float(TARGET_FPS)
