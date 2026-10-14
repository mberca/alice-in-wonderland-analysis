"""A local map/combine/shuffle/reduce exercise, not a distributed engine."""

from collections import Counter, defaultdict
from itertools import groupby
import json


def map_characters(text, *, letters_only=True, ignore_case=True):
    if ignore_case:
        text = text.casefold()
    for character in text:
        if not letters_only or character.isalpha():
            yield character, 1


def reduce_sorted(pairs):
    previous = None
    for key, group in groupby(pairs, key=lambda pair: pair[0]):
        if previous is not None and key <= previous:
            raise ValueError("Reducer input is not sorted by character.")
        total = 0
        for character, count in group:
            if not isinstance(character, str) or len(character) != 1:
                raise ValueError("Each key must be one Unicode character.")
            if isinstance(count, bool) or not isinstance(count, int) or count < 1:
                raise ValueError("Counts must be positive integers.")
            total += count
        yield key, total
        previous = key


def mapreduce_counts(text, *, chunk_size=4096, letters_only=True, ignore_case=True):
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int) or chunk_size < 1:
        raise ValueError("Chunk size must be a positive integer.")
    shuffled = defaultdict(list)
    for start in range(0, len(text), chunk_size):
        combined = Counter()
        for key, value in map_characters(text[start:start + chunk_size],
                                         letters_only=letters_only, ignore_case=ignore_case):
            combined[key] += value
        for key, count in combined.items():
            shuffled[key].append(count)
    pairs = ((key, count) for key in sorted(shuffled) for count in shuffled[key])
    return dict(reduce_sorted(pairs))


def encode_pair(pair):
    return json.dumps(list(pair), ensure_ascii=True)


def decode_pairs(lines):
    for number, line in enumerate(lines, 1):
        try:
            pair = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON on pair line {number}: {error.msg}") from error
        if (not isinstance(pair, list) or len(pair) != 2 or not isinstance(pair[0], str)
                or len(pair[0]) != 1 or isinstance(pair[1], bool)
                or not isinstance(pair[1], int) or pair[1] < 1):
            raise ValueError(f"Invalid character/count pair on line {number}.")
        yield tuple(pair)
