# WS3 analysis deviations log

Every triggered decision rule (ADR-0004 D1–D9) and every departure from a frozen pre-registration (ADR-0004/0005/0007/0008/0010) is logged here with a date and a pointer, per the `experiment-discipline` skill and PLAN §8. Numbers are cited from generated artifacts, never retyped.

---

## 2026-07-10 08:46 — WS3-5-RQ4 · H4b centroid operationalization (NO deviation — resolved in the PRE-REG)

**Not a deviation. Recorded because it looked like one and the resolution should be findable.**

ADR-0005 §8b H4b converges skills toward "their register-cluster centroid", while RQ1 (WS3-3-CLUSTER, D3) declared **NO DISCRETE DIALECTS** (best k-means silhouette < 0.10) — so at first read the H4b referent looks undefined. It is **not**: the RQ4 PRE-REG block (`LEDGER_LOG.md#WS3-5-RQ4`, 2026-07-10 08:46) already froze the operationalization _before any outcome was seen_ — H4b's centroid is the **nearest of the frozen RQ1 k=5 k-means reference centroids**, with the RQ1 population's frozen z-transform, and the PRE-REG pre-registers the exact interpretive caveat to carry with any H4b result ("convergence toward the nearest of the RQ1 k-means reference centroids, a partition RQ1 found dimensional not categorical; not a validated dialect"). The test is well-defined and **runs as pre-registered** — no substitution, no downgrade, no user decision needed. Both H4a and H4b are confirmatory, BH q=0.10 over the 2-family (D6-style).

No decision rule (D1–D9) fired for WS3-5-RQ4. Result recorded at `paper/code/ws3/LEDGER_LOG.md#WS3-5-RQ4`.
