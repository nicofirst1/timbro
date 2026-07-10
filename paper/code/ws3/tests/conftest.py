"""Make per-step script dirs importable by their flat module names (post-reorg 2026-07-10)."""
import sys
from pathlib import Path

_WS3 = Path(__file__).resolve().parents[1]
for _d in ("common", "step1_extraction", "step2_descriptives", "step3_clustering", "step4_adoption", "step5_rq4", "step7_rq5"):
    sys.path.insert(0, str(_WS3 / _d))
