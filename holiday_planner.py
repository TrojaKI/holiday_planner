#!/usr/bin/env python3
"""
Holiday Planner / Betriebsplaner

Features
--------
- Feiertage über python-holidays (AT/DE etc.)
- Zusatzregeln über JSON
- nth_weekday / last_weekday
- easter_offset (z.B. Aschermittwoch)
- relative_range mit:
    workdays_only
    count_mode = net | gross
- Urlaubsoptimierung (1–3 Tage)
- Maximale Freizeit bei X Urlaubstagen

Kompatibel mit Debian Bookworm (holidays 0.10.x) und neueren Versionen.
"""

import argparse
import json
import calendar
from datetime import date, timedelta
import holidays


# -------------------------------------------------
# Basic helpers
# -------------------------------------------------

def is_weekend(d):
    return d.weekday() >= 5


def is_public_holiday(d, holiday_sets):
    for h in holiday_sets:
        if d in h:
            return True
    return False


def is_workday(d, holiday_sets):
    return not is_weekend(d) and not is_public_holiday(d, holiday_sets)


# -------------------------------------------------
# Easter calculation (Gregorian)
# -------------------------------------------------

def get_easter_sunday(year):
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


# -------------------------------------------------
# Holiday sets
# -------------------------------------------------

def build_holiday_sets(year, countries):
    sets = []
    for c in countries:
        code = c.get("code")
        prov = c.get("province")
        try:
            h = holidays.CountryHoliday(code, prov=prov, years=year)
            sets.append(h)
        except Exception as e:
            print(f"Fehler bei {code}-{prov}: {e}")
    return sets


# -------------------------------------------------
# Relative day helpers
# -------------------------------------------------

def get_nth_weekday(year, month, weekday, n):
    count = 0
    for day in range(1, 32):
        try:
            d = date(year, month, day)
        except ValueError:
            break
        if d.weekday() == weekday:
            count += 1
            if count == n:
                return d
    return None


def get_last_weekday(year, month, weekday):
    last = calendar.monthrange(year, month)[1]
    for d in range(last, 0, -1):
        dt = date(year, month, d)
        if dt.weekday() == weekday:
            return dt
    return None


# -------------------------------------------------
# Resolve base date for rules
# -------------------------------------------------

def resolve_base_date(year, base):
    t = base["type"]

    if t == "fixed":
        return date(year, base["month"], base["day"])

    if t == "easter_offset":
        easter = get_easter_sunday(year)
        return easter + timedelta(days=base["offset"])

    if t == "nth_weekday":
        return get_nth_weekday(year, base["month"], base["weekday"], base["n"])

    if t == "last_weekday":
        return get_last_weekday(year, base["month"], base["weekday"])

    return None


# -------------------------------------------------
# Extra holidays
# -------------------------------------------------

def add_extra_holidays(year, holiday_sets, countries, config):

    if not config or "extra_holidays" not in config:
        return

    for extra in config["extra_holidays"]:

        t = extra["type"]
        name = extra["name"]

        # -------------------------------------------------
        # fixed date
        # -------------------------------------------------
        if t == "fixed":
            d = date(year, extra["month"], extra["day"])

            for idx in range(len(holiday_sets)):
                holiday_sets[idx][d] = name

        # -------------------------------------------------
        # easter offset
        # -------------------------------------------------
        elif t == "easter_offset":

            easter = get_easter_sunday(year)
            d = easter + timedelta(days=extra["offset"])

            for idx in range(len(holiday_sets)):
                holiday_sets[idx][d] = name

        # -------------------------------------------------
        # nth weekday
        # -------------------------------------------------
        elif t == "nth_weekday":

            d = get_nth_weekday(
                year,
                extra["month"],
                extra["weekday"],
                extra["n"]
            )

            if d:
                for idx in range(len(holiday_sets)):
                    holiday_sets[idx][d] = name

        # -------------------------------------------------
        # last weekday
        # -------------------------------------------------
        elif t == "last_weekday":

            d = get_last_weekday(
                year,
                extra["month"],
                extra["weekday"]
            )

            if d:
                for idx in range(len(holiday_sets)):
                    holiday_sets[idx][d] = name

        # -------------------------------------------------
        # relative range
        # -------------------------------------------------
        elif t == "relative_range":

            base_date = resolve_base_date(year, extra["base"])
            length = extra["length"]
            workdays_only = extra.get("workdays_only", False)
            count_mode = extra.get("count_mode", "net")

            if not base_date:
                continue

            current = base_date
            added = 0

            # NET = echte Arbeitstage zählen
            if count_mode == "net":

                while added < length:

                    if not workdays_only or is_workday(current, holiday_sets):

                        for idx in range(len(holiday_sets)):
                            holiday_sets[idx][current] = name

                        added += 1

                    current += timedelta(days=1)

            # GROSS = Kalendertage zählen
            else:

                for i in range(length):

                    d = base_date + timedelta(days=i)

                    for idx in range(len(holiday_sets)):
                        holiday_sets[idx][d] = name


# -------------------------------------------------
# Vacation optimisation
# -------------------------------------------------

def maximize_free_time(year, holiday_sets, vacation_days=1):

    results = []

    start = date(year, 1, 1)
    end = date(year, 12, 31)

    current = start

    while current <= end:

        if is_workday(current, holiday_sets):

            used = 0
            d = current

            while used < vacation_days and d <= end:
                if is_workday(d, holiday_sets):
                    used += 1
                d += timedelta(days=1)

            while d <= end and not is_workday(d, holiday_sets):
                d += timedelta(days=1)

            span = (d - current).days

            results.append((current, span))

        current += timedelta(days=1)

    return sorted(results, key=lambda x: x[1], reverse=True)


# -------------------------------------------------
# Reporting
# -------------------------------------------------

def list_year(year, holiday_sets):

    all_days = {}

    for h in holiday_sets:
        for d, name in h.items():
            if d.year == year:
                all_days[d] = name

    for d in sorted(all_days):
        print(d, all_days[d])


def show_vacation_optimisation(year, holiday_sets, max_days):

    print("\nUrlaubsoptimierung\n")

    for days in range(1, max_days + 1):

        results = maximize_free_time(year, holiday_sets, days)

        print(f"\n{days} Urlaubstage:")

        for r in results[:5]:
            print(f"Start {r[0]} → {r[1]} freie Tage")


# -------------------------------------------------
# CLI
# -------------------------------------------------

def parse_countries(text):

    result = []

    for item in text.split(","):

        if "-" in item:
            code, prov = item.split("-")
            result.append({"code": code, "province": prov})
        else:
            result.append({"code": item, "province": None})

    return result


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("--countries", help="AT,DE-BY etc")
    parser.add_argument("--config", help="JSON config file")
    parser.add_argument("--list-year", type=int)
    parser.add_argument("--optimize-vacation", type=int)
    parser.add_argument("--max-vac-days", type=int, default=3)

    args = parser.parse_args()

    config = None

    if args.config:
        with open(args.config) as f:
            config = json.load(f)

    if args.countries:
        countries = parse_countries(args.countries)
    elif config and "countries" in config:
        countries = config["countries"]
    else:
        print("Keine Länder angegeben")
        return

    year = args.list_year or args.optimize_vacation

    if not year:
        print("Bitte Jahr angeben")
        return

    holiday_sets = build_holiday_sets(year, countries)

    add_extra_holidays(year, holiday_sets, countries, config)

    if args.list_year:
        list_year(year, holiday_sets)

    if args.optimize_vacation:
        show_vacation_optimisation(year, holiday_sets, args.max_vac_days)


if __name__ == "__main__":
    main()
