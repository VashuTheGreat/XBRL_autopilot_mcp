import sys
from pathlib import Path

# Ensure root directory is on the python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api import app as fastapi_app


class VercelPathFixMiddleware:
    """Restores the original client path on Vercel when rewrites forward to /api/index.py."""

    def __init__(self, asgi_app):
        self.asgi_app = asgi_app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            headers = dict(scope.get("headers", []))
            
            # Check headers Vercel commonly sends for the original client request path
            orig_path = None
            for h in (b"x-matched-path", b"x-forwarded-uri", b"x-invoke-path"):
                if h in headers:
                    val = headers[h].decode("utf-8", errors="replace")
                    # If x-matched-path is not just the destination script itself
                    if val and not val.endswith("/api/index.py") and not val.endswith("/api/index"):
                        orig_path = val
                        break

            curr_path = scope.get("path", "")

            if orig_path:
                scope["path"] = orig_path
            elif curr_path.startswith("/api/index.py/"):
                scope["path"] = curr_path[len("/api/index.py"):]
            elif curr_path.startswith("/api/index/"):
                scope["path"] = curr_path[len("/api/index"):]
            elif curr_path in ("/api/index.py", "/api/index"):
                scope["path"] = "/"

        await self.asgi_app(scope, receive, send)


# Wrap FastAPI app for Vercel ASGI execution
app = VercelPathFixMiddleware(fastapi_app)
