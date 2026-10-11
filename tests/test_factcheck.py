from atlas_api.search.factcheck import allowed_publishers, match


def test_general_news_domain_is_not_a_fact_checker():
    assert match("https://g1.globo.com/politica/eleicoes/2026/noticia/x.html") is None


def test_fato_ou_fake_is_identified_check():
    pub, is_check = match("https://g1.globo.com/fato-ou-fake/noticia/2026/x.ghtml")
    assert pub.name == "Fato ou Fake (g1)"
    assert is_check is True


def test_aos_fatos_identified():
    pub, is_check = match("https://www.aosfatos.org/noticias/exemplo/")
    assert pub.name == "Aos Fatos"
    assert is_check is True


def test_unknown_domain_rejected():
    assert match("https://blog-aleatorio.example/checagem") is None


def test_allowed_publishers_are_explicit():
    domains = {p["domain"] for p in allowed_publishers()}
    assert "aosfatos.org" in domains
    assert "google.com" not in domains
