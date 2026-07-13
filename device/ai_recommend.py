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


def _parse_titles(text):
    """Pull a JSON array of titles out of the model's reply, tolerating stray prose."""
    s, e = text.find("["), text.rfind("]")
    if s != -1 and e != -1 and e > s:
        try:
            return [str(x) for x in json.loads(text[s:e + 1])]
        except Exception:
            pass
    # fallback: one title per line, strip bullets/numbering
    out = []
    for ln in text.splitlines():
        ln = ln.strip().lstrip("-*0123456789. ").strip().strip('"')
        if ln:
            out.append(ln)
    return out


def suggest(category, have_titles, n=10):
    """Return up to n new Wikipedia titles for `category`, excluding have_titles."""
    provider, model_override, key = _settings()
    if provider not in PROVIDERS:
        raise RuntimeError(f"Unknown provider: {provider}")
    if not key:
        raise RuntimeError("No AI key. Set it in Piwi Connect.")
    model = model_override or PROVIDERS[provider]["model"]
    topic = "any interesting subject" if category.lower() == "all" else f"the topic '{category}'"
    sample = have_titles[:10]
    prompt = (
        f"I keep a small offline Wikipedia reader. My library on {topic} already has: "
        f"{', '.join(sample) if sample else '(nothing yet)'}. "
        f"Suggest {n} more real English Wikipedia article titles about {topic} that are "
        f"NOT already listed. Reply with ONLY a JSON array of exact article-title strings, "
        f'e.g. ["Titanic", "Apollo 11"]. No other text.')
    titles = _parse_titles(_call(provider, key, model, prompt))
    have = {t.strip().lower() for t in have_titles}
    out, seen = [], set()
    for t in titles:
        k = t.strip().lower()
        if t.strip() and k not in have and k not in seen:
            seen.add(k)
            out.append(t.strip())
    return out[:n]


# ---- self-check ------------------------------------------------------------
def _selftest():
    assert _parse_titles('junk ["A","B","A"] tail') == ["A", "B", "A"]
    assert _parse_titles("- One\n2. Two\n\"Three\"") == ["One", "Two", "Three"]
    print("ai_recommend selftest OK")


if __name__ == "__main__":
    _selftest()
