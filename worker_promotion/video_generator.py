#!/usr/bin/env python3
"""
==============================================
  HỆ THỐNG TẠO VIDEO TỰ ĐỘNG TỪ ẢNH
  (CapCut Template Recreation - Full Effects)
==============================================
11 hiệu ứng chuyển cảnh + Ken Burns + Nhạc nền
"""

import os, sys, glob, subprocess, tempfile, shutil, math, random
from PIL import Image, ImageFilter, ImageEnhance, ImageDraw
import numpy as np

# ============================================================
# CẤU HÌNH
# ============================================================
TEMPLATE_CONFIG = {
    "canvas_width": 1080,
    "canvas_height": 1920,
    "fps": 30,
    "num_slots": 9,
    "slide_durations": [3.0, 2.5, 2.5, 3.0, 2.5, 2.5, 3.0, 2.5, 2.5],
    "transition_duration": 0.6,
    # Thứ tự transition giống template gốc
    "transitions": [
        "door_opens",        # Door Opens
        "multi_impact",      # Multi-impact (flash + shake zoom)
        "rotate_snap",       # Rotate Snap
        "chromo_zoom",       # Chromo-zoom
        "bw_to_color",       # Chuyển đen trắng → có màu
        "mist",              # Mist / Khói
        "lightning_flash",   # Fluorescent Scan / Sấm sét
        "popping_cards",     # Popping Cards / Mở album
    ],
    "ken_burns_presets": [
        {"start_scale": 1.0,  "end_scale": 1.15, "start_pos": (0.5, 0.5), "end_pos": (0.45, 0.4)},
        {"start_scale": 1.15, "end_scale": 1.0,  "start_pos": (0.4, 0.4), "end_pos": (0.5, 0.5)},
        {"start_scale": 1.0,  "end_scale": 1.2,  "start_pos": (0.5, 0.5), "end_pos": (0.55, 0.45)},
        {"start_scale": 1.1,  "end_scale": 1.0,  "start_pos": (0.55, 0.45), "end_pos": (0.5, 0.5)},
        {"start_scale": 1.0,  "end_scale": 1.15, "start_pos": (0.5, 0.55), "end_pos": (0.45, 0.5)},
        {"start_scale": 1.2,  "end_scale": 1.0,  "start_pos": (0.45, 0.5), "end_pos": (0.5, 0.5)},
        {"start_scale": 1.0,  "end_scale": 1.1,  "start_pos": (0.5, 0.5), "end_pos": (0.5, 0.45)},
        {"start_scale": 1.1,  "end_scale": 1.0,  "start_pos": (0.5, 0.45), "end_pos": (0.5, 0.5)},
        {"start_scale": 1.0,  "end_scale": 1.15, "start_pos": (0.45, 0.5), "end_pos": (0.55, 0.5)},
    ],
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BGM_PATH = os.path.join(SCRIPT_DIR, "audio", "6860551212433934337.mp3")
SFX_PATH = os.path.join(SCRIPT_DIR, "audio", "7385625652571015179.mp3")


# ============================================================
# HELPERS
# ============================================================
def ease_in_out(t):
    return 0.5 - 0.5 * math.cos(t * math.pi)

def ease_out_back(t):
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)

def ease_out_elastic(t):
    if t == 0 or t == 1: return t
    return pow(2, -10*t) * math.sin((t*10-0.75)*(2*math.pi)/3) + 1

def clamp(v, lo=0, hi=255):
    return max(lo, min(hi, int(v)))


# ============================================================
# IMAGE PROCESSING
# ============================================================
def load_and_fit_image(image_path, canvas_w, canvas_h):
    img = Image.open(image_path).convert("RGB")
    img_w, img_h = img.size
    canvas_ratio = canvas_w / canvas_h
    img_ratio = img_w / img_h

    if img_ratio > canvas_ratio:
        new_h = canvas_h
        new_w = int(canvas_h * img_ratio)
    else:
        new_w = canvas_w
        new_h = int(canvas_w / img_ratio)

    img_resized = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - canvas_w) // 2
    top = (new_h - canvas_h) // 2
    img_cropped = img_resized.crop((left, top, left + canvas_w, top + canvas_h))
    return np.array(img_cropped, dtype=np.uint8)


def apply_ken_burns(frame_array, t, duration, preset, canvas_w, canvas_h):
    progress = ease_in_out(min(1.0, t / max(0.001, duration)))
    scale = preset["start_scale"] + (preset["end_scale"] - preset["start_scale"]) * progress
    cx = preset["start_pos"][0] + (preset["end_pos"][0] - preset["start_pos"][0]) * progress
    cy = preset["start_pos"][1] + (preset["end_pos"][1] - preset["start_pos"][1]) * progress

    h, w = frame_array.shape[:2]
    vw, vh = int(w / scale), int(h / scale)
    x = max(0, min(int(cx * w - vw / 2), w - vw))
    y = max(0, min(int(cy * h - vh / 2), h - vh))

    cropped = frame_array[y:y+vh, x:x+vw]
    img = Image.fromarray(cropped)
    img = img.resize((canvas_w, canvas_h), Image.LANCZOS)
    return np.array(img, dtype=np.uint8)


def zoom_frame(frame, scale, w, h):
    """Zoom vào giữa frame."""
    img = Image.fromarray(frame)
    nw, nh = max(2, int(w * scale)), max(2, int(h * scale))
    img = img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - w) // 2, (nh - h) // 2
    return np.array(img.crop((left, top, left + w, top + h)), dtype=np.uint8)


def _paste_safe(canvas, src, xo, yo):
    """Paste src array onto canvas at (xo, yo), clamping to bounds."""
    ch, cw = canvas.shape[:2]
    sh, sw = src.shape[:2]
    # Source region
    sx1 = max(0, -xo)
    sy1 = max(0, -yo)
    sx2 = min(sw, cw - xo)
    sy2 = min(sh, ch - yo)
    # Dest region
    dx1 = max(0, xo)
    dy1 = max(0, yo)
    rw = sx2 - sx1
    rh = sy2 - sy1
    if rw > 0 and rh > 0:
        canvas[dy1:dy1+rh, dx1:dx1+rw] = src[sy1:sy1+rh, sx1:sx1+rw]


def shake_frame(frame, intensity, w, h):
    """Di chuyển frame ngẫu nhiên tạo hiệu ứng rung."""
    dx = int(random.uniform(-intensity, intensity))
    dy = int(random.uniform(-intensity, intensity))
    result = np.zeros_like(frame)
    sx = max(0, dx); sy = max(0, dy)
    ex = min(w, w + dx); ey = min(h, h + dy)
    osx = max(0, -dx); osy = max(0, -dy)
    rw = ex - sx; rh = ey - sy
    if rw > 0 and rh > 0:
        result[sy:sy+rh, sx:sx+rw] = frame[osy:osy+rh, osx:osx+rw]
    return result


def to_grayscale(frame):
    """Chuyển frame sang đen trắng."""
    gray = np.dot(frame[..., :3], [0.299, 0.587, 0.114])
    return np.stack([gray]*3, axis=-1).astype(np.uint8)


def add_vignette(frame, intensity=0.5):
    """Thêm hiệu ứng tối viền."""
    h, w = frame.shape[:2]
    Y, X = np.ogrid[:h, :w]
    cx, cy = w / 2, h / 2
    dist = np.sqrt((X - cx)**2 + (Y - cy)**2)
    max_dist = math.sqrt(cx**2 + cy**2)
    mask = 1.0 - intensity * (dist / max_dist) ** 2
    mask = np.clip(mask, 0, 1)
    return (frame * mask[:, :, np.newaxis]).astype(np.uint8)


# ============================================================
# TRANSITIONS — 11 hiệu ứng chuyển cảnh
# ============================================================

def transition_door_opens(fa, fb, p, w, h):
    """Door Opens: Ảnh tách ra hai bên như mở cửa, lộ ảnh mới."""
    ep = ease_in_out(p)
    result = fb.copy()
    split = int(w * 0.5 * ep)
    if split < w // 2:
        # Thêm shadow ở mép cửa
        shadow_w = max(1, int(w * 0.03))
        # Left door
        left_piece = fa[:, split:w//2].copy()
        result[:, :w//2-split] = left_piece
        # Right door
        right_piece = fa[:, w//2:w-split].copy()
        result[:, w//2+split:] = right_piece
        # Shadow gradient ở mép
        for i in range(shadow_w):
            alpha = (shadow_w - i) / shadow_w * 0.6
            col_l = w//2 - split + i
            col_r = w//2 + split - i
            if 0 <= col_l < w:
                result[:, col_l] = (result[:, col_l] * (1-alpha)).astype(np.uint8)
            if 0 <= col_r < w:
                result[:, col_r] = (result[:, col_r] * (1-alpha)).astype(np.uint8)
    return result


def transition_multi_impact(fa, fb, p, w, h):
    """Multi-impact: Flash trắng + rung lắc + zoom giật giật."""
    if p < 0.15:
        # Flash trắng sáng lóa
        flash = min(1.0, p / 0.08)
        white = np.full_like(fa, 255)
        return (fa * (1-flash*0.9) + white * flash*0.9).astype(np.uint8)
    elif p < 0.3:
        # Đen
        darkness = 1.0 - (p - 0.15) / 0.15
        return (fa * darkness * 0.3).astype(np.uint8)
    else:
        # Zoom giật giật (nháy nháy ảnh to dần)
        zp = (p - 0.3) / 0.7
        # Tạo hiệu ứng giật: zoom nhanh rồi dừng, zoom nhanh rồi dừng
        num_beats = 4
        beat = zp * num_beats
        beat_phase = beat - int(beat)
        # Mỗi beat: zoom nhanh rồi settle
        base_scale = 1.4 - 0.4 * zp  # Thu nhỏ dần về 1.0
        jitter = 0.08 * math.sin(beat_phase * math.pi) * (1 - zp)
        scale = base_scale + jitter
        result = zoom_frame(fb, scale, w, h)
        # Shake nhẹ
        if zp < 0.7:
            result = shake_frame(result, 12 * (1-zp), w, h)
        return result


def transition_rotate_snap(fa, fb, p, w, h):
    """Rotate Snap: Xoay nhỏ rồi snap vào ảnh mới như đóng sách."""
    if p < 0.4:
        rp = p / 0.4
        angle = rp * 20
        scale = max(0.1, 1.0 - rp * 0.4)
        img = Image.fromarray(fa)
        img = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=(0,0,0))
        nw, nh = max(2, int(w * scale)), max(2, int(h * scale))
        img = img.resize((nw, nh), Image.LANCZOS)
        result = np.zeros((h, w, 3), dtype=np.uint8)
        xo, yo = (w-nw)//2, (h-nh)//2
        _paste_safe(result, np.array(img), xo, yo)
        return result
    else:
        rp = (p - 0.4) / 0.6
        ep = ease_out_back(min(1.0, rp))
        angle = (1 - ep) * -15
        scale = max(0.1, 0.6 + ep * 0.4)
        img = Image.fromarray(fb)
        img = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=(0,0,0))
        nw, nh = max(2, int(w * scale)), max(2, int(h * scale))
        img = img.resize((nw, nh), Image.LANCZOS)
        result = np.zeros((h, w, 3), dtype=np.uint8)
        xo, yo = (w-nw)//2, (h-nh)//2
        _paste_safe(result, np.array(img), xo, yo)
        return result


def transition_chromo_zoom(fa, fb, p, w, h):
    """Chromo-zoom: Zoom với chromatic aberration (tách RGB mạnh)."""
    ep = ease_in_out(p)
    blend = (fa.astype(np.float32) * (1-ep) + fb.astype(np.float32) * ep).astype(np.uint8)
    # Zoom ra/vào
    scale = 1.0 + 0.15 * math.sin(p * math.pi)
    blend = zoom_frame(blend, scale, w, h)
    # Chromatic aberration mạnh
    shift = int(15 * math.sin(p * math.pi))
    if shift > 0:
        result = blend.copy()
        result[:, shift:, 0] = blend[:, :-shift, 0]   # Red shift right
        result[:, :-shift, 2] = blend[:, shift:, 2]    # Blue shift left
        # Green stays
        return result
    return blend


def transition_bw_to_color(fa, fb, p, w, h):
    """Đen trắng → Có màu: Ảnh mới hiện dần từ B&W."""
    ep = ease_in_out(p)
    if p < 0.4:
        # Ảnh cũ fade ra → đen trắng
        rp = p / 0.4
        gray_a = to_grayscale(fa)
        return (fa * (1-rp) + gray_a * rp).astype(np.uint8)
    elif p < 0.5:
        # Hold đen trắng nhẹ
        gray_b = to_grayscale(fb)
        return add_vignette(gray_b, 0.4)
    else:
        # Đen trắng → dần có màu
        rp = (p - 0.5) / 0.5
        ep2 = ease_in_out(rp)
        gray_b = to_grayscale(fb)
        result = (gray_b * (1-ep2) + fb.astype(np.float32) * ep2).astype(np.uint8)
        # Tăng saturation dần
        img = Image.fromarray(result)
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(0.5 + 1.0 * ep2)
        return np.array(img, dtype=np.uint8)


def transition_mist(fa, fb, p, w, h):
    """Mist / Khói: Hiệu ứng sương mù dày đặc rồi tan."""
    ep = ease_in_out(p)
    # Tạo noise pattern cho khói
    noise = np.random.randint(200, 255, (h//4, w//4, 3), dtype=np.uint8)
    noise_img = Image.fromarray(noise).resize((w, h), Image.LANCZOS)
    noise_img = noise_img.filter(ImageFilter.GaussianBlur(radius=40))
    smoke = np.array(noise_img, dtype=np.float32)

    # Blur cả 2 frame
    blur_r = int(min(p, 1-p) * 30) + 1
    img_a = Image.fromarray(fa)
    img_b = Image.fromarray(fb)
    if blur_r > 1:
        img_a = img_a.filter(ImageFilter.GaussianBlur(radius=blur_r))
        img_b = img_b.filter(ImageFilter.GaussianBlur(radius=blur_r))

    fa_b = np.array(img_a, dtype=np.float32)
    fb_b = np.array(img_b, dtype=np.float32)

    # Blend: A → khói → B
    base = fa_b * (1-ep) + fb_b * ep
    smoke_intensity = math.sin(p * math.pi) * 0.55
    result = base * (1-smoke_intensity) + smoke * smoke_intensity
    return np.clip(result, 0, 255).astype(np.uint8)


def transition_lightning_flash(fa, fb, p, w, h):
    """Fluorescent Scan / Sấm sét: Flash sáng chói + rung."""
    if p < 0.1:
        return fa
    elif p < 0.2:
        # Flash 1 - sấm chớp
        flash = ((p - 0.1) / 0.1) 
        white = np.full_like(fa, 255)
        result = (fa * (1-flash*0.95) + white * flash*0.95).astype(np.uint8)
        return shake_frame(result, 15, w, h)
    elif p < 0.3:
        # Tối đen nhanh
        darkness = (p - 0.2) / 0.1
        return (fa * (1 - darkness * 0.8)).astype(np.uint8)
    elif p < 0.4:
        # Flash 2 - mạnh hơn
        flash = math.sin((p - 0.3) / 0.1 * math.pi)
        white = np.full_like(fb, 255)
        mix = (fb * 0.3 + white * 0.7 * flash).astype(np.float32)
        result = np.clip(mix, 0, 255).astype(np.uint8)
        return shake_frame(result, 20, w, h)
    elif p < 0.55:
        # Flash 3 nhẹ  
        flash = math.sin((p - 0.4) / 0.15 * math.pi) * 0.4
        result = (fb.astype(np.float32) * (1+flash)).astype(np.float32)
        result = np.clip(result, 0, 255).astype(np.uint8)
        return shake_frame(result, 8, w, h)
    else:
        # Settle vào ảnh mới
        rp = (p - 0.55) / 0.45
        residual_shake = max(0, 5 * (1-rp))
        result = fb if residual_shake < 1 else shake_frame(fb, residual_shake, w, h)
        return result


def transition_scan_light(fa, fb, p, w, h):
    """Scan Light: Dải sáng quét từ trái sang phải."""
    ep = ease_in_out(p)
    result = fa.copy()
    scan_pos = int(w * ep)
    beam_w = max(1, int(w * 0.12))

    if scan_pos > 0:
        result[:, :min(scan_pos, w)] = fb[:, :min(scan_pos, w)]

    for i in range(beam_w):
        x = scan_pos - beam_w//2 + i
        if 0 <= x < w:
            intensity = 1.0 - abs(i - beam_w/2) / (beam_w/2)
            glow = 255 * intensity * 0.9
            result[:, x] = np.clip(result[:, x].astype(np.float32) + glow, 0, 255).astype(np.uint8)
    return result


def transition_fold(fa, fb, p, w, h):
    """Fold: Ảnh cũ gập lại như lật trang sách."""
    ep = ease_in_out(p)
    result = fb.copy()
    fold_w = int(w * (1 - ep))
    if fold_w > 5:
        img_a = Image.fromarray(fa)
        # Perspective distortion simulation
        img_a = img_a.resize((fold_w, h), Image.LANCZOS)
        darkening = 0.3 + 0.7 * (1-ep)
        arr = (np.array(img_a, dtype=np.float32) * darkening)
        # Thêm gradient shadow ở mép gập
        for i in range(min(fold_w, 30)):
            shadow = i / 30 * 0.5
            arr[:, fold_w-1-i] *= (1 - shadow)
        result[:, :fold_w] = np.clip(arr, 0, 255).astype(np.uint8)
    return result


def transition_popping_cards(fa, fb, p, w, h):
    """Popping Cards / Mở album: Ảnh mới bay ra từ giữa như mở album."""
    ep = ease_out_back(min(1.0, p * 1.1))
    # Ảnh cũ thu nhỏ và xoay nhẹ
    if p < 0.3:
        rp = p / 0.3
        scale = 1.0 - rp * 0.3
        angle = rp * -8
        img = Image.fromarray(fa)
        img = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=(0,0,0))
        return np.array(img, dtype=np.uint8)

    # Ảnh mới pop ra từ giữa
    scale = max(0.01, ep * 1.0)
    nw, nh = int(w * scale), int(h * scale)
    if nw < 2 or nh < 2:
        return np.zeros((h, w, 3), dtype=np.uint8)

    img_b = Image.fromarray(fb)
    img_b = img_b.resize((nw, nh), Image.LANCZOS)

    # Background: ảnh cũ blurred + darkened
    bg = Image.fromarray(fa).filter(ImageFilter.GaussianBlur(radius=15))
    bg = ImageEnhance.Brightness(bg).enhance(0.3)
    result = np.array(bg.resize((w, h), Image.LANCZOS), dtype=np.uint8)

    # Paste ảnh mới ở giữa
    xo, yo = (w-nw)//2, (h-nh)//2
    card = np.array(img_b, dtype=np.uint8)
    # Thêm viền trắng (như card)
    border = 4
    if nw > border*2 and nh > border*2:
        padded = np.full((nh + border*2, nw + border*2, 3), 255, dtype=np.uint8)
        padded[border:border+nh, border:border+nw] = card
        pxo, pyo = max(0, xo-border), max(0, yo-border)
        ph, pw = padded.shape[:2]
        # Clamp to canvas
        cw = min(pw, w - pxo)
        ch = min(ph, h - pyo)
        if cw > 0 and ch > 0:
            result[pyo:pyo+ch, pxo:pxo+cw] = padded[:ch, :cw]
    else:
        if xo >= 0 and yo >= 0 and xo+nw <= w and yo+nh <= h:
            result[yo:yo+nh, xo:xo+nw] = card

    # Drop shadow
    return result


def transition_zigzag(fa, fb, p, w, h):
    """Zigzag View: Ảnh mới lộ dần theo pattern zigzag."""
    ep = ease_in_out(p)
    result = fa.copy()
    num_strips = 8
    strip_h = h // num_strips

    for i in range(num_strips):
        # Mỗi strip chạy từ trái hoặc phải
        direction = 1 if i % 2 == 0 else -1
        strip_progress = max(0, min(1, (ep - i * 0.05) / 0.6))

        if strip_progress > 0:
            y_start = i * strip_h
            y_end = min(y_start + strip_h, h)
            reveal = int(w * strip_progress)

            if direction == 1:
                result[y_start:y_end, :reveal] = fb[y_start:y_end, :reveal]
            else:
                result[y_start:y_end, w-reveal:] = fb[y_start:y_end, w-reveal:]
    return result


def transition_x_opening(fa, fb, p, w, h):
    """X Opening: Ảnh mới lộ ra từ 4 góc theo hình chữ X."""
    ep = ease_in_out(p)
    result = fa.copy()

    # Tạo mask hình X mở rộng dần
    cx, cy = w // 2, h // 2
    Y, X = np.ogrid[:h, :w]
    # Khoảng cách angular từ center
    angles = np.arctan2(Y - cy, X - cx)

    # 4 quadrants mở ra
    spread = ep * math.pi / 2
    mask = np.zeros((h, w), dtype=np.float32)

    for base_angle in [0, math.pi/2, math.pi, -math.pi/2]:
        diff = np.abs(angles - base_angle)
        diff = np.minimum(diff, 2*math.pi - diff)
        quad_mask = np.clip(1.0 - diff / max(0.01, spread), 0, 1)
        mask = np.maximum(mask, quad_mask)

    mask = np.clip(mask * 1.5, 0, 1)
    result = (fa * (1 - mask[:,:,np.newaxis]) + fb * mask[:,:,np.newaxis]).astype(np.uint8)
    return result


def transition_crossfade(fa, fb, p, w, h):
    ep = ease_in_out(p)
    return (fa * (1-ep) + fb * ep).astype(np.uint8)


TRANSITION_FUNCTIONS = {
    "door_opens": transition_door_opens,
    "multi_impact": transition_multi_impact,
    "rotate_snap": transition_rotate_snap,
    "chromo_zoom": transition_chromo_zoom,
    "bw_to_color": transition_bw_to_color,
    "mist": transition_mist,
    "lightning_flash": transition_lightning_flash,
    "scan_light": transition_scan_light,
    "fold": transition_fold,
    "popping_cards": transition_popping_cards,
    "zigzag": transition_zigzag,
    "x_opening": transition_x_opening,
    "crossfade": transition_crossfade,
}


# ============================================================
# VIDEO GENERATION
# ============================================================
def generate_video(image_paths, output_path, config=None):
    if config is None:
        config = TEMPLATE_CONFIG

    W, H = config["canvas_width"], config["canvas_height"]
    FPS = config["fps"]
    num_slots = config["num_slots"]
    durations = config["slide_durations"]
    trans_dur = config["transition_duration"]
    transitions = config["transitions"]
    kb_presets = config["ken_burns_presets"]

    while len(image_paths) < num_slots:
        image_paths.append(image_paths[len(image_paths) % len(image_paths)])
    image_paths = image_paths[:num_slots]

    print(f"📸 Loading {len(image_paths)} images...")
    frames_data = []
    for i, path in enumerate(image_paths):
        print(f"   [{i+1}/{len(image_paths)}] {os.path.basename(path)}")
        frames_data.append(load_and_fit_image(path, W, H))

    total_duration = sum(durations)
    total_frames = int(total_duration * FPS)
    print(f"🎬 {total_duration:.1f}s ({total_frames} frames) | {len(transitions)} transitions")

    tmp_dir = tempfile.mkdtemp(prefix="videogen_")
    print(f"⚙️  Rendering...")

    frame_idx = 0
    for slide_i in range(num_slots):
        slide_dur = durations[slide_i]
        slide_frames = int(slide_dur * FPS)
        kb = kb_presets[slide_i]

        for f in range(slide_frames):
            t = f / FPS
            frame = apply_ken_burns(frames_data[slide_i], t, slide_dur, kb, W, H)

            time_to_end = slide_dur - t
            if slide_i < num_slots - 1 and time_to_end <= trans_dur:
                tp = 1.0 - (time_to_end / trans_dur)
                tn = transitions[slide_i] if slide_i < len(transitions) else "crossfade"
                tf = TRANSITION_FUNCTIONS.get(tn, transition_crossfade)
                nf = apply_ken_burns(frames_data[slide_i+1], 0, durations[slide_i+1], kb_presets[slide_i+1], W, H)
                frame = tf(frame, nf, tp, W, H)

            Image.fromarray(frame).save(os.path.join(tmp_dir, f"frame_{frame_idx:06d}.png"), "PNG")
            frame_idx += 1
            if frame_idx % (FPS*2) == 0:
                print(f"   {frame_idx/total_frames*100:.0f}%")

    print(f"✅ {frame_idx} frames rendered")
    print(f"🎥 Encoding...")

    raw = os.path.join(tmp_dir, "raw.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(FPS),
        "-i", os.path.join(tmp_dir, "frame_%06d.png"),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", raw
    ], capture_output=True, check=True)

    if os.path.exists(BGM_PATH):
        print(f"🎵 Adding music...")
        vd = frame_idx / FPS
        subprocess.run([
            "ffmpeg", "-y", "-i", raw, "-i", BGM_PATH,
            "-filter_complex",
            f"[1:a]atrim=0:{vd},afade=t=out:st={vd-1.5}:d=1.5,volume=0.7[a]",
            "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart", output_path
        ], capture_output=True, check=True)
    else:
        shutil.copy2(raw, output_path)

    shutil.rmtree(tmp_dir)
    sz = os.path.getsize(output_path) / 1024 / 1024
    print(f"🎉 Done! {output_path} ({sz:.1f} MB, {frame_idx/FPS:.1f}s, {W}x{H})")


# ============================================================
# CLI
# ============================================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("python3 video_generator.py <images_dir> [output.mp4]")
        sys.exit(1)

    d = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) >= 3 else os.path.join(os.path.dirname(d), "output_video.mp4")

    valid = {'.jpg', '.jpeg', '.png', '.webp'}
    imgs = []
    for f in sorted(os.listdir(d)):
        fp = os.path.join(d, f)
        if os.path.splitext(f)[1].lower() in valid and os.path.getsize(fp) > 100:
            try:
                Image.open(fp).verify()
                imgs.append(fp)
            except:
                pass

    if not imgs:
        print("No valid images found"); sys.exit(1)

    print(f"📂 {len(imgs)} images")
    generate_video(imgs, out)
