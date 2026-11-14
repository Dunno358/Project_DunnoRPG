from django.core.exceptions import ValidationError


CITY_SHOPS = (
    "Kowal", "Łuczarz", "Rusznikarz", "Kramarz muzyczny", "Płatnerz",
    "Krawiec", "Jubiler", "Karczma", "Stoisko z eliksirami", "Myśliwy",
    "Kupiec", "Handlarz zwierząt",
)


def parse_city_discounts(value):
    discounts = {}
    shop_names = {name.casefold() for name in CITY_SHOPS} | {"all"}
    for entry in (value or "").split(";"):
        if not entry.strip():
            continue
        name, separator, percent = entry.strip().rpartition("-")
        name = name.strip().casefold()
        try:
            percent = int(percent)
        except ValueError:
            raise ValidationError("Podaj zniżki w formacie Kowal-10;Kupiec-15.")
        if not separator or name not in shop_names or not 0 <= percent <= 100:
            raise ValidationError(
                "Podaj nazwę sklepu lub all i zniżkę od 0 do 100, np. all-20;Kowal-10."
            )
        if name in discounts:
            raise ValidationError("Każdy sklep może wystąpić tylko raz.")
        discounts[name] = percent
    return discounts


def validate_city_discounts(value):
    parse_city_discounts(value)
