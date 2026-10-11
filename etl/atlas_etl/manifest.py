from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Resource:
    key: str
    dataset: str
    kind: str
    url: str
    listed_in_catalog: bool
    license: str
    description: str
    ue: str | None = None

    @property
    def filename(self) -> str:
        if self.kind.startswith("ibge_"):
            return f"ibge/{self.key}.geojson"
        name = self.url.rsplit("/", 1)[-1]
        return f"secao/{name}" if self.kind == "secao" else name


def load_manifest(path: Path) -> list[Resource]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    default_license = doc["license"]
    out: list[Resource] = []
    for r in doc["resources"]:
        out.append(Resource(r["key"], r["dataset"], r["kind"], r["url"], bool(r["listed_in_catalog"]),
                            r.get("license", default_license), r.get("description", "")))
    for t in doc.get("templates", []):
        for ue in t["ues"]:
            out.append(Resource(t["key"].format(ue=ue), t["dataset"], t["kind"], t["url"].format(ue=ue),
                                bool(t["listed_in_catalog"]), t.get("license", default_license),
                                t.get("description", ""), ue=ue))
    for g in doc.get("geometry", []):
        out.append(Resource(g["key"], g["dataset"], g["kind"], g["url"], bool(g["listed_in_catalog"]),
                            g.get("license", default_license), g.get("description", "")))
    keys = [r.key for r in out]
    if len(keys) != len(set(keys)):
        raise ValueError("manifesto com chaves duplicadas")
    for r in out:
        if not r.url.startswith(("https://cdn.tse.jus.br/", "https://servicodados.ibge.gov.br/")):
            raise ValueError(f"URL fora dos domínios oficiais permitidos: {r.url}")
    return out


def by_key(resources: list[Resource]) -> dict[str, Resource]:
    return {r.key: r for r in resources}
