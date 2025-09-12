# fungsi komunikasi ke LLM

import httpx
from app import config

async def call_llm(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {"prompt": prompt, "max_tokens": 256}
        headers = {"Content-Type": "application/json"}
        if config.LLM_API_KEY:
            headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"
        resp = await client.post(config.LLM_API_URL, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        if "text" in data:
            return data["text"]
        if "output" in data:
            return data["output"]
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0].get("text") or data["choices"][0].get("message", {}).get("content")
        return str(data)
