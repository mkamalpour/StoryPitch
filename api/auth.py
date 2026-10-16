"""Optional shared API-key protection for the local application."""

from hmac import compare_digest
from fastapi import Header, HTTPException
from config import API_KEY


def api_key_required(x_api_key: str | None = Header(None)):
    if API_KEY and not compare_digest((x_api_key or "").encode(), API_KEY.encode()):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True
