#!/usr/bin/env python3
"""
Holiday Planner / Betriebsplaner

Features
--------
- Public holidays via python-holidays (AT/DE etc.)
- Extra rules via JSON config
- nth_weekday / last_weekday
- easter_offset (e.g. Ash Wednesday)
- relative_range with:
    workdays_only
    count_mode = net | gross
- Bridge day detection
- 1-day vacation analysis (Thu/Tue holidays)
- Vacation window analysis with efficiency metrics
- Company shutdown recommendation
- Legacy vacation optimization (--optimize-vacation)

Compatible with Debian Bookworm (holidays 0.10.x) and newer versions.
"""

import argparse
import json
import sys
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
    holiday_sets = []
    has_new_api = hasattr(holidays, "country_holidays")

    for c in countries:
        if isinstance(c, str):
            if "-" in c:
                code, prov = c.split("-", 1)
                code = code.upper()
                prov = prov.upper()
            else:
                code = c.upper()
                prov = None
        elif isinstance(c, dict):
            code = c.get("code", "").upper()
            prov = c.get("province")
            if prov:
                prov = prov.upper()
        else:
            print(f"Invalid country entry: {c}")
            continue

        try:
            if has_new_api:
                try:
                    h = holidays.country_holidays(code, subdiv=prov, language="de", years=year)
                except Exception:
                    h = holidays.country_holidays(code, subdiv=prov, years=year)
            else:
                h = holidays.CountryHoliday(code, prov=prov, years=year)
            holiday_sets.append(h)
        except Exception as e:
            print(f"Error for {code}-{prov}: {e}")

    return holiday_sets


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
# Calendar map
# -------------------------------------------------

def build_year_calendar(year, holiday_sets):
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    delta = timedelta(days=1)

    free_days = set()
    for h in holiday_sets:
        free_days.update(d for d in h if d.year == year)

    calendar_map = {}
    current = start
    while current <= end:
        if current.weekday() >= 5 or current in free_days:
            calendar_map[current] = 1
        else:
            calendar_map[current] = 0
        current += delta

    return calendar_map


# -------------------------------------------------
# Extra holidays
# -------------------------------------------------

def add_extra_holidays(year, holiday_sets, countries, config):
    if not config or "extra_holidays" not in config:
        return

    for extra in config["extra_holidays"]:
        t = extra["type"]
        name = extra["name"]
        province_filter = extra.get("province")

        # -------------------------------------------------
        # fixed date
        # -------------------------------------------------
        if t == "fixed":
            d = date(year, extra["month"], extra["day"])

        # -------------------------------------------------
        # easter offset
        # -------------------------------------------------
        elif t == "easter_offset":
            easter = get_easter_sunday(year)
            d = easter + timedelta(days=extra["offset"])

        # -------------------------------------------------
        # nth weekday
        # -------------------------------------------------
        elif t == "nth_weekday":
            d = get_nth_weekday(year, extra["month"], extra["weekday"], extra["n"])
            if not d:
                continue

        # -------------------------------------------------
        # last weekday
        # -------------------------------------------------
        elif t == "last_weekday":
            d = get_last_weekday(year, extra["month"], extra["weekday"])
            if not d:
                continue

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

            # NET = count actual working days
            if count_mode == "net":
                while added < length:
                    if not workdays_only or is_workday(current, holiday_sets):
                        for idx, c in enumerate(countries):
                            if province_filter is not None:
                                c_prov = c.get("province") if isinstance(c, dict) else None
                                if c_prov != province_filter:
                                    continue
                            if current in holiday_sets[idx]:
                                print(f"Warning: {current} overwrites '{holiday_sets[idx][current]}' with '{name}'")
                            holiday_sets[idx][current] = name
                        added += 1
                    current += timedelta(days=1)

            # GROSS = count calendar days
            else:
                for i in range(length):
                    d_range = base_date + timedelta(days=i)
                    for idx, c in enumerate(countries):
                        if province_filter is not None:
                            c_prov = c.get("province") if isinstance(c, dict) else None
                            if c_prov != province_filter:
                                continue
                        if d_range in holiday_sets[idx]:
                            print(f"Warning: {d_range} overwrites '{holiday_sets[idx][d_range]}' with '{name}'")
                        holiday_sets[idx][d_range] = name

            continue

        else:
            continue

        # Apply holiday to matching country entries (with optional province filter)
        for idx, c in enumerate(countries):
            if province_filter is not None:
                c_prov = c.get("province") if isinstance(c, dict) else None
                if c_prov != province_filter:
                    continue
            if d in holiday_sets[idx]:
                print(f"Warning: {d} overwrites '{holiday_sets[idx][d]}' with '{name}'")
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


def analyze_vacation_windows(year, holiday_sets, max_vac_days=3):
    cal = build_year_calendar(year, holiday_sets)
    days = sorted(cal.keys())
    results = []

    for i in range(len(days)):
        for vac_days in range(1, max_vac_days + 1):
            vacation_dates = []
            workday_count = 0

            # Assign vacation days starting at i
            for j in range(i, len(days)):
                if cal[days[j]] == 0:
                    vacation_dates.append(days[j])
                    workday_count += 1
                    if workday_count == vac_days:
                        break

            if workday_count != vac_days:
                continue

            # Count consecutive free days from i
            free_count = 0
            k = i
            while k < len(days):
                if cal[days[k]] == 1 or days[k] in vacation_dates:
                    free_count += 1
                    k += 1
                else:
                    break

            efficiency = free_count / vac_days
            results.append({
                "start": days[i],
                "vac_days": vac_days,
                "free_days": free_count,
                "efficiency": round(efficiency, 2),
                "vacation_dates": vacation_dates
            })

    return sorted(results, key=lambda x: (-x["efficiency"], -x["free_days"]))


# -------------------------------------------------
# Bridge day analysis
# -------------------------------------------------

def detect_bridge_days(year, holiday_sets):
    bridge_days = []
    all_holidays = set()
    for h in holiday_sets:
        all_holidays.update(d for d in h if d.year == year)

    for hday in sorted(all_holidays):
        weekday = hday.weekday()
        # Thursday → Friday bridge
        if weekday == 3:
            bridge = hday + timedelta(days=1)
            if bridge.weekday() < 5 and bridge not in all_holidays:
                bridge_days.append((bridge, "Brückentag (nach Feiertag Do)"))
        # Tuesday → Monday bridge
        elif weekday == 1:
            bridge = hday - timedelta(days=1)
            if bridge.weekday() < 5 and bridge not in all_holidays:
                bridge_days.append((bridge, "Brückentag (vor Feiertag Di)"))

    return bridge_days


def analyze_one_day_vacation(year, holiday_sets):
    results = []
    all_holidays = set()
    for h in holiday_sets:
        all_holidays.update(d for d in h if d.year == year)

    for hday in sorted(all_holidays):
        wd = hday.weekday()

        # Thursday → take Friday off for 4-day weekend
        if wd == 3:
            friday = hday + timedelta(days=1)
            if friday.weekday() < 5 and friday not in all_holidays:
                results.append((friday, hday, 4))

        # Tuesday → take Monday off for 4-day weekend
        if wd == 1:
            monday = hday - timedelta(days=1)
            if monday.weekday() < 5 and monday not in all_holidays:
                results.append((monday, hday, 4))

    return results


# -------------------------------------------------
# Reporting
# -------------------------------------------------

def show_vacation_optimisation(year, holiday_sets, max_days):
    print("\nUrlaubsoptimierung\n")
    for days in range(1, max_days + 1):
        results = maximize_free_time(year, holiday_sets, days)
        print(f"\n{days} Urlaubstage:")
        for r in results[:5]:
            print(f"Start {r[0]} → {r[1]} freie Tage")


def list_holidays_with_bridges(year, holiday_sets, extra_holidays=None, only_workdays=False):
    bridge_days = detect_bridge_days(year, holiday_sets)

    combined = {}

    # Regular holidays — first-seen wins for duplicate dates across countries
    for h in holiday_sets:
        for day, name in h.items():
            if day.year == year and day not in combined:
                combined[day] = name

    # Optional extra holidays
    if extra_holidays:
        for day, name in extra_holidays:
            if day not in combined:
                combined[day] = name

    # Bridge days
    for day, name in bridge_days:
        if day not in combined:
            combined[day] = name

    print(f"\nBetriebsplaner – Feiertage & Brückentage {year}")
    for day in sorted(combined):
        if only_workdays and day.weekday() >= 5:
            continue
        weekday = day.strftime("%A")
        print(f"{day} ({weekday:10s}): {combined[day]}")


def print_vacation_analysis(year, holiday_sets):
    results = analyze_one_day_vacation(year, holiday_sets)
    print(f"\n1 Urlaubstag → 4 Tage frei ({year})")
    for vacation_day, holiday, free_days in results:
        print(
            f"Urlaub am {vacation_day} "
            f"(Feiertag {holiday}) → {free_days} Tage frei"
        )


def print_top_vacation_options(year, holiday_sets, max_vac_days=3, top=10):
    results = analyze_vacation_windows(year, holiday_sets, max_vac_days)
    print(f"\nBeste Urlaubsoptionen {year} (1–{max_vac_days} Tage)\n")
    for r in results[:top]:
        vac_list = ", ".join(str(d) for d in r["vacation_dates"])
        print(
            f"{r['vac_days']} Urlaubstage → "
            f"{r['free_days']} Tage frei | "
            f"Effizienz {r['efficiency']} | "
            f"Urlaub: {vac_list}"
        )


def suggest_company_shutdown(year, holiday_sets):
    results = analyze_vacation_windows(year, holiday_sets, 3)
    print("\nEmpfohlene Betriebsruhe-Zeiträume:\n")
    for r in results:
        if r["free_days"] >= 7 and r["vac_days"] <= 3:
            start = r["start"]
            end = start + timedelta(days=r["free_days"] - 1)
            print(
                f"{start} bis {end} "
                f"({r['vac_days']} Urlaubstage → {r['free_days']} Tage frei)"
            )
            break


# -------------------------------------------------
# CLI
# -------------------------------------------------

def parse_countries(text):
    result = []
    for item in text.split(","):
        item = item.strip()
        if "-" in item:
            code, prov = item.split("-", 1)
            result.append({"code": code.upper(), "province": prov.upper()})
        else:
            result.append({"code": item.upper(), "province": None})
    return result


def main():
    parser = argparse.ArgumentParser(description="Betriebsplaner – Feiertage & Brückentage")
    parser.add_argument("--countries", help="Comma-separated: AT, DE-BY, AT-W")
    parser.add_argument("--config", help="JSON config file with countries and extra_holidays")
    parser.add_argument("--list-year", type=int, help="List holidays + bridge days for year")
    parser.add_argument("--only-workdays", action="store_true", help="With --list-year: skip weekends")
    parser.add_argument("--optimize-vacation", type=int, help="Legacy vacation optimization")
    parser.add_argument("--analyze-vacation", type=int, help="Vacation analysis with efficiency metrics")
    parser.add_argument("--max-vac-days", type=int, default=3,
                        help="Max vacation days for analysis (default: 3)")
    parser.add_argument("--top", type=int, default=10,
                        help="Number of top results (default: 10)")
    parser.add_argument("--suggest-shutdown", type=int,
                        help="Company shutdown recommendation for year")

    args = parser.parse_args()

    config = {}
    if args.config:
        with open(args.config) as f:
            config = json.load(f)

    if args.countries:
        countries = parse_countries(args.countries)
    elif "countries" in config:
        countries = config["countries"]
    else:
        print("No countries specified")
        sys.exit(1)

    if args.list_year:
        year = args.list_year
        holiday_sets = build_holiday_sets(year, countries)
        add_extra_holidays(year, holiday_sets, countries, config)
        list_holidays_with_bridges(year, holiday_sets, only_workdays=args.only_workdays)
        return

    if args.optimize_vacation:
        year = args.optimize_vacation
        holiday_sets = build_holiday_sets(year, countries)
        add_extra_holidays(year, holiday_sets, countries, config)
        show_vacation_optimisation(year, holiday_sets, args.max_vac_days)
        return

    if args.analyze_vacation:
        year = args.analyze_vacation
        holiday_sets = build_holiday_sets(year, countries)
        add_extra_holidays(year, holiday_sets, countries, config)
        results = analyze_vacation_windows(year, holiday_sets, args.max_vac_days)
        print(f"\nBeste Urlaubsoptionen {year}\n")
        for r in results[:args.top]:
            vac_list = ", ".join(str(d) for d in r["vacation_dates"])
            print(
                f"{r['vac_days']} Urlaubstage → "
                f"{r['free_days']} Tage frei | "
                f"Effizienz {r['efficiency']} | "
                f"Urlaub: {vac_list}"
            )
        return

    if args.suggest_shutdown:
        year = args.suggest_shutdown
        holiday_sets = build_holiday_sets(year, countries)
        add_extra_holidays(year, holiday_sets, countries, config)
        suggest_company_shutdown(year, holiday_sets)
        return

    print("No action specified. Use --list-year, --analyze-vacation, --optimize-vacation, or --suggest-shutdown.")


if __name__ == "__main__":
    main()
