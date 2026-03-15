## Vacation Optimizer

Berechnet Feiertage für AT/DE-Bundesländer, erlaubt benutzerdefinierte Zusatzfeiertage per JSON
und optimiert Urlaubsplanung: Welche Urlaubstage ergeben die längste zusammenhängende Freizeit?

### Features

- Offizielle Feiertage für AT, DE und weitere Länder (via `python-holidays`)
- Bundesländer-spezifische Feiertage (z.B. AT-N, DE-BY)
- Bewegliche Feiertage über Ostern-Offset (z.B. Aschermittwoch)
- n-ter Wochentag im Monat (`nth_weekday`)
- Letzter Wochentag im Monat (`last_weekday`)
- Urlaubs-/Betriebsbereiche (`relative_range`) mit `workdays_only` und `count_mode net/gross`
- Urlaubsoptimierung: maximale Freizeit bei 1–N Urlaubstagen


## Installation

Python 3 und die `holidays`-Bibliothek werden benötigt:

```bash
pip install holidays
```

Auf Debian/Ubuntu:

```bash
apt install python3-holidays
```


## Usage

```
python3 holiday_planner.py [OPTIONEN]
```

| Argument | Beschreibung |
|---|---|
| `--countries CODE` | Länder/Bundesländer, kommagetrennt (z.B. `AT-N`, `DE-BY,AT`) |
| `--config FILE` | JSON-Konfigurationsdatei (kann `countries` und `extra_holidays` enthalten) |
| `--list-year JAHR` | Alle Feiertage des angegebenen Jahres ausgeben |
| `--optimize-vacation JAHR` | Urlaubsoptimierung für das angegebene Jahr |
| `--max-vac-days N` | Maximale Anzahl Urlaubstage bei Optimierung (Standard: 3) |

**Hinweis:** `--countries` und `--config` können kombiniert werden. `--countries` überschreibt
die `countries`-Angabe aus der Konfigurationsdatei.

### Beispiele

Feiertage eines Jahres anzeigen (Niederösterreich):
```bash
python3 holiday_planner.py --countries AT-N --list-year 2026
```

Mit JSON-Konfiguration (Länder + Zusatzfeiertage):
```bash
python3 holiday_planner.py --config custom_days.json --list-year 2026
```

Urlaubsoptimierung mit bis zu 5 Urlaubstagen:
```bash
python3 holiday_planner.py --countries AT-N --optimize-vacation 2026 --max-vac-days 5
```

Urlaubsoptimierung mit JSON-Konfiguration und maximal 3 Tagen:
```bash
python3 holiday_planner.py --config custom_days.json --optimize-vacation 2026 --max-vac-days 3
```


## JSON-Konfiguration

Die JSON-Datei kann zwei Felder enthalten:

```json
{
  "countries": [
    { "code": "AT", "province": "N" }
  ],
  "extra_holidays": [ ... ]
}
```

Das Feld `countries` ist optional, wenn `--countries` auf der Kommandozeile angegeben wird.

### Typen in `extra_holidays`

#### `fixed` — Fester Jahrestag

```json
{
  "type": "fixed",
  "month": 11,
  "day": 15,
  "name": "Hl. Leopold"
}
```

#### `easter_offset` — Relativ zu Ostersonntag

`offset` in Tagen (negativ = vor Ostern).

```json
{
  "type": "easter_offset",
  "offset": -46,
  "name": "Aschermittwoch"
}
```

#### `nth_weekday` — N-ter Wochentag im Monat

`weekday`: 0 = Montag, 1 = Dienstag, …, 4 = Freitag, 5 = Samstag, 6 = Sonntag

```json
{
  "type": "nth_weekday",
  "month": 10,
  "weekday": 0,
  "n": 2,
  "name": "2. Montag im Oktober"
}
```

#### `last_weekday` — Letzter Wochentag im Monat

```json
{
  "type": "last_weekday",
  "month": 6,
  "weekday": 4,
  "name": "Letzter Freitag im Juni"
}
```

#### `relative_range` — Bereich ab einem Basisdatum

Markiert mehrere aufeinanderfolgende Tage ab einem berechneten Startdatum.
Das `base`-Objekt unterstützt alle vier obigen Typen (`fixed`, `easter_offset`,
`nth_weekday`, `last_weekday`).

| Feld | Beschreibung |
|---|---|
| `base` | Startdatum (beliebiger Typ, siehe oben) |
| `length` | Anzahl der Tage |
| `workdays_only` | `true`: nur Arbeitstage werden gezählt/markiert |
| `count_mode` | `"net"`: `length` = echte Arbeitstage; `"gross"`: `length` = Kalendertage |

```json
{
  "type": "relative_range",
  "base": {
    "type": "nth_weekday",
    "month": 8,
    "weekday": 0,
    "n": 2
  },
  "length": 10,
  "workdays_only": true,
  "count_mode": "net",
  "name": "Sommerurlaub"
}
```

Dieses Beispiel markiert 10 Arbeitstage Sommerurlaub ab dem 2. Montag im August.

### Vollständiges Konfigurationsbeispiel

```json
{
  "countries": [
    { "code": "AT", "province": "N" }
  ],
  "extra_holidays": [
    {
      "type": "fixed",
      "month": 11,
      "day": 15,
      "name": "Hl. Leopold"
    },
    {
      "type": "easter_offset",
      "offset": -46,
      "name": "Aschermittwoch"
    },
    {
      "type": "nth_weekday",
      "month": 10,
      "weekday": 0,
      "n": 2,
      "name": "2. Montag im Oktober"
    },
    {
      "type": "last_weekday",
      "month": 6,
      "weekday": 4,
      "name": "Letzter Freitag im Juni"
    },
    {
      "type": "relative_range",
      "base": {
        "type": "nth_weekday",
        "month": 8,
        "weekday": 0,
        "n": 2
      },
      "length": 10,
      "workdays_only": true,
      "count_mode": "net",
      "name": "Sommerurlaub"
    }
  ]
}
```


## Beispielausgabe

```
$ python3 holiday_planner.py --countries AT-N --list-year 2026

2026-01-01 Neujahr
2026-01-06 Heilige Drei Könige
2026-04-06 Ostermontag
2026-05-01 Staatsfeiertag
...
```

```
$ python3 holiday_planner.py --countries AT-N --optimize-vacation 2026 --max-vac-days 3

Urlaubsoptimierung

1 Urlaubstage:
Start 2026-01-02 → 4 freie Tage
Start 2026-04-30 → 4 freie Tage
...

2 Urlaubstage:
Start 2026-05-28 → 9 freie Tage
...
```
