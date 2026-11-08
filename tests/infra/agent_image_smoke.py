"""Run inside the hardened agent image with the local model mounted read-only."""
import importlib
import importlib.metadata
import os
import sys

packages = {
    "torch": "torch", "torchvision": "torchvision", "transformers": "transformers",
    "peft": "peft", "timm": "timm", "accelerate": "accelerate",
    "safetensors": "safetensors", "scikit-learn": "sklearn", "scipy": "scipy",
    "numpy": "numpy", "pandas": "pandas", "pillow": "PIL", "imagehash": "imagehash",
    "opencv-python-headless": "cv2", "matplotlib": "matplotlib", "tqdm": "tqdm",
    "pyarrow": "pyarrow",
}
assert os.getuid() == 1004 and os.getgid() == 1004
assert sys.version_info[:2] == (3, 12)
for distribution, module in packages.items():
    importlib.import_module(module)
    print(f"{distribution}=={importlib.metadata.version(distribution)}", flush=True)

import torch
from transformers import ViTMAEModel, DINOv3ViTModel

assert torch.cuda.is_available()
a = torch.tensor([[1., 2.], [3., 4.]])
assert torch.equal((a.cuda() @ a.cuda()).cpu(), a @ a)
print(f"CUDA {torch.version.cuda}; cuDNN {torch.backends.cudnn.version()}; GPU {torch.cuda.get_device_name()}", flush=True)
model = ViTMAEModel.from_pretrained('/inputs/models/skhoha/SKELEX', local_files_only=True)
model.config.mask_ratio = 0.0
model.eval().cuda()
with torch.inference_mode():
    out = model(pixel_values=torch.zeros(1, 3, 224, 224, device='cuda'), noise=torch.arange(196, device='cuda').unsqueeze(0))
assert out.last_hidden_state.shape == (1, 197, 1024)
assert torch.isfinite(out.last_hidden_state).all()
print('SKELEX forward passed: (1, 197, 1024)', flush=True)
