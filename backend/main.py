from fastapi import FastAPI

app = FastAPI(
    title="AI Control Center API",
    version="0.1.0"
)

@app.get("/health")
def health_check():
    return {
        "status": "online",
        "service": "AI Control Center",
        "version": "0.1.0"
    }
