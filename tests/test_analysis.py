import base64
from collections import Counter
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from wonderland.analysis import analyse
from wonderland.core import (ROMANS, chapter_signatures, concordance, count_word,
                             legacy_counts, load_book, moving_average_ttr,
                             parse_book, tokenize, word_key)
from wonderland.mapreduce import (decode_pairs, encode_pair, map_characters,
                                  mapreduce_counts, reduce_sorted)
from wonderland.site import render_story

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "alice-gutenberg-11.txt"


class EmbeddedData(HTMLParser):
    def __init__(self):
        super().__init__()
        self.capture = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("id") == "wonderland-data":
            self.capture = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.capture = False

    def handle_data(self, data):
        if self.capture:
            self.parts.append(data)


def fixture(first="Alice met Rabbit. Alice's rabbit-hole."):
    chapters = [f"CHAPTER {roman}. Title {roman}\n\n{first if index == 0 else 'A quiet page.'}"
                for index, roman in enumerate(ROMANS)]
    return ("Project Gutenberg\n\n*** START OF THIS PROJECT GUTENBERG EBOOK ALICE ***\n"
            "FRONT MATTER MUST NOT COUNT\n\n" + "\n\n".join(chapters)
            + "\n\nTHE END\n\nEnd of Project Gutenberg's Alice\n"
            "*** END OF THIS PROJECT GUTENBERG EBOOK ALICE ***\n"
            "*** START: FULL LICENSE ***\nA synthetic test notice, not the real edition licence.\n").encode("utf-8")


class CorpusTests(unittest.TestCase):
    def test_boundaries_exclude_titles_end_credit_and_licence(self):
        book = parse_book(fixture())
        self.assertEqual(len(book.chapters), 12)
        self.assertEqual(book.chapters[0].text, "Alice met Rabbit. Alice's rabbit-hole.")
        self.assertEqual(book.chapters[-1].text, "A quiet page.")
        for excluded in ("FRONT MATTER", "Title XII", "THE END", "Project Gutenberg", "notice"):
            self.assertNotIn(excluded, book.narrative)

    def test_ambiguous_missing_or_out_of_order_boundaries_fail(self):
        raw = fixture()
        for broken in (
            raw.replace(b"*** START OF", b"*** BEGIN OF"),
            raw + b"\n*** END OF THIS PROJECT GUTENBERG EBOOK OTHER ***\n",
            raw.replace(b"CHAPTER II.", b"CHAPTER III."),
            raw.replace(b"*** START: FULL LICENSE ***", b"licence missing"),
        ):
            with self.subTest(broken=broken[:40]), self.assertRaises(ValueError):
                parse_book(broken)

    def test_empty_chapter_is_not_silently_accepted(self):
        with self.assertRaisesRegex(ValueError, "no word tokens"):
            parse_book(fixture("123 !"))

    def test_hash_preserves_original_bytes_but_analysis_normalises_newlines(self):
        raw = b"\xef\xbb\xbf" + fixture().replace(b"\n", b"\r\n")
        book = parse_book(raw)
        self.assertEqual(book.source_sha256, sha256(raw).hexdigest())
        self.assertEqual(base64.b64decode(book.original_base64), raw)
        self.assertNotIn("\r", book.narrative)
        self.assertEqual(book.chapters[0].text, parse_book(fixture()).chapters[0].text)

    def test_word_boundaries_keep_apostrophes_and_hyphens_not_quotes_or_numbers(self):
        tokens = tokenize("“Alice’s” rabbit-hole... Alice! 123 naïve king--queen")
        self.assertEqual([t.text for t in tokens],
                         ["Alice’s", "rabbit-hole", "Alice", "naïve", "king", "queen"])
        text = "“Alice’s” rabbit-hole... Alice! 123 naïve king--queen"
        for token in tokens:
            self.assertEqual(text[token.start:token.end], token.text)

    def test_case_and_possessives_are_separate_counting_decisions(self):
        tokens = tokenize("Alice ALICE Alice's Alice’s rabbit rabbit-hole Rabbit")
        self.assertEqual(count_word(tokens, "Alice", ignore_case=False), 1)
        self.assertEqual(count_word(tokens, "Alice"), 2)
        self.assertEqual(count_word(tokens, "Alice", possessives=True), 4)
        self.assertEqual(count_word(tokens, "Rabbit"), 2)
        self.assertEqual(count_word(tokens, "Rabbit", ignore_case=False), 1)
        self.assertEqual(legacy_counts("Alice 'Alice' Alice's Rabbit Rabbit-hole"),
                         {"Alice": 1, "Rabbit": 1})

    def test_concordance_matches_whole_tokens_and_reports_recoverable_spans(self):
        book = parse_book(fixture("Alice, MALICE, Alice's and rabbit-hole; Rabbit."))
        rows = concordance(book, "Alice", context=4)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["before"], "")
        self.assertEqual(len(concordance(book, "Alice", possessives=True)), 2)
        for row in concordance(book, "Rabbit"):
            self.assertEqual(book.chapters[row["chapter"] - 1].text[row["start"]:row["end"]],
                             row["match"])
        self.assertEqual(concordance(book, "Rabbit", chapter=2), [])
        for query in ("", "two words", "<script>"):
            with self.subTest(query=query), self.assertRaises(ValueError):
                concordance(book, query)
        with self.assertRaises(ValueError):
            concordance(book, "Alice", chapter=13)

    def test_moving_window_diversity_matches_a_brute_force_reference(self):
        words = "a b a c d a b b e a b c".split()
        for window in (1, 3, 5, len(words)):
            expected = sum(len(set(words[i:i + window])) / window
                           for i in range(len(words) - window + 1)) / (len(words) - window + 1)
            self.assertAlmostEqual(moving_average_ttr(words, window), expected)
        self.assertIsNone(moving_average_ttr(words, 100))
        with self.assertRaises(ValueError):
            moving_average_ttr(words, 0)

    def test_tfidf_can_distinguish_chapter_specific_from_equally_frequent_words(self):
        counts = [Counter({"rabbit": 3, "said": 3, "the": 10}),
                  Counter({"queen": 3, "said": 3, "the": 10})]
        scores = chapter_signatures(counts, [16, 16])
        self.assertEqual(scores[0][0]["word"], "rabbit")
        self.assertEqual(scores[1][0]["word"], "queen")
        self.assertNotIn("the", [row["word"] for row in scores[0]])

    def test_short_chapters_do_not_fabricate_100_word_diversity(self):
        result, _ = analyse(parse_book(fixture()))
        self.assertIsNone(result["chapters"][0]["mattr_100"])

    def test_case_discovery_keeps_legacy_scope_and_punctuation_rules(self):
        raw = fixture("Rabbit rabbit 'rabbit' rabbit-hole.").replace(
            b"FRONT MATTER MUST NOT COUNT", b"Rabbit Rabbit")
        result, _ = analyse(parse_book(raw))
        self.assertEqual(result["legacy_case_comparison"], {"rabbit": 1, "Rabbit": 3})
        self.assertEqual(result["target_totals"]["Rabbit"]["exact"], 1)

    def test_browser_offsets_use_utf16_even_before_non_bmp_text(self):
        book = parse_book(fixture("A 😀 Rabbit and Alice."))
        _, evidence = analyse(book)
        chapter, start, end = evidence["index"]["Rabbit"][0]
        text = book.chapters[chapter - 1].text
        reconstructed = text.encode("utf-16-le")[start * 2:end * 2].decode("utf-16-le")
        self.assertEqual(reconstructed, "Rabbit")


class MapReduceTests(unittest.TestCase):
    def test_partitioned_results_equal_a_direct_counter_for_many_chunk_sizes(self):
        text = "Aa eé Straße\nRabbit\tA! 👑"
        for chunk_size in (1, 2, 7, 4096):
            for letters_only in (True, False):
                for ignore_case in (True, False):
                    normalised = text.casefold() if ignore_case else text
                    expected = Counter(c for c in normalised if not letters_only or c.isalpha())
                    with self.subTest(chunk=chunk_size, letters=letters_only, fold=ignore_case):
                        self.assertEqual(mapreduce_counts(text, chunk_size=chunk_size,
                                                         letters_only=letters_only,
                                                         ignore_case=ignore_case), expected)
        self.assertEqual(mapreduce_counts(""), {})
        with self.assertRaises(ValueError):
            mapreduce_counts(text, chunk_size=0)

    def test_json_lines_handle_whitespace_quotes_and_unicode_keys(self):
        pairs = list(map_characters("e\n\t\"😀e", letters_only=False, ignore_case=False))
        decoded = list(decode_pairs(encode_pair(pair) + "\n" for pair in pairs))
        self.assertEqual(dict(reduce_sorted(sorted(decoded))), Counter("e\n\t\"😀e"))

    def test_reducer_rejects_unsorted_keys_and_invalid_counts(self):
        with self.assertRaisesRegex(ValueError, "not sorted"):
            list(reduce_sorted([("b", 1), ("a", 1)]))
        for invalid in (["e", 0], ["e", True], ["ee", 1], ["e", 1.5]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                list(decode_pairs([json.dumps(invalid)]))
        with self.assertRaisesRegex(ValueError, "Invalid JSON"):
            list(decode_pairs(["not json"]))


class ProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book = load_book(SOURCE)
        cls.result, cls.evidence = analyse(cls.book)

    def cli(self, *arguments, input_text=None):
        return subprocess.run([sys.executable, "-m", "wonderland", *map(str, arguments)],
                              cwd=ROOT, input=input_text, capture_output=True,
                              text=True, encoding="utf-8")

    def test_original_word_result_is_reproduced_without_relabeling_the_character_claim(self):
        self.assertEqual(self.result["legacy_reproduction"], {"Alice": 377, "Rabbit": 40})
        self.assertEqual(self.result["legacy_case_comparison"], {"rabbit": 2, "Rabbit": 40})
        for form, count in self.result["legacy_case_comparison"].items():
            self.assertEqual(count, self.result["historical_report"][form])
        self.assertEqual(self.result["target_totals"]["Alice"],
                         {"exact": 386, "folded": 386, "possessive": 396})
        self.assertEqual(self.result["target_totals"]["Rabbit"],
                         {"exact": 39, "folded": 42, "possessive": 46})
        self.assertNotEqual(self.result["characters"]["full_source"]["literal_lowercase_e"],
                            self.result["historical_report"]["lowercase_e"])

    def test_every_indexed_occurrence_reconstructs_a_real_token_and_matches_the_summary(self):
        self.assertEqual(sum(len(rows) for rows in self.evidence["index"].values()),
                         self.result["summary"]["words"])
        texts = {chapter.number: chapter.text.encode("utf-16-le") for chapter in self.book.chapters}
        for form, rows in self.evidence["index"].items():
            for chapter, start, end in rows:
                actual = texts[chapter][start * 2:end * 2].decode("utf-16-le")
                self.assertEqual(word_key(actual, ignore_case=False), form)
        for term in self.result["targets"]:
            self.assertEqual(len(concordance(self.book, term)),
                             self.result["target_totals"][term]["folded"])
        self.assertEqual(sum(chapter["words"] for chapter in self.result["chapters"]),
                         self.result["summary"]["words"])

    def test_source_and_published_provenance_are_consistent(self):
        provenance = json.loads((ROOT / "data" / "provenance.json").read_text())
        self.assertEqual(self.book.source_sha256, provenance["sha256"])
        self.assertEqual(len(SOURCE.read_bytes()), provenance["bytes"])
        self.assertIn("Section 1.", self.book.license_text)
        self.assertEqual(self.result["characters"]["narrative"]["hash_signs"], 0)
        self.assertEqual(self.result["characters"]["full_source"]["hash_signs"], 1)

    def test_script_data_cannot_close_its_html_container(self):
        hostile = {"example": "</script><img src=x onerror=alert(1)>&"}
        with tempfile.TemporaryDirectory() as folder:
            template = Path(folder) / "page.html"
            template.write_text('<script type="application/json">__WONDERLAND_DATA__</script>',
                                encoding="utf-8")
            page = render_story(hostile, {}, template)
            self.assertEqual(page.count("</script>"), 1)
            self.assertNotIn("<img", page)
            payload = page[page.index(">") + 1:page.rindex("</script>")]
            self.assertEqual(json.loads(payload)["analysis"], hostile)

    def test_build_is_reproducible_and_check_detects_a_stale_output(self):
        with tempfile.TemporaryDirectory() as folder:
            output, site = Path(folder) / "outputs", Path(folder) / "index.html"
            options = ["build", "--output", output, "--site", site]
            built = self.cli(*options)
            self.assertEqual(built.returncode, 0, built.stderr)
            original = site.read_bytes()
            checked = self.cli(*options, "--check")
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertEqual(site.read_bytes(), original)
            self.assertNotIn(b"\r\n", original)
            parser = EmbeddedData()
            parser.feed(site.read_text(encoding="utf-8"))
            embedded = json.loads("".join(parser.parts))
            self.assertEqual(embedded["analysis"]["legacy_case_comparison"],
                             self.result["legacy_case_comparison"])
            self.assertEqual(embedded["evidence"]["license"], self.book.license_text)
            self.assertEqual(base64.b64decode(embedded["evidence"]["original_base64"]),
                             SOURCE.read_bytes())
            (output / "term_counts.csv").write_text("stale\n")
            bad = self.cli(*options, "--check")
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("stale", bad.stderr)

    def test_cli_query_and_errors_do_not_return_success_shaped_empty_results(self):
        result = self.cli("query", "Rabbit", "--chapter", "8", "--limit", "2")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["count"], 6)
        self.assertEqual(len(data["matches"]), 2)
        for args in (("query", "two words"), ("query", "Alice", "--source", "absent.txt"),
                     ("mapreduce", "--chunk-size", "0")):
            bad = self.cli(*args)
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("error:", bad.stderr)

    def test_streaming_mapper_shuffle_reducer_agrees_with_direct_counting(self):
        text = "Rabbit eE ß\n"
        mapped = self.cli("mapper", input_text=text)
        self.assertEqual(mapped.returncode, 0, mapped.stderr)
        shuffled = self.cli("shuffle", input_text=mapped.stdout)
        self.assertEqual(shuffled.returncode, 0, shuffled.stderr)
        reduced = self.cli("reducer", input_text=shuffled.stdout)
        self.assertEqual(reduced.returncode, 0, reduced.stderr)
        self.assertEqual(dict(decode_pairs(reduced.stdout.splitlines())),
                         Counter(c for c in text.casefold() if c.isalpha()))


if __name__ == "__main__":
    unittest.main()
