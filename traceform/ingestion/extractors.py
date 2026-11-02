"""
# §3.1 Source Ingestion — file extraction utilities.

Supports: plain text, PDF (pdfplumber), DOCX (python-docx), images (pytesseract OCR), video (reference only).
Video transcription is explicitly OUT OF SCOPE for V1 (§3.1).
"""

import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# §3.1 V1 scope: video files are accepted as attachments and stored by reference only.
# Transcription and claim extraction from video is explicitly deferred per §3.1.
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".wmv"}

# §3.1 §7 — File type whitelist
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".jpg", ".jpeg", ".png", ".tiff", ".bmp", ".gif"} | VIDEO_EXTENSIONS

# §1.4 — ~15k word cap per context-window rationale. Reject or truncate-with-warning beyond this.
MAX_EXTRACTED_WORDS = 15_000
MAX_EXTRACTED_CHARS = MAX_EXTRACTED_WORDS * 6  # ~6 chars/word average


class ExtractionError(Exception):
    """Raised when extraction fails; message is actionable (names what failed and why)."""
    pass


class VideoReferenceOnly(Exception):
    """
    §3.1 V1 scope — raised for video files to signal they must be stored by reference only.
    The caller should store the file path and link it to the Source record without extracting text.
    """
    pass


def extract_text_from_file(
    file_content: bytes,
    filename: str,
    ocr_confidence_threshold: float = 0.6,
) -> tuple[str, str | None]:
    """
    Extract text from an uploaded file.

    Args:
        file_content: Raw file bytes.
        filename: Original filename (used to determine type by extension).
        ocr_confidence_threshold: Minimum average OCR confidence; raises ExtractionError if below.

    Returns:
        Tuple of (extracted_text, content_type) where content_type is the detected type.

    Raises:
        ExtractionError: With an actionable error message naming what failed and why.
        VideoReferenceOnly: For video files — caller must store by reference, not extract text.
    """
    suffix = Path(filename).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise ExtractionError(
            f"File type '{suffix}' is not supported. "
            f"Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
        )

    if suffix in VIDEO_EXTENSIONS:
        raise VideoReferenceOnly(
            f"Video file '{filename}' accepted. Per V1 scope (§3.1), video files are stored "
            "by reference only. No transcription or claim extraction is performed."
        )

    if suffix in {".txt", ".md"}:
        return _extract_plain_text(file_content), "text/plain"

    if suffix == ".pdf":
        return _extract_pdf(file_content), "application/pdf"

    if suffix == ".docx":
        return _extract_docx(file_content), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    if suffix in {".jpg", ".jpeg", ".png", ".tiff", ".bmp", ".gif"}:
        return _extract_image_ocr(file_content, filename, ocr_confidence_threshold), f"image/{suffix.lstrip('.')}"

    raise ExtractionError(f"Unhandled file type '{suffix}'.")


def _extract_plain_text(content: bytes) -> str:
    if b"\x00" in content or sum(b < 9 or 13 < b < 32 for b in content) > max(3, len(content) // 100):
        raise ExtractionError("This text file contains binary data. Choose a readable TXT or Markdown document.")
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            return content.decode("latin-1")
        except Exception as e:
            raise ExtractionError(f"Plain text extraction failed: could not decode as UTF-8 or Latin-1. Error: {e}")


def _extract_pdf(content: bytes) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            pages_text = []
            if getattr(pdf.doc, "is_extractable", True) is False:
                raise ExtractionError("PDF text extraction is restricted. Upload an unlocked, text-based PDF.")
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    pages_text.append(page_text)
            extracted = "\n\n".join(pages_text)

        if not extracted.strip():
            raise ExtractionError(
                "PDF extraction produced no text. The file may be image-only or encrypted. "
                "Try re-uploading as an image for OCR extraction."
            )
        return extracted
    except ImportError:
        raise ExtractionError("PDF extraction failed: pdfplumber is not installed.")
    except Exception as e:
        if isinstance(e, ExtractionError):
            raise
        raise ExtractionError(f"PDF extraction failed: {e}. Ensure the PDF is not encrypted or corrupted.")


def _extract_docx(content: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(content))
        from docx.text.paragraph import Paragraph
        from docx.table import Table
        paragraphs = []
        for block in doc.element.body:
            if block.tag.endswith("}p"):
                paragraphs.append(Paragraph(block, doc).text)
            elif block.tag.endswith("}tbl"):
                paragraphs.extend(" | ".join(cell.text for cell in row.cells) for row in Table(block, doc).rows)
        extracted = "\n\n".join(paragraphs)
        if not extracted.strip():
            raise ExtractionError(
                "DOCX extraction produced no text. The document may be empty or use unsupported formatting."
            )
        return extracted
    except ImportError:
        raise ExtractionError("DOCX extraction failed: python-docx is not installed.")
    except Exception as e:
        if isinstance(e, ExtractionError):
            raise
        raise ExtractionError(f"DOCX extraction failed: {e}.")


def _extract_image_ocr(content: bytes, filename: str, confidence_threshold: float) -> str:
    try:
        import pytesseract
        from PIL import Image
        image = Image.open(io.BytesIO(content))
        # Get OCR data with confidence scores
        ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        confidences = [
            float(c) for c in ocr_data["conf"] if str(c).replace(".", "", 1).isdigit() and float(c) >= 0
        ]
        if not confidences:
            raise ExtractionError("OCR confidence could not be measured. Upload a clearer scan or a text document.")
        if confidences:
            avg_confidence = sum(confidences) / len(confidences) / 100.0  # tesseract uses 0-100
            if avg_confidence < confidence_threshold:
                raise ExtractionError(
                    f"OCR confidence for '{filename}' is {avg_confidence:.0%}, below the "
                    f"{confidence_threshold:.0%} threshold. The image may be too low resolution, "
                    "blurry, or contain non-text content. Try a higher-quality scan."
                )

        extracted = pytesseract.image_to_string(image)
        if not extracted.strip():
            raise ExtractionError(
                f"OCR produced no text from '{filename}'. The image may not contain readable text."
            )
        return extracted
    except ImportError:
        raise ExtractionError("Image OCR failed: pytesseract or Pillow is not installed.")
    except Exception as e:
        if isinstance(e, ExtractionError):
            raise
        raise ExtractionError(f"Image OCR failed for '{filename}': {e}.")


def validate_extraction_length(text: str, operator_truncate: bool = False) -> tuple[str, bool]:
    """
    §1.4 / §7 — Enforce the ~15k word extracted text cap.

    Args:
        text: The extracted text.
        operator_truncate: If True, truncate with a warning appended; if False, reject.

    Returns:
        Tuple of (text, was_truncated).

    Raises:
        ExtractionError: If text exceeds the cap and operator_truncate is False.
    """
    if len(text) <= MAX_EXTRACTED_CHARS and len(text.split()) <= MAX_EXTRACTED_WORDS:
        return text, False

    word_count = len(text.split())
    if not operator_truncate:
        raise ExtractionError(
            f"Extracted text is {word_count:,} words (~{len(text):,} chars), exceeding the "
            f"{MAX_EXTRACTED_WORDS:,}-word limit (§1.4 context-window constraint). "
            "Set 'truncate_long_content=true' in the request to truncate with a warning."
        )

    words = list(__import__("re").finditer(r"\S+", text))
    word_end = words[MAX_EXTRACTED_WORDS - 1].end() if len(words) >= MAX_EXTRACTED_WORDS else len(text)
    truncated = text[:min(MAX_EXTRACTED_CHARS, word_end)]
    # Keep complete words when the character ceiling cuts through a word.
    if len(truncated) < len(text) and not text[len(truncated)].isspace() and not truncated[-1].isspace():
        boundary = __import__("re").search(r"\s+\S*$", truncated)
        if boundary:
            truncated = truncated[:boundary.start()]
    logger.warning(
        "Extracted text truncated to %d chars (original: %d chars, %d words)",
        len(truncated), len(text), word_count,
    )
    return truncated, True
