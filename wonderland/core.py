"""Explicit corpus boundaries and deterministic, inspectable text measures."""

from collections import Counter
from base64 import b64encode
from dataclasses import dataclass
from hashlib import sha256
from math import log
from pathlib import Path
import re
import unicodedata

ROMANS = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII")
TOKEN_RE = re.compile(r"[^\W\d_]+(?:['\u2019-][^\W\d_]+)*", re.UNICODE)
CHAPTER_RE = re.compile(r"^CHAPTER ([IVX]+)\.\s+(.+?)\s*$", re.MULTILINE)
START_RE = re.compile(r"^\*\*\* START OF (?:THIS|THE) PROJECT GUTENBERG.*\*\*\*\s*$", re.MULTILINE)
END_RE = re.compile(r"^\*\*\* END OF (?:THIS|THE) PROJECT GUTENBERG.*\*\*\*\s*$", re.MULTILINE)
TARGETS = ("Alice", "Rabbit", "Queen", "King", "Hatter", "Dormouse",
           "Duchess", "Gryphon", "Caterpillar", "Turtle")
LEGACY_REMOVED = '"!.,;:&?'
STOPWORDS = frozenset("""
a about above after again against all am an and any are aren't as at be because
been before being below between both but by can can't cannot could couldn't did
didn't do does doesn't doing don't down during each few for from further had
hadn't has hasn't have haven't having he he'd he'll he's her here here's hers
herself him himself his how how's i i'd i'll i'm i've if in into is isn't it
it's its itself just me more most mustn't my myself no nor not now of off on
once only or other ought our ours ourselves out over own same shall shan't she
she'd she'll she's should shouldn't so some such than that that's the their
theirs them themselves then there there's these they they'd they'll they're
they've this those through to too under until up us very was wasn't we we'd
we'll we're we've were weren't what what's when when's where where's which
while who who's whom why why's will with won't would wouldn't you you'd you'll
you're you've your yours yourself yourselves
""".split())


@dataclass(frozen=True)
class Token:
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class Chapter:
    number: int
    roman: str
    title: str
    text: str


@dataclass(frozen=True)
class Book:
    chapters: tuple[Chapter, ...]
    source_text: str
    source_sha256: str
    source_bytes: int
    license_text: str
    source_header: str
    original_base64: str

    @property
    def narrative(self):
        return "\n\n".join(chapter.text for chapter in self.chapters)


def tokenize(text):
    """Keep internal apostrophes and hyphens; exclude numbers and punctuation."""
    return [Token(match.group(), match.start(), match.end()) for match in TOKEN_RE.finditer(text)]


def word_key(word, *, ignore_case=True, possessives=False):
    key = unicodedata.normalize("NFC", word).replace("\u2019", "'")
    if ignore_case:
        key = key.casefold()
    if possessives and key.lower().endswith("'s"):
        key = key[:-2]
    return key


def validate_term(term):
    term = unicodedata.normalize("NFC", term.strip())
    if not TOKEN_RE.fullmatch(term):
        raise ValueError("Enter one word; internal apostrophes and hyphens are allowed.")
    return term


def parse_book(raw):
    """Fail on uncertain boundaries rather than silently analyse legal boilerplate."""
    text = unicodedata.normalize("NFC", raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n"))
    starts, ends = list(START_RE.finditer(text)), list(END_RE.finditer(text))
    if len(starts) != 1 or len(ends) != 1 or starts[0].end() >= ends[0].start():
        raise ValueError("Expected one ordered pair of Project Gutenberg START/END markers.")
    marker = "*** START: FULL LICENSE ***"
    if marker not in text[ends[0].end():]:
        raise ValueError("The source must retain its complete Project Gutenberg licence.")
    body = text[starts[0].end():ends[0].start()]
    body = re.split(r"(?m)^End of Project Gutenberg", body, maxsplit=1)[0]
    body = re.sub(r"\s+THE END\s*\Z", "", body)
    headings = list(CHAPTER_RE.finditer(body))
    if tuple(match.group(1) for match in headings) != ROMANS:
        raise ValueError("Expected the twelve unique, ordered chapter headings I-XII.")
    chapters = []
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(body)
        content = body[heading.end():end].strip()
        if not tokenize(content):
            raise ValueError(f"Chapter {heading.group(1)} contains no word tokens.")
        chapters.append(Chapter(index + 1, heading.group(1), heading.group(2), content))
    return Book(tuple(chapters), text, sha256(raw).hexdigest(), len(raw),
                text[text.index(marker):].strip(), text[:starts[0].start()].strip(),
                b64encode(raw).decode("ascii"))


def load_book(path):
    return parse_book(Path(path).read_bytes())


def count_word(tokens, term, *, ignore_case=True, possessives=False):
    target = word_key(validate_term(term), ignore_case=ignore_case, possessives=possessives)
    return sum(word_key(token.text, ignore_case=ignore_case, possessives=possessives) == target
               for token in tokens)


def legacy_counts(text, targets=("Alice", "Rabbit")):
    """Replicate the supplied Python 2 exercise, without its obsolete has_key calls."""
    cleaned = text.translate(str.maketrans("", "", LEGACY_REMOVED))
    counts = Counter(cleaned.split())
    return {target: counts[target] for target in targets}


def moving_average_ttr(words, window=100):
    if isinstance(window, bool) or not isinstance(window, int) or window < 1:
        raise ValueError("MATTR window must be a positive integer.")
    if len(words) < window:
        return None
    current = Counter(words[:window])
    total_unique = len(current)
    for index in range(window, len(words)):
        outgoing = words[index - window]
        current[outgoing] -= 1
        if current[outgoing] == 0:
            del current[outgoing]
        current[words[index]] += 1
        total_unique += len(current)
    return total_unique / ((len(words) - window + 1) * window)


def ranked_words(counts, *, content_only=True, limit=20):
    eligible = ((word, count) for word, count in counts.items()
                if not content_only or (word not in STOPWORDS and len(word) >= 3))
    return [{"word": word, "count": count}
            for word, count in sorted(eligible, key=lambda item: (-item[1], item[0]))[:limit]]


def chapter_signatures(chapter_counts, chapter_lengths, limit=5):
    """Chapter TF-IDF: full-token denominator, smoothed IDF, count >= 3."""
    documents = len(chapter_counts)
    document_frequency = Counter(word for counts in chapter_counts for word in counts)
    results = []
    for counts, length in zip(chapter_counts, chapter_lengths):
        candidates = []
        for word, count in counts.items():
            if count < 3 or word in STOPWORDS or len(word) < 3:
                continue
            score = count / length * (log((1 + documents) / (1 + document_frequency[word])) + 1)
            candidates.append({"word": word, "count": count, "tf_idf": round(score, 8)})
        results.append(sorted(candidates, key=lambda item: (-item["tf_idf"], item["word"]))[:limit])
    return results


def concordance(book, term, *, chapter=None, ignore_case=True, possessives=False, context=65):
    validate_term(term)
    if chapter is not None and chapter not in range(1, 13):
        raise ValueError("Chapter must be between 1 and 12.")
    if context < 0:
        raise ValueError("Context must be nonnegative.")
    target = word_key(term, ignore_case=ignore_case, possessives=possessives)
    matches = []
    for section in book.chapters:
        if chapter is not None and section.number != chapter:
            continue
        for token in tokenize(section.text):
            if word_key(token.text, ignore_case=ignore_case, possessives=possessives) != target:
                continue
            matches.append({
                "chapter": section.number, "title": section.title,
                "before": section.text[max(0, token.start - context):token.start],
                "match": section.text[token.start:token.end],
                "after": section.text[token.end:token.end + context],
                "start": token.start, "end": token.end,
            })
    return matches
