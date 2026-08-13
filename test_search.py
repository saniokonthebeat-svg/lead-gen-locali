import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
if not API_KEY:
    sys.exit("Errore: GOOGLE_PLACES_API_KEY non trovata nel file .env")

URL = "https://places.googleapis.com/v1/places:searchText"

CATEGORIES = [
    "ristoranti a Altamura",
    "hotel a Altamura",
    "bar a Altamura",
    "parrucchieri a Altamura",
    "studi dentistici a Altamura",
    "panifici a Altamura",
    "farmacie a Altamura",
    "palestre a Altamura",
    "agriturismo a Altamura",
    "autofficine a Altamura",
]

FIELD_MASK = (
    "places.displayName,"
    "places.formattedAddress,"
    "places.internationalPhoneNumber,"
    "places.websiteUri"
)


def search_category(category: str) -> None:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    payload = {"textQuery": category}

    response = requests.post(URL, json=payload, headers=headers)
    response.raise_for_status()

    data = response.json()
    places = data.get("places", [])

    print(f"\n=== {category} ({len(places)} risultati) ===")

    for place in places:
        name = place.get("displayName", {}).get("text", "N/D")
        address = place.get("formattedAddress", "N/D")
        phone = place.get("internationalPhoneNumber", "N/D")
        website = place.get("websiteUri")
        website_status = "SÌ" if website else "NO"

        print(f"- {name}")
        print(f"  Indirizzo: {address}")
        print(f"  Telefono: {phone}")
        print(f"  Website: {website or 'non presente'} (websiteUri presente: {website_status})")


if __name__ == "__main__":
    for category in CATEGORIES:
        try:
            search_category(category)
        except requests.RequestException as error:
            print(f"\nErrore per '{category}': {error}")