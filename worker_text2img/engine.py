import json
import urllib.request
import random
import os
import logging
import time
from shared_core.minio_utils import upload_file_to_minio

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ComfyUI API configuration
COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")

def generate_image(prompt_text, width=1024, height=1024, seed=None):
    """
    Tạo ảnh bằng SDXL-Lightning (4-step). 
    Thay thế hoàn toàn cho workflow FLUX cũ để tiết kiệm VRAM.
    """
    if seed is None:
        seed = random.randint(1, 1000000000)
    
    # Workflow tối giản cho SDXL-Lightning
    workflow = {
        "1": {
            "inputs": {
                "ckpt_name": "sdxl_lightning_4step.safetensors"
            },
            "class_type": "CheckpointLoaderSimple"
        },
        "2": {
            "inputs": {
                "text": prompt_text,
                "clip": ["1", 1]
            },
            "class_type": "CLIPTextEncode"
        },
        "3": {
            "inputs": {
                "text": "low quality, blurry, distorted, text, watermark, deformed, ugly",
                "clip": ["1", 1]
            },
            "class_type": "CLIPTextEncode"
        },
        "4": {
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1
            },
            "class_type": "EmptyLatentImage"
        },
        "5": {
            "inputs": {
                "seed": seed,
                "steps": 4,           # Chuẩn Lightning 4-step
                "cfg": 1.0,           # Luôn để 1.0 cho dòng Lightning
                "sampler_name": "euler",
                "scheduler": "sgm_uniform", # Quan trọng nhất để ra ảnh đẹp
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0]
            },
            "class_type": "KSampler"
        },
        "6": {
            "inputs": {
                "samples": ["5", 0],
                "vae": ["1", 2]
            },
            "class_type": "VAEDecode"
        },
        "7": {
            "inputs": {
                "filename_prefix": "Lightning_Gen",
                "images": ["6", 0]
            },
            "class_type": "SaveImage"
        }
    }

    p = {"prompt": workflow}
    data = json.dumps(p).encode('utf-8')
    url = f"{COMFYUI_URL}/prompt"
    req = urllib.request.Request(url, data=data)
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            prompt_id = result['prompt_id']
            logger.info(f"Prompt sent to ComfyUI (SDXL-Lightning), ID: {prompt_id}")
            return prompt_id
    except Exception as e:
        logger.error(f"Lỗi kết nối ComfyUI: {e}")
        raise Exception(f"Lỗi kết nối ComfyUI: {e}")

def wait_for_image(prompt_id, timeout=600):
    """
    Đợi ComfyUI xử lý xong và lấy tên file ảnh.
    """
    start_time = time.time()
    url = f"{COMFYUI_URL}/history/{prompt_id}"
    
    while time.time() - start_time < timeout:
        try:
            with urllib.request.urlopen(url) as response:
                history = json.loads(response.read().decode('utf-8'))
                if prompt_id in history:
                    prompt_info = history[prompt_id]
                    
                    # Kiểm tra lỗi thực thi
                    status = prompt_info.get("status", {})
                    if status.get("completed", False):
                        messages = status.get("messages", [])
                        for msg in messages:
                            if isinstance(msg, list) and len(msg) > 0 and msg[0] == "execution_error":
                                error_details = msg[1] if len(msg) > 1 else {}
                                exception_msg = error_details.get("exception_message", "Unknown ComfyUI error")
                                node_id = error_details.get("node_id", "unknown")
                                raise Exception(f"ComfyUI Error on node {node_id}: {exception_msg}")
                        
                        # Lấy ảnh đầu ra
                        outputs = prompt_info.get('outputs', {})
                        for node_id in outputs:
                            if 'images' in outputs[node_id]:
                                return outputs[node_id]['images'][0]['filename']
                                
                        raise Exception("Workflow completed but no image found.")
        except Exception as e:
            if "ComfyUI Error" in str(e) or "no image found" in str(e):
                raise e
            logger.warning(f"Polling history... {e}")
        
        time.sleep(2)
    
    raise Exception(f"Timeout (prompt_id: {prompt_id})")

def generate_image_and_upload(prompt, job_id, project_id, width=1024, height=1024, seed=None, config_data=None):
    """
    Hàm điều phối chính: Tạo ảnh -> Đợi -> Tải về -> Upload MinIO -> Lưu DB.
    """
    # 1. Gửi yêu cầu tạo ảnh
    prompt_id = generate_image(prompt, width=width, height=height, seed=seed)
    
    # 2. Đợi kết quả
    filename = wait_for_image(prompt_id)
    
    # 3. Tải ảnh từ ComfyUI về server tạm
    view_url = f"{COMFYUI_URL}/view?filename={filename}"
    local_tmp_path = f"/tmp/{filename}"
    
    try:
        urllib.request.urlretrieve(view_url, local_tmp_path)
        logger.info(f"Downloaded image to {local_tmp_path}")
        
        # 4. Upload lên MinIO và Đăng ký Database (PostgreSQL)
        from shared_core.database import SessionLocal
        from shared_core.models import VideoJob, Asset
        from shared_core.worker_base import get_or_create_job_folders
        
        db = SessionLocal()
        user_id = None
        parent_folder_id = None
        output_folder_id = None
        video_name_cleaned = f"Job_{job_id}"
        
        try:
            job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
            if job and job.project:
                user_id = job.project.user_id
                
            video_name = "Lightning_Image"
            if config_data:
                video_name = config_data.get("title") or config_data.get("name") or f"Img_{job_id}"
                
            if user_id:
                parent_folder_id, output_folder_id, video_name_cleaned = get_or_create_job_folders(db, job_id, user_id, video_name)
        except Exception as db_err:
            logger.error(f"DB Error: {db_err}")
            
        # Xác định đường dẫn MinIO
        if parent_folder_id and output_folder_id:
            object_name = f"jobs/{job_id}_{video_name_cleaned}/output/lightning_{job_id}_{int(time.time())}.png"
        else:
            object_name = f"projects/{project_id}/images/lightning_{job_id}_{int(time.time())}.png"
            
        s3_uri = upload_file_to_minio(object_name, local_tmp_path)
        
        # Lưu thông tin Asset vào Postgres
        if user_id:
            try:
                file_size = os.path.getsize(local_tmp_path)
                asset = Asset(
                    user_id=user_id,
                    asset_type="image",
                    file_name=os.path.basename(object_name),
                    display_name=os.path.basename(object_name),
                    file_size_bytes=file_size,
                    s3_url=s3_uri,
                    mime_type="image/png",
                    folder_id=output_folder_id,
                    source="generated"
                )
                db.add(asset)
                db.commit()
                logger.info(f"Registered SDXL-Lightning image in DB.")
            except Exception as asset_err:
                logger.error(f"Failed to register asset: {asset_err}")
        
        db.close()
        
        # Xóa file tạm
        if os.path.exists(local_tmp_path):
            os.remove(local_tmp_path)
            
        return s3_uri
    except Exception as e:
        logger.error(f"Error handling image: {e}")
        raise Exception(f"Error handling image: {e}")

if __name__ == "__main__":
    # Test nhanh (Cần ComfyUI đang chạy)
    test_prompt = "A majestic dragon on a mountain peak, cinematic, highly detailed"
    print("Testing SDXL-Lightning generation...")
    try:
        pid = generate_image(test_prompt)
        print(f"Prompt ID: {pid}")
        fname = wait_for_image(pid)
        print(f"Success! Image saved as: {fname}")
    except Exception as e:
        print(f"Test failed: {e}")
