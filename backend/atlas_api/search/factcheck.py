"""Lista explícita de publicações de checagem consideradas pela busca de checagens.

Um resultado só é tratado como de checador se o domínio estiver aqui. "checagem publicada
identificada" exige que a URL esteja no caminho editorial de checagem do veículo; a conclusão
(rating) NÃO é extraída: o sistema não lê as páginas e não classifica alegações.
Revise a lista periodicamente (ver docs/SEARCH.md).
"""
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Publisher:
    name: str
    domain: str
    check_paths: tuple[str, ...]  # prefixos de caminho que identificam páginas de checagem


PUBLISHERS: tuple[Publisher, ...] = (
    Publisher("Aos Fatos", "aosfatos.org", ("/noticias/",)),
    Publisher("Agência Lupa", "lupa.uol.com.br", ("/jornalismo/",)),
    Publisher("Agência Lupa", "lupa.news", ("/",)),
    Publisher("Fato ou Fake (g1)", "g1.globo.com", ("/fato-ou-fake/",)),
    Publisher("AFP Checamos", "checamos.afp.com", ("/doc.afp.com.",  "/")),
    Publisher("Projeto Comprova", "projetocomprova.com.br", ("/publica",)),
    Publisher("Estadão Verifica", "estadao.com.br", ("/estadao-verifica/",)),
    Publisher("UOL Confere", "noticias.uol.com.br", ("/confere/",)),
    Publisher("Justiça Eleitoral — Fato ou Boato", "justicaeleitoral.jus.br", ("/fato-ou-boato/",)),
    Publisher("TSE — Fato ou Boato", "tse.jus.br", ("/comunicacao/noticias/", "/fato-ou-boato")),
)


def match(url: str) -> tuple[Publisher, bool] | None:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().removeprefix("www.")
    path = parts.path or "/"
    for p in PUBLISHERS:
        if host == p.domain or host.endswith("." + p.domain):
            if p.domain in ("g1.globo.com", "estadao.com.br", "noticias.uol.com.br", "tse.jus.br") \
                    and not any(path.startswith(cp) for cp in p.check_paths):
                return None  # veículo generalista: só a editoria de checagem conta
            return p, any(path.startswith(cp) for cp in p.check_paths)
    return None


def allowed_publishers() -> list[dict]:
    return [{"name": p.name, "domain": p.domain, "check_paths": list(p.check_paths)} for p in PUBLISHERS]
