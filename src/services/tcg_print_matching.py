"""Match locally recognized card text against print-specific catalog metadata."""

from __future__ import annotations

import difflib
import re
from typing import NamedTuple, TypedDict

from src.db.tcg_repository import SqliteTcgRepository
from src.services.tcg_card_ocr import OcrLine

_COLLECTOR_PATTERN = re.compile(
    r"(?<!\w)([a-z]{0,5}\s*\d{1,4}[a-z]?)\s*[/／]\s*([a-z]{0,5}\s*\d{1,4})(?!\w)",
    re.IGNORECASE,
)
_ARTIST_PREFIX = re.compile(r"^(?:illus(?:t|trator|tration)?\.?|illustrated\s+by)\s*[:.]?\s*", re.IGNORECASE)
_LANGUAGE_SUFFIXES = ("en", "de", "fr", "es", "it", "pt", "ja")


class PrintMatch(TypedDict):
    strength: float
    attacks: list[str]
    collector_number: str | None
    artist: str | None
    set_code: str | None


class _CollectorRead(NamedTuple):
    number: str
    total: int
    text: str
    confidence: float


def _collector_reads(text: str, confidence: float) -> list[_CollectorRead]:
    reads = []
    for match in _COLLECTOR_PATTERN.finditer(text):
        number = _normalize_number(match.group(1))
        total_digits = re.search(r"\d+", match.group(2))
        if number and total_digits and int(total_digits.group()) > 0:
            reads.append(_CollectorRead(number, int(total_digits.group()), match.group(), confidence))
    return reads


def _normalize_text(value: str) -> str:
    return " ".join(re.findall(r"[^\W_]+", value.casefold()))


def _normalize_number(value: str) -> str:
    value = re.sub(r"\s+", "", value).casefold()
    match = re.fullmatch(r"([a-z]*)(\d+)([a-z]?)", value)
    if not match:
        return ""
    return f"{match.group(1)}{int(match.group(2))}{match.group(3)}"


def _attack_text(value: str) -> str:
    return re.sub(r"\s+\d{1,4}[+x×-]?\s*$", "", value.strip(), flags=re.IGNORECASE)


def _artist_text(value: str) -> str:
    prefix = _ARTIST_PREFIX.match(value)
    artist = value[prefix.end():].strip() if prefix else value.strip()
    if not prefix and (len(artist.split()) < 2 or any(character.isdigit() for character in artist)):
        return ""
    return artist if 2 <= len(artist) <= 80 else ""


def _similarity(left: str, right: str) -> float:
    left, right = _normalize_text(left), _normalize_text(right)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    if min(len(left), len(right)) < 5:
        return 0.0
    similarity = difflib.SequenceMatcher(None, left, right).ratio()
    return similarity if similarity >= 0.9 else 0.0


def match_print_text(
    repository: SqliteTcgRepository,
    candidate_ids: set[str],
    lines: list[OcrLine],
) -> dict[str, PrintMatch]:
    """Return bounded positive evidence without penalizing absent metadata."""
    attacks = [
        (_attack_text(line["text"]), line["confidence"])
        for line in lines if line["region"] == "body" and line["confidence"] >= 0.75
        and len(_attack_text(line["text"])) >= 3
    ]
    artists = []
    collectors: list[_CollectorRead] = []
    codes = []
    for line in lines:
        text, confidence = line["text"], line["confidence"]
        if line["region"] != "footer" and not _ARTIST_PREFIX.match(text):
            continue
        if confidence >= 0.85:
            artist = _artist_text(text)
            if artist:
                artists.append((artist, confidence))
        if line["region"] != "footer":
            continue
        if confidence >= 0.85:
            code = re.sub(r"[^a-z0-9]", "", text.casefold())
            if 2 <= len(code) <= 7 and any(character.isalpha() for character in code):
                codes.append((code, confidence))
        verified_text = line.get("verification_text")
        verified_confidence = line.get("verification_confidence")
        if confidence >= 0.9 and verified_text and verified_confidence is not None and verified_confidence >= 0.8:
            verified = {
                (item.number, item.total) for item in _collector_reads(verified_text, verified_confidence)
            }
            collectors.extend(
                item._replace(confidence=min(confidence, verified_confidence))
                for item in _collector_reads(text, confidence) if (item.number, item.total) in verified
            )

    if not attacks and not artists and not collectors and not codes:
        return {}
    possible_codes = {code for code, _ in codes}
    possible_codes.update(
        code[:-2] for code, _ in codes
        if len(code) > 3 and code[-2:] in _LANGUAGE_SUFFIXES
    )
    metadata = repository.get_print_metadata(
        candidate_ids=candidate_ids,
        attack_names=(text for text, _ in attacks),
        artists=(artist for artist, _ in artists),
        printed_totals=(collector.total for collector in collectors),
        set_codes=possible_codes,
    )
    matches: dict[str, PrintMatch] = {}
    for card_id, card in metadata.items():
        attack_candidates = []
        for name in set(card["attacks"]):
            for index, (text, confidence) in enumerate(attacks):
                strength = confidence * _similarity(name, text)
                if strength:
                    attack_candidates.append((strength, name, index))
        attack_matches = []
        used_names = set()
        used_lines = set()
        for strength, name, index in sorted(attack_candidates, reverse=True):
            if name not in used_names and index not in used_lines:
                attack_matches.append((strength, name))
                used_names.add(name)
                used_lines.add(index)
        attack_strength = min(
            1.0,
            (attack_matches[0][0] * 0.75 if attack_matches else 0.0)
            + (attack_matches[1][0] * 0.25 if len(attack_matches) > 1 else 0.0),
        )

        collector = max(
            (
                item for item in collectors
                if _normalize_number(card["number"]) == item.number
                and card["printed_total"] == item.total
            ),
            key=lambda item: item.confidence, default=None,
        )
        artist_matches = [
            (confidence * _similarity(card["artist"], text), text)
            for text, confidence in artists if card["artist"]
        ]
        artist_strength, artist = max(artist_matches, default=(0.0, ""))
        set_code = (card["set_code"] or "").casefold()
        code_strength = max(
            (
                confidence for code, confidence in codes
                if set_code and (code == set_code or any(code == set_code + suffix for suffix in _LANGUAGE_SUFFIXES))
            ),
            default=0.0,
        )
        strength = (
            0.30 * attack_strength
            + 0.50 * (collector.confidence if collector else 0.0)
            + 0.15 * artist_strength
            + 0.05 * code_strength
        )
        if strength:
            matches[card_id] = {
                "strength": strength,
                "attacks": [name for _, name in attack_matches],
                "collector_number": collector.text if collector else None,
                "artist": artist if artist_strength else None,
                "set_code": card["set_code"] if code_strength else None,
            }
    return matches
