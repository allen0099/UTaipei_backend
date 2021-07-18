from datetime import date


def get_year() -> int:
    today = date.today()
    return today.year - 1911 if today.month > 6 else today.year - 1912