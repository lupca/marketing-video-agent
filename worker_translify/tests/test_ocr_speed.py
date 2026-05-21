import time
import cv2
from paddleocr import PaddleOCR

# Load a test frame
cap = cv2.VideoCapture("./translify_tmp/scene_3/raw_clip.mp4")
ret, frame = cap.read()
cap.release()

if not ret:
    print("Failed to load test frame")
    exit(1)

cv2.imwrite("test_frame.jpg", frame)

def benchmark(name, ocr_instance):
    # Warmup
    _ = ocr_instance.ocr("test_frame.jpg")
    
    # Measure
    t0 = time.time()
    for _ in range(20):
        _ = ocr_instance.ocr("test_frame.jpg")
    t1 = time.time()
    avg_time = (t1 - t0) / 20
    print(f"{name}: Average time per frame = {avg_time:.4f}s ({1.0/avg_time:.1f} FPS)")
    return avg_time

print("Initializing GPU Detector (RTX 4060 Ti)...")
ocr_gpu = PaddleOCR(
    use_textline_orientation=True,
    lang="ch",
    device="gpu",
    enable_mkldnn=False,
    ocr_version="PP-OCRv4"
)
t_gpu = benchmark("GPU Detector", ocr_gpu)
