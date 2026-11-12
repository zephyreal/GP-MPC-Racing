"""Alternative Uvicorn entry point; reuses existing course authentication without modifying app.py."""
import hashlib
from fastapi.responses import HTMLResponse,FileResponse
import app as course
from .server import register,ROOT
app=course.app
register(app,vars(course))
# Add one public, non-sensitive navigation script after the platform's existing scripts.
for route in app.routes:
    if getattr(route,'path',None)=='/' and getattr(route,'methods',set())=={'GET'}:
        original=route.dependant.call
        def home():
            response=original()
            content=response.body.decode('utf-8') if isinstance(response,HTMLResponse) else course.Path(response.path).read_text()
            version=hashlib.sha256((ROOT/'static/entry.js').read_bytes()).hexdigest()[:16]
            content=content.replace('</body>',f'<script src="/courses/design/vehicle/entry.js?v={version}"></script></body>')
            return HTMLResponse(content,headers={'Cache-Control':'no-cache'})
        route.dependant.call=home
        break
