"""Consulta real ao SearXNG do Compose. Não roda no CI (`not live_search`)."""
import json
import subprocess

import pytest

pytestmark = pytest.mark.live_search


def test_searxng_json_returns_results():
    try:
        out = subprocess.check_output(
            ["docker", "compose", "exec", "-T", "searxng", "wget", "-q", "-O", "-",
             "http://127.0.0.1:8080/search?q=TSE%20eleicoes%202026&format=json&language=pt-BR"],
            cwd="/home/joao/Documentos/eleicao2026", timeout=40,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        pytest.skip(f"SearXNG indisponível: {exc}")
    data = json.loads(out)
    assert data.get("results"), data.get("unresponsive_engines")
    first = data["results"][0]
    assert first.get("url", "").startswith("http")
    assert first.get("title")
