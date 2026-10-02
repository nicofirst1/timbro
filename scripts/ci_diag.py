import os, glob, hashlib, numpy as np
import torch, transformers, sentence_transformers, huggingface_hub
from sentence_transformers import SentenceTransformer
print("versions", torch.__version__, transformers.__version__, sentence_transformers.__version__, huggingface_hub.__version__)
root = os.path.expanduser("~/.cache/huggingface/hub")
for f in sorted(glob.glob(root + "/models--*/**", recursive=True)):
    if os.path.isfile(f):
        h = hashlib.sha256(open(f, "rb").read()).hexdigest()[:12]
        print("file", f.replace(root, ""), os.path.getsize(f), h)
for r in glob.glob(root + "/models--*/refs/main"):
    print("ref", r.replace(root, ""), open(r).read())
a = "I fixed the parser today. It dropped the last row, so I added a guard and a test."
b = "A cat slept on the warm windowsill all afternoon while it rained outside."
for kw in [dict(local_files_only=True), dict(cache_folder=os.path.expanduser("~/fresh-hf"))]:
    m = SentenceTransformer("all-MiniLM-L6-v2", **kw)
    print("tokens", kw, m.tokenizer.tokenize(a)[:12])
    e = m.encode([a, b], normalize_embeddings=True)
    print("sim", kw, float(np.dot(e[0], e[1])))
