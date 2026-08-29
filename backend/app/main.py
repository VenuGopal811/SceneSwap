import os
from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

app = FastAPI(title="Scene Swap App")


@app.get("/health")
def health():
    return {"status": "ok", "env": os.getenv("APP_ENV", "unknown")}


# Segmentation, scene generation, and compositing routes get added here
# as separate stages, per DESIGN.md — kept independent so the backend
# for any one stage can change without touching the others.
