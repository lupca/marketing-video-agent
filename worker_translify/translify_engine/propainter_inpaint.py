import os
import gc
import cv2
import numpy as np
import shutil
import tempfile
import logging
import torch

from propainter.propainter_video import (
    RawFrameSequencer,
    RawMaskSequencer,
    ScaledProPainterIterator,
    run_streaming_propainter
)

# Monkeypatch BufferedSequencer.trim_buffer_to to a no-op because our chunks are small
# and trimming causes negative-index AssertionErrors when sliding windows fetch reference frames.
try:
    from pytorchcv.models.common.stream import BufferedSequencer
    BufferedSequencer.trim_buffer_to = lambda self, start: None
    logging.getLogger(__name__).info("Monkeypatched BufferedSequencer.trim_buffer_to to prevent index trimming errors.")
except Exception as patch_err:
    logging.getLogger(__name__).warning(f"Failed to patch BufferedSequencer: {patch_err}")

logger = logging.getLogger(__name__)

def _inpaint_video_frames_propainter_single_chunk(
    frames: list,
    masks: list,
    work_dir: str,
    image_resize_ratio: float = 1.0,
    mask_dilation: int = 4
) -> list:
    """
    Apply SOTA ProPainter deep learning video inpainting on a single chunk of video frames.
    """
    # ProPainter requires at least 2 frames for optical flow tracking
    if len(frames) < 2:
        logger.warning("ProPainter chunk requires at least 2 frames. Falling back to OpenCV Telea.")
        out_frames = []
        for frame, mask in zip(frames, masks):
            kernel = np.ones((5, 5), np.uint8)
            dilated_mask = cv2.dilate(mask, kernel, iterations=1)
            inp = cv2.inpaint(frame, dilated_mask, 5, cv2.INPAINT_TELEA)
            out_frames.append(inp)
        return out_frames

    # Aggressive memory cleanup before starting
    gc.collect()
    try:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except Exception as e:
        logger.warning(f"Failed to clear CUDA cache before single chunk run: {e}")

    # Create a unique temp folder
    temp_dir = tempfile.mkdtemp(prefix="propainter_chunk_", dir=work_dir)

    frame_paths = []
    mask_paths = []

    try:
        # Save all frames and masks as PNGs to disk
        for i, (frame, mask) in enumerate(zip(frames, masks)):
            frame_path = os.path.join(temp_dir, f"frame_{i:05d}.png")
            mask_path = os.path.join(temp_dir, f"mask_{i:05d}.png")
            
            cv2.imwrite(frame_path, frame)
            
            binary_mask = np.zeros_like(mask)
            binary_mask[mask > 0] = 255
            cv2.imwrite(mask_path, binary_mask)
            
            frame_paths.append(frame_path)
            mask_paths.append(mask_path)

        # Setup ProPainter sequencers
        raw_frames = RawFrameSequencer(data=[frame_paths])
        raw_masks = RawMaskSequencer(data=[mask_paths])
        
        # Use low VRAM config: pp_window_size=30, step=5
        vi_iterator = ScaledProPainterIterator(
            raw_frames=raw_frames,
            raw_masks=raw_masks,
            image_resize_ratio=image_resize_ratio,
            mask_dilation=mask_dilation,
            pp_window_size=30,
            step=5
        )
        
        # Run streaming ProPainter
        out_rgb = run_streaming_propainter(vi_iterator)
        
        # Convert output back to list of BGR frames
        out_bgr = [cv2.cvtColor(f, cv2.COLOR_RGB2BGR) for f in out_rgb]
        
        return out_bgr

    finally:
        # Clean up temp folder and files
        try:
            shutil.rmtree(temp_dir)
        except Exception as cleanup_err:
            logger.error(f"Error cleaning up temp dir {temp_dir}: {cleanup_err}")
            
        # Clean up variables and GPU memory
        try:
            del raw_frames
            del raw_masks
            del vi_iterator
            del out_rgb
        except NameError:
            pass
        gc.collect()
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
        except Exception as cleanup_gpu_err:
            logger.warning(f"Failed to clear CUDA cache in finally block: {cleanup_gpu_err}")


def inpaint_video_frames_propainter(
    frames: list,
    masks: list,
    work_dir: str,
    image_resize_ratio: float = 1.0,
    mask_dilation: int = 4
) -> list:
    """
    Apply SOTA ProPainter deep learning video inpainting on a list of BGR video frames.
    Uses video chunking and small window size for maximum VRAM safety.
    
    Parameters
    ----------
    frames : list of np.ndarray
        List of BGR video frames (numpy arrays, uint8).
    masks : list of np.ndarray
        List of single-channel masks (numpy arrays, uint8, >0 means pixel should be inpainted).
    work_dir : str
        Directory to create the temporary files under.
    image_resize_ratio : float, default 1.0
        Resize ratio to save VRAM (e.g. 0.5 to resize frames to half size during inference).
    mask_dilation : int, default 4
        ProPainter internal mask dilation (must be > 0).
        
    Returns
    -------
    list of np.ndarray
        List of inpainted BGR video frames.
    """
    assert len(frames) == len(masks), f"Mismatch: {len(frames)} frames vs {len(masks)} masks"
    if len(frames) == 0:
        return []

    # Dynamically scale down for large resolutions to prevent CUDA OOM
    # 16GB VRAM on RTX 4060 Ti can easily handle up to 1920px native resolution.
    h, w = frames[0].shape[:2]
    max_dim = max(h, w)
    if max_dim > 1920:
        dynamic_ratio = 1920.0 / max_dim
        if image_resize_ratio > dynamic_ratio:
            logger.info(f"Dynamically reducing image_resize_ratio from {image_resize_ratio} to {dynamic_ratio:.3f} to prevent CUDA OOM (max dim: {max_dim}px)")
            image_resize_ratio = dynamic_ratio

    N = len(frames)
    
    # 1. If no frame has any mask (nothing to inpaint), bypass entirely
    has_any_mask = any(np.any(m > 0) for m in masks)
    if not has_any_mask:
        logger.info("No active text/mask detected in any frame. Bypassing ProPainter.")
        return list(frames)

    # 2. Chunking parameters (optimized for 16GB VRAM)
    chunk_size = 30
    overlap = 8
    
    # Generate intervals
    intervals = []
    start = 0
    while start < N:
        if N - start <= chunk_size:
            intervals.append((start, N))
            break
        else:
            end = start + chunk_size
            if N - (end - overlap) < 10:
                intervals.append((start, N))
                break
            intervals.append((start, end))
            start = end - overlap

    logger.info(f"Splitting {N} frames into {len(intervals)} chunks for VRAM-safe ProPainter. Chunks: {intervals}")
    
    # Initialize output list
    inpainted_frames = [None] * N
    
    try:
        for idx, (start_idx, end_idx) in enumerate(intervals):
            chunk_frames = frames[start_idx:end_idx]
            chunk_masks = masks[start_idx:end_idx]
            
            # Check if this specific chunk has any mask
            chunk_has_mask = any(np.any(m > 0) for m in chunk_masks)
            if not chunk_has_mask:
                logger.info(f"Chunk {idx} ({start_idx}-{end_idx}) has no mask. Copying original frames.")
                inp_chunk = list(chunk_frames)
            else:
                logger.info(f"Processing chunk {idx} ({start_idx}-{end_idx}) with ProPainter...")
                inp_chunk = _inpaint_video_frames_propainter_single_chunk(
                    frames=chunk_frames,
                    masks=chunk_masks,
                    work_dir=work_dir,
                    image_resize_ratio=image_resize_ratio,
                    mask_dilation=mask_dilation
                )
            
            # Merge inp_chunk into inpainted_frames
            if idx == 0:
                for i in range(len(inp_chunk)):
                    inpainted_frames[start_idx + i] = inp_chunk[i]
            else:
                # Merge overlap region: [start_idx, start_idx + overlap]
                overlap_len = min(overlap, len(inp_chunk))
                for i in range(overlap_len):
                    global_idx = start_idx + i
                    prev_frame = inpainted_frames[global_idx]
                    curr_frame = inp_chunk[i]
                    alpha = i / max(1, overlap_len - 1)
                    # Blend the two frames
                    inpainted_frames[global_idx] = cv2.addWeighted(prev_frame, 1.0 - alpha, curr_frame, alpha, 0.0)
                
                # Copy rest of the chunk
                for i in range(overlap_len, len(inp_chunk)):
                    inpainted_frames[start_idx + i] = inp_chunk[i]
                    
        return inpainted_frames

    except Exception as e:
        logger.error(f"Error during chunked ProPainter inpainting: {e}", exc_info=True)
        logger.warning("Encountered error in ProPainter pipeline. Falling back to OpenCV Telea.")
        fallback_frames = []
        for frame, mask in zip(frames, masks):
            kernel = np.ones((9, 9), np.uint8)
            dilated_mask = cv2.dilate(mask, kernel, iterations=1)
            inp = cv2.inpaint(frame, dilated_mask, 5, cv2.INPAINT_TELEA)
            fallback_frames.append(inp)
        return fallback_frames
