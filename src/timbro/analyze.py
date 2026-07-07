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
_BLANK_LINE = re.compile(r"\n[ \t]*\n")
_SENTENCE_END = re.compile(r"[.!?]+")  # ponytail: naive sentence count, no spaCy in _struct

# Folk-advice exploratory features (#21).
_INLINE_CODE_SPAN = re.compile(r"`([^`\n]+)`")
_MD_LINK = re.compile(r"\[(.*?)\]\((.*?)\)")
_EXTERNAL_REF = re.compile(r"(scripts/|references/|assets/)[^\s)\]]*")
_NAMED_SECTIONS = (
    "examples", "guidelines", "when to use", "procedure", "pitfalls", "usage", "instructions",
)
_NAME_FORMAT = re.compile(r"[a-z0-9-]{1,64}")
_HEADING_MARK = re.compile(r"^[ \t]*#{1,6}[ \t]+")
_FM_WHEN_CLAUSE = re.compile(r"\b(when|use (this|it) (when|for|to)|whenever|if you)\b", re.I)
_FM_OR_WORD = re.compile(r"\bor\b", re.I)
_FM_WILDCARD = re.compile(r"\b(any|all|every|always|whenever|anything|everything)\b", re.I)
_ALLCAPS = re.compile(r"\b[A-Z][A-Z']+\b")
_ALLCAPS_DIRECTIVES = {"ALWAYS", "NEVER", "MUST", "NOT", "DON'T", "DO"}
_CONTRASTIVE = re.compile(r"^(do|don'?t|correct|incorrect|good|bad)\s*:", re.I)
_CONTRASTIVE_SYMBOLS = ("✅", "❌", "✓", "✗")

_CONTENT_POS = {"NOUN", "PROPN", "VERB", "ADJ", "ADV"}
_COH_CONTENT_POS = {"NOUN", "PROPN", "VERB", "ADJ"}
_CLAUSAL_DEPS = {"ccomp", "xcomp", "advcl", "acl", "relcl"}
_CONDITIONAL_MARKS = {"if", "unless", "when"}
_SECOND_PERSON = {"you", "your", "yours", "you're", "yourself"}
_CROSS_REFERENCE = re.compile(
    r"\b(?:see also|see below|see above|refer to|as described in|cf\.)", re.I
)
_LEXICON_DIR = Path(__file__).parent / "lexicons"


@lru_cache(maxsize=None)
def _lexicon(name: str) -> tuple[tuple[str, ...], ...]:
    lines = (_LEXICON_DIR / name).read_text(encoding="utf-8").splitlines()
    entries = (ln.strip() for ln in lines if ln.strip() and not ln.startswith("#"))
    return tuple(tuple(entry.lower().split()) for entry in entries)


@lru_cache(maxsize=None)
def _plain_pairs() -> tuple[tuple[tuple[str, ...], str], ...]:
    lines = (_LEXICON_DIR / "plain_wording.txt").read_text(encoding="utf-8").splitlines()
    pairs = []
    for ln in lines:
        if not ln.strip() or ln.startswith("#"):
            continue
        complex_side, _, plain = ln.partition("\t")
        pairs.append((tuple(complex_side.lower().split()), plain.strip()))
    return tuple(pairs)


@lru_cache(maxsize=None)
def _hype_entries() -> tuple[tuple[str, ...], ...]:
    # Hype is matched on surface FORM, not lemma: en_core_web_sm mangles participial adjectives
    # ("groundbreaking" -> "groundbreake") and splits hyphenated compounds into three tokens
    # ("world-class" -> world - class), so the lemma-matching used by the frozen boosters/hedges
    # lexicons silently drops most of this list. Entries are tokenized the same way spaCy splits
    # (hyphen kept as its own token) so multiword and hyphenated terms line up against the forms.
    lines = (_LEXICON_DIR / "hype.txt").read_text(encoding="utf-8").splitlines()
    entries = []
    for ln in lines:
        stripped = ln.strip()
        if not stripped or stripped.startswith("#"):
            continue
        entries.append(tuple(stripped.lower().replace("-", " - ").split()))
    return tuple(entries)


def _lexicon_matches(lemmas: list[str], entries: tuple[tuple[str, ...], ...]) -> int:
    count = 0
    for entry in entries:
        width = len(entry)
        for i in range(len(lemmas) - width + 1):
            if tuple(lemmas[i : i + width]) == entry:
                count += 1
    return count

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


def _imperative_ratio(sentences) -> float | None:
    if not sentences:
        return None
    imperative = 0
    for sent in sentences:
        root = sent.root
        if root.tag_ != "VB":
            continue
        if any(c.dep_ in {"nsubj", "nsubjpass"} for c in root.children):
            continue
        if sent.text.rstrip().endswith("?"):
            continue
        imperative += 1
    return imperative / len(sentences)


def _first_person_ratio(sentences) -> float | None:
    if not sentences:
        return None
    count = sum(
        1
        for sent in sentences
        if any(c.dep_ == "nsubj" and c.lemma_.lower() in {"i", "we"} for c in sent.root.children)
    )
    return count / len(sentences)


def _conditional_clauses_per_sentence(doc, n_sentences: int) -> float | None:
    if not n_sentences:
        return None
    count = sum(
        1
        for tok in doc
        if tok.dep_ == "advcl"
        and any(c.dep_ == "mark" and c.lemma_.lower() in _CONDITIONAL_MARKS for c in tok.children)
    )
    return count / n_sentences


def _struct_features(raw: str) -> tuple[dict, str]:
    n = len(raw)
    headings = list(_HEADING.finditer(raw))
    code_chars = sum(len(m.group(0)) for m in _FENCE.finditer(raw))
    lines = raw.split("\n")
    non_blank = [ln for ln in lines if ln.strip()]
    ordered_lines = sum(1 for ln in lines if _ORDERED_LIST.match(ln))
    bullet_lines = sum(1 for ln in lines if _BULLET_LIST.match(ln))
    list_lines = ordered_lines + bullet_lines
    prose = strip_markup(raw)

    inline_chars = sum(len(s) for s in _INLINE_CODE_SPAN.findall(_FENCE.sub("", raw)))

    # External refs: bare scripts//references//assets/ tokens (with markdown links
    # collapsed to their text) plus the same pattern inside every link target.
    bare_refs = len(_EXTERNAL_REF.findall(_MD_LINK.sub(lambda m: m.group(1), raw)))
    target_refs = sum(len(_EXTERNAL_REF.findall(m.group(2))) for m in _MD_LINK.finditer(raw))

    named_section = 0
    for m in headings:
        htext = _HEADING_MARK.sub("", m.group(0)).strip().lower()
        if any(s in htext for s in _NAMED_SECTIONS):
            named_section = 1
            break

    # Long-paragraph ratio (#22): split blank-line-delimited paragraphs of the raw text with
    # frontmatter and fenced code removed, so neither is double-counted as prose.
    without_fences = _FENCE.sub("", _FRONTMATTER.sub("", raw))
    paragraphs = [p for p in _BLANK_LINE.split(without_fences) if p.strip()]
    long_paragraphs = sum(1 for p in paragraphs if len(_SENTENCE_END.findall(p)) > 6)

    frontmatter = {}
    fm_match = _FRONTMATTER.match(raw)
    if fm_match:
        try:
            loaded = yaml.safe_load(fm_match.group(1))
        except yaml.YAMLError:
            loaded = None
        if isinstance(loaded, dict):
            frontmatter = loaded

    name = frontmatter.get("name")
    description = frontmatter.get("description")
    if isinstance(description, str) and description:
        fm_tokens = len(_analyze_nlp()(description))
        wildcards = len(_FM_WILDCARD.findall(description))
        fm_desc = {
            "fm_desc_present": 1,
            "fm_desc_tokens": fm_tokens,
            "fm_desc_when_clause": 1 if _FM_WHEN_CLAUSE.search(description) else 0,
            "fm_desc_or_count": len(_FM_OR_WORD.findall(description)),
            "fm_desc_wildcard_per_token": wildcards / fm_tokens if fm_tokens else 0,
        }
    else:
        fm_desc = {
            "fm_desc_present": 0,
            "fm_desc_tokens": 0,
            "fm_desc_when_clause": 0,
            "fm_desc_or_count": 0,
            "fm_desc_wildcard_per_token": 0,
        }

    struct = {
        "struct_heading_count": len(headings),
        "struct_max_heading_depth": max((len(m.group(1)) for m in headings), default=0),
        "struct_code_char_ratio": code_chars / n if n else None,
        "struct_list_item_ratio": list_lines / len(non_blank) if non_blank else None,
        "struct_table_count": len(_TABLE_SEPARATOR.findall(raw)),
        "struct_prose_ratio": len(prose) / n if n else None,
        "struct_frontmatter_field_count": len(frontmatter),
        "struct_line_count": len(lines) if raw else 0,
        "struct_inline_code_char_ratio": inline_chars / n if n else 0.0,
        "struct_ordered_list_ratio": ordered_lines / len(non_blank) if non_blank else 0.0,
        "struct_bullet_list_ratio": bullet_lines / len(non_blank) if non_blank else 0.0,
        "struct_external_ref_count": bare_refs + target_refs,
        "struct_named_section_present": named_section,
        "struct_name_format_valid": 1 if isinstance(name, str) and _NAME_FORMAT.fullmatch(name) else 0,
        "struct_long_paragraph_ratio": long_paragraphs / len(paragraphs) if paragraphs else 0.0,
        **fm_desc,
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

    if sentences:
        long_sents = sum(
            1 for sent in sentences if sum(1 for t in sent if not t.is_space) > 25
        )
        out["read_long_sentence_ratio"] = long_sents / len(sentences)
    else:
        out["read_long_sentence_ratio"] = 0.0

    out["dict_imperative_ratio"] = _imperative_ratio(sentences)
    out["dict_first_person_subject_ratio"] = _first_person_ratio(sentences)
    out["dict_contrastive_example_count"] = sum(
        1
        for ln in prose.split("\n")
        if (s := ln.lstrip()) and (_CONTRASTIVE.match(s) or s[0] in _CONTRASTIVE_SYMBOLS)
    )

    all_tokens = [t for t in doc if not t.is_space]
    n_all = len(all_tokens)
    allcaps_hits = sum(1 for w in _ALLCAPS.findall(prose) if w in _ALLCAPS_DIRECTIVES)
    out["dict_allcaps_directive_per_1k"] = allcaps_hits / n_all * 1000 if n_all else 0.0
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

    all_lemmas = [t.lemma_.lower() for t in all_tokens]
    out["dict_hedge_per_1k"] = (
        _lexicon_matches(all_lemmas, _lexicon("hedges.txt")) / n_all * 1000 if n_all else 0.0
    )
    out["dict_booster_per_1k"] = (
        _lexicon_matches(all_lemmas, _lexicon("boosters.txt")) / n_all * 1000 if n_all else 0.0
    )
    all_forms = [t.text.lower() for t in all_tokens]
    out["dict_hype_per_1k"] = (
        _lexicon_matches(all_forms, _hype_entries()) / n_all * 1000 if n_all else 0.0
    )
    out["dict_negation_per_1k"] = (
        _lexicon_matches(all_lemmas, _lexicon("negations.txt")) / n_all * 1000 if n_all else 0.0
    )
    out["dict_conditional_per_1k"] = (
        _lexicon_matches(all_lemmas, _lexicon("connectives_conditional.txt")) / n_all * 1000
        if n_all
        else 0.0
    )
    out["dict_conditional_clauses_per_sentence"] = _conditional_clauses_per_sentence(
        doc, len(sentences)
    )

    second_person = sum(1 for t in all_tokens if t.text.lower() in _SECOND_PERSON)
    out["dict_second_person_per_1k"] = second_person / n_all * 1000 if n_all else 0.0

    cross_refs = len(_CROSS_REFERENCE.findall(prose))
    out["dict_cross_reference_per_1k"] = cross_refs / n_all * 1000 if n_all else 0.0

    plain_matches = 0
    plain_replacements = []
    for entry, plain in _plain_pairs():
        hits = _lexicon_matches(all_lemmas, (entry,))
        if hits:
            plain_matches += hits
            plain_replacements.append([" ".join(entry), plain])
    out["dict_plain_replacement_per_1k"] = plain_matches / n_all * 1000 if n_all else 0.0
    out["dict_plain_replacements_json"] = json.dumps(plain_replacements)

    if len(sentences) < 2:
        out["coh_lemma_overlap_adj"] = None
    else:
        sent_lemma_sets = [
            {t.lemma_.lower() for t in sent if t.pos_ in _COH_CONTENT_POS} for sent in sentences
        ]
        overlaps = []
        for a, b in zip(sent_lemma_sets, sent_lemma_sets[1:]):
            union = a | b
            overlaps.append(len(a & b) / len(union) if union else 0.0)
        out["coh_lemma_overlap_adj"] = sum(overlaps) / len(overlaps)

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
    fieldnames = [k for k in rows[0] if not k.endswith("_json")]
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
