from atlas_api.photos import PhotoNotFound, cached_photo_path, fetch_official_photo, photo_zip_url


def test_zip_url_is_official_tse_cdn():
    url = photo_zip_url(2022, "BR")
    assert url.startswith("https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2022/fotos/")
    assert url.endswith("foto_cand2022_BR_div.zip")


def test_rejects_invented_year_or_ue():
    try:
        photo_zip_url(2026, "BR")
        assert False
    except PhotoNotFound:
        pass
    try:
        fetch_official_photo(2022, "../BR", "1")
        assert False
    except PhotoNotFound:
        pass
    assert cached_photo_path(2022, "BR", "0") is None
