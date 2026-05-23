import json
import urllib.request
import random
import os
import logging
import time
from shared_core.minio_utils import upload_file_to_minio

logger = logging.getLogger(__name__)

# ComfyUI API configuration
# Use environment variable for COMFYUI_URL, defaulting to localhost
COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")

def generate_flux_image(prompt_text, width=1024, height=1024, seed=None):
    if seed is None:
        seed = random.randint(1, 1000000000)
    
    # Workflow chuyên dụng cho FLUX với các thành phần tách biệt
    workflow = {
        "1": {
            "inputs": {
                "unet_name": "flux1-schnell-fp8-e4m3fn.safetensors",
                "weight_dtype": "default"
            },
            "class_type": "UNETLoader"
        },
        "2": {
            "inputs": {
                "clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
                "clip_name2": "clip_l.safetensors",
                "type": "flux"
            },
            "class_type": "DualCLIPLoader"
        },
        "3": {
            "inputs": {
                "vae_name": "flux_vae.safetensors"
            },
            "class_type": "VAELoader"
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
                "text": prompt_text,
                "clip": ["2", 0]
            },
            "class_type": "CLIPTextEncode"
        },
        "6": {
            "inputs": {
                "seed": seed,
                "steps": 4, # Schnell recommended steps is 4
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["5", 0],
                "negative": ["7", 0],
                "latent_image": ["4", 0]
            },
            "class_type": "KSampler"
        },
        "7": {
            "inputs": {
                "text": "",
                "clip": ["2", 0]
            },
            "class_type": "CLIPTextEncode"
        },
        "8": {
            "inputs": {
                "samples": ["6", 0],
                "vae": ["3", 0]
            },
            "class_type": "VAEDecode"
        },
        "9": {
            "inputs": {
                "filename_prefix": "FLUX_Gen",
                "images": ["8", 0]
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
            logger.info(f"Prompt sent to ComfyUI, ID: {prompt_id}")
            return prompt_id
    except Exception as e:
        logger.error(f"Lỗi kết nối ComfyUI: {e}")
        raise Exception(f"Lỗi kết nối ComfyUI: {e}")

def wait_for_image(prompt_id, timeout=600):
    """
    Polls ComfyUI history to wait for the prompt to complete and get the image filename.
    Aborts immediately if ComfyUI reports an execution error.
    """
    start_time = time.time()
    url = f"{COMFYUI_URL}/history/{prompt_id}"
    
    while time.time() - start_time < timeout:
        try:
            with urllib.request.urlopen(url) as response:
                history = json.loads(response.read().decode('utf-8'))
                if prompt_id in history:
                    prompt_info = history[prompt_id]
                    
                    # 1. Check for ComfyUI execution errors
                    status = prompt_info.get("status", {})
                    if status.get("completed", False):
                        messages = status.get("messages", [])
                        for msg in messages:
                            if isinstance(msg, list) and len(msg) > 0 and msg[0] == "execution_error":
                                error_details = msg[1] if len(msg) > 1 else {}
                                exception_msg = error_details.get("exception_message", "Unknown ComfyUI error")
                                node_id = error_details.get("node_id", "unknown")
                                raise Exception(f"ComfyUI Error on node {node_id}: {exception_msg}")
                        
                        # 2. Check for successful output images
                        outputs = prompt_info.get('outputs', {})
                        for node_id in outputs:
                            if 'images' in outputs[node_id]:
                                return outputs[node_id]['images'][0]['filename']
                                
                        raise Exception("ComfyUI workflow completed but no output images were saved.")
        except Exception as e:
            # If it is a parsed ComfyUI workflow exception, raise it immediately
            if "ComfyUI Error" in str(e) or "no output images" in str(e):
                raise e
            logger.warning(f"Error polling history: {e}")
        
        time.sleep(2)
    
    raise Exception(f"Timeout waiting for image generation (prompt_id: {prompt_id})")

def generate_flux_image_and_upload(prompt, job_id, project_id, width=1024, height=1024, seed=None):
    """
    Main orchestration function: generate image via ComfyUI and upload to MinIO.
    """
    # 1. Trigger generation
    prompt_id = generate_flux_image(prompt, width=width, height=height, seed=seed)
    
    # 2. Wait for result
    filename = wait_for_image(prompt_id)
    
    # 3. Download/Locate image
    # ComfyUI stores outputs in its 'output' directory.
    # We might need to fetch it via API if worker is on a different machine,
    # but for local dev, we might assume it's accessible or fetch via view API.
    
    view_url = f"{COMFYUI_URL}/view?filename={filename}"
    local_tmp_path = f"/tmp/{filename}"
    
    try:
        urllib.request.urlretrieve(view_url, local_tmp_path)
        logger.info(f"Downloaded generated image to {local_tmp_path}")
        
        # 4. Upload to MinIO
        object_name = f"projects/{project_id}/images/flux_{job_id}_{int(time.time())}.png"
        s3_uri = upload_file_to_minio(object_name, local_tmp_path)
        
        # Cleanup local tmp
        if os.path.exists(local_tmp_path):
            os.remove(local_tmp_path)
            
        return s3_uri
    except Exception as e:
        logger.error(f"Error handling image file: {e}")
        raise Exception(f"Error handling image file: {e}")
