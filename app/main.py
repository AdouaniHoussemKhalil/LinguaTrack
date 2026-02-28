from fastapi import FastAPI
from app.routers import health

app = FastAPI(title="LinguaTrack API")

app.include_router(health.router)

@app.get("/")
def root():
    return {"message": "LinguaTrack API running"}