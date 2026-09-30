from pydantic import BaseModel

class QueryRequest(BaseModel):
    query: str

class SaveQueryRequest(BaseModel):
    name: str
    query: str
