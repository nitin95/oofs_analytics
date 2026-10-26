# OOFS Analytics

OOFS Analytics turns Le Mans Ultimate result XMLs into per-event pace and race-descriptor data, then builds static, interactive season reports. The generated site lives in `docs/` and can be published with GitHub Pages.

## Setup

Use Python 3 with `pandas` and `numpy` installed:

```powershell
python -m pip install pandas numpy
```

Run commands from the repository root so the default `assets/` and `docs/` paths resolve correctly.

## Generate Reports

1. Add or update result XML files in `assets/xml/<season>/<series>/`, where `<series>` is `sprint` or `multiclass`.
2. Add matching event entries to `assets/json/<season>.json` (see [Event Configuration](#event-configuration)).
3. Build the reports:

	 ```powershell
	 python generate_stats_page.py
	 ```

This command processes all configured seasons. It first regenerates event CSVs from the configured XML files, then reads those CSVs to assemble and write the HTML reports. Missing XML files are reported and skipped.

To generate event CSVs for just one season without rebuilding HTML, run:

```powershell
python csv_lib.py --season season4
```

Repeat `--season` to select multiple seasons. The CSV generator also accepts `--input-root`, `--output-root`, and `--config-root` when using non-default data directories. The previous `python generate_descriptor_csvs.py` command remains available as a compatibility entrypoint.

## Event Configuration

Each season JSON file starts with a `season_info` object containing its display name, year, and description. It also contains up to four event groups: `sprint_qualis`, `sprint_races`, `multiclass_qualis`, and `multiclass_races`. Each key must match an XML filename in the corresponding `assets/xml/<season>/<series>/` directory. An event entry provides the display name and reference lap time for each car class, for example:

```json
{
	"season_info": {
		"name": "Season 6",
		"year": 2026,
		"description": "OOFS S6"
	},
	"sprint_qualis": {
		"s6-sc1.xml": {
			"name": "Fuji",
			"reference_times": {
				"lmp3": 94.197,
				"gt3": 99.184
			}
		}
	}
}
```

Reference-time keys can be `gt3`, `lmp3`, `hyper`, or `p2ur`; `default` can be used as a fallback. Race and qualifying events should have their own reference times when those differ.

## Data Flow and Reports

- `lmu_descriptors.py` parses an event XML and calculates pace values and, for races, descriptors such as consistency, reliability, incidents, track limits, lap completion, pit stops, and pit-lane loss.
- `generate_descriptor_csvs.py` writes one CSV per configured event to `assets/csv/<season>/<series>/`, preserving the XML filename stem. CSVs include driver/class identity, pace fields, descriptors, and season/session metadata. Qualifying CSVs leave race-only descriptor fields blank.
- `csv_lib.py` owns season configuration, driver-name normalization, rookie history, event loading, and comparison-data preparation. It also generates the per-event descriptor CSVs; `generate_descriptor_csvs.py` remains as a compatible command entrypoint.
- `html_lib.py` turns comparison data into report pages, tables, sidebars, and driver-colored pace charts. `generate_stats_page.py` orchestrates the season-specific loading and output paths.
- `elo_lib.py` calculates cumulative Elo ratings from configured race results, separately for Sprint GT3, Sprint LMP3, Multiclass GT3, and Multiclass Prototype. Ratings start at 1500; drivers use K=64 throughout their first season in a category and K=32 in later seasons. Pages are written to `docs/elo.html` and `docs/elo_<category>.html` in order of each category's first race. The top-level Rankings link opens the earliest category.
- Race pages include round-by-round descriptor tables and chart hover details. Qualifying reports show pace data without race-only descriptors. Sprint reports split into LMP3 and GT3 pages when the season has separate sprint-class data.

Generated event pages are written to `docs/<season>/`. The top-level `docs/index.html` is regenerated from `templates/index.html` by `generate_stats_page.py`.

## Repository Layout

```text
assets/
	json/       Per-season event names and reference lap times
	xml/        Source result files, organized by season and series
	csv/        Generated per-event data, organized by season and series
templates/    HTML and CSS used to render reports
docs/         Static site and generated season report pages
tests/        Unit tests
```

The `archive/` directory contains older analysis artifacts and is not part of the report-generation pipeline. The page template loads Plotly from its CDN, so interactive charts require a network connection in the browser.

## Tests

Run the unit tests with:

```powershell
python -m unittest discover -s tests
```

## Notes

Wet race times use the leader's lap time/(leader's quali pct vs alien + 1.5% race pace penalty)