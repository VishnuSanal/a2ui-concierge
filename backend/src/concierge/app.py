from fastapi import FastAPI

app = FastAPI(title="A2UI Gift Concierge")

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
