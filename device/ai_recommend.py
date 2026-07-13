"""Ask a cheap LLM for related Wikipedia article titles.

Provider-neutral (Anthropic / OpenAI / Grok) because the user picks the provider;
raw HTTP via urllib keeps the device dependency-free. The Anthropic path uses the
documented Messages API shape (x-api-key, anthropic-version, content[0].text).
Set PIWI_AI_PROVIDER + PIWI_AI_KEY (see config).
"""
import json
import urllib.request

import config

PROVIDERS = {
    "anthropic": {"url": "https://api.anthropic.com/v1/messages", "model": "claude-haiku-4-5"},
    "openai":    {"url": "https://api.openai.com/v1/chat/completions", "model": "gpt-4o-mini"},
    "grok":      {"url": "https://api.x.ai/v1/chat/completions", "model": "grok-3-mini"},
}


def _settings():
    """(provider, model_override, key) — ai.json (set via Piwi Connect) beats env."""
    provider, model, key = config.AI_PROVIDER, config.AI_MODEL, config.AI_KEY
    try:
        with open(config.AI_CONFIG_PATH, encoding="utf-8") as f:
            d = json.load(f)
        provider = d.get("provider") or provider
        model = d.get("model") or model
        key = d.get("key") or key
    except Exception:
        pass
    return provider, model, key


def save_settings(provider=None, model=None, key=None):
    """Persist AI settings. An empty/None key leaves the stored key untouched."""
    d = {}
    try:
        with open(config.AI_CONFIG_PATH, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        pass
    if provider is not None:
        d["provider"] = provider
    if model is not None:
        d["model"] = model
    if key:
        d["key"] = key
    with open(config.AI_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f)


def settings_public():
    """Provider/model + whether a key is set — never returns the key itself."""
    p, m, k = _settings()
    return {"provider": p, "model": m or PROVIDERS.get(p, {}).get("model", ""),
            "has_key": bool(k)}


def _post(url, headers, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={**headers, "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _call(provider, key, model, prompt):
    if provider == "anthropic":
        data = _post(PROVIDERS["anthropic"]["url"],
                     {"x-api-key": key, "anthropic-version": "2023-06-01"},
                     {"model": model, "max_tokens": 1024,
                      "messages": [{"role": "user", "content": prompt}]})
        return data["content"][0]["text"]
    # openai + grok share the OpenAI chat/completions shape
    data = _post(PROVIDERS[provider]["url"],
                 {"authorization": f"Bearer {key}"},
                 {"model": model, "max_tokens": 1024,
                  "messages": [{"role": "user", "content": prompt}]})
    return data["choices"][0]["message"]["content"]


def _parse_items(text):
    """Pull (title, category) pairs from the reply. Accepts a JSON array of
    {title, category} objects, of bare title strings, or a bulleted list."""
    s, e = text.find("["), text.rfind("]")
    if s != -1 and e != -1 and e > s:
        try:
            out = []
            for x in json.loads(text[s:e + 1]):
                if isinstance(x, dict):
                    out.append((str(x.get("title", "")), x.get("category")))
                else:
                    out.append((str(x), None))
            return out
        except Exception:
            pass
    # fallback: one title per line, no category
    out = []
    for ln in text.splitlines():
        ln = ln.strip().lstrip("-*0123456789. ").strip().strip('"')
        if ln:
            out.append((ln, None))
    return out


def suggest(category, have_titles, existing_categories=None, n=10):
    """Return up to n (title, category) suggestions, excluding have_titles.
    category is the folder picked on the device ("All" lets the AI choose folders)."""
    provider, model_override, key = _settings()
    if provider not in PROVIDERS:
        raise RuntimeError(f"Unknown provider: {provider}")
    if not key:
        raise RuntimeError("No AI key. Set it in Piwi Connect.")
    model = model_override or PROVIDERS[provider]["model"]
    topic = "any interesting subject" if category.lower() == "all" else f"the topic '{category}'"
    folders = ", ".join(existing_categories or []) or "(none yet)"
    sample = have_titles[:10]
    prompt = (
        f"I keep a small offline Wikipedia reader organised into folders. "
        f"Existing folders: {folders}. My library on {topic} already has: "
        f"{', '.join(sample) if sample else '(nothing yet)'}. "
        f"Suggest {n} more real English Wikipedia article titles about {topic} that are "
        f"NOT already listed. For each, assign a folder — reuse an existing folder name "
        f"when it fits, otherwise a short sensible new one. Reply with ONLY a JSON array of "
        f'objects like [{{"title": "Titanic", "category": "History"}}]. No other text.')
    items = _parse_items(_call(provider, key, model, prompt))
    have = {t.strip().lower() for t in have_titles}
    out, seen = [], set()
    for title, cat in items:
        k = title.strip().lower()
        if title.strip() and k not in have and k not in seen:
            seen.add(k)
            out.append((title.strip(), (cat or "").strip() or None))
    return out[:n]


# ---- self-check ------------------------------------------------------------
def _selftest():
    assert _parse_items('x [{"title":"A","category":"H"},{"title":"B"}] y') == [
        ("A", "H"), ("B", None)]
    assert _parse_items('["A","B"]') == [("A", None), ("B", None)]
    assert _parse_items("- One\n2. Two") == [("One", None), ("Two", None)]
    print("ai_recommend selftest OK")


if __name__ == "__main__":
    _selftest()
