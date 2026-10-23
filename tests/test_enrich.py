from scripts.enrich_tel import pick_tel


def test_common_tel_first():
    assert pick_tel({"tel": "02-111-2222"}, {"infocenterfood": "02-733-9240"}) == "02-111-2222"


def test_intro_fallback_strips_html():
    assert pick_tel({"tel": ""}, {"infocenterfood": "02-733-9240<br>"}) == "02-733-9240"


def test_intro_other_fields():
    assert pick_tel({}, {"infocenterculture": " <b>02-1</b> "}) == "02-1"


def test_nothing():
    assert pick_tel({"tel": ""}, {}) == ""
    assert pick_tel({}, None) == ""
