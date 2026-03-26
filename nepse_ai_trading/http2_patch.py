"""
Monkey-patch for nepse library to disable HTTP/2 in Docker.

HTTP/2 causes connection hangs in containerized environments with NEPSE API.
This patch forces HTTP/1.1 which works reliably.
"""
import sys
import httpx

# Save original httpx.Client
_original_httpx_client = httpx.Client

# Create patched version that forces http2=False
def patched_httpx_client(*args, **kwargs):
    """Force HTTP/1.1 by setting http2=False."""
    if 'http2' in kwargs and kwargs['http2']:
        print("[PATCH] Disabling HTTP/2 for NEPSE API (Docker compatibility)")
        kwargs['http2'] = False
    return _original_httpx_client(*args, **kwargs)

# Apply monkey patch
httpx.Client = patched_httpx_client

print("[PATCH] HTTP/2 disabled for httpx - Docker compatibility enabled")
