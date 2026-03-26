"""
Monkey-patch for nepse library to disable HTTP/2 in Docker.

HTTP/2 causes connection hangs in containerized environments with NEPSE API.
This patch forces HTTP/1.1 which works reliably.
"""
import httpx

# Save original httpx.Client
_OriginalHttpxClient = httpx.Client

# Create patched version that forces http2=False
class PatchedHttpxClient(_OriginalHttpxClient):
    """Patched httpx.Client that forces HTTP/1.1 by setting http2=False."""
    
    def __init__(self, *args, **kwargs):
        """Force HTTP/1.1 by setting http2=False."""
        if 'http2' in kwargs and kwargs['http2']:
            print("[PATCH] Disabling HTTP/2 for NEPSE API (Docker compatibility)")
        kwargs['http2'] = False  # Always disable HTTP/2
        super().__init__(*args, **kwargs)

# Apply monkey patch - replace with our subclass
httpx.Client = PatchedHttpxClient

print("[PATCH] HTTP/2 disabled for httpx - Docker compatibility enabled")
