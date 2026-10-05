# OOFS Analytics

## Regenerate the statistics

1. Add or update result XML files under `assets/xml/season*/sprint/` or `assets/xml/season*/multiclass/`.
2. Add or update the session's event metadata and reference times in the appropriate `assets/json/season*.json` file.
3. Run the report generator, which recalculates event CSVs before building the pages:

	```powershell
	python generate_stats_page.py
	```

	To regenerate CSVs for one season independently, run:

	```powershell
	python generate_descriptor_csvs.py --season season4
	```

Event CSVs are stored under `assets/csv/season*/race_type/` with the XML event stem, for example `assets/csv/season4/multiclass/s6-mc1-r.csv`. Each contains driver and class identity, legacy pace fields, race descriptors, and session metadata. Qualifying rows contain pace data; race-only values are blank. Race reports include round-by-round descriptor tables and chart hover details.

