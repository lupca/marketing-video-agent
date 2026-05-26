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
from shared_core.minio_utils import is_minio_path, get_object_name, get_presigned_url
try:
    from agent import CapCutSkillAgent
except ImportError:
    from .agent import CapCutSkillAgent


logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif", ".heic"}

def is_image_url(url: str) -> bool:
    """Detect if a URL points to an image file based on extension or Content-Type."""
    if not url:
        return False
    # Strip query string for extension check
    path = url.split("?")[0].lower()
    ext = os.path.splitext(path)[1]
    if ext in IMAGE_EXTENSIONS:
        return True
    # Fallback: HEAD request to check Content-Type
    try:
        resp = requests.head(url, timeout=5, allow_redirects=True)
        content_type = resp.headers.get("Content-Type", "")
        return content_type.startswith("image/")
    except Exception:
        pass
    return False

def resolve_api_url(url: str) -> str:
    """
    If url points to localhost/127.0.0.1 and we are running inside WSL,
    automatically resolve and use the Windows host IP address.
    """
    if "localhost" in url or "127.0.0.1" in url:
        is_wsl = False
        try:
            with open("/proc/version", "r") as f:
                if "microsoft" in f.read().lower():
                    is_wsl = True
        except Exception:
            pass
            
        if is_wsl:
            try:
                with open("/proc/net/route", "r") as f:
                    lines = f.readlines()
                for line in lines[1:]:
                    parts = line.split()
                    if parts[1] == "00000000":  # default route
                        gw_hex = parts[2]
                        gw_bytes = [int(gw_hex[i:i+2], 16) for i in range(0, 8, 2)]
                        gw_bytes.reverse()
                        host_ip = ".".join(map(str, gw_bytes))
                        new_url = url.replace("localhost", host_ip).replace("127.0.0.1", host_ip)
                        return new_url
            except Exception as e:
                pass
    return url

def resolve_asset_url(path: str) -> str:
    """
    If the path is an S3 URI (s3://...), convert it to a presigned HTTP URL
    so VectCutAPI can download it directly.
    """
    if path and is_minio_path(path):
        obj_name = get_object_name(path)
        presigned = get_presigned_url(obj_name, expires_seconds=86400) # 24 hours
        logger.info(f"Resolved S3 path '{path}' to URL: {presigned}")
        return presigned
    return path

# Khởi tạo Celery App dùng cơ sở hạ tầng chung của marketing-video-agent
celery_app = create_celery_app("worker_capcut", worker_type="capcut")

# Đường dẫn API và Thư mục Draft có thể cấu hình qua biến môi trường
VECTCUT_API_URL = resolve_api_url(os.getenv("VECTCUT_API_URL", "http://localhost:9002").rstrip('/'))
CAPCUT_DRAFT_FOLDER = os.getenv("CAPCUT_DRAFT_FOLDER", "E:\\capcut\\CapCut Drafts")

def to_wsl_path(path: str) -> str:
    """Convert a Windows file path (e.g. E:\\path) to a WSL mount path (/mnt/e/path)."""
    path = path.replace("\\", "/")
    if len(path) > 1 and path[1] == ":":
        drive = path[0].lower()
        return f"/mnt/{drive}{path[2:]}"
    return path

@celery_app.task(name="worker_capcut.tasks.learn_capcut_template", bind=True)
def learn_capcut_template(self, draft_id: str, dataset_id: str = None, dify_base_url: str = None, dify_api_key: str = None):
    """
    Celery task to learn from a CapCut draft template.
    Parses the timeline structure and uploads the resulting Markdown Blueprint to Dify.
    """
    logger.info(f"CapCut Template Learning picked up Draft ID: {draft_id}")
    
    # Update status to "learning" in database
    from shared_core.database import SessionLocal as InternalSessionLocal
    from shared_core.models import SystemSetting
    
    try:
        with InternalSessionLocal() as db:
            setting = db.query(SystemSetting).filter(SystemSetting.key == "capcut_learned_templates").first()
            if not setting:
                setting = SystemSetting(key="capcut_learned_templates", value={})
                db.add(setting)
            val = dict(setting.value or {})
            val[draft_id] = {
                "status": "learning",
                "template_name": draft_id,
                "updated_at": datetime.now().isoformat(),
                "document_id": None,
                "error": None
            }
            setting.value = val
            db.commit()
    except Exception as db_err:
        logger.error(f"Failed to save learning status to DB: {db_err}")

    # 1. Resolve paths
    win_draft_path = os.path.join(CAPCUT_DRAFT_FOLDER, draft_id)
    wsl_draft_path = to_wsl_path(win_draft_path)
    
    logger.info(f"Windows Draft Path: {win_draft_path} -> WSL Path: {wsl_draft_path}")
    
    if not os.path.exists(wsl_draft_path):
        err_msg = f"Không tìm thấy thư mục nháp CapCut tại đường dẫn: {wsl_draft_path}"
        logger.error(err_msg)
        
        # Update to failed status in DB
        try:
            with InternalSessionLocal() as db:
                setting = db.query(SystemSetting).filter(SystemSetting.key == "capcut_learned_templates").first()
                if setting:
                    val = dict(setting.value or {})
                    val[draft_id] = {
                        "status": "failed",
                        "template_name": draft_id,
                        "updated_at": datetime.now().isoformat(),
                        "document_id": None,
                        "error": err_msg
                    }
                    setting.value = val
                    db.commit()
        except Exception as db_err:
            logger.error(f"Failed to save failed path status to DB: {db_err}")
            
        return {"success": False, "error": err_msg}
        
    try:
        # 2. Parse CapCut timeline draft
        try:
            from worker_capcut.parsers.capcut_draft_parser import CapCutDraftParser
        except ImportError:
            try:
                from parsers.capcut_draft_parser import CapCutDraftParser
            except ImportError:
                import sys
                sys.path.append(os.path.dirname(os.path.abspath(__file__)))
                from parsers.capcut_draft_parser import CapCutDraftParser
            
        parser = CapCutDraftParser(wsl_draft_path)
        summary = parser.parse()
        md_content = parser.generate_markdown_summary(summary)
        
        # 3. Resolve Dify config
        from shared_core.database import SessionLocal as InternalSessionLocal
        from shared_core.models import SystemSetting
        
        db_dataset_id = None
        db_api_key = None
        db_base_url = None
        
        with InternalSessionLocal() as db:
            dify_setting = db.query(SystemSetting).filter(SystemSetting.key == "dify_settings").first()
            if dify_setting and dify_setting.value:
                db_dataset_id = dify_setting.value.get("dataset_id")
                db_api_key = dify_setting.value.get("api_key")
                db_base_url = dify_setting.value.get("base_url")
                
        # Resolve overrides
        final_dataset_id = dataset_id or db_dataset_id
        final_api_key = dify_api_key or db_api_key
        final_base_url = dify_base_url or db_base_url or "https://api.dify.ai/v1"
        
        if not final_dataset_id:
            raise ValueError("Chưa cấu hình Dataset ID (Knowledge Base ID) của Dify!")
        if not final_api_key:
            raise ValueError("Chưa cấu hình API Key của Dify!")
            
        # 4. Upload to Dify
        try:
            from worker_capcut.dify_client import DifyDatasetClient
        except ImportError:
            try:
                from dify_client import DifyDatasetClient
            except ImportError:
                import sys
                sys.path.append(os.path.dirname(os.path.abspath(__file__)))
                from dify_client import DifyDatasetClient
            
        client = DifyDatasetClient(base_url=final_base_url, api_key=final_api_key)
        
        doc_name = f"template_{summary['template_name']}.md"
        resp = client.upload_document_by_text(
            dataset_id=final_dataset_id,
            name=doc_name,
            text=md_content
        )
        
        # Update success status in database
        try:
            with InternalSessionLocal() as db:
                setting = db.query(SystemSetting).filter(SystemSetting.key == "capcut_learned_templates").first()
                if setting:
                    val = dict(setting.value or {})
                    val[draft_id] = {
                        "status": "success",
                        "template_name": summary.get('template_name', draft_id),
                        "updated_at": datetime.now().isoformat(),
                        "document_id": resp.get("document", {}).get("id"),
                        "error": None
                    }
                    setting.value = val
                    db.commit()
        except Exception as db_err:
            logger.error(f"Failed to save success status to DB: {db_err}")

        return {
            "success": True,
            "template_name": summary['template_name'],
            "document_id": resp.get("document", {}).get("id"),
            "summary": summary
        }
    except Exception as e:
        logger.error(f"Lỗi khi học template CapCut: {e}", exc_info=True)
        # Update fail status in database
        try:
            with InternalSessionLocal() as db:
                setting = db.query(SystemSetting).filter(SystemSetting.key == "capcut_learned_templates").first()
                if setting:
                    val = dict(setting.value or {})
                    val[draft_id] = {
                        "status": "failed",
                        "template_name": draft_id,
                        "updated_at": datetime.now().isoformat(),
                        "document_id": None,
                        "error": str(e)
                    }
                    setting.value = val
                    db.commit()
        except Exception as db_err:
            logger.error(f"Failed to save fail status to DB: {db_err}")
            
        return {"success": False, "error": str(e)}

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
        
        actual_draft_id = create_res["output"]["draft_id"]
        logger.info(f"VectCutAPI Server cấp Draft ID thực tế: {actual_draft_id}")
        insert_log(db, job_id, f"VectCutAPI Server cấp Draft ID thực tế: {actual_draft_id}")
        
        update_job(db, job, progress_percent=20)

        # 4. Trích xuất tài nguyên âm thanh (Audio Assets)
        assets = config.get("assets", {})
        audio_cfg = assets.get("audio", {})
        bgm_url = resolve_asset_url(audio_cfg.get("bgm_path"))
        voiceover_url = resolve_asset_url(audio_cfg.get("voiceover_path"))
        
        # Trích xuất và dịch thuật timeline bằng CapCutSkillAgent
        timeline = config.get("timeline_script", [])
        
        insert_log(db, job_id, "Đang khởi tạo CapCut Skill Agent để phân tích kịch bản...")
        agent = CapCutSkillAgent()
        timeline = agent.translate_timeline(timeline)
        insert_log(db, job_id, "CapCut Skill Agent đã hoàn thành dịch tham số chuyển cảnh/hoạt cảnh chuẩn CapCut.")

        # Tính toán tổng thời lượng video dựa trên timeline dịch thuật
        total_duration = 0.0
        if timeline:
            total_duration = float(timeline[-1]["time_range"][1])
        else:
            total_duration = 10.0

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
            video_url = resolve_asset_url(video_folders.get(video_src_id))
            start, end = seg.get("time_range", [0, 5])
            text_overlay = seg.get("text_overlay")
            
            # Đọc các tham số chuyển cảnh và hoạt cảnh đã dịch từ Agent
            transition = seg.get("transition")
            intro_animation = seg.get("intro_animation")
            intro_animation_duration = seg.get("intro_animation_duration", 0.5)
            outro_animation = seg.get("outro_animation")
            outro_animation_duration = seg.get("outro_animation_duration", 0.5)
            visual_effects = seg.get("visual_effects", [])

            logger.info(f"Đang xử lý phân cảnh [{segment_name}]: {start}s -> {end}s")
            insert_log(db, job_id, f"Đang xử lý phân cảnh {idx+1}/{total_segments}: {segment_name} ({start}s -> {end}s)")

            # Thêm Video Track hoặc Image Track
            if video_url:
                asset_is_image = is_image_url(video_url)
                logger.info(f"Thêm {'ảnh' if asset_is_image else 'video'} source {video_src_id}: {video_url}")

                if asset_is_image:
                    img_payload = {
                        "draft_id": actual_draft_id,
                        "image_url": video_url,
                        "start": start,
                        "end": end,
                        "track_name": "video_main",
                    }
                    if transition:
                        img_payload["transition"] = transition
                        img_payload["transition_duration"] = 0.5
                    if intro_animation:
                        img_payload["intro_animation"] = intro_animation
                        img_payload["intro_animation_duration"] = intro_animation_duration
                    if outro_animation:
                        img_payload["outro_animation"] = outro_animation
                        img_payload["outro_animation_duration"] = outro_animation_duration
                    
                    try:
                        _safe_post(f"{VECTCUT_API_URL}/add_image", img_payload, timeout=15)
                    except Exception as img_err:
                        err_str = str(img_err).lower()
                        # Xử lý phòng thủ nếu VectCutAPI trả lỗi chuyển cảnh không hợp lệ
                        if "unsupported transition" in err_str or "transition setting skipped" in err_str:
                            logger.warning(f"Bỏ qua transition '{transition}' không hỗ trợ ở ảnh: {img_err}")
                            insert_log(db, job_id, f"Cảnh báo: Bỏ qua transition '{transition}' không hỗ trợ cho ảnh. Đang thử lại...")
                            try:
                                img_payload.pop("transition", None)
                                img_payload.pop("transition_duration", None)
                                _safe_post(f"{VECTCUT_API_URL}/add_image", img_payload, timeout=15)
                                logger.info("Đã chèn ảnh thành công không chứa transition.")
                            except Exception as retry_err:
                                raise retry_err
                        else:
                            try:
                                img_payload.pop("transition", None)
                                img_payload.pop("transition_duration", None)
                                _safe_post(f"{VECTCUT_API_URL}/add_image", img_payload, timeout=15)
                            except Exception as retry_err:
                                raise retry_err
                else:
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
                    if intro_animation:
                        vid_payload["intro_animation"] = intro_animation
                        vid_payload["intro_animation_duration"] = intro_animation_duration
                    if outro_animation:
                        vid_payload["outro_animation"] = outro_animation
                        vid_payload["outro_animation_duration"] = outro_animation_duration
                    
                    try:
                        _safe_post(f"{VECTCUT_API_URL}/add_video", vid_payload, timeout=15)
                    except Exception as vid_err:
                        err_str = str(vid_err).lower()
                        if "unsupported transition" in err_str or "transition setting skipped" in err_str:
                            logger.warning(f"Bỏ qua transition '{transition}' không hỗ trợ ở video: {vid_err}")
                            insert_log(db, job_id, f"Cảnh báo: Bỏ qua transition '{transition}' không hỗ trợ cho video. Đang thử lại...")
                            try:
                                vid_payload.pop("transition", None)
                                vid_payload.pop("transition_duration", None)
                                _safe_post(f"{VECTCUT_API_URL}/add_video", vid_payload, timeout=15)
                                logger.info("Đã chèn video thành công không chứa transition.")
                            except Exception as retry_err:
                                if "overlap" in str(retry_err).lower():
                                    logger.info("Video đã tồn tại trong draft (trùng khớp dòng thời gian), tiếp tục...")
                                else:
                                    raise retry_err
                        else:
                            try:
                                vid_payload.pop("transition", None)
                                vid_payload.pop("transition_duration", None)
                                _safe_post(f"{VECTCUT_API_URL}/add_video", vid_payload, timeout=15)
                            except Exception as retry_err:
                                if "overlap" in str(retry_err).lower():
                                    logger.info("Video đã tồn tại trong draft (trùng khớp dòng thời gian), tiếp tục...")
                                else:
                                    raise retry_err

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

            prog = 40 + int((idx + 1) / total_segments * 40)
            update_job(db, job, progress_percent=prog)

        # 6. Lưu Dự Án vào phân vùng lưu trữ CapCut của máy Windows
        logger.info(f"Đang lưu dự án nháp vào thư mục CapCut: {CAPCUT_DRAFT_FOLDER}")
        insert_log(db, job_id, f"Lưu dự án nháp vào thư mục Windows: {CAPCUT_DRAFT_FOLDER}")
        
        _safe_post(f"{VECTCUT_API_URL}/save_draft", {
            "draft_id": actual_draft_id,
            "draft_folder": CAPCUT_DRAFT_FOLDER
        }, timeout=60)
        
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
