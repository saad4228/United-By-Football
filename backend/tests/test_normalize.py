import pytest

from app.match.normalize import name_similarity, normalize_name


@pytest.mark.parametrize(
    "variant",
    ["Manchester City", "Man City", "Manchester City FC", "Man. City", "MANCHESTER CITY F.C."],
)
def test_manchester_city_variants_normalize_identically(variant):
    assert normalize_name(variant) == "manchester city"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("FC Bayern München", "bayern munchen"),
        ("Club Atlético de Madrid", "atletico madrid"),
        ("Bayer 04 Leverkusen", "bayer leverkusen"),
        ("Brighton & Hove Albion", "brighton and hove albion"),
        ("Nott'm Forest", "nottingham forest"),
        ("Man Utd", "manchester united"),
        ("AC Milan", "milan"),
    ],
)
def test_normalization_strips_noise(raw, expected):
    assert normalize_name(raw) == expected


def test_city_and_united_are_not_confused():
    city = {normalize_name("Manchester City"), "mci"}
    assert name_similarity(normalize_name("Man Utd"), city) < 0.8
    assert name_similarity(normalize_name("Man City"), city) == 1.0


def test_partial_names_score_high():
    forms = {normalize_name("Borussia Dortmund")}
    assert name_similarity(normalize_name("Dortmund"), forms) >= 0.86
