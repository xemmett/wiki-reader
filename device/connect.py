#!/usr/bin/env python3
"""Piwi Connect — the web portal. Started/stopped from the device Settings screen.

Runs a small FastAPI app on port 8000 so you can add articles from a phone or
laptop on the same wifi. Reuses the device's own library + Wikipedia importer, so
anything added here shows up on the device next time you open the Library.

Run standalone for testing:  python connect.py
"""
import os

from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

import config
import library
import wiki_import

app = FastAPI(title="Piwi Connect")
WEB = os.path.join(config.BASE, "web")


@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(WEB, "index.html"), encoding="utf-8") as f:
        return f.read()


@app.get("/api/library")
def api_library():
    db = library.connect()
    return [dict(r) for r in library.all_articles(db)]


@app.post("/api/import")
def api_import(article: str = Form(...), category: str = Form("wikipedia"),
               lang: str = Form("en")):
    try:
        title, extract = wiki_import.fetch(wiki_import.title_from_arg(article), lang)
    except SystemExit as e:
        raise HTTPException(404, str(e))
    wiki_import.save(category, title, wiki_import.to_markdown(title, extract))
    wiki_import.save_image(category, title, lang)
    library.import_dir(library.connect())
    return {"ok": True, "title": title}


@app.post("/api/upload")
async def api_upload(file: UploadFile, category: str = Form("uploads")):
    if not file.filename.endswith(".md"):
        raise HTTPException(400, "only .md files")
    body = (await file.read()).decode("utf-8", "replace")
    title = wiki_import.title_from_arg(file.filename[:-3])
    wiki_import.save(category, title, body)
    library.import_dir(library.connect())
    return {"ok": True, "title": title}


@app.delete("/api/article/{article_id}")
def api_delete(article_id: int):
    library.delete(library.connect(), article_id)
    return JSONResponse({"ok": True})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
