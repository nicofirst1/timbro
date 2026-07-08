#!/usr/bin/env python3
"""Build skills.sh installs-join table (paper/data/skillssh_meta.parquet).

*** GATED — DO NOT RUN THE CRAWL WITHOUT EXPLICIT SIGN-OFF ***

skills.sh (Ling et al.'s marketplace) exposes ~20,000 skill detail pages via public,
robots-allowed sitemaps. Each detail page embeds a JSON-LD block carrying total installs
(schema.org `userInteractionCount`), stars, first-seen date, and security-audit verdicts.
Joined onto skill-diffs texts by `owner/repo/skill`, this is the PRIMARY RQ2 outcome
(paper/README.md §3–§4 step 7).

The crawl itself is ~3h over ~20K pages and is gated on two conditions
(paper/code/ws1/LEDGER.md "GATED" note, paper/README.md §5/§6):
  (a) reading https://skills.sh/terms and confirming crawling/reuse is permitted, and
  (b) explicit user sign-off on the time/politeness cost.

Running this script with NO flags prints the plan and aborts — no network call is made.
To proceed past the guard you must pass BOTH `--i-have-read-terms` and `--confirm-crawl`.
`--check-terms-only` performs exactly two read-only GETs (robots.txt, /terms) so a human can
make that determination; it never touches a sitemap or a skill page.

NEVER call `https://skills.sh/api/*` — it is OIDC-gated AND robots-disallowed. `polite_get()`
hard-guards against any URL containing "/api/" on the skills.sh host; this is not optional and
must not be removed or bypassed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

import pyarrow as pa
import pyarrow.parquet as pq
import requests

from _manifest import data_dir, write_manifest

# --------------------------------------------------------------------------- constants

BASE_URL = "https://skills.sh"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
TERMS_URL = f"{BASE_URL}/terms"
# robots.txt (fetched 2026-07-07 via --check-terms-only) names the sitemap on the `www`
# subdomain: "Sitemap: https://www.skills.sh/sitemap.xml" — use that, not the bare host.
SITEMAP_INDEX_URL = "https://www.skills.sh/sitemap.xml"

CONTACT_EMAIL = "nicofirst1@gmail.com"
USER_AGENT = (
    "timbro-paper-ws1-bot/1.0 "
    f"(+contact: {CONTACT_EMAIL}; academic corpus build; "
    "see paper/code/ws1/README.md in shl0ms/timbro-adjacent research repo)"
)

MAX_REQ_PER_SEC = 2.0  # recipe cap (paper/README.md §4 step 7) — do not raise without sign-off
REQUEST_TIMEOUT_S = 30
MAX_RETRIES_PER_URL = 5

# This is a local tag, not one of _schema.SOURCE_* — skillssh_meta.parquet is a metadata
# table JOINED onto the corpus by owner/repo/skill, never merged into corpus.parquet, so it
# is intentionally outside CORPUS_COLUMNS / the SOURCE_* enum owned by _schema.py.
SOURCE_SKILLSSH = "skillssh_meta"

OUTPUT_COLUMNS = ["owner", "repo", "skill", "installs", "stars", "first_seen", "audit_verdict", "url"]


# --------------------------------------------------------------------------- hard guard

def _assert_not_api(url: str) -> None:
    """Hard guard: never call skills.sh/api/* — OIDC-gated AND robots-disallowed.

    This check is deliberately not configurable. If you are tempted to special-case an
    /api/ URL here, stop — read paper/README.md §3's skills.sh row and §5 guardrail 3 again.
    """
    parsed = urlparse(url)
    if parsed.netloc.endswith("skills.sh") and "/api/" in parsed.path:
        raise RuntimeError(
            f"REFUSING to call {url!r}: skills.sh/api/* is OIDC-gated and robots-disallowed "
            "(paper/README.md §3, §5 guardrail 3). This is a hard guard, not a bug."
        )


# --------------------------------------------------------------------------- rate limiting

class RateLimiter:
    """Simple token-less rate limiter: sleeps so calls stay at or under `max_per_sec`."""

    def __init__(self, max_per_sec: float):
        self._min_interval = 1.0 / max_per_sec
        self._last_call: float | None = None

    def wait(self) -> None:
        now = time.monotonic()
        if self._last_call is not None:
            elapsed = now - self._last_call
            remaining = self._min_interval - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last_call = time.monotonic()


# --------------------------------------------------------------------------- caching

def cache_dir() -> Path:
    d = data_dir() / "skillssh_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_paths(url: str) -> tuple[Path, Path]:
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    body_path = cache_dir() / f"{key}.body"
    meta_path = cache_dir() / f"{key}.meta.json"
    return body_path, meta_path


def cache_read(url: str) -> str | None:
    body_path, meta_path = _cache_paths(url)
    if body_path.exists() and meta_path.exists():
        return body_path.read_text(encoding="utf-8", errors="replace")
    return None


def cache_write(url: str, body: str, status: int) -> None:
    body_path, meta_path = _cache_paths(url)
    body_path.write_text(body, encoding="utf-8")
    meta_path.write_text(json.dumps({"url": url, "status": status, "fetched_utc": time.time()}), encoding="utf-8")


# --------------------------------------------------------------------------- polite fetch

def polite_get(
    session: requests.Session,
    url: str,
    rate_limiter: RateLimiter,
    *,
    use_cache: bool = True,
) -> str:
    """GET `url` with the recipe's politeness contract: UA+contact, <=2 req/s, cache, 429 honor.

    Never fetches a URL under skills.sh/api/* (see `_assert_not_api`).
    """
    _assert_not_api(url)

    if use_cache:
        cached = cache_read(url)
        if cached is not None:
            return cached

    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES_PER_URL + 1):
        rate_limiter.wait()
        try:
            resp = session.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT_S)
        except requests.RequestException as exc:
            last_exc = exc
            print(f"[build_skillssh] request error on {url} (attempt {attempt}): {exc}")
            time.sleep(min(2 ** attempt, 30))
            continue

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            delay = float(retry_after) if retry_after and retry_after.isdigit() else min(2 ** attempt, 60)
            print(f"[build_skillssh] 429 on {url}, honoring Retry-After={delay}s")
            time.sleep(delay)
            continue

        if resp.status_code >= 500:
            print(f"[build_skillssh] {resp.status_code} on {url} (attempt {attempt}), backing off")
            time.sleep(min(2 ** attempt, 30))
            continue

        resp.raise_for_status()
        if use_cache:
            cache_write(url, resp.text, resp.status_code)
        return resp.text

    raise RuntimeError(f"Failed to fetch {url} after {MAX_RETRIES_PER_URL} attempts: {last_exc}")


# --------------------------------------------------------------------------- terms / robots check

def check_terms_only() -> int:
    """Read-only permission check: fetch ONLY robots.txt and /terms, print verdicts.

    Two requests total, no cache write needed (this is a human-facing sanity check, not
    part of the cached crawl artifact), no sitemap, no skill page. Safe to run anytime.
    """
    session = requests.Session()
    print(f"[build_skillssh] GET {ROBOTS_URL}")
    try:
        robots_resp = session.get(ROBOTS_URL, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT_S)
        robots_resp.raise_for_status()
        print("----- robots.txt -----")
        print(robots_resp.text)
    except requests.RequestException as exc:
        print(f"[build_skillssh] FAILED to fetch {ROBOTS_URL}: {exc}")

    print(f"\n[build_skillssh] GET {TERMS_URL}")
    try:
        terms_resp = session.get(TERMS_URL, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT_S)
        terms_resp.raise_for_status()
        print("----- /terms (raw response body) -----")
        print(terms_resp.text)
    except requests.RequestException as exc:
        print(f"[build_skillssh] FAILED to fetch {TERMS_URL}: {exc}")

    return 0


# --------------------------------------------------------------------------- sitemap

def fetch_sitemap_shards(session: requests.Session, rate_limiter: RateLimiter) -> list[str]:
    """Fetch /sitemap.xml, return the list of `sitemap-skills-*.xml` shard URLs."""
    xml_text = polite_get(session, SITEMAP_INDEX_URL, rate_limiter)
    root = ET.fromstring(xml_text)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    shard_urls = []
    for loc in root.findall(".//sm:sitemap/sm:loc", ns) or root.findall(".//loc"):
        url = (loc.text or "").strip()
        if "sitemap-skills-" in url:
            shard_urls.append(url)
    if not shard_urls:
        # Fall back: maybe /sitemap.xml IS a single urlset already listing skill pages.
        for loc in root.findall(".//sm:url/sm:loc", ns) or root.findall(".//loc"):
            url = (loc.text or "").strip()
            if url:
                shard_urls.append(url)
    return shard_urls


def fetch_shard_urls(session: requests.Session, rate_limiter: RateLimiter, shard_url: str) -> list[str]:
    """Fetch one sitemap-skills-*.xml shard, return the skill detail-page URLs it lists."""
    xml_text = polite_get(session, shard_url, rate_limiter)
    root = ET.fromstring(xml_text)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [
        (loc.text or "").strip()
        for loc in (root.findall(".//sm:url/sm:loc", ns) or root.findall(".//loc"))
        if (loc.text or "").strip()
    ]
    return urls


# --------------------------------------------------------------------------- detail-page parsing

_JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.DOTALL | re.IGNORECASE
)

# skills.sh skill detail pages are /{owner}/{repo}/{skill} — NO "/skills/" path prefix
# (verified against a live page 2026-07-08; the earlier /skills/-prefixed regex matched
# nothing). Owner and owner/repo listing pages have <3 segments and are not skills.


def _deep_find(obj, predicate):
    """Recursively search a JSON-LD dict/list for the first value satisfying `predicate(key, val)`."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if predicate(k, v):
                return v
            found = _deep_find(v, predicate)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _deep_find(item, predicate)
            if found is not None:
                return found
    return None


def parse_owner_repo_skill(url: str) -> tuple[str, str, str] | None:
    segs = [s for s in urlparse(url).path.strip("/").split("/") if s]
    if len(segs) != 3:
        return None
    return segs[0], segs[1], segs[2]


def parse_detail_page(html: str, url: str) -> dict | None:
    """Extract owner/repo/skill/installs/stars/first_seen/audit_verdict from a detail page.

    Best-effort against schema.org JSON-LD conventions (the recipe names
    `userInteractionCount` as the installs field). The exact key names for stars/
    first_seen/audit_verdict were NOT verified against a live page (the crawl is gated),
    so this parser searches broadly by key-name substring rather than a fixed exact path.
    If the gate is lifted, spot-check the first ~20 parsed rows against the rendered pages
    before trusting the full run — record any correction in LEDGER.md.
    """
    owr = parse_owner_repo_skill(url)
    if owr is None:
        print(f"[build_skillssh] WARNING: could not parse owner/repo/skill from {url}")
        return None
    owner, repo, skill = owr

    installs = stars = first_seen = audit_verdict = None
    for match in _JSONLD_RE.finditer(html):
        raw = match.group(1).strip()
        try:
            blob = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if installs is None:
            installs = _deep_find(blob, lambda k, v: k == "userInteractionCount" and isinstance(v, (int, float, str)))
        if stars is None:
            stars = _deep_find(
                blob, lambda k, v: k.lower() in ("stars", "starcount", "ratingvalue") and isinstance(v, (int, float, str))
            )
        if first_seen is None:
            first_seen = _deep_find(
                blob, lambda k, v: k.lower() in ("firstseen", "datecreated", "datepublished") and isinstance(v, str)
            )
        if audit_verdict is None:
            audit_verdict = _deep_find(
                blob, lambda k, v: "audit" in k.lower() and "verdict" in k.lower()
            )
            if audit_verdict is None:
                audit_verdict = _deep_find(blob, lambda k, v: k.lower() in ("auditverdict", "securityverdict"))

    def _to_int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    return {
        "owner": owner,
        "repo": repo,
        "skill": skill,
        "installs": _to_int(installs),
        "stars": _to_int(stars),
        "first_seen": str(first_seen) if first_seen is not None else None,
        "audit_verdict": str(audit_verdict) if audit_verdict is not None else None,
        "url": url,
    }


# --------------------------------------------------------------------------- crawl orchestration

def run_crawl(rate: float) -> Path:
    session = requests.Session()
    rate_limiter = RateLimiter(rate)

    print(f"[build_skillssh] Re-reading {ROBOTS_URL} and {TERMS_URL} for the provenance record...")
    robots_text = polite_get(session, ROBOTS_URL, rate_limiter)
    terms_text = polite_get(session, TERMS_URL, rate_limiter)
    print(f"[build_skillssh] robots.txt cached ({len(robots_text)} chars), /terms cached ({len(terms_text)} chars)")

    print(f"[build_skillssh] Fetching sitemap index: {SITEMAP_INDEX_URL}")
    shard_urls = fetch_sitemap_shards(session, rate_limiter)
    print(f"[build_skillssh] Found {len(shard_urls)} shard(s)")

    detail_urls: list[str] = []
    for shard_url in shard_urls:
        urls = fetch_shard_urls(session, rate_limiter, shard_url)
        print(f"[build_skillssh]   {shard_url} -> {len(urls)} skill URLs")
        detail_urls.extend(urls)

    # Dedup while preserving determinism.
    detail_urls = sorted(set(detail_urls))

    # skills.sh's skills sitemap includes a handful of /api/* URLs (robots-disallowed;
    # not skill detail pages). Drop them up front with one summary line instead of a
    # per-URL WARNING from the polite_get guard, which stays as a backstop.
    api_urls = [u for u in detail_urls if "/api/" in urlparse(u).path]
    if api_urls:
        detail_urls = [u for u in detail_urls if u not in set(api_urls)]
        print(f"[build_skillssh] filtered {len(api_urls)} /api/* URLs from the sitemap "
              f"(robots-disallowed, not skill pages)")
    print(f"[build_skillssh] {len(detail_urls)} unique skill detail pages to crawl")

    rows: list[dict] = []
    for i, url in enumerate(detail_urls):
        if (i + 1) % 500 == 0:
            print(f"[build_skillssh] Progress: {i + 1}/{len(detail_urls)}")
        try:
            html = polite_get(session, url, rate_limiter)
        except Exception as exc:
            print(f"[build_skillssh] WARNING: failed to fetch {url}: {exc}")
            continue
        row = parse_detail_page(html, url)
        if row is not None:
            rows.append(row)

    rows.sort(key=lambda r: (r["owner"], r["repo"], r["skill"]))

    schema = pa.schema(
        [
            ("owner", pa.string()),
            ("repo", pa.string()),
            ("skill", pa.string()),
            ("installs", pa.int64()),
            ("stars", pa.int64()),
            ("first_seen", pa.string()),
            ("audit_verdict", pa.string()),
            ("url", pa.string()),
        ]
    )
    arrays = [pa.array([r.get(col) for r in rows]) for col in OUTPUT_COLUMNS]
    table = pa.table({col: arr for col, arr in zip(OUTPUT_COLUMNS, arrays)}, schema=schema)

    out_path = data_dir() / "skillssh_meta.parquet"
    pq.write_table(table, str(out_path))
    print(f"[build_skillssh] Wrote {len(rows)} rows to {out_path}")

    write_manifest(
        out_path,
        source=SOURCE_SKILLSSH,
        inputs=[
            {"url": ROBOTS_URL, "fetch_utc": time.time()},
            {"url": TERMS_URL, "fetch_utc": time.time()},
            {"url": SITEMAP_INDEX_URL, "n_shards": len(shard_urls)},
        ],
        n_rows=len(rows),
        packages=["requests", "pyarrow"],
        extra={"rate_limit_req_per_sec": rate, "n_detail_urls_attempted": len(detail_urls)},
    )
    return out_path


# --------------------------------------------------------------------------- gate + CLI

PLAN_TEXT = f"""\
[build_skillssh] PLAN (not executed):
  1. GET {ROBOTS_URL}  — confirm skill detail pages + sitemaps are crawl-allowed.
  2. GET {TERMS_URL}   — confirm crawling/reuse is permitted; STOP if it forbids this.
  3. GET {SITEMAP_INDEX_URL} -> discover sitemap-skills-*.xml shards (~20,000 URLs total).
  4. Crawl each skill detail page at <= {MAX_REQ_PER_SEC} req/s with UA:
       {USER_AGENT}
     Cache raw HTML under paper/data/skillssh_cache/ (never re-fetch a cached URL).
     Honor 429 + Retry-After. Never call {BASE_URL}/api/* (OIDC-gated, robots-disallowed).
  5. Parse each page's JSON-LD block for installs (userInteractionCount), stars,
     first-seen date, audit verdict; key rows on owner/repo/skill.
  6. Write paper/data/skillssh_meta.parquet + a committed manifest.

  Estimated cost: ~20,000 requests at <= {MAX_REQ_PER_SEC} req/s -> ~3 hours.

This script is GATED (paper/code/ws1/LEDGER.md, "GATED build_skillssh.py"; paper/README.md
§4 step 7, §5, §6). It will not proceed without BOTH --i-have-read-terms and --confirm-crawl.
"""


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Build paper/data/skillssh_meta.parquet from skills.sh (GATED — see module docstring).",
    )
    p.add_argument(
        "--check-terms-only",
        action="store_true",
        help="Read-only permission check: GET robots.txt and /terms only (2 requests), then exit. "
        "No sitemap, no skill pages, no gate flags required.",
    )
    p.add_argument(
        "--i-have-read-terms",
        action="store_true",
        help="Attest that you have personally read https://skills.sh/terms and it permits this crawl/reuse.",
    )
    p.add_argument(
        "--confirm-crawl",
        action="store_true",
        help="Explicit sign-off to run the ~3h, ~20K-page crawl.",
    )
    p.add_argument(
        "--rate",
        type=float,
        default=MAX_REQ_PER_SEC,
        help=f"Max requests/sec (default {MAX_REQ_PER_SEC}; recipe cap — do not raise without sign-off).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_argparser().parse_args(argv)

    if args.check_terms_only:
        return check_terms_only()

    print(PLAN_TEXT)

    if not (args.i_have_read_terms and args.confirm_crawl):
        sys.exit(
            "[build_skillssh] ABORTING: gate not satisfied. This build is GATED — see the "
            "'GATED' note in paper/code/ws1/LEDGER.md and paper/README.md §4 step 7 / §5 / §6. "
            "Re-run with --check-terms-only to read robots.txt + /terms yourself, then pass both "
            "--i-have-read-terms and --confirm-crawl only after explicit user sign-off."
        )

    if args.rate > MAX_REQ_PER_SEC:
        sys.exit(
            f"[build_skillssh] ABORTING: --rate {args.rate} exceeds the recipe cap of "
            f"{MAX_REQ_PER_SEC} req/s (paper/README.md §4 step 7). Do not raise this without sign-off."
        )

    run_crawl(args.rate)
    return 0


if __name__ == "__main__":
    sys.exit(main())
