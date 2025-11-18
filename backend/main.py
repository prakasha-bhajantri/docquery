# backend/main.py
from fastapi import FastAPI
from .routers import router
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="DocQueryAPI")

app.include_router(router, prefix="")

origins = [
    "http://localhost:3000",  # Allow your frontend port
    "*"                       # Or use '*' for all origins in development
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {"message": "DocQuery API is running"}


def main():
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")

if __name__ == "__main__":
    main()