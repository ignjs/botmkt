from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from services.stock_analyzer import get_stock_data
from services.perplexity import analyze_stock

app = FastAPI(title="StockBot API")

class StockRequest(BaseModel):
    symbol: str = "IAM.SN"

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/analyze")
async def analyze(req: StockRequest):
    try:
        ind = await get_stock_data(req.symbol)
        analisis = await analyze_stock(req.symbol, ind)
        return {"symbol": req.symbol, "data": ind, "analisis": analisis}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("endpoints:app", host="0.0.0.0", port=8000)
