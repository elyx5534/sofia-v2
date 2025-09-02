"""
Minimal test server to debug the issue
"""

from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Minimal server working", "time": datetime.now().isoformat()}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/test-html", response_class=HTMLResponse)
async def test_html():
    return (
        """
    <html>
    <head><title>Test</title></head>
    <body>
        <h1>Minimal HTML Test</h1>
        <p>If you see this, basic HTML rendering works!</p>
        <p>Time: """
        + datetime.now().strftime("%H:%M:%S")
        + """</p>
    </body>
    </html>
    """
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8080)
