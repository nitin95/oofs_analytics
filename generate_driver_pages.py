"""Generate individual driver profile pages from configured event CSVs."""

import html
import os
import re

import pandas as pd

import csv_lib
import elo_lib
import html_lib


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.path.join(ROOT_DIR, 'assets', 'csv')
CONFIG_ROOT = os.path.join(ROOT_DIR, 'assets', 'json')
OUTPUT_DIR = os.path.join(ROOT_DIR, 'docs', 'profiles')
SERIES = ('sprint', 'multiclass')
SESSIONS = (('qualis', 'qualifying'), ('races', 'race'))
CATEGORY_LABELS = {
    ('sprint', 'GT3'): 'Sprint GT3',
    ('sprint', 'LMP3'): 'Sprint LMP3',
    ('multiclass', 'GT3'): 'Multiclass GT3',
    ('multiclass', 'PROTOTYPE'): 'Multiclass Prototype',
}
CATEGORY_ELO_SLUGS = {
    ('sprint', 'GT3'): 'sprint_gt3',
    ('sprint', 'LMP3'): 'sprint_lmp3',
    ('multiclass', 'GT3'): 'multiclass_gt3',
    ('multiclass', 'PROTOTYPE'): 'multiclass_prototype',
}


def _as_number(value):
    number = pd.to_numeric(value, errors='coerce')
    return None if pd.isna(number) else float(number)


def _read_event_csv(path):
    try:
        return pd.read_csv(path)
    except (OSError, UnicodeDecodeError, pd.errors.ParserError):
        return None


def collect_driver_records(data_root=DATA_ROOT, config_root=CONFIG_ROOT):
    """Collect qualifying and race records keyed by canonical driver name."""
    profiles = {}
    season_ids = list(csv_lib.SEASONS)

    for season_order, season_id in enumerate(season_ids):
        config = csv_lib.load_season_config(season_id, config_root)
        season_name = config.get('season_info', {}).get('name', season_id)

        for series in SERIES:
            for session_order, (section_suffix, session) in enumerate(SESSIONS):
                section_name = f'{series}_{section_suffix}'
                for event_order, (filename, event_info) in enumerate(
                    config.get(section_name, {}).items()
                ):
                    csv_path = csv_lib.build_csv_path(
                        season_id, series, filename, output_root=data_root
                    )
                    frame = _read_event_csv(csv_path)
                    if frame is None or frame.empty:
                        continue

                    for row in frame.to_dict('records'):
                        driver_value = row.get('Driver_name')
                        if pd.isna(driver_value):
                            driver_value = row.get('Driver')
                        if pd.isna(driver_value) or not str(driver_value).strip():
                            continue

                        name = csv_lib.normalize_driver_name(driver_value)
                        category = csv_lib.get_driver_category(
                            row.get('CarClass', ''), series
                        )
                        if category is None:
                            continue

                        record = {
                            'season_id': season_id,
                            'season_name': season_name,
                            'series': series,
                            'category': category,
                            'category_label': CATEGORY_LABELS[(series, category)],
                            'session': session,
                            'event': event_info.get(
                                'name', os.path.splitext(filename)[0]
                            ),
                            'position': _as_number(row.get('Position')),
                            'finish_status': str(row.get('FinishStatus', '') or ''),
                            'laps': _as_number(row.get('Laps')),
                            'car': str(row.get('Car', '') or ''),
                            'car_number': str(row.get('CarNumber', '') or ''),
                            'avg_pace_pct_alien': _as_number(
                                row.get('avg_pace_pct_alien')
                            ),
                            'consistency': _as_number(row.get('consistency')),
                            'reliability': _as_number(row.get('reliability')),
                            'incidents': _as_number(row.get('n_inchidents')),
                            '_season_order': season_order,
                            '_event_order': event_order,
                            '_session_order': session_order,
                        }
                        profiles.setdefault(name, {'race': [], 'qualifying': []})[
                            session
                        ].append(record)

    for profile in profiles.values():
        for records in profile.values():
            records.sort(key=lambda record: (
                record['_season_order'],
                record['_event_order'],
                record['_session_order'],
            ))
    return profiles


def _mean(records, key):
    values = [record[key] for record in records if record[key] is not None]
    return sum(values) / len(values) if values else None


def _finish_positions(records):
    return [record['position'] for record in records if record['position'] is not None]


def _build_elo_lookup(config_root, data_root):
    """Return final category ratings and ranks indexed by canonical driver name."""
    category_by_slug = {
        slug: category for category, slug in CATEGORY_ELO_SLUGS.items()
    }
    lookup = {}
    for ranking in elo_lib.build_rankings(config_root, data_root):
        category = category_by_slug.get(ranking['slug'])
        if category is None:
            continue
        lookup[category] = {
            csv_lib.normalize_driver_name(standing['driver']): {
                'rating': standing.get('rating', standing.get('race_rating')),
                'rank': rank,
            }
            for rank, standing in enumerate(ranking['standings'], start=1)
        }
    return lookup


def _category_stats(races, qualis):
    positions = _finish_positions(races)
    qualifying_positions = _finish_positions(qualis)
    return {
        'starts': len(races),
        'wins': sum(position == 1 for position in positions),
        'podiums': sum(position <= 3 for position in positions),
        'poles': sum(position == 1 for position in qualifying_positions),
        'dnfs': sum('dnf' in record['finish_status'].lower() for record in races),
        'best_finish': min(positions) if positions else None,
        'average_finish': _mean(races, 'position'),
        'average_qualifying': _mean(qualis, 'position'),
        'average_quali_pace': _mean(qualis, 'avg_pace_pct_alien'),
        'laps': sum(record['laps'] or 0 for record in races),
        'average_pace': _mean(races, 'avg_pace_pct_alien'),
        'average_consistency': _mean(races, 'consistency'),
        'average_reliability': _mean(races, 'reliability'),
        'incidents': sum(record['incidents'] or 0 for record in races),
    }


def _format_number(value, decimals=0):
    if value is None:
        return 'N/A'
    return f'{value:,.{decimals}f}'


def _metric(label, value):
    return (
        '<div class="metric"><span>' + html.escape(label) + '</span>'
        '<strong>' + html.escape(str(value)) + '</strong></div>'
    )


def _metric_grid(metrics):
    return '<div class="metric-grid">' + ''.join(
        _metric(label, value) for label, value in metrics
    ) + '</div>'


def _profile_styles():
    return '''
<style>
    body { line-height: 1.5; }
    .profile-content { max-width: 1120px; margin: 0 auto; padding: 24px; }
    .profile-nav { display: flex; justify-content: space-between; gap: 16px; margin-bottom: 24px; }
    .profile-nav a, .profile-list a { color: #ccfc00; text-decoration: none; }
    .profile-nav a:hover, .profile-list a:hover { text-decoration: underline; }
    .profile-heading { text-align: left; padding: 24px 0 20px; border-bottom: 1px solid #454852; }
    .profile-heading h1 { color: #ccfc00; font-size: 2.2em; overflow-wrap: anywhere; }
    .profile-heading p { color: #c5c7ce; margin-top: 6px; }
    .profile-section { margin-top: 30px; }
    .profile-section h2 { color: #ccfc00; font-size: 1.35em; margin-bottom: 14px; }
    .profile-section h3 { margin: 24px 0 10px; color: #fff; font-size: 1.05em; }
    .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(145px, 1fr)); gap: 1px; background: #41444c; border: 1px solid #41444c; }
    .metric { background: #14161f; padding: 14px; min-height: 78px; }
    .metric span { display: block; color: #b5b8c2; font-size: .82em; }
    .metric strong { display: block; margin-top: 4px; color: white; font-size: 1.25em; }
    .profile-table-wrap { overflow-x: auto; }
    .profile-table { width: 100%; border-collapse: collapse; min-width: 640px; }
    .profile-table th, .profile-table td { padding: 10px 12px; border-bottom: 1px solid #41444c; text-align: left; white-space: nowrap; }
    .profile-table th { color: #ccfc00; background: #14161f; }
    .profile-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1px; background: #41444c; border: 1px solid #41444c; }
    .profile-list a { display: block; background: #14161f; padding: 14px; }
    .profile-list a[hidden] { display: none; }
    .profile-list small { display: block; color: #b5b8c2; margin-top: 4px; }
    .profile-search { width: 100%; padding: 12px 14px; border: 1px solid #555963; border-radius: 4px; background: #14161f; color: #fff; font: inherit; }
    .profile-search:focus { outline: 2px solid #ccfc00; outline-offset: 2px; }
    .alphabet-bar { display: flex; flex-wrap: wrap; gap: 4px; margin: 12px 0 18px; }
    .alphabet-bar button { min-width: 34px; min-height: 34px; border: 1px solid #555963; border-radius: 3px; background: #14161f; color: #fff; cursor: pointer; font: inherit; }
    .alphabet-bar button:hover:not(:disabled), .alphabet-bar button[aria-pressed="true"] { background: #ccfc00; border-color: #ccfc00; color: #111; }
    .alphabet-bar button:disabled { color: #666a74; cursor: not-allowed; }
    .profile-count { color: #b5b8c2; margin: 0 0 10px; }
    .profile-empty { display: none; padding: 18px; color: #c5c7ce; background: #14161f; }
    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
    .profile-footer { color: #aeb1bb; margin-top: 32px; font-size: .85em; }
    @media (max-width: 640px) {
        .profile-content { padding: 14px 8px; }
        .profile-heading h1 { font-size: 1.8em; }
        .profile-nav { flex-wrap: wrap; }
    }
</style>'''


def _base_page(title, body):
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <link rel="stylesheet" href="../styles.css">
    {_profile_styles()}
</head>
<body>
    <main class="profile-content">
        {body}
    </main>
</body>
</html>
'''


def _render_results(records):
    recent = [record for record in records if record['session'] == 'race'][-12:]
    recent.reverse()
    if not recent:
        return '<p>No race results are available.</p>'

    rows = []
    for record in recent:
        position = _format_number(record['position'])
        rows.append(
            '<tr>'
            f'<td>{html.escape(record["season_name"])}</td>'
            f'<td>{html.escape(record["event"])}</td>'
            f'<td>{html.escape(record["category_label"])}</td>'
            f'<td>{position}</td>'
            f'<td>{html.escape(record["finish_status"])}</td>'
            '</tr>'
        )
    return (
        '<div class="profile-table-wrap"><table class="profile-table">'
        '<thead><tr><th>Season</th><th>Event</th><th>Category</th>'
        '<th>Finish</th><th>Status</th></tr></thead><tbody>'
        + ''.join(rows)
        + '</tbody></table></div>'
    )


def render_driver_page(name, profile, generated_date, elo_lookup=None):
    display_name = html_lib.format_driver_name(name)
    races = profile['race']
    qualis = profile['qualifying']
    all_records = races + qualis
    categories = sorted({
        (record['series'], record['category']) for record in all_records
    }, key=lambda item: CATEGORY_LABELS[item])
    stats = _category_stats(races, qualis)
    latest_race = races[-1] if races else None
    current_season = latest_race['season_name'] if latest_race else 'No race data'

    details = [current_season]
    if latest_race and latest_race['car_number'] not in ('', 'nan', 'None'):
        details.append(f"#{latest_race['car_number']}")
    if latest_race and latest_race['car'] not in ('', 'nan', 'None'):
        details.append(latest_race['car'])

    category_sections = []
    for series, category in categories:
        category_label = CATEGORY_LABELS[(series, category)]
        category_races = [
            record for record in races
            if record['series'] == series and record['category'] == category
        ]
        category_qualis = [
            record for record in qualis
            if record['series'] == series and record['category'] == category
        ]
        category_stats = _category_stats(category_races, category_qualis)
        category_elo = (elo_lookup or {}).get((series, category), {}).get(name, {})
        category_sections.append(
            '<section class="profile-section">'
            f'<h2>{html.escape(category_label)}</h2>'
            + _metric_grid([
                ('Starts', category_stats['starts']),
                ('Wins', category_stats['wins']),
                ('Podiums', category_stats['podiums']),
                ('Poles', category_stats['poles']),
                ('Best finish', _format_number(category_stats['best_finish'])),
                ('Average finish', _format_number(category_stats['average_finish'], 2)),
                ('Average qualifying', _format_number(category_stats['average_qualifying'], 2)),
                ('Average quali pace vs alien', _format_number(category_stats['average_quali_pace'], 2) + '%'),
                ('DNFs', category_stats['dnfs']),
                ('Laps completed', _format_number(category_stats['laps'])),
                ('Average race pace vs alien', _format_number(category_stats['average_pace'], 2) + '%'),
                ('Average consistency', _format_number(category_stats['average_consistency'], 3)),
                ('Average reliability', _format_number(category_stats['average_reliability'], 3)),
                ('Incidents', category_stats['incidents']),
                ('Category ELO', _format_number(category_elo.get('rating'), 1)),
                ('Driver rank', f"#{category_elo['rank']}" if category_elo else 'N/A'),
            ])
            + '</section>'
        )

    body = (
        '<nav class="profile-nav">'
        '<a href="../index.html"><img class="header-logo" src="../logo.png" alt="OOFS Analytics"></a>'
        '<header class="profile-heading">'
                f'<h1>{html.escape(display_name)}</h1>'
                f'<p>{html.escape(" | ".join(details))}</p>'
        '</header>'
        '<a href="index.html">Back to all driver profiles</a>'
        '</nav>'
        '<section class="profile-section"><h2>Overall career stats</h2>'
        + _metric_grid([
            ('Race starts', stats['starts']),
            ('Wins', stats['wins']),
            ('Podiums', stats['podiums']),
            ('Pole positions', stats['poles']),
            ('Best finish', _format_number(stats['best_finish'])),
            ('Average finish', _format_number(stats['average_finish'], 2)),
            ('DNFs', stats['dnfs']),
            ('Categories', len(categories)),
            ('Seasons raced', len({record['season_id'] for record in races})),
            ('Laps completed', _format_number(stats['laps'])),
        ])
        + '</section>'
        + ''.join(category_sections)
        + '<section class="profile-section"><h2>Recent race results</h2>'
        + _render_results(races)
        + '</section>'
        + f'<footer class="profile-footer">Generated from OOFS event data on {html.escape(generated_date)}.</footer>'
    )
    return _base_page(f'{display_name} | Driver Profile', body)


def _slugify(name):
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return slug or 'driver'


def generate_driver_pages(output_dir=OUTPUT_DIR, data_root=DATA_ROOT,
                          config_root=CONFIG_ROOT, generated_date=None):
    """Write an index and one profile page for every driver in the CSV data."""
    from datetime import date

    generated_date = generated_date or date.today().isoformat()
    profiles = collect_driver_records(data_root, config_root)
    elo_lookup = _build_elo_lookup(config_root, data_root)
    os.makedirs(output_dir, exist_ok=True)

    slugs = {}
    for name in sorted(profiles, key=str.casefold):
        base_slug = _slugify(name)
        slug = base_slug
        suffix = 2
        while slug in slugs.values():
            slug = f'{base_slug}-{suffix}'
            suffix += 1
        slugs[name] = slug
        output_path = os.path.join(output_dir, f'{slug}.html')
        with open(output_path, 'w', encoding='utf-8') as page_file:
            page_file.write(
                render_driver_page(name, profiles[name], generated_date, elo_lookup)
            )

    profile_links = []
    profile_initials = {name[0].upper() for name in profiles if name}
    for name in sorted(profiles, key=str.casefold):
        profile = profiles[name]
        categories = sorted({
            record['category_label']
            for record in profile['race'] + profile['qualifying']
        })
        profile_links.append(
            f'<a class="profile-entry" data-initial="{html.escape(name[0].upper(), quote=True)}" '
            f'data-name="{html.escape(name.casefold(), quote=True)}" '
            f'href="{html.escape(slugs[name])}.html">'
            f'{html.escape(html_lib.format_driver_name(name))}'
            f'<small>{len(profile["race"])} race results | '
            f'{html.escape(", ".join(categories))}</small></a>'
        )

    alphabet_buttons = ['<button type="button" data-letter="all" aria-pressed="true">All</button>']
    alphabet_buttons.extend(
        '<button type="button" data-letter="{letter}" aria-pressed="false"{disabled}>{letter}</button>'.format(
            letter=letter,
            disabled='' if letter in profile_initials else ' disabled',
        )
        for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    )
    index_body = (
        '<nav class="profile-nav">'
        '<a href="../index.html"><img class="header-logo" src="../logo.png" alt="OOFS Analytics"></a>'
        '<header class="profile-heading"><h1>Driver Profiles</h1>'
        f'<p>{len(profiles)} drivers from configured event CSVs</p></header>'
        '</nav>'
        '<section class="profile-section">'
        '<label class="sr-only" for="profileSearch">Search drivers</label>'
        '<input class="profile-search" id="profileSearch" type="search" '
        'placeholder="Search driver names" autocomplete="off">'
        '<div class="alphabet-bar" role="group" aria-label="Filter profiles by first letter">'
        + ''.join(alphabet_buttons)
        + '</div>'
        f'<p class="profile-count" id="profileCount" aria-live="polite">Showing {len(profiles)} of {len(profiles)} drivers</p>'
        '<div class="profile-list" id="profileList">'
        + ''.join(profile_links)
        + '</div><p class="profile-empty" id="profileEmpty">No profiles match your search.</p>'
        '</section>'
        + '''<script>
            const profileSearch = document.getElementById('profileSearch');
            const profileEntries = Array.from(document.querySelectorAll('.profile-entry'));
            const letterButtons = Array.from(document.querySelectorAll('.alphabet-bar button'));
            const profileCount = document.getElementById('profileCount');
            const profileEmpty = document.getElementById('profileEmpty');
            const availableLetters = new Set(profileEntries.map(entry => entry.dataset.initial));
            let activeLetter = 'all';

            function filterProfiles() {
                const query = profileSearch.value.trim().toLocaleLowerCase();
                let visibleCount = 0;
                for (const entry of profileEntries) {
                    const matchesLetter = activeLetter === 'all' || entry.dataset.initial === activeLetter;
                    const matchesQuery = entry.dataset.name.includes(query);
                    const isVisible = matchesLetter && matchesQuery;
                    entry.hidden = !isVisible;
                    if (isVisible) visibleCount += 1;
                }
                profileCount.textContent = `Showing ${visibleCount} of ${profileEntries.length} drivers`;
                profileEmpty.style.display = visibleCount ? 'none' : 'block';
            }

            profileSearch.addEventListener('input', () => {
                const hasQuery = profileSearch.value.trim().length > 0;
                if (hasQuery) {
                    activeLetter = 'all';
                    for (const button of letterButtons) {
                        button.setAttribute('aria-pressed', String(button.dataset.letter === 'all'));
                    }
                }
                for (const button of letterButtons) {
                    button.disabled = button.dataset.letter !== 'all'
                        && (hasQuery || !availableLetters.has(button.dataset.letter));
                }
                filterProfiles();
            });
            for (const button of letterButtons) {
                button.addEventListener('click', () => {
                    activeLetter = button.dataset.letter;
                    for (const candidate of letterButtons) {
                        candidate.setAttribute('aria-pressed', String(candidate === button));
                    }
                    filterProfiles();
                });
            }
        </script>'''
        + f'<footer class="profile-footer">Generated from OOFS event data on {html.escape(generated_date)}.</footer>'
    )
    index_path = os.path.join(output_dir, 'index.html')
    with open(index_path, 'w', encoding='utf-8') as index_file:
        index_file.write(_base_page('Driver Profiles', index_body))
    return len(profiles)


def main():
    driver_count = generate_driver_pages()
    print(f'Generated {driver_count} driver profiles in {OUTPUT_DIR}')


if __name__ == '__main__':
    main()