from fastapi import FastAPI

app = FastAPI(title="Eioku", version="0.1.0")


@app.get("/")
async def root():
    """Hello world endpoint."""
    return {"message": "Hello World"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
