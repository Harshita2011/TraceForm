"""
# §3.1 Object Storage — local disk abstraction.
# Storage backend is swapped to S3-compatible later by replacing this module.
"""

import os
import uuid
import re
from pathlib import Path

_STORAGE_PATH = Path(os.getenv("OBJECT_STORAGE_PATH", "./storage_data"))


def save_raw_file(content: bytes, filename: str) -> str:
    """
    Save raw uploaded file bytes to local disk.
    Preserves original filename with a collision-resistant hash.
    Returns a relative path (object key) for storage in Source.raw_content_ref.
    """
    _STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    p = Path(filename)
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', p.stem).strip(' .')[:180] or "upload"
    suffix = p.suffix or ".txt"
    key = f"{stem}_{uuid.uuid4().hex[:8]}{suffix}"
    dest = _STORAGE_PATH / key
    dest.write_bytes(content)
    return str(key)


def save_rendered_file(content: bytes, filename: str) -> str:
    """
    Save a rendered artifact (e.g. PPTX, PDF) to local disk.
    Returns a relative path (object key) for storage in Artifact.rendered_file_ref.
    The filename is preserved as-is (callers supply a meaningful name).
    """
    rendered_path = _STORAGE_PATH / "rendered"
    rendered_path.mkdir(parents=True, exist_ok=True)
    # Prefix with UUID to avoid collisions across generations
    key = f"rendered/{uuid.uuid4()}_{filename}"
    dest = _STORAGE_PATH / key
    dest.write_bytes(content)
    return str(key)


def get_raw_file_path(ref: str) -> Path:
    """Return the absolute path for a stored file reference."""
    return _STORAGE_PATH / ref
