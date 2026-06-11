# api/auth.py
from fastapi import Header, HTTPException
from config import API_KEY

def api_key_required(x_api_key: str | None = Header(None)):
    # If API_KEY unset, no enforcement (local dev)
    if not API_KEY:
        return True
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True
