import os
import json
import asyncio
import subprocess
import base64
import tempfile
import uuid
import time
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Form
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response
import aiosqlite
import httpx
import psutil

app = FastAPI(title="LocalMind Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
DB_PATH = Path("localmind.db")
UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(exist_ok=True)

http_client = None

async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db

async def init_db():
    db = await get_db()
    await db.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT,
            created_at INTEGER,
            updated_at INTEGER,
            model TEXT,
            message_count INTEGER DEFAULT 0,
            pinned INTEGER DEFAULT 0,
            branch_of TEXT
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT,
            role TEXT,
            content TEXT,
            images TEXT,
            created_at INTEGER,
            tokens INTEGER,
            ms_elapsed INTEGER,
            reasoning TEXT,
            rating INTEGER,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS prompt_library (
            id TEXT PRIMARY KEY,
            title TEXT,
            prompt TEXT,
            variables TEXT,
            created_at INTEGER
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_base (
            id TEXT PRIMARY KEY,
            filename TEXT,
            chunk_index INTEGER,
            content TEXT,
            embedding BLOB,
            created_at INTEGER
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS cloud_providers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            provider_type TEXT NOT NULL,
            api_key TEXT,
            base_url TEXT,
            models TEXT,
            enabled INTEGER DEFAULT 1,
            created_at INTEGER
        )
    """)
    await db.commit()
    await db.close()

CLOUD_PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        "supports_vision": True,
        "supports_streaming": True
    },
    "anthropic": {
        "name": "Anthropic (Claude)",
        "base_url": "https://api.anthropic.com/v1",
        "default_models": ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-opus-20240229", "claude-3-haiku-20240307"],
        "supports_vision": True,
        "supports_streaming": True
    },
    "google": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "default_models": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
        "supports_vision": True,
        "supports_streaming": True
    },
    "azure": {
        "name": "Azure OpenAI",
        "base_url": "",
        "default_models": ["gpt-4", "gpt-35-turbo"],
        "supports_vision": True,
        "supports_streaming": True
    },
    "deepseek": {
        "name": "DeepSeek API",
        "base_url": "https://api.deepseek.com/v1",
        "default_models": ["deepseek-chat", "deepseek-coder"],
        "supports_vision": False,
        "supports_streaming": True
    },
    "cohere": {
        "name": "Cohere",
        "base_url": "https://api.cohere.ai/v2",
        "default_models": ["command-r-plus", "command-r", "command"],
        "supports_vision": False,
        "supports_streaming": True
    },
    "xai": {
        "name": "xAI (Grok)",
        "base_url": "https://api.x.ai/v1",
        "default_models": ["grok-2", "grok-2-vision-1212"],
        "supports_vision": True,
        "supports_streaming": True
    },
    "mistral": {
        "name": "Mistral AI",
        "base_url": "https://api.mistral.ai/v1",
        "default_models": ["mistral-large-latest", "mistral-small-latest", "codestral-latest"],
        "supports_vision": False,
        "supports_streaming": True
    },
    "perplexity": {
        "name": "Perplexity",
        "base_url": "https://api.perplexity.ai",
        "default_models": ["llama-3.1-sonar-small-128k-online", "llama-3.1-sonar-large-128k-online"],
        "supports_vision": False,
        "supports_streaming": True
    },
    "openrouter": {
        "name": "OpenRouter (Aggregated)",
        "base_url": "https://openrouter.ai/api/v1",
        "default_models": ["openai/gpt-4o", "anthropic/claude-3.5-sonnet", "google/gemini-pro-1.5"],
        "supports_vision": True,
        "supports_streaming": True
    }
}

async def get_ollama_client():
    global http_client
    if http_client is None:
        http_client = httpx.AsyncClient(base_url=OLLAMA_HOST, timeout=None)
    return http_client

@app.on_event("startup")
async def startup():
    await init_db()

@app.on_event("shutdown")
async def shutdown():
    global http_client
    if http_client:
        await http_client.aclose()

@app.get("/")
async def serve_webui():
    return HTMLResponse(Path("webui.html").read_text())

@app.get("/api/health")
async def health_check():
    client = await get_ollama_client()
    ollama_ok = False
    models = []
    try:
        resp = await client.get("/api/tags")
        if resp.status_code == 200:
            ollama_ok = True
            models = resp.json().get("models", [])
    except:
        pass

    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return {
        "ollama": ollama_ok,
        "models": models,
        "ram_free": mem.available,
        "disk_free": disk.free
    }

@app.get("/api/models")
async def list_models():
    client = await get_ollama_client()
    try:
        resp = await client.get("/api/tags")
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="Failed to get models")
        data = resp.json()
        enriched = []
        for m in data.get("models", []):
            model_info = {
                "name": m.get("name", ""),
                "size": m.get("size", 0),
                "modified_at": m.get("modified_at", ""),
                "badges": []
            }
            name = model_info["name"].lower()
            if "reason" in name or "deepseek" in name or "r1" in name:
                model_info["badges"].append("REASON")
            if "vision" in name or "llama3.2" in name:
                model_info["badges"].append("VISION")
            if "mistral" in name:
                model_info["badges"].append("FAST")
            if "qwen" in name or "code" in name:
                model_info["badges"].append("CODE")
            enriched.append(model_info)
        return enriched
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/pull-model")
async def pull_model(name: str = Form(...)):
    async def generate():
        proc = await asyncio.create_subprocess_exec(
            "ollama", "pull", name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        async for line in proc.stdout:
            yield f"data: {json.dumps({'status': line.decode()})}\n\n"
        await proc.wait()
    return StreamingResponse(generate(), media_type="text/event-stream")

@app.delete("/api/models/{name}")
async def delete_model(name: str):
    client = await get_ollama_client()
    resp = await client.delete("/api/delete", json={"name": name})
    return {"success": resp.status_code == 200}

@app.get("/api/conversations")
async def list_conversations():
    db = await get_db()
    rows = await db.execute("""
        SELECT * FROM conversations ORDER BY updated_at DESC
    """)
    results = []
    async for row in rows:
        results.append(dict(row))
    await db.close()
    return results

@app.post("/api/conversations")
async def create_conversation(data: dict):
    db = await get_db()
    conv_id = data.get("id", str(uuid.uuid4()))
    now = int(time.time())
    await db.execute("""
        INSERT OR REPLACE INTO conversations (id, title, created_at, updated_at, model, message_count, pinned, branch_of)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        conv_id,
        data.get("title", "New Chat"),
        data.get("created_at", now),
        now,
        data.get("model", ""),
        data.get("message_count", 0),
        data.get("pinned", 0),
        data.get("branch_of")
    ))
    await db.commit()
    await db.close()
    return {"id": conv_id}

@app.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    db = await get_db()
    await db.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
    await db.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    await db.commit()
    await db.close()
    return {"success": True}

@app.get("/api/conversations/{conv_id}/messages")
async def get_conversation_messages(conv_id: str):
    db = await get_db()
    rows = await db.execute("""
        SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC
    """, (conv_id,))
    results = []
    async for row in rows:
        results.append(dict(row))
    await db.close()
    return results

@app.post("/api/conversations/{conv_id}/messages")
async def add_message(conv_id: str, data: dict):
    db = await get_db()
    msg_id = str(uuid.uuid4())
    now = int(time.time())
    await db.execute("""
        INSERT INTO messages (id, conversation_id, role, content, images, created_at, tokens, ms_elapsed, reasoning, rating)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        msg_id,
        conv_id,
        data.get("role", "user"),
        data.get("content", ""),
        data.get("images", ""),
        now,
        data.get("tokens", 0),
        data.get("ms_elapsed", 0),
        data.get("reasoning", ""),
        data.get("rating")
    ))
    await db.execute("""
        UPDATE conversations SET updated_at = ?, message_count = message_count + 1 WHERE id = ?
    """, (now, conv_id))
    await db.commit()
    await db.close()
    return {"id": msg_id}

@app.get("/api/export/{conv_id}")
async def export_conversation(conv_id: str, format: str = Query("md")):
    db = await get_db()
    conv = await db.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,))
    conv = await conv.fetchone()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    rows = await db.execute("""
        SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC
    """, (conv_id,))
    messages = []
    async for row in rows:
        messages.append(dict(row))
    await db.close()

    if format == "json":
        return {
            "conversation": dict(conv),
            "messages": messages
        }

    md = f"# {conv['title']}\n\n"
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if msg.get("reasoning"):
            content = f"**Reasoning:**\n{msg['reasoning']}\n\n**Response:**\n{content}"
        md += f"**{role.upper()}**: {content}\n\n"
    
    return Response(md, media_type="text/markdown")

@app.post("/api/upload-image")
async def upload_image(file: UploadFile = File(...)):
    contents = await file.read()
    if len(contents) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 20MB)")
    
    b64 = base64.b64encode(contents).decode()
    return {
        "base64": b64,
        "mime": file.content_type,
        "size": len(contents)
    }

@app.post("/api/ocr")
async def ocr_image(data: dict):
    client = await get_ollama_client()
    b64 = data.get("base64", "")
    resp = await client.post("/api/chat", json={
        "model": "llama3.2-vision:11b",
        "messages": [{
            "role": "user",
            "content": "Extract ALL text visible in this image exactly as it appears.",
            "images": [b64]
        }],
        "stream": False
    })
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="OCR failed")
    result = resp.json()
    return {"text": result.get("message", {}).get("content", "")}

@app.get("/api/system-stats")
async def system_stats():
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    
    gpu_used = None
    gpu_total = None
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            used, total = result.stdout.strip().split(",")
            gpu_used = int(used)
            gpu_total = int(total)
    except:
        pass

    ollama_pid = None
    loaded_model = None
    try:
        client = await get_ollama_client()
        resp = await client.get("/api/ps")
        if resp.status_code == 200:
            data = resp.json()
            loaded_model = data.get("model")
            ollama_pid = data.get("pid")
    except:
        pass

    return {
        "cpu": cpu,
        "ram_used": mem.used,
        "ram_total": mem.total,
        "gpu_vram_used": gpu_used,
        "gpu_vram_total": gpu_total,
        "ollama_pid": ollama_pid,
        "loaded_model": loaded_model
    }

@app.post("/api/embeddings")
async def get_embeddings(text: str = Form(...)):
    client = await get_ollama_client()
    try:
        resp = await client.post("/api/embeddings", json={
            "model": "nomic-embed-text",
            "prompt": text
        })
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="Embedding failed")
        data = resp.json()
        return {"embedding": data.get("embedding", [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/knowledge-base")
async def add_to_knowledge_base(file: UploadFile = File(...)):
    contents = await file.read()
    text = contents.decode("utf-8", errors="ignore")
    
    chunks = []
    chunk_size = 500
    overlap = 50
    for i in range(0, len(text), chunk_size - overlap):
        chunk = text[i:i+chunk_size]
        if chunk.strip():
            chunks.append(chunk)

    db = await get_db()
    kb_id = str(uuid.uuid4())
    now = int(time.time())
    
    for idx, chunk in enumerate(chunks):
        await db.execute("""
            INSERT INTO knowledge_base (id, filename, chunk_index, content, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (kb_id, file.filename, idx, chunk, now))
    
    await db.commit()
    await db.close()
    return {"id": kb_id, "chunks": len(chunks)}

@app.get("/api/knowledge-base")
async def list_knowledge_base():
    db = await get_db()
    rows = await db.execute("""
        SELECT DISTINCT filename, MIN(created_at) as created_at FROM knowledge_base GROUP BY filename
    """)
    results = []
    async for row in rows:
        results.append({"filename": row[0], "created_at": row[1]})
    await db.close()
    return results

@app.post("/api/knowledge-search")
async def search_knowledge_base(query: str = Form(...), top_k: int = Form(3)):
    client = await get_ollama_client()
    try:
        resp = await client.post("/api/embeddings", json={
            "model": "nomic-embed-text",
            "prompt": query
        })
        if resp.status_code != 200:
            return {"chunks": []}
        query_embedding = resp.json().get("embedding", [])
    except:
        return {"chunks": []}
    
    db = await get_db()
    rows = await db.execute("SELECT content FROM knowledge_base LIMIT 50")
    chunks = []
    async for row in rows:
        chunks.append({"content": row[0], "score": 0.5})
    await db.close()
    return {"chunks": chunks[:top_k]}

@app.get("/api/prompt-library")
async def list_prompts():
    db = await get_db()
    rows = await db.execute("SELECT * FROM prompt_library ORDER BY created_at DESC")
    results = []
    async for row in rows:
        results.append(dict(row))
    await db.close()
    return results

@app.post("/api/prompt-library")
async def create_prompt(data: dict):
    db = await get_db()
    prompt_id = str(uuid.uuid4())
    now = int(time.time())
    await db.execute("""
        INSERT INTO prompt_library (id, title, prompt, variables, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (prompt_id, data.get("title", ""), data.get("prompt", ""), 
          json.dumps(data.get("variables", [])), now))
    await db.commit()
    await db.close()
    return {"id": prompt_id}

@app.delete("/api/prompt-library/{prompt_id}")
async def delete_prompt(prompt_id: str):
    db = await get_db()
    await db.execute("DELETE FROM prompt_library WHERE id = ?", (prompt_id,))
    await db.commit()
    await db.close()
    return {"success": True}

@app.post("/api/run-code")
async def run_code(code: str = Form(...), language: str = Form("python")):
    if language != "python":
        raise HTTPException(status_code=400, detail="Only Python is supported")
    
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()
            result = subprocess.run(
                ["python3", f.name],
                capture_output=True,
                text=True,
                timeout=10
            )
            os.unlink(f.name)
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "error": None if result.returncode == 0 else "Execution failed"
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "", "error": "Timeout (10s)"}
    except Exception as e:
        return {"stdout": "", "stderr": "", "error": str(e)}

@app.get("/api/settings/{key}")
async def get_setting(key: str):
    db = await get_db()
    row = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = await row.fetchone()
    await db.close()
    return {"value": row[0] if row else None}

@app.post("/api/settings/{key}")
async def set_setting(key: str, value: str):
    db = await get_db()
    await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    await db.commit()
    await db.close()
    return {"success": True}

@app.get("/api/cloud-providers")
async def list_cloud_providers():
    db = await get_db()
    rows = await db.execute("SELECT * FROM cloud_providers ORDER BY name")
    results = []
    async for row in rows:
        r = dict(row)
        if r.get("api_key"):
            r["api_key"] = r["api_key"][:8] + "..." if len(r["api_key"]) > 8 else "***"
        results.append(r)
    await db.close()
    return results

@app.get("/api/cloud-providers/available")
async def get_available_providers():
    return CLOUD_PROVIDERS

@app.post("/api/cloud-providers")
async def add_cloud_provider(data: dict):
    db = await get_db()
    provider_id = str(uuid.uuid4())
    now = int(time.time())
    provider_type = data.get("provider_type", "")
    
    provider_info = CLOUD_PROVIDERS.get(provider_type, {})
    base_url = data.get("base_url", provider_info.get("base_url", ""))
    models = data.get("models", provider_info.get("default_models", []))
    
    await db.execute("""
        INSERT INTO cloud_providers (id, name, provider_type, api_key, base_url, models, enabled, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        provider_id,
        data.get("name", provider_info.get("name", provider_type)),
        provider_type,
        data.get("api_key", ""),
        base_url,
        json.dumps(models),
        1,
        now
    ))
    await db.commit()
    await db.close()
    return {"id": provider_id, "success": True}

@app.put("/api/cloud-providers/{provider_id}")
async def update_cloud_provider(provider_id: str, data: dict):
    db = await get_db()
    updates = []
    values = []
    if "name" in data:
        updates.append("name = ?")
        values.append(data["name"])
    if "api_key" in data:
        updates.append("api_key = ?")
        values.append(data["api_key"])
    if "base_url" in data:
        updates.append("base_url = ?")
        values.append(data["base_url"])
    if "models" in data:
        updates.append("models = ?")
        values.append(json.dumps(data["models"]))
    if "enabled" in data:
        updates.append("enabled = ?")
        values.append(1 if data["enabled"] else 0)
    
    if updates:
        values.append(provider_id)
        await db.execute(f"UPDATE cloud_providers SET {', '.join(updates)} WHERE id = ?", values)
        await db.commit()
    await db.close()
    return {"success": True}

@app.delete("/api/cloud-providers/{provider_id}")
async def delete_cloud_provider(provider_id: str):
    db = await get_db()
    await db.execute("DELETE FROM cloud_providers WHERE id = ?", (provider_id,))
    await db.commit()
    await db.close()
    return {"success": True}

@app.get("/api/cloud-models")
async def list_all_cloud_models():
    db = await get_db()
    rows = await db.execute("SELECT * FROM cloud_providers WHERE enabled = 1")
    all_models = []
    async for row in rows:
        r = dict(row)
        provider_info = CLOUD_PROVIDERS.get(r["provider_type"], {})
        models = json.loads(r.get("models", "[]"))
        for model in models:
            all_models.append({
                "id": f"{r['provider_type']}:{model}",
                "name": model,
                "provider": r["name"],
                "provider_type": r["provider_type"],
                "supports_vision": provider_info.get("supports_vision", False),
                "enabled": r["enabled"]
            })
    await db.close()
    return all_models

@app.post("/api/chat/cloud")
async def chat_with_cloud(data: dict):
    model_id = data.get("model", "")
    messages = data.get("messages", [])
    stream = data.get("stream", False)
    temperature = data.get("temperature", 0.7)
    max_tokens = data.get("max_tokens", 4096)
    
    if ":" not in model_id:
        raise HTTPException(status_code=400, detail="Invalid cloud model format")
    
    provider_type, model_name = model_id.split(":", 1)
    
    db = await get_db()
    row = await db.execute("SELECT * FROM cloud_providers WHERE provider_type = ? AND enabled = 1", (provider_type,))
    provider = await row.fetchone()
    await db.close()
    
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found or disabled")
    
    if not provider["api_key"]:
        raise HTTPException(status_code=400, detail="API key not configured")
    
    provider_info = CLOUD_PROVIDERS.get(provider_type, {})
    base_url = provider["base_url"] or provider_info.get("base_url", "")
    
    headers = {}
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    if provider_type == "openai":
        headers["Authorization"] = f"Bearer {provider['api_key']}"
        headers["Content-Type"] = "application/json"
        if stream:
            payload["stream"] = True
    
    elif provider_type == "anthropic":
        headers["x-api-key"] = provider["api_key"]
        headers["anthropic-version"] = "2023-06-01"
        headers["Content-Type"] = "application/json"
        payload["system"] = messages[0]["content"] if messages and messages[0]["role"] == "system" else ""
        anthropic_messages = [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] != "system"]
        payload["messages"] = anthropic_messages
    
    elif provider_type == "google":
        headers["Content-Type"] = "application/json"
        url = f"{base_url}/models/{model_name}:generateContent"
        payload["contents"] = [{"role": "user", "parts": [{"text": m["content"]} for m in messages]}]
        payload["generationConfig"] = {"temperature": temperature, "maxOutputTokens": max_tokens}
    
    elif provider_type == "deepseek":
        headers["Authorization"] = f"Bearer {provider['api_key']}"
        headers["Content-Type"] = "application/json"
    
    elif provider_type == "cohere":
        headers["Authorization"] = f"Bearer {provider['api_key']}"
        headers["Content-Type"] = "application/json"
        payload["model"] = model_name
    
    elif provider_type == "xai":
        headers["Authorization"] = f"Bearer {provider['api_key']}"
        headers["Content-Type"] = "application/json"
    
    elif provider_type == "mistral":
        headers["Authorization"] = f"Bearer {provider['api_key']}"
        headers["Content-Type"] = "application/json"
    
    elif provider_type == "perplexity":
        headers["Authorization"] = f"Bearer {provider['api_key']}"
        headers["Content-Type"] = "application/json"
    
    elif provider_type == "openrouter":
        headers["Authorization"] = f"Bearer {provider['api_key']}"
        headers["Content-Type"] = "application/json"
        headers["HTTP-Referer"] = "http://localhost:8080"
        headers["X-Title"] = "LocalMind"
    
    elif provider_type == "azure":
        headers["api-key"] = provider["api_key"]
        headers["Content-Type"] = "application/json"
        url = f"{base_url}/openai/deployments/{model_name}/chat/completions?api-version=2024-02-01"
        if stream:
            url += "&api-version=2024-02-15-preview"
    
    async def generate():
        async with httpx.AsyncClient(timeout=None) as client:
            if provider_type == "google":
                resp = await client.post(url, headers=headers, json=payload, params={"key": provider["api_key"].split("=")[-1] if "=" in provider["api_key"] else provider["api_key"]})
            elif provider_type == "azure":
                resp = await client.post(url, headers=headers, json=payload)
            else:
                resp = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            
            if stream:
                async for line in resp.aiter_lines():
                    if line.strip():
                        if provider_type == "anthropic":
                            if line.startswith("data: "):
                                yield line + "\n\n"
                        else:
                            if line.startswith("data: "):
                                yield line + "\n\n"
                yield "data: [DONE]\n\n"
            else:
                result = resp.json()
                yield f"data: {json.dumps(result)}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)