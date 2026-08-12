from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from retriever import query_rag

app = FastAPI(title="Production HR RAG API")

class QueryRequest(BaseModel):
    query: str
    region: Optional[str] = None

class QueryResponse(BaseModel):
    answer: str

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/chat", response_model=QueryResponse)
def chat_endpoint(req: QueryRequest):
    try:
        ans = query_rag(req.query, region=req.region)
        return QueryResponse(answer=ans)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
