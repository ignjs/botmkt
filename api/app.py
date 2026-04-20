from fastapi import FastAPI

from api.endpoints import router

app = FastAPI(title="BotMKT API", version="1.0.0")
app.include_router(router)
