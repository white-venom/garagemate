"""
Pull the car make / model / year / km out of free text with plain regex.
Good enough for "my 2017 swift diesel has done 80k km", no AI needed.
"""

import re
from datetime import date

from core.text import normalize

# make key -> (display name, models)
MAKES = {
    "maruti": ("Maruti Suzuki", [
        "Swift", "Dzire", "Baleno", "Alto", "Alto K10", "Wagon R", "WagonR", "Ertiga", "Brezza", "Vitara Brezza", "Ciaz",
        "Celerio", "S-Presso", "Ignis", "XL6", "Grand Vitara", "Fronx", "Eeco", "Jimny", "Invicto", "Ritz", "Zen",
        "800", "Omni", "A-Star", "S-Cross",
    ]),
    "hyundai": ("Hyundai", [
        "i10", "Grand i10", "Grand i10 Nios", "i20", "Creta", "Venue", "Verna", "Aura", "Alcazar", "Tucson", "Exter",
        "Santro", "Xcent", "Eon", "Elantra", "Kona", "Ioniq 5",
    ]),
    "tata": ("Tata", [
        "Nexon", "Punch", "Tiago", "Tigor", "Harrier", "Safari", "Altroz", "Curvv", "Indica", "Indigo", "Nano", "Zest",
        "Bolt", "Hexa", "Sumo",
    ]),
    "mahindra": ("Mahindra", [
        "Thar", "Scorpio", "Scorpio N", "XUV700", "XUV500", "XUV300", "XUV 3XO", "XUV400", "Bolero", "Bolero Neo",
        "KUV100", "Marazzo", "TUV300",
    ]),
    "honda": ("Honda", ["City", "Amaze", "Jazz", "WR-V", "Elevate", "Civic", "Brio", "Mobilio", "CR-V", "Accord"]),
    "toyota": ("Toyota", [
        "Innova", "Innova Crysta", "Innova Hycross", "Fortuner", "Glanza", "Urban Cruiser", "Hyryder", "Corolla",
        "Corolla Altis", "Etios", "Etios Liva", "Camry", "Rumion", "Hilux", "Legender",
    ]),
    "kia": ("Kia", ["Seltos", "Sonet", "Carens", "Carnival", "Syros", "EV6"]),
    "renault": ("Renault", ["Kwid", "Triber", "Kiger", "Duster", "Lodgy", "Scala", "Pulse"]),
    "nissan": ("Nissan", ["Magnite", "Sunny", "Micra", "Kicks", "Terrano"]),
    "volkswagen": ("Volkswagen", ["Polo", "Vento", "Virtus", "Taigun", "Tiguan", "Ameo", "Jetta"]),
    "skoda": ("Skoda", ["Rapid", "Slavia", "Kushaq", "Octavia", "Superb", "Kylaq", "Kodiaq", "Laura", "Fabia"]),
    "mg": ("MG", ["Hector", "Hector Plus", "Astor", "ZS EV", "Comet", "Gloster", "Windsor"]),
    "ford": ("Ford", ["EcoSport", "Figo", "Aspire", "Endeavour", "Fiesta", "Freestyle", "Ikon"]),
    "jeep": ("Jeep", ["Compass", "Meridian", "Wrangler"]),
    "citroen": ("Citroen", ["C3", "C3 Aircross", "Basalt", "C5 Aircross"]),
    "chevrolet": ("Chevrolet", ["Beat", "Spark", "Cruze", "Sail", "Enjoy", "Tavera"]),
    "fiat": ("Fiat", ["Punto", "Linea"]),
    "byd": ("BYD", ["Atto 3", "Seal", "eMax 7"]),
    "bmw": ("BMW", ["3 Series", "5 Series", "X1", "X3", "X5"]),
    "mercedes": ("Mercedes-Benz", ["C-Class", "E-Class", "A-Class", "GLA", "GLC", "GLE"]),
    "audi": ("Audi", ["A4", "A6", "Q3", "Q5", "Q7"]),
    "volvo": ("Volvo", ["XC40", "XC60", "XC90", "S60"]),
}

MAKE_ALIASES = {
    "maruti suzuki": "maruti", "suzuki": "maruti", "vw": "volkswagen", "merc": "mercedes",
    "mercedes benz": "mercedes", "benz": "mercedes", "chevy": "chevrolet", "tata motors": "tata",
}

# model names that are also normal words ("spark plug", "oil seal", "city traffic").
# these only count when the make is mentioned too.
AMBIGUOUS_MODELS = {
    "city", "beat", "spark", "seal", "sail", "enjoy", "pulse", "punch", "bolt", "zest", "compass", "scala", "jazz",
    "rapid", "superb", "comet", "800", "windsor", "basalt", "carnival", "sunny", "kicks", "aura", "venue", "safari",
    "aspire", "freestyle", "elevate", "amaze", "exter",
}

FUEL_TYPES = {
    "petrol": "petrol", "diesel": "diesel", "cng": "cng", "lpg": "lpg", "electric": "electric", "ev": "electric",
    "hybrid": "hybrid",
}

# a 4 digit number that isn't followed by a unit ("2000 km" is not a year)
YEAR_RE = re.compile(r"\b(19[89]\d|20[0-4]\d)\b(?!\s*(?:k\b|km|kms|kilomet|miles?|rs|rupees))", re.IGNORECASE)
# 80,000 km / 80000km / 80k km / 1.2 lakh km / 50,000 miles
ODOMETER_RE = re.compile(
    r"(\d+(?:[.,]\d+)*)\s*(k|thousand|lakh|lakhs|lac|lacs)?\s*(km|kms|kilometers?|kilometres?|miles?)\b",
    re.IGNORECASE,
)


def _build_model_lookup():
    lookup = {}
    for make, (_, models) in MAKES.items():
        for model in models:
            lookup[normalize(model)] = (make, model)
    # longest first so "grand i10 nios" wins over "i10"
    return dict(sorted(lookup.items(), key=lambda item: len(item[0]), reverse=True))


MODEL_LOOKUP = _build_model_lookup()


def _contains(text, phrase):
    return re.search(rf"\b{re.escape(phrase)}\b", text) is not None


def _find_make(text):
    for alias, make in MAKE_ALIASES.items():
        if _contains(text, alias):
            return make
    for make in MAKES:
        if _contains(text, make):
            return make
    return None


def _find_model(text, make=None):
    for key, (model_make, display_name) in MODEL_LOOKUP.items():
        if make and model_make != make:
            continue
        if not make and key in AMBIGUOUS_MODELS:
            continue
        if _contains(text, key):
            return model_make, display_name
    return None, None


def _parse_odometer(raw_text):
    match = ODOMETER_RE.search(raw_text)
    if not match:
        return None
    number, multiplier, unit = match.groups()
    number = number.replace(",", "")
    try:
        value = float(number)
    except ValueError:
        return None

    multiplier = (multiplier or "").lower()
    if multiplier in ("k", "thousand"):
        value *= 1_000
    elif multiplier.startswith("la"):
        value *= 100_000
    if unit.lower().startswith("mile"):
        value *= 1.609

    value = int(value)
    return value if 0 < value < 2_000_000 else None


def extract_vehicle_details(raw_text):
    """Returns whatever we could find: make, model, year, odometer_km, fuel_type."""
    raw_text = raw_text or ""
    text = normalize(raw_text)
    details = {}

    make = _find_make(text)
    model_make, model = _find_model(text, make)
    make = make or model_make
    if make:
        details["make"] = MAKES[make][0]
    if model:
        details["model"] = model

    year_match = YEAR_RE.search(raw_text)
    if year_match and int(year_match.group(1)) <= date.today().year + 1:
        details["year"] = int(year_match.group(1))

    odometer = _parse_odometer(raw_text)
    if odometer:
        details["odometer_km"] = odometer

    for word, fuel in FUEL_TYPES.items():
        if _contains(text, word):
            details["fuel_type"] = fuel
            break

    return details


def mentions_vehicle(normalized_text):
    return _find_make(normalized_text) is not None or _find_model(normalized_text)[0] is not None
