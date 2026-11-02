"""Provider credentials are encrypted at rest and are never serialized into API responses."""
import os
import tempfile
from pathlib import Path
from cryptography.fernet import Fernet


def _cipher():
    key = os.getenv("TRACEFORM_MASTER_KEY")
    if not key:
        if os.getenv("APP_ENV", "development") == "production":
            raise RuntimeError("TRACEFORM_MASTER_KEY is required in production")
        folder = Path(os.getenv("OBJECT_STORAGE_PATH", "./storage_data")).resolve()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / ".provider-master-key"
        if not path.exists():
            fd, temporary = tempfile.mkstemp(dir=folder, prefix=".provider-key-")
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(Fernet.generate_key())
                    stream.flush()
                    os.fsync(stream.fileno())
                try:
                    # Publish a fully written file, never an empty partial key.
                    os.link(temporary, path)
                except FileExistsError:
                    pass
            finally:
                Path(temporary).unlink(missing_ok=True)
        key = path.read_bytes()
        # This local development file must be backed up separately from the database.
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_key(value):
    return _cipher().encrypt(value.encode()).decode() if value else None


def decrypt_key(value):
    return _cipher().decrypt(value.encode()).decode() if value else None
