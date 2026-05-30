import json
import os
import re
from typing import List

from ingestion.models import ParsedDocument
from ingestion.parsers.base_parser import BaseParser


def _parse_vtt(content: str) -> List[dict]:
    """
    Parses a WebVTT (.vtt) file exported from Microsoft Teams and returns a
    list of speaker-turn dicts: {"speaker": str, "timestamp": str, "text": str}.
    Teams VTT files use two common formats:
      1. Speaker embedded in the cue text as "Name: message"
      2. Speaker in an HTML <v> tag: <v Speaker Name>message</v>
    Both are handled so the function works with any Teams export version.
    Cues with no text after stripping the speaker prefix are skipped.
    """
    segments = []

    # Each VTT cue block is separated by a blank line
    blocks = re.split(r"\n{2,}", content.strip())

    for block in blocks:
        lines = block.strip().splitlines()
        if not lines:
            continue

        # Skip the file header and numeric cue identifiers
        if lines[0].strip() == "WEBVTT":
            continue
        if re.match(r"^\d+$", lines[0].strip()):
            lines = lines[1:]
        if not lines:
            continue

        # First remaining line should be the timestamp range
        timestamp_match = re.match(
            r"^(\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3}",
            lines[0],
        )
        if not timestamp_match:
            continue

        timestamp = timestamp_match.group(1)
        cue_text = " ".join(lines[1:]).strip()

        if not cue_text:
            continue

        # Format 2: <v Speaker Name>message</v>
        v_tag_match = re.match(r"<v\s+([^>]+)>(.*?)</v>", cue_text, re.DOTALL)
        if v_tag_match:
            speaker = v_tag_match.group(1).strip()
            text = v_tag_match.group(2).strip()
        # Format 1: "Speaker Name: message"
        elif ": " in cue_text:
            speaker, _, text = cue_text.partition(": ")
        else:
            speaker = "Unknown"
            text = cue_text

        if text:
            segments.append({
                "speaker": speaker,
                "timestamp": timestamp,
                "text": text,
            })

    return segments


def _parse_teams_json(content: str) -> List[dict]:
    """
    Parses the JSON format returned by the Microsoft Graph API for Teams meeting
    transcripts (GET /communications/callRecords/{id}/sessions/{id}/segments).
    Each entry in the "value" array represents one utterance with speaker and
    transcript text.  The function normalises Graph API field names to the same
    {"speaker", "timestamp", "text"} shape used by _parse_vtt.
    """
    data = json.loads(content)
    segments = []

    # Support both a raw list and the Graph API {"value": [...]} envelope
    entries = data if isinstance(data, list) else data.get("value", [])

    for entry in entries:
        # Graph API nests the speaker under "participant" -> "user" -> "displayName"
        speaker = (
            entry.get("participant", {})
                 .get("user", {})
                 .get("displayName", "")
            or entry.get("speaker", "Unknown")
        )
        timestamp = entry.get("offsetInSeconds", entry.get("timestamp", ""))
        if isinstance(timestamp, (int, float)):
            # Convert seconds offset to HH:MM:SS
            h, rem = divmod(int(timestamp), 3600)
            m, s = divmod(rem, 60)
            timestamp = f"{h:02d}:{m:02d}:{s:02d}"

        text = entry.get("text", entry.get("transcript", "")).strip()

        if text:
            segments.append({
                "speaker": speaker,
                "timestamp": str(timestamp),
                "text": text,
            })

    return segments


class TeamsTranscriptParser(BaseParser):
    """
    Ingests Microsoft Teams meeting transcripts from either:
      - .vtt files (the default export from Teams / Stream)
      - .json files from the Microsoft Graph API transcript endpoint
    The full transcript text (all speakers concatenated) goes into
    ParsedDocument.content for full-document search, while ParsedDocument.segments
    carries the speaker-level breakdown so the chunker can attribute each chunk
    to the right person.
    Author is set to the meeting organiser passed by the caller; the date should
    be the meeting date in ISO-8601 format.
    """

    def parse(
        self,
        file_path: str,
        meeting_organiser: str = "",
        meeting_date: str = "",
        meeting_title: str = "",
        access_level: str = "internal",
        domain: str = "",
    ) -> ParsedDocument:
        """
        Reads the transcript file, auto-detects VTT vs JSON by extension, and
        delegates to the appropriate parse helper.  Reconstructs the full
        conversation text as "Speaker (HH:MM:SS): text" lines so keyword search
        and LLM context windows see a readable transcript, not raw JSON.
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Transcript file not found: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()

        with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()

        if ext == ".vtt":
            segments = _parse_vtt(content)
        elif ext == ".json":
            segments = _parse_teams_json(content)
        else:
            raise ValueError(
                f"Unsupported transcript format '{ext}'. Use .vtt or .json."
            )

        # Build a readable full-text representation for embedding
        lines = [
            f"{seg['speaker']} ({seg['timestamp']}): {seg['text']}"
            for seg in segments
        ]
        full_text = "\n".join(lines)

        return ParsedDocument(
            content=full_text,
            author=meeting_organiser,
            date=meeting_date,
            source_system="Teams",
            source_file=file_path,
            access_level=access_level,
            domain=domain,
            title=meeting_title or os.path.basename(file_path),
            segments=segments,
        )
