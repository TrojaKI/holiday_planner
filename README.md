## Vacation optimizer

✔ AT / DE Feiertage
✔ Bundesländer
✔ bewegliche Feiertage (Ostern-Offset)
✔ nth_weekday / last_weekday
✔ Bereiche (relative_range)
✔ workdays_only
✔ count_mode net/gross
✔ Urlaubsoptimierung

## Usage examples

- Feiertage eines Jahres anzeigen
```
python3 holiday_planner.py \
  --countries AT-N \
  --list-year 2026
```

- Mit JSON-Konfiguration
```
  python3 holiday_planner.py \
  --config config.json \
  --list-year 2026
```


- Urlaubsoptimierung (1–3 Tage)
```
python3 holiday_planner.py \
  --countries AT-N \
  --optimize-vacation 2026
```

 optional:
```
  --max-vac-days 3
```


## Json example

