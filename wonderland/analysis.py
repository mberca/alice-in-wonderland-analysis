"""Build auditable corpus measures and compact source-position evidence."""

from collections import Counter, defaultdict
import csv
import json
from pathlib import Path

from . import __version__
from .core import (TARGETS, chapter_signatures, count_word, legacy_counts,
                   moving_average_ttr, ranked_words, tokenize, word_key)
from .mapreduce import mapreduce_counts

HISTORICAL_RESULTS = {"Alice": 377, "Rabbit": 40, "rabbit": 2, "lowercase_e": 15394}


def analyse(book):
    rows, all_words, chapter_counts, lengths = [], [], [], []
    index = defaultdict(list)
    for chapter in book.chapters:
        tokens = tokenize(chapter.text)
        words = [word_key(token.text) for token in tokens]
        counts = Counter(words)
        all_words.extend(words)
        chapter_counts.append(counts)
        lengths.append(len(tokens))
        terms = {}
        diversity = moving_average_ttr(words)
        utf16 = [0]
        for character in chapter.text:
            utf16.append(utf16[-1] + (2 if ord(character) > 0xFFFF else 1))
        for term in TARGETS:
            terms[term] = {
                "exact": count_word(tokens, term, ignore_case=False),
                "folded": count_word(tokens, term),
                "possessive": count_word(tokens, term, possessives=True),
            }
        for token in tokens:
            index[word_key(token.text, ignore_case=False)].append(
                [chapter.number, utf16[token.start], utf16[token.end]])
        rows.append({
            "number": chapter.number, "roman": chapter.roman, "title": chapter.title,
            "words": len(words), "types": len(counts), "hapax": sum(n == 1 for n in counts.values()),
            "mattr_100": round(diversity, 6) if diversity is not None else None,
            "terms": terms, "top_words": ranked_words(counts),
        })
    for row, signature in zip(rows, chapter_signatures(chapter_counts, lengths)):
        row["signature"] = signature
    counts = Counter(all_words)
    totals = {term: {mode: sum(row["terms"][term][mode] for row in rows)
                     for mode in ("exact", "folded", "possessive")} for term in TARGETS}
    character_data = {}
    for scope, text in (("narrative", book.narrative), ("full_source", book.source_text)):
        characters = mapreduce_counts(text)
        character_data[scope] = {
            "letters": sorted(characters.items(), key=lambda pair: (-pair[1], pair[0])),
            "total_letters": sum(characters.values()),
            "literal_lowercase_e": text.count("e"),
            "hash_signs": text.count("#"), "percent_signs": text.count("%"),
        }
    diversity = moving_average_ttr(all_words)
    result = {
        "schema_version": 1, "engine_version": __version__,
        "source": {
            "title": "Alice's Adventures in Wonderland", "author": "Lewis Carroll",
            "edition": "The Millennium Fulcrum Edition 3.0", "ebook": 11,
            "url": "https://www.gutenberg.org/ebooks/11",
            "sha256": book.source_sha256, "bytes": book.source_bytes,
        },
        "summary": {"chapters": len(rows), "words": len(all_words), "types": len(counts),
                    "hapax": sum(value == 1 for value in counts.values()),
                    "mattr_100": round(diversity, 6) if diversity is not None else None},
        "targets": list(TARGETS), "target_totals": totals, "chapters": rows,
        "word_frequencies": [{"word": word, "count": count}
                             for word, count in sorted(counts.items(), key=lambda p: (-p[1], p[0]))],
        "top_content_words": ranked_words(counts, limit=40),
        "top_all_words": ranked_words(counts, content_only=False, limit=40),
        "historical_report": HISTORICAL_RESULTS,
        "legacy_reproduction": legacy_counts(book.source_text),
        "legacy_case_comparison": legacy_counts(book.source_text, targets=("rabbit", "Rabbit")),
        "characters": character_data,
    }
    evidence = {
        "offset_encoding": "UTF-16 code units within each chapter",
        "chapters": [{"number": c.number, "text": c.text} for c in book.chapters],
        "index": {key: value for key, value in sorted(index.items())},
        "forms": {key: {"folded": word_key(key), "possessive": word_key(key, possessives=True)}
                  for key in sorted(index)},
        "source_header": book.source_header, "license": book.license_text,
        "original_base64": book.original_base64,
    }
    return result, evidence


def write_csv(path, rows, fields):
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(result, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "analysis.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8", newline="\n")
    write_csv(output / "chapter_metrics.csv", [
        {key: row[key] for key in ("number", "title", "words", "types", "hapax", "mattr_100")}
        for row in result["chapters"]], ("number", "title", "words", "types", "hapax", "mattr_100"))
    term_rows = []
    for chapter in result["chapters"]:
        for term, modes in chapter["terms"].items():
            term_rows.append({"chapter": chapter["number"], "term": term, **modes,
                              "folded_per_1000": round(modes["folded"] / chapter["words"] * 1000, 6)})
    write_csv(output / "term_counts.csv", term_rows,
              ("chapter", "term", "exact", "folded", "possessive", "folded_per_1000"))
    write_csv(output / "word_frequencies.csv", result["word_frequencies"], ("word", "count"))
    character_rows = []
    for scope, data in result["characters"].items():
        for character, count in data["letters"]:
            character_rows.append({"scope": scope, "character": character, "count": count,
                                   "share": round(count / data["total_letters"], 8)})
    write_csv(output / "character_counts.csv", character_rows, ("scope", "character", "count", "share"))
