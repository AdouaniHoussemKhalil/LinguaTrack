from fastapi import FastAPI
from app.routers import health, text_router, user_router
from app.core.database import engine, Base


app = FastAPI(title="LinguaTrack API")

Base.metadata.create_all(bind=engine)

app.include_router(health.router)

@app.get("/")
def root():
    return {"message": "LinguaTrack API running"}


app.include_router(user_router.router)
app.include_router(text_router.router)