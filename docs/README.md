# Sprint Race Pace Statistics

This directory contains the generated GitHub Pages reports for all configured seasons.

## Overview

Reports are generated from event CSVs under `assets/csv/season*/race_type/`. Race pages display:

- **Race Pace Trend**: Interactive Plotly chart showing pace progress across all 5 rounds
- **Pace vs Alien Data**: Comparison table of all drivers' lap times relative to the best fictional lap time (alien pace)
- **Driver Improvement Comparison**: Analysis showing which drivers improved the most between the first 2 rounds and last 2 rounds
- **Race Descriptors**: Round-by-round tables for race pace, consistency, reliability, incidents, track limits, lap completion, pit stops, and pit-lane loss
- **Chart Hover Details**: Event-specific pace and descriptor values for race pages; qualifying hover remains pace-only

## Updating the Page

To update the statistics with new race data:

1. Add or update XML files in `assets/xml/season*/sprint/` or `assets/xml/season*/multiclass/`.
2. Add or update event metadata and reference values in the appropriate `assets/json/season*.json` file.
3. Run `python generate_stats_page.py`. This recalculates CSVs and then generates the reports.

To generate CSVs for one season without rebuilding reports, run `python generate_descriptor_csvs.py --season season4`.

The page will automatically update on your GitHub Pages site.

## Files

- `index.html` - The main GitHub Pages website (auto-generated)
- `.nojekyll` - Tells GitHub Pages to serve files as-is
- `README.md` - This file

## Technology Stack

- Python data processing (pandas, numpy)
- Plotly for interactive visualizations
- HTML/CSS for responsive design

## GitHub Pages Setup

To enable GitHub Pages for this repository:

1. Go to repository **Settings** > **Pages**
2. Select **Deploy from a branch**
3. Choose **main** branch and **/docs** folder
4. Your site will be published at: `https://<username>.github.io/<repo-name>/`

## Data Sources

Event CSVs mirror configured XML filenames and are stored by season and series, for example `assets/csv/season4/multiclass/s6-mc1-r.csv`. XML files remain under `assets/xml/`; each season's reference times are stored in `assets/json/season*.json`. Each CSV contains one row per driver, including class identity, pace values, and descriptors; qualifying CSVs leave race-only fields blank.

Race XML inputs use filenames in the following format:
- `s3-sc1-r.xml` - Portimao (Reference time: 103.14s)
- `s3-sc2-r.xml` - Le Mans (Reference time: 235.31s)
- `s3-sc3-r.xml` - Interlagos (Reference time: 93.65s)
- `s3-sc4-r.xml` - Monza (Reference time: 99.01s)
- `s3-sc5-r.xml` - Sebring (Reference time: 120.17s)

The pace percentages are calculated relative to these reference lap times.
