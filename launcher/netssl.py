"""TLS for the launcher's HTTPS calls: the Windows root store plus certifi's bundle (shipped in the exe).
Python only sees the roots Windows already holds, and Windows fetches a missing root only when a browser needs it:
on the net cafe machine (06/11) and on the dev machine every update check failed with CERTIFICATE_VERIFY_FAILED
(GitHub's chain ends in a root those stores did not have yet)."""
import ssl

_ctx = None


def context():
    global _ctx
    if _ctx is None:
        ctx = ssl.create_default_context()
        try:
            import certifi
            ctx.load_verify_locations(certifi.where())
        except Exception:  # noqa: BLE001
            pass
        _ctx = ctx
    return _ctx
