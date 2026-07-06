"""``timbro analyze`` (#17): one deterministic linguistic feature vector per document.

No LLM, no network at analyze time. Profiles/rubrics/scoring/verdicts are untouched --
this is a standalone slice for the SKILL.md linguistic-topology paper (paper/README.md
WS2 Issue A). `struct_*` runs on the raw markdown; everything else runs on prose
isolated via the #16 markup stripper (`timbro.rubrics.preprocess.strip_markup`).
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path

import textdescriptives as td
import yaml
from lexical_diversity import lex_div
from wordfreq import zipf_frequency

from timbro.core import POS_TAGS
from timbro.rubrics.preprocess import strip_markup

_FRONTMATTER = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n?", re.S)
_FENCE = re.compile(r"(```|~~~).*?\1", re.S)
_HEADING = re.compile(r"(?m)^[ \t]*(#{1,6})[ \t]+.*$")
_TABLE_SEPARATOR = re.compile(r"(?m)^[ \t]*:?-{2,}:?(?:[ \t]*\|[ \t]*:?-{2,}:?)+[ \t]*$")
_BULLET_LIST = re.compile(r"^[ \t]*[-*+][ \t]+")
_ORDERED_LIST = re.compile(r"^[ \t]*\d+\.[ \t]+")

_CONTENT_POS = {"NOUN", "PROPN", "VERB", "ADJ", "ADV"}
_CLAUSAL_DEPS = {"ccomp", "xcomp", "advcl", "acl", "relcl"}

# textdescriptives' extract_df column -> our snake_case name (exact renames are decisions
# from the #17 spec: syn_mean_dependency_distance, not syn_dependency_distance_mean).
_TD_RENAME = {
    "n_tokens": "desc_tokens",
    "n_unique_tokens": "desc_unique_tokens",
    "proportion_unique_tokens": "desc_proportion_unique_tokens",
    "n_characters": "desc_characters",
    "n_sentences": "desc_sentences",
    "token_length_mean": "desc_token_length_mean",
    "token_length_median": "desc_token_length_median",
    "token_length_std": "desc_token_length_std",
    "sentence_length_mean": "desc_sentence_length_mean",
    "sentence_length_median": "desc_sentence_length_median",
    "sentence_length_std": "desc_sentence_length_std",
    "syllables_per_token_mean": "desc_syllables_per_token_mean",
    "syllables_per_token_median": "desc_syllables_per_token_median",
    "syllables_per_token_std": "desc_syllables_per_token_std",
    "flesch_reading_ease": "read_flesch_reading_ease",
    "flesch_kincaid_grade": "read_flesch_kincaid_grade",
    "smog": "read_smog",
    "gunning_fog": "read_gunning_fog",
    "automated_readability_index": "read_automated_readability_index",
    "coleman_liau_index": "read_coleman_liau_index",
    "lix": "read_lix",
    "rix": "read_rix",
    "dependency_distance_mean": "syn_mean_dependency_distance",
    "dependency_distance_std": "syn_dependency_distance_std",
    "prop_adjacent_dependency_relation_mean": "syn_prop_adjacent_dependency_relation_mean",
    "prop_adjacent_dependency_relation_std": "syn_prop_adjacent_dependency_relation_std",
    "first_order_coherence": "coh_first_order_coherence",
    "second_order_coherence": "coh_second_order_coherence",
}


@lru_cache(maxsize=1)
def _analyze_nlp():
    import spacy

    try:
        nlp = spacy.load("en_core_web_sm", disable=["ner"])
    except OSError as e:  # pragma: no cover
        raise OSError("Run: uv run python -m spacy download en_core_web_sm") from e
    for name in ("descriptive_stats", "readability", "dependency_distance", "coherence"):
        nlp.add_pipe(f"textdescriptives/{name}")
    return nlp


@lru_cache(maxsize=1)
def _dep_labels() -> tuple[str, ...]:
    return tuple(sorted(_analyze_nlp().get_pipe("parser").labels))


def _clean(value):
    """NaN -> None so JSON/CSV output is valid; everything else passes through."""
    if isinstance(value, float) and value != value:  # NaN != NaN
        return None
    return value


def _token_depth(tok) -> int:
    # spaCy builds a fresh Token wrapper per `.head` access, so `is` identity never
    # matches even at the root (whose head is itself by index) -- compare by `.i`.
    depth = 0
    while tok.head.i != tok.i:
        tok = tok.head
        depth += 1
    return depth


def _struct_features(raw: str) -> tuple[dict, str]:
    n = len(raw)
    headings = list(_HEADING.finditer(raw))
    code_chars = sum(len(m.group(0)) for m in _FENCE.finditer(raw))
    lines = raw.split("\n")
    non_blank = [ln for ln in lines if ln.strip()]
    list_lines = sum(1 for ln in lines if _BULLET_LIST.match(ln) or _ORDERED_LIST.match(ln))
    prose = strip_markup(raw)

    frontmatter = {}
    fm_match = _FRONTMATTER.match(raw)
    if fm_match:
        try:
            loaded = yaml.safe_load(fm_match.group(1))
        except yaml.YAMLError:
            loaded = None
        if isinstance(loaded, dict):
            frontmatter = loaded

    struct = {
        "struct_heading_count": len(headings),
        "struct_max_heading_depth": max((len(m.group(1)) for m in headings), default=0),
        "struct_code_char_ratio": code_chars / n if n else None,
        "struct_list_item_ratio": list_lines / len(non_blank) if non_blank else None,
        "struct_table_count": len(_TABLE_SEPARATOR.findall(raw)),
        "struct_prose_ratio": len(prose) / n if n else None,
        "struct_frontmatter_field_count": len(frontmatter),
        "frontmatter_json": json.dumps(frontmatter),
    }
    return struct, prose


def _nlp_features(prose: str) -> dict:
    doc = _analyze_nlp()(prose[:100000])
    out = {}

    row = td.extract_df(doc).iloc[0].to_dict()
    for src, dst in _TD_RENAME.items():
        out[dst] = _clean(row.get(src))

    sentences = list(doc.sents)
    if sentences:
        depths = [max((_token_depth(t) for t in sent), default=0) for sent in sentences]
        clausal = sum(1 for t in doc if t.dep_ in _CLAUSAL_DEPS)
        out["syn_mean_tree_depth"] = sum(depths) / len(depths)
        out["syn_clausal_per_sentence"] = clausal / len(sentences)
    else:
        out["syn_mean_tree_depth"] = None
        out["syn_clausal_per_sentence"] = None

    all_tokens = [t for t in doc if not t.is_space]
    n_all = len(all_tokens)
    pos_counts = Counter(t.pos_ for t in all_tokens)
    for tag in POS_TAGS:
        out[f"posdep_pos_{tag}"] = pos_counts.get(tag, 0) / n_all if n_all else 0.0
    dep_counts = Counter(t.dep_ for t in all_tokens)
    for label in _dep_labels():
        out[f"posdep_dep_{label}"] = dep_counts.get(label, 0) / n_all if n_all else 0.0

    content_lemmas = [t.lemma_.lower() for t in doc if t.is_alpha and t.pos_ in _CONTENT_POS]
    out["lex_mtld"] = lex_div.mtld(content_lemmas)
    out["lex_hdd"] = lex_div.hdd(content_lemmas)
    zipfs = [zipf_frequency(w, "en") for w in content_lemmas]
    out["lex_zipf_mean"] = sum(zipfs) / len(zipfs) if zipfs else None

    return out


def analyze_text(raw: str) -> dict:
    """One feature vector (no `path` key) for a raw document's text."""
    struct, prose = _struct_features(raw)
    return {**struct, **_nlp_features(prose)}


def analyze_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    return {"path": str(path), **analyze_text(text)}


def _write_jsonl(rows: list[dict], out) -> None:
    for row in rows:
        out.write(json.dumps(row) + "\n")


def _write_csv(rows: list[dict], out) -> None:
    fieldnames = [k for k in rows[0] if k != "frontmatter_json"]
    writer = csv.DictWriter(out, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)


def run_analyze(paths: list[str], fmt: str = "jsonl", out_path: str | None = None) -> int:
    files = []
    for p in paths:
        path = Path(p)
        if path.suffix not in {".md", ".txt"}:
            print(f"skipping {p}: not a .md/.txt file", file=sys.stderr)
            continue
        if not path.is_file():
            print(f"skipping {p}: no such file", file=sys.stderr)
            continue
        files.append(path)

    if not files:
        print("no .md/.txt files to analyze", file=sys.stderr)
        return 1

    rows = [analyze_file(path) for path in files]
    write = _write_csv if fmt == "csv" else _write_jsonl
    if out_path:
        with open(out_path, "w", encoding="utf-8", newline="") as fh:
            write(rows, fh)
    else:
        write(rows, sys.stdout)
    return 0
