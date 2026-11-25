"""Query embedding through Ollama, with the same pinned model the indexer used."""

from __future__ import annotations

import httpx

# Must mirror indexer/pipeline/embed.py: nomic-embed-text uses task prefixes, and the
# query side takes 'search_query: ' where documents took 'search_document: '.
QUERY_PREFIX = {"nomic-embed-text": "search_query: "}


def query_prefix(model: str) -> str:
    return QUERY_PREFIX.get(model.split(":")[0], "")


class OllamaEmbedder:
    def __init__(self, base_url: str, model: str, timeout: float = 15.0) -> None:
        self.url = base_url.rstrip("/") + "/api/embed"
        self.model = model
        self.client = httpx.Client(timeout=httpx.Timeout(timeout, connect=5.0))
        self._version: str | None = None

    def model_version(self) -> str:
        """'nomic-embed-text@0a109f422b47': the model's digest from Ollama, read once.
        Two pulls of the same tag can be different weights; the digest says which."""
        if self._version is None:
            try:
                r = self.client.get(self.url.replace("/api/embed", "/api/tags"))
                r.raise_for_status()
                name = self.model if ":" in self.model else self.model + ":latest"
                digest = next((m.get("digest", "") for m in r.json().get("models", [])
                               if m.get("name") in (self.model, name)), "")
                self._version = f"{self.model}@{digest[:12] or 'unknown'}"
            except Exception:
                return f"{self.model}@unknown"      # try again on the next request
        return self._version

    def embed(self, text: str) -> list[float]:
        payload = {"model": self.model, "input": [query_prefix(self.model) + text],
                   "truncate": True}
        last: Exception | None = None
        for _ in range(2):                       # one retry on a transport blip
            try:
                r = self.client.post(self.url, json=payload)
                r.raise_for_status()
                return [float(x) for x in r.json()["embeddings"][0]]
            except httpx.TransportError as exc:
                last = exc
        raise RuntimeError(f"query embedding failed: {last!r}")
