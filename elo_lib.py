"""Calculate race-result Elo ratings and render static ranking pages."""

import html
import os
import shutil
from datetime import datetime

import pandas as pd

import csv_lib
import html_lib


INITIAL_RATING = 1500.0
K_FACTOR = 32.0
FIRST_SEASON_K_FACTOR = 64.0
SERIES_ORDER = ('sprint', 'multiclass')
CATEGORY_SPECS = (
    ('Sprint GT3', 'sprint', 'gt3', 'sprint_gt3'),
    ('Sprint LMP3', 'sprint', 'lmp3', 'sprint_lmp3'),
    ('Multiclass GT3', 'multiclass', 'gt3', 'multiclass_gt3'),
    ('Multiclass Prototype', 'multiclass', 'prototype', 'multiclass_prototype'),
)


def _category_mask(classes, category):
    class_names = classes.fillna('').astype(str).str.lower()
    if category == 'gt3':
        return class_names.str.contains('gt3')
    if category == 'lmp3':
        return class_names.str.contains('lmp3') | class_names.eq('p3')
    return class_names.str.contains('hyper|lmp2|p2ur', regex=True)


def _expected_score(rating, opponent_rating):
    return 1 / (1 + 10 ** ((opponent_rating - rating) / 400))


def update_event_ratings(ratings, finish_positions, k_factors=None):
    """Apply simultaneous pairwise Elo updates with optional per-driver K values."""
    if len(finish_positions) < 2:
        return dict(ratings)

    starting_ratings = {
        driver: ratings.get(driver, INITIAL_RATING)
        for driver in finish_positions
    }
    updates = {}
    opponents_count = len(finish_positions) - 1

    for driver, position in finish_positions.items():
        score_delta = 0.0
        for opponent, opponent_position in finish_positions.items():
            if opponent == driver:
                continue
            actual_score = (
                1.0 if position < opponent_position
                else 0.5 if position == opponent_position
                else 0.0
            )
            score_delta += actual_score - _expected_score(
                starting_ratings[driver], starting_ratings[opponent]
            )
        k_factor = (k_factors or {}).get(driver, K_FACTOR)
        updates[driver] = k_factor * score_delta / opponents_count

    return {
        driver: ratings.get(driver, INITIAL_RATING) + updates.get(driver, 0.0)
        for driver in ratings.keys() | starting_ratings.keys()
    }


def _calculate_ratings(events):
    ratings = {}
    first_season_by_driver = {}
    for event in events:
        for driver in event['finish_positions']:
            first_season_by_driver.setdefault(driver, event['season_id'])

    for event in events:
        finish_positions = event['finish_positions']
        for driver in finish_positions:
            ratings.setdefault(driver, INITIAL_RATING)
        k_factors = {
            driver: (
                FIRST_SEASON_K_FACTOR
                if first_season_by_driver[driver] == event['season_id']
                else K_FACTOR
            )
            for driver in finish_positions
        }
        ratings = update_event_ratings(ratings, finish_positions, k_factors)
    return ratings


def build_rankings(config_root='assets/json', csv_root='assets/csv'):
    """Build race and qualifying Elo standings for each series/class."""
    seasons = csv_lib.load_season_metadata(config_root)
    category_events = {
        spec[3]: {'race': [], 'quali': []} for spec in CATEGORY_SPECS
    }
    category_by_key = {spec[3]: spec for spec in CATEGORY_SPECS}
    event_order = 0
    quali_order = 0
    category_order = {}

    for season_id, season_info in seasons.items():
        config = csv_lib.load_season_config(season_id, config_root)
        for series in SERIES_ORDER:
            for event_group, rating_type in (('races', 'race'), ('qualis', 'quali')):
                for filename, event_info in config.get(
                    f'{series}_{event_group}', {}
                ).items():
                    if rating_type == 'race':
                        current_event_order = event_order
                        event_order += 1
                    else:
                        current_event_order = quali_order
                        quali_order += 1

                    csv_path = csv_lib.build_csv_path(
                        season_id, series, filename, output_root=csv_root
                    )
                    if not os.path.exists(csv_path):
                        continue
                    try:
                        event_data = pd.read_csv(csv_path)
                    except (OSError, pd.errors.ParserError):
                        continue

                    if 'CarClass' not in event_data or 'Position' not in event_data:
                        continue
                    driver_column = (
                        'Driver_name' if 'Driver_name' in event_data else 'Driver'
                    )
                    if driver_column not in event_data:
                        continue

                    positions = pd.to_numeric(event_data['Position'], errors='coerce')
                    driver_names = event_data[driver_column].fillna('').astype(str).str.strip()
                    for _, category_series, class_name, slug in CATEGORY_SPECS:
                        if category_series != series:
                            continue
                        category_rows = event_data.loc[
                            _category_mask(event_data['CarClass'], class_name)
                        ].copy()
                        category_rows['_position'] = positions.loc[category_rows.index]
                        category_rows['_driver'] = driver_names.loc[category_rows.index]
                        category_rows = category_rows[
                            category_rows['_driver'].ne('')
                            & category_rows['_position'].notna()
                        ]
                        if category_rows.empty:
                            continue

                        finish_positions = (
                            category_rows.groupby('_driver', sort=False)['_position']
                            .min()
                            .sort_values(kind='stable')
                            .to_dict()
                        )
                        dnf_drivers = set()
                        if rating_type == 'race' and 'FinishStatus' in category_rows:
                            dnf_drivers = set(category_rows.loc[
                                category_rows['FinishStatus'].fillna('').astype(str)
                                .str.contains('DNF', case=False),
                                '_driver',
                            ])
                        category_events[slug][rating_type].append({
                            'event_order': current_event_order,
                            'season_id': season_id,
                            'season': season_info.get('name', season_id),
                            'track': event_info.get('name', os.path.splitext(filename)[0]),
                            'finish_positions': finish_positions,
                            'dnf_drivers': dnf_drivers,
                        })
                        if rating_type == 'race':
                            category_order[slug] = min(
                                category_order.get(slug, current_event_order),
                                current_event_order,
                            )
                        elif slug not in category_order:
                            category_order[slug] = len(seasons) * 10000 + current_event_order

    rankings = []
    ordered_categories = sorted(
        (
            (category_order[slug], slug, events)
            for slug, events in category_events.items()
            if events['race'] or events['quali']
        ),
        key=lambda item: item[0],
    )
    for _, slug, event_groups in ordered_categories:
        race_events = event_groups['race']
        quali_events = event_groups['quali']
        race_ratings = _calculate_ratings(race_events)
        quali_ratings = _calculate_ratings(quali_events)
        driver_stats = {}

        for event in quali_events:
            finish_positions = event['finish_positions']
            pole_position = min(finish_positions.values())
            for driver, position in finish_positions.items():
                stats = driver_stats.setdefault(driver, {
                    'starts': 0,
                    'position_total': 0.0,
                    'dnfs': 0,
                    'wins': 0,
                    'pole_positions': 0,
                    'podiums': 0,
                })
                stats['pole_positions'] += position == pole_position

        for event in race_events:
            finish_positions = event['finish_positions']
            dnf_drivers = event.get('dnf_drivers', set())
            ordered = sorted(finish_positions.items(), key=lambda item: item[1])
            for position_index, (driver, position) in enumerate(ordered, start=1):
                stats = driver_stats.setdefault(driver, {
                    'starts': 0,
                    'position_total': 0.0,
                    'dnfs': 0,
                    'wins': 0,
                    'pole_positions': 0,
                    'podiums': 0,
                })
                stats['starts'] += 1
                stats['position_total'] += position
                stats['dnfs'] += driver in dnf_drivers
                stats['wins'] += position_index == 1
                stats['podiums'] += position_index <= 3
                stats['last_event'] = f"{event['season']} · {event['track']}"

        all_drivers = race_ratings.keys() | quali_ratings.keys()
        standings = [
            {
                'driver': driver,
                'race_rating': race_ratings.get(driver),
                'quali_rating': quali_ratings.get(driver),
                'elo_differential': (
                    race_ratings[driver] - quali_ratings[driver]
                    if driver in race_ratings and driver in quali_ratings
                    else None
                ),
                **driver_stats.get(driver, {
                    'starts': 0,
                    'position_total': 0.0,
                    'dnfs': 0,
                    'wins': 0,
                    'pole_positions': 0,
                    'podiums': 0,
                    'last_event': '—',
                }),
                'average_finish_position': (
                    driver_stats[driver]['position_total'] / driver_stats[driver]['starts']
                    if driver_stats.get(driver, {}).get('starts') else None
                ),
            }
            for driver in all_drivers
        ]
        standings.sort(key=lambda row: (
            row['race_rating'] is None,
            -(row['race_rating'] or 0),
            -(row['quali_rating'] or 0),
            row['driver'],
        ))
        rankings.append({
            'title': category_by_key[slug][0],
            'slug': slug,
            'standings': standings,
        })

    return rankings


def _render_table(standings):
    rows = []
    for rank, standing in enumerate(standings, start=1):
        race_rating = standing['race_rating']
        quali_rating = standing['quali_rating']
        elo_differential = standing['elo_differential']
        average_finish = standing['average_finish_position']
        cells = [
            f'<td>{rank}</td>',
            f'<td>{html.escape(html_lib.format_driver_name(standing["driver"]))}</td>',
            f'<td>{race_rating:.1f}</td>' if race_rating is not None else '<td>&mdash;</td>',
            f'<td>{quali_rating:.1f}</td>'
            if quali_rating is not None else '<td>&mdash;</td>',
            f'<td>{elo_differential:+.1f}</td>'
            if elo_differential is not None else '<td>&mdash;</td>',
            f'<td>{standing["starts"]}</td>',
            f'<td>{average_finish:.2f}</td>'
            if average_finish is not None else '<td>&mdash;</td>',
            f'<td>{standing["dnfs"]}</td>',
            f'<td>{standing["wins"]}</td>',
            f'<td>{standing["pole_positions"]}</td>',
            f'<td>{standing["podiums"]}</td>',
            f'<td>{html.escape(standing["last_event"])}</td>',
        ]
        rows.append(f'<tr>{"".join(cells)}</tr>')
    return '\n'.join(rows)


def _render_sidebar(rankings, active_slug, page_names):
    links = []
    for ranking in rankings:
        active = ' active' if ranking['slug'] == active_slug else ''
        links.append(
            f'<li><a class="{active.strip()}" href="{page_names[ranking["slug"]]}">'
            f'{html.escape(ranking["title"])}</a></li>'
        )
    return (
        '<aside class="sidebar elo-sidebar"><div class="sidebar-content">'
        '<a href="index.html"><img class="header-logo" src="logo.png" alt="OOFS Analytics"></a>'
        '<div class="section-group"><h4>Driver Rankings</h4>'
        f'<ul>{"".join(links)}</ul></div>'
        '</div></aside>'
    )


def generate_pages(
    output_root='docs',
    template_path=None,
    config_root='assets/json',
    csv_root='assets/csv',
):
    """Write the first chronological category to elo.html and its peers beside it."""
    rankings = build_rankings(config_root, csv_root)
    if not rankings:
        print('  No race CSV data available for Elo rankings')
        return []

    if template_path is None:
        template_path = os.path.join(
            os.path.dirname(__file__), 'templates', 'elo_page.html'
        )
    with open(template_path, 'r', encoding='utf-8') as template_file:
        template = template_file.read()

    page_names = {
        ranking['slug']: (
            'elo.html' if index == 0 else f"elo_{ranking['slug']}.html"
        )
        for index, ranking in enumerate(rankings)
    }
    generated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    os.makedirs(output_root, exist_ok=True)
    shutil.copyfile(
        os.path.join(os.path.dirname(__file__), 'templates', 'styles.css'),
        os.path.join(output_root, 'styles.css'),
    )
    for ranking in rankings:
        page = template
        replacements = {
            '{title}': html.escape(f"{ranking['title']} Elo Rankings"),
            '{sidebar}': _render_sidebar(rankings, ranking['slug'], page_names),
            '{standings}': _render_table(ranking['standings']),
            '{generated_at}': generated_at,
        }
        for placeholder, value in replacements.items():
            page = page.replace(placeholder, value)
        output_path = os.path.join(output_root, page_names[ranking['slug']])
        with open(output_path, 'w', encoding='utf-8') as output_file:
            output_file.write(page)
        print(f'  Generated {output_path}')

    return [os.path.join(output_root, name) for name in page_names.values()]