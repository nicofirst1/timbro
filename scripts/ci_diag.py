import os, glob, hashlib, numpy as np
import torch, transformers, sentence_transformers, huggingface_hub
from sentence_transformers import SentenceTransformer
print("versions", torch.__version__, transformers.__version__, sentence_transformers.__version__, huggingface_hub.__version__)
root = os.path.expanduser("~/.cache/huggingface/hub")
for r in glob.glob(root + "/models--*/refs/main"):
    print("ref", r.replace(root, ""), open(r).read())
a = "I fixed the parser today. It dropped the last row, so I added a guard and a test."
b = "A cat slept on the warm windowsill all afternoon while it rained outside."
for kw in [dict(local_files_only=True), dict(local_files_only=True, device="cpu")]:
    m = SentenceTransformer("all-MiniLM-L6-v2", **kw)
    print("device", kw, m.device, "mps_available", torch.backends.mps.is_available())
    e = m.encode([a, b], normalize_embeddings=True)
    print("sim", kw, float(np.dot(e[0], e[1])))
