"""
Celery worker for CapCut Draft Generator.
"""

import os
import requests
import logging
from datetime import datetime, timezone
from shared_core.worker_base import create_celery_app, update_job, insert_log
from shared_core.database import SessionLocal
from shared_core.models import VideoJob

logger = logging.getLogger(__name__)

# Khởi tạo Celery App dùng cơ sở hạ tầng chung của marketing-video-agent
celery_app = create_celery_app("worker_capcut", worker_type="capcut")

# Đường dẫn API và Thư mục Draft có thể cấu hình qua biến môi trường
VECTCUT_API_URL = os.getenv("VECTCUT_API_URL", "http://localhost:9001").rstrip('/')
CAPCUT_DRAFT_FOLDER = os.getenv("CAPCUT_DRAFT_FOLDER", "E:\\capcut\\CapCut Drafts")

@celery_app.task(name="worker_capcut.tasks.process_capcut_job", bind=True)
def process_capcut_job(self, job_id: int, config_data: dict = None):
    """
    CapCut Worker Task: Dựng dự án nháp CapCut từ kịch bản phân tích đầu ra của AI Leader Agent.
    """
    logger.info(f"CapCut Draft Worker picked up Job ID: {job_id}")
    
    db = SessionLocal()
    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        logger.error(f"Job {job_id} không tồn tại trong cơ sở dữ liệu.")
        db.close()
        return

    def _safe_post(url, payload, timeout=15):
        try:
            res = requests.post(url, json=payload, timeout=timeout)
            res.raise_for_status()
        except Exception as conn_err:
            raise RuntimeError(f"Không thể kết nối đến API {url}. Hãy kiểm tra xem VectCutAPI đã được bật chưa! Chi tiết: {conn_err}")
            
        try:
            res_json = res.json()
        except Exception:
            # Nếu phản hồi chứa HTML của MinIO Console thay vì JSON
            if "MinIO Console" in res.text or "<!doctype html>" in res.text:
                raise RuntimeError(
                    f"Xung đột cổng mạng! Cổng 9001 hiện tại đang được sử dụng bởi MinIO Console của Docker, "
                    f"chứ không phải VectCutAPI Server. Vui lòng cấu hình VectCutAPI chạy trên cổng khác (Ví dụ: 9002) "
                    f"và thiết lập biến môi trường VECTCUT_API_URL=http://localhost:9002 cho Worker."
                )
            raise RuntimeError(f"Phản hồi từ {url} không phải là JSON hợp lệ: {res.text[:200]}")

        if not res_json.get("success", False):
            raise ValueError(f"VectCutAPI trả về lỗi khi gọi {url}: {res_json.get('error')}")
        return res_json

    try:
        # 1. Khởi động tiến trình xử lý
        now = datetime.now(timezone.utc)
        update_job(db, job, status="PROCESSING", started_at=now, progress_percent=5)
        insert_log(db, job_id, "Bắt đầu khởi tạo dự án dựng nháp CapCut...")

        # 2. Đọc cấu hình đầu vào (Input Spec)
        config = job.config_data
        if not config:
            raise ValueError("Không tìm thấy payload cấu hình trong job (config_data rỗng)")
        
        project_id = job.project_id
        draft_id = f"dfd_{project_id}"
        
        # 3. Khởi tạo Draft mới qua VectCutAPI
        logger.info("Khởi tạo Draft mới trên VectCutAPI...")
        insert_log(db, job_id, "Khởi tạo Draft mới trên VectCutAPI...")
        create_res = _safe_post(f"{VECTCUT_API_URL}/create_draft", {
            "width": 1080,
            "height": 1920
        }, timeout=15)
        
        # Nhận draft_id thực tế được sinh bởi VectCutAPI Server
        actual_draft_id = create_res["output"]["draft_id"]
        logger.info(f"VectCutAPI Server cấp Draft ID thực tế: {actual_draft_id}")
        insert_log(db, job_id, f"VectCutAPI Server cấp Draft ID thực tế: {actual_draft_id}")
        
        update_job(db, job, progress_percent=20)

        # 4. Trích xuất tài nguyên âm thanh (Audio Assets)
        assets = config.get("assets", {})
        audio_cfg = assets.get("audio", {})
        bgm_url = audio_cfg.get("bgm_path")
        voiceover_url = audio_cfg.get("voiceover_path")
        
        # Tính toán tổng thời lượng video dựa trên timeline_script
        timeline = config.get("timeline_script", [])
        total_duration = 0.0
        if timeline:
            total_duration = float(timeline[-1]["time_range"][1])
        else:
            total_duration = 10.0 # Thời lượng dự phòng mặc định

        # Chèn nhạc nền BGM
        if bgm_url:
            logger.info(f"Đang chèn nhạc nền BGM: {bgm_url}")
            insert_log(db, job_id, f"Đang chèn nhạc nền BGM: {os.path.basename(bgm_url)}")
            _safe_post(f"{VECTCUT_API_URL}/add_audio", {
                "draft_id": actual_draft_id,
                "audio_url": bgm_url,
                "start": 0,
                "end": total_duration,
                "volume": 0.4,
                "track_name": "bgm"
            }, timeout=15)

        # Chèn Voiceover (Nếu có)
        if voiceover_url:
            logger.info(f"Đang chèn giọng đọc Voiceover: {voiceover_url}")
            insert_log(db, job_id, f"Đang chèn giọng đọc Voiceover: {os.path.basename(voiceover_url)}")
            _safe_post(f"{VECTCUT_API_URL}/add_audio", {
                "draft_id": actual_draft_id,
                "audio_url": voiceover_url,
                "start": 0,
                "end": total_duration,
                "volume": 1.0,
                "track_name": "voiceover"
            }, timeout=15)

        update_job(db, job, progress_percent=40)

        # 5. Duyệt và dựng phân cảnh hình ảnh & phụ đề chữ
        video_folders = assets.get("video_folders", {})
        total_segments = len(timeline)
        
        for idx, seg in enumerate(timeline):
            segment_name = seg.get("segment", f"segment_{idx+1}")
            video_src_id = seg.get("video_source")
            video_url = video_folders.get(video_src_id)
            start, end = seg.get("time_range", [0, 5])
            text_overlay = seg.get("text_overlay")
            transition = seg.get("transition")
            visual_effects = seg.get("visual_effects", [])

            logger.info(f"Đang xử lý phân cảnh [{segment_name}]: {start}s -> {end}s")
            insert_log(db, job_id, f"Đang xử lý phân cảnh {idx+1}/{total_segments}: {segment_name} ({start}s -> {end}s)")

            # Thêm Video Track
            if video_url:
                logger.info(f"Thêm video source {video_src_id}: {video_url}")
                vid_payload = {
                    "draft_id": actual_draft_id,
                    "video_url": video_url,
                    "start": start,
                    "end": end,
                    "track_name": "video_main",
                }
                if transition:
                    vid_payload["transition"] = transition
                    vid_payload["transition_duration"] = 0.5
                
                _safe_post(f"{VECTCUT_API_URL}/add_video", vid_payload, timeout=15)

            # Thêm Phụ Đề Text Overlay
            if text_overlay:
                logger.info(f"Thêm phụ đề chữ: '{text_overlay[:30]}...'")
                _safe_post(f"{VECTCUT_API_URL}/add_text", {
                    "draft_id": actual_draft_id,
                    "text": text_overlay,
                    "start": start,
                    "end": end,
                    "font_size": 48,
                    "font_color": "#FFFF00",  # Mặc định màu vàng nổi bật
                    "shadow_enabled": True,
                    "background_color": "#000000"
                }, timeout=15)

            # Thêm Visual Effects (Nếu có)
            if visual_effects:
                effect_name = visual_effects[0]
                logger.info(f"Thêm hiệu ứng hình ảnh: {effect_name}")
                try:
                    _safe_post(f"{VECTCUT_API_URL}/add_effect", {
                        "draft_id": actual_draft_id,
                        "effect_type": effect_name,
                        "start": start,
                        "end": end,
                        "effect_category": "scene"
                    }, timeout=15)
                except Exception as eff_err:
                    logger.warning(f"Không thể chèn hiệu ứng '{effect_name}': {eff_err}")
                    insert_log(db, job_id, f"Cảnh báo: Không thể thêm hiệu ứng '{effect_name}' (Bỏ qua). Chi tiết: {eff_err}", "WARNING")

            # Tính toán tiến trình động khi duyệt phân cảnh (từ 40% -> 80%)
            prog = 40 + int((idx + 1) / total_segments * 40)
            update_job(db, job, progress_percent=prog)

        # 6. Lưu Dự Án vào phân vùng lưu trữ CapCut của máy Windows
        logger.info(f"Đang lưu dự án nháp vào thư mục CapCut: {CAPCUT_DRAFT_FOLDER}")
        insert_log(db, job_id, f"Lưu dự án nháp vào thư mục Windows: {CAPCUT_DRAFT_FOLDER}")
        
        _safe_post(f"{VECTCUT_API_URL}/save_draft", {
            "draft_id": actual_draft_id,
            "draft_folder": CAPCUT_DRAFT_FOLDER
        }, timeout=60)  # Tăng timeout cho tác vụ download và save
        
        update_job(db, job, progress_percent=95)

        # 7. Đánh dấu thành công hoàn toàn
        completed_now = datetime.now(timezone.utc)
        note_msg = f"Đã dựng thành công Bản nháp CapCut tại thư mục: {os.path.join(CAPCUT_DRAFT_FOLDER, actual_draft_id)}"
        
        update_job(
            db, job,
            status="SUCCESS",
            progress_percent=100,
            note=note_msg,
            completed_at=completed_now
        )
        insert_log(db, job_id, f"Dựng bản nháp thành công! Bạn có thể mở CapCut Desktop lên để biên tập dự án: {actual_draft_id}")

    except Exception as e:
        logger.error(f"Lỗi khi dựng Bản nháp CapCut cho Job {job_id}: {str(e)}", exc_info=True)
        insert_log(db, job_id, f"Lỗi Fatal: {str(e)}", "ERROR")
        
        completed_now = datetime.now(timezone.utc)
        update_job(
            db, job,
            status="FAILED",
            error_message=str(e)[:500],
            completed_at=completed_now
        )
    finally:
        db.close()
