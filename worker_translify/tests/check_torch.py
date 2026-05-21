import torch
import paddle

print("--- HEALTH CHECK ---")
print("PyTorch CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("PyTorch GPU:", torch.cuda.get_device_name(0))

print("Paddle CUDA available:", paddle.device.is_compiled_with_cuda())
if paddle.device.is_compiled_with_cuda():
    print("Paddle GPU device count:", paddle.device.get_device_count())
