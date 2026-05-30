from typing import List
from config import CHUNK_SIZE, CHUNK_OVERLAP


def _split_on_separators(text: str, separators: List[str]) -> List[str]:
    """
    Recursively splits text on a priority-ordered list of separators.
    Tries the first separator; if the resulting pieces are still larger than
    CHUNK_SIZE it recurses with the remaining separators.  Falls back to
    hard character slicing when no separator works.
    """
    if not text.strip():
        return []

    sep = separators[0]
    next_seps = separators[1:]

    parts = text.split(sep)
    result: List[str] = []

    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(part) <= CHUNK_SIZE or not next_seps:
            result.append(part)
        else:
            result.extend(_split_on_separators(part, next_seps))

    return result


def chunk_text(text: str) -> List[str]:
    """
    Turns a long string into a list of overlapping chunks of at most CHUNK_SIZE
    characters.  The split hierarchy (paragraph → sentence → word → character)
    keeps semantic boundaries intact rather than cutting mid-sentence.
    Overlap of CHUNK_OVERLAP characters is prepended to each chunk so that
    context spanning a boundary is not lost at retrieval time.
    """
    separators = ["\n\n", "\n", ". ", " ", ""]
    pieces = _split_on_separators(text, separators)

    chunks: List[str] = []
    current = ""

    for piece in pieces:
        # If adding this piece would exceed the limit, flush current and start fresh
        if current and len(current) + len(piece) + 1 > CHUNK_SIZE:
            chunks.append(current.strip())
            # Carry the tail of the previous chunk as overlap
            current = current[-CHUNK_OVERLAP:] + " " + piece
        else:
            current = (current + " " + piece).strip() if current else piece

    if current.strip():
        chunks.append(current.strip())

    return chunks


def chunk_pages(pages: List[dict]) -> List[dict]:
    """
    Chunks a list of page dicts ({"page": int, "text": str}) produced by the
    PDF parser.  Returns a flat list of {"page": int, "text": str, "chunk_index": int}
    so the page number is preserved on every chunk for metadata tagging.
    """
    result = []
    global_index = 0

    for page_dict in pages:
        page_num = page_dict["page"]
        page_chunks = chunk_text(page_dict["text"])

        for chunk in page_chunks:
            result.append({
                "page": page_num,
                "text": chunk,
                "chunk_index": global_index,
            })
            global_index += 1

    return result


def chunk_segments(segments: List[dict]) -> List[dict]:
    """
    Chunks Teams transcript segments ({"speaker": str, "timestamp": str, "text": str})
    into manageable pieces.  Speaker turns shorter than CHUNK_SIZE are kept whole;
    longer monologues are split and each sub-chunk retains the original speaker
    and timestamp so attribution is never lost.
    """
    result = []
    global_index = 0

    for seg in segments:
        speaker = seg.get("speaker", "Unknown")
        timestamp = seg.get("timestamp", "")
        sub_chunks = chunk_text(seg["text"])

        for chunk in sub_chunks:
            result.append({
                "speaker": speaker,
                "timestamp": timestamp,
                "text": chunk,
                "chunk_index": global_index,
            })
            global_index += 1

    return result
