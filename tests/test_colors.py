from atlas_api.scope import color_for_party, party_hex


def test_party_colors_pt_red_pl_yellow():
    assert party_hex("PT", "13") == "#E30613"
    assert party_hex("PL", "22") == "#F5C400"
    assert color_for_party("PT") == "#E30613"
    assert color_for_party("PL") == "#F5C400"
    assert party_hex(None, "22") == "#F5C400"
    assert party_hex("MISSÃO") == "#C2410C"
    assert party_hex("PARTIDO INEXISTENTE XYZ") is None
