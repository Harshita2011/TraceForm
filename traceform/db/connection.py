"""Translate hosted PostgreSQL URLs for SQLAlchemy's asyncpg driver."""
import ssl

from sqlalchemy.engine import make_url


def connection_settings(raw_url):
    url = make_url(raw_url)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+asyncpg")
    if url.drivername.startswith("sqlite"):
        return url, {"check_same_thread": False, "timeout": 30}
    args = {}
    if url.drivername == "postgresql+asyncpg":
        # Neon supplies libpq options. asyncpg uses `ssl`, and does not implement
        # libpq channel_binding. Use authenticated TLS with hostname verification.
        neon = (url.host or "").endswith(".neon.tech")
        mode = url.query.get("sslmode", url.query.get("ssl"))
        if neon or mode in {"require", "verify-ca", "verify-full"}:
            if neon and mode in {"disable", "allow", "prefer"}:
                raise ValueError("Neon requires authenticated TLS.")
            args["ssl"] = ssl.create_default_context()
            url = url.difference_update_query(["sslmode", "ssl", "channel_binding"])
        elif "sslmode" in url.query or "channel_binding" in url.query:
            raise ValueError("Use sslmode=require or verify-full for hosted PostgreSQL.")
    return url, args
