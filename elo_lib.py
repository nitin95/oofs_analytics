"""Calculate race-result Elo ratings and render static ranking pages."""

import html
import os
import shutil
from datetime import datetime

import pandas as pd

import csv_lib
import driver_blacklist
import html_lib


INITIAL_RATING = 1500.0
K_FACTOR = 32.0
FIRST_SEASON_GAIN_K_FACTOR = 40.0
FIRST_SEASON_LOSS_K_FACTOR = 24.0
SERIES_ORDER = ('sprint', 'multiclass')
CATEGORY_SPECS = (
    ('Sprint GT3', 'sprint', 'gt3', 'sprint_gt3'),
    ('Sprint LMP3', 'sprint', 'lmp3', 'sprint_lmp3'),
    ('Endurance GT3', 'multiclass', 'gt3', 'multiclass_gt3'),
    ('Endurance Prototype', 'multiclass', 'prototype', 'multiclass_prototype'),
)


def _category_mask(classes, category):
    class_names = classes.fillna('').astype(str).str.lower()
    if category == 'gt3':
        return class_names.str.contains('gt3')
    if category == 'lmp3':
        return class_names.str.contains('lmp3') | class_names.eq('p3')
    return class_names.str.contains('hyper|lmp2|p2ur', regex=True)


def _descriptor_flag_mask(frame, column):
    values = frame.get(column)
    if values is None:
        return pd.Series(False, index=frame.index)
    return values.fillna(False).astype(str).str.strip().str.lower().isin(
        ('true', '1')
    )


def _overall_class_name(value):
    if pd.isna(value):
        return ''
    class_name = str(value).strip()
    normalized = class_name.lower()
    if 'gt3' in normalized:
        return 'GT3'
    if 'lmp3' in normalized or normalized == 'p3':
        return 'LMP3'
    if 'hyper' in normalized:
        return 'Hyper'
    if 'lmp2' in normalized or 'p2ur' in normalized:
        return 'LMP2/P2UR'
    return class_name


def _expected_score(rating, opponent_rating):
    return 1 / (1 + 10 ** ((opponent_rating - rating) / 400))


def update_event_ratings(ratings, finish_positions, k_factors=None):
    """Apply simultaneous pairwise Elo updates with per-driver gain/loss K values."""
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
        driver_k_factors = (k_factors or {}).get(driver, K_FACTOR)
        if isinstance(driver_k_factors, tuple):
            gain_k_factor, loss_k_factor = driver_k_factors
        else:
            gain_k_factor = loss_k_factor = driver_k_factors
        k_factor = gain_k_factor if score_delta > 0 else loss_k_factor
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
                (FIRST_SEASON_GAIN_K_FACTOR, FIRST_SEASON_LOSS_K_FACTOR)
                if first_season_by_driver[driver] == event['season_id']
                else (K_FACTOR, K_FACTOR)
            )
            for driver in finish_positions
        }
        ratings = update_event_ratings(ratings, finish_positions, k_factors)
    return ratings


def _build_rankings(config_root='assets/json', csv_root='assets/csv'):
    """Build category and all-series Elo standings from configured results."""
    blacklisted_names = driver_blacklist.load_blacklisted_names(
        csv_lib.normalize_driver_name
    )
    seasons = csv_lib.load_season_metadata(config_root)
    category_events = {
        spec[3]: {'race': [], 'quali': []} for spec in CATEGORY_SPECS
    }
    category_dns_counts = {spec[3]: {} for spec in CATEGORY_SPECS}
    overall_dns_counts = {}
    overall_class_events = {}
    category_by_key = {spec[3]: spec for spec in CATEGORY_SPECS}
    event_order = 0
    quali_order = 0
    category_order = {}

    for season_index, (season_id, season_info) in enumerate(seasons.items()):
        config = csv_lib.load_season_config(season_id, config_root)
        for series in SERIES_ORDER:
            for event_group, rating_type in (('races', 'race'), ('qualis', 'quali')):
                configured_events = config.get(f'{series}_{event_group}', {})
                for event_index, (filename, event_info) in enumerate(
                    configured_events.items()
                ):
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

                    dns_rows = event_data.iloc[0:0]
                    if rating_type == 'race':
                        dns_mask = _descriptor_flag_mask(event_data, 'is_DNS')
                        dns_rows = event_data.loc[dns_mask].copy()
                        event_data = event_data.loc[~dns_mask]

                    if 'CarClass' not in event_data or 'Position' not in event_data:
                        continue
                    driver_column = (
                        'Driver_name' if 'Driver_name' in event_data else 'Driver'
                    )
                    if driver_column not in event_data:
                        continue

                    if not dns_rows.empty:
                        dns_rows['_driver'] = (
                            dns_rows[driver_column].fillna('').astype(str).str.strip()
                        )
                        dns_rows['_car_class'] = dns_rows['CarClass'].map(
                            _overall_class_name
                        )
                        dns_rows = dns_rows[
                            dns_rows['_driver'].ne('')
                            & dns_rows['_car_class'].ne('')
                        ]
                        dns_rows = dns_rows.loc[
                            ~dns_rows['_driver'].map(
                                csv_lib.normalize_driver_name
                            ).isin(blacklisted_names)
                        ]
                        for car_class, class_rows in dns_rows.groupby(
                            '_car_class', sort=False
                        ):
                            counts = overall_dns_counts.setdefault(car_class, {})
                            for driver in set(class_rows['_driver']):
                                counts[driver] = counts.get(driver, 0) + 1

                        for _, category_series, class_name, slug in CATEGORY_SPECS:
                            if category_series != series:
                                continue
                            category_dns_rows = dns_rows.loc[
                                _category_mask(dns_rows['CarClass'], class_name)
                            ]
                            counts = category_dns_counts[slug]
                            for driver in set(category_dns_rows['_driver']):
                                counts[driver] = counts.get(driver, 0) + 1

                    positions = pd.to_numeric(event_data['Position'], errors='coerce')
                    driver_names = event_data[driver_column].fillna('').astype(str).str.strip()
                    all_class_rows = event_data.copy()
                    all_class_rows['_position'] = positions
                    all_class_rows['_driver'] = driver_names
                    all_class_rows['_car_class'] = event_data['CarClass'].map(
                        _overall_class_name
                    )
                    all_class_rows = all_class_rows[
                        all_class_rows['_driver'].ne('')
                        & all_class_rows['_position'].notna()
                        & all_class_rows['_car_class'].ne('')
                    ]
                    all_class_rows = all_class_rows.loc[
                        ~all_class_rows['_driver'].map(
                            csv_lib.normalize_driver_name
                        ).isin(blacklisted_names)
                    ]
                    for car_class, class_rows in all_class_rows.groupby(
                        '_car_class', sort=False
                    ):
                        finish_positions = (
                            class_rows.groupby('_driver', sort=False)['_position']
                            .min()
                            .sort_values(kind='stable')
                            .to_dict()
                        )
                        dnf_drivers = set()
                        if rating_type == 'race':
                            dnf_drivers = set(class_rows.loc[
                                _descriptor_flag_mask(class_rows, 'is_DNF'),
                                '_driver',
                            ])
                        overall_class_events.setdefault(
                            car_class, {'race': [], 'quali': []}
                        )[rating_type].append({
                            'event_order': current_event_order,
                            'overall_order': (
                                season_index,
                                event_index,
                                SERIES_ORDER.index(series),
                            ),
                            'season_id': season_id,
                            'season': season_info.get('name', season_id),
                            'track': event_info.get('name', os.path.splitext(filename)[0]),
                            'finish_positions': finish_positions,
                            'dnf_drivers': dnf_drivers,
                        })

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
                        category_rows = category_rows.loc[
                            ~category_rows['_driver'].map(
                                csv_lib.normalize_driver_name
                            ).isin(blacklisted_names)
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
                        if rating_type == 'race':
                            dnf_drivers = set(category_rows.loc[
                                _descriptor_flag_mask(category_rows, 'is_DNF'),
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
                    'dns': 0,
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
                    'dns': 0,
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

        for driver, dns_count in category_dns_counts[slug].items():
            stats = driver_stats.setdefault(driver, {
                'starts': 0,
                'position_total': 0.0,
                'dnfs': 0,
                'dns': 0,
                'wins': 0,
                'pole_positions': 0,
                'podiums': 0,
            })
            stats['dns'] += dns_count

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
                    'dns': 0,
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

    overall_standings = []
    for car_class, event_groups in overall_class_events.items():
        race_events = sorted(
            event_groups['race'], key=lambda event: event['overall_order']
        )
        quali_events = sorted(
            event_groups['quali'], key=lambda event: event['overall_order']
        )
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
                    'dns': 0,
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
                    'dns': 0,
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

        for driver, dns_count in overall_dns_counts.get(car_class, {}).items():
            stats = driver_stats.setdefault(driver, {
                'starts': 0,
                'position_total': 0.0,
                'dnfs': 0,
                'dns': 0,
                'wins': 0,
                'pole_positions': 0,
                'podiums': 0,
            })
            stats['dns'] += dns_count

        for driver in race_ratings.keys() | quali_ratings.keys():
            stats = driver_stats.get(driver, {})
            overall_standings.append({
                'driver': driver,
                'car_class': car_class,
                'race_rating': race_ratings.get(driver),
                'quali_rating': quali_ratings.get(driver),
                'elo_differential': (
                    race_ratings[driver] - quali_ratings[driver]
                    if driver in race_ratings and driver in quali_ratings
                    else None
                ),
                'starts': stats.get('starts', 0),
                'position_total': stats.get('position_total', 0.0),
                'dnfs': stats.get('dnfs', 0),
                'dns': stats.get('dns', 0),
                'wins': stats.get('wins', 0),
                'pole_positions': stats.get('pole_positions', 0),
                'podiums': stats.get('podiums', 0),
                'last_event': stats.get('last_event', '—'),
                'average_finish_position': (
                    stats['position_total'] / stats['starts']
                    if stats.get('starts') else None
                ),
            })

    class_order = {name: index for index, name in enumerate(overall_class_events)}
    overall_standings.sort(key=lambda row: (
        class_order[row['car_class']],
        row['race_rating'] is None,
        -(row['race_rating'] or 0),
        -(row['quali_rating'] or 0),
        row['driver'],
    ))
    previous_class = None
    class_rank = 0
    for standing in overall_standings:
        if standing['car_class'] != previous_class:
            previous_class = standing['car_class']
            class_rank = 0
        class_rank += 1
        standing['rank'] = class_rank

    return rankings, overall_standings


def build_rankings(config_root='assets/json', csv_root='assets/csv'):
    """Build race and qualifying Elo standings for each series/class."""
    rankings, _ = _build_rankings(config_root, csv_root)
    return rankings


def _render_table(standings):
    rows = []
    for rank, standing in enumerate(standings, start=1):
        race_rating = standing['race_rating']
        quali_rating = standing['quali_rating']
        elo_differential = standing['elo_differential']
        average_finish = standing['average_finish_position']
        cells = [
            f'<td>{standing.get("rank", rank)}</td>',
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
            f'<td>{standing["dns"]}</td>',
            f'<td>{standing["wins"]}</td>',
            f'<td>{standing["pole_positions"]}</td>',
            f'<td>{standing["podiums"]}</td>',
            f'<td>{html.escape(standing.get("last_event", "—"))}</td>',
        ]
        rows.append(f'<tr>{"".join(cells)}</tr>')
    return '\n'.join(rows)


def _render_table_html(standings):
    headers = (
        ('Rank', 'number'), ('Driver', 'text'), ('Race ELO', 'number'),
        ('Quali ELO', 'number'), ('ELO Diff', 'number'), ('Starts', 'number'),
        ('Avg Finish', 'number'), ('DNFs', 'number'), ('DNS', 'number'),
        ('Wins', 'number'),
        ('Pole Positions', 'number'), ('Podiums', 'number'),
    )
    header_html = ''.join(
        f'<th scope="col" aria-sort="none"><button class="elo-sort" '
        f'type="button" data-sort-column="{index}" data-sort-type="{sort_type}" '
        f'aria-label="Sort by {label} ascending">{label} '
        '<span class="elo-sort-indicator" aria-hidden="true">&#8597;</span>'
        '</button></th>'
        for index, (label, sort_type) in enumerate(headers)
    )
    return (
        '<div class="table-container"><table class="elo-table"><thead><tr>'
        f'{header_html}<th scope="col">Last Event</th>'
        '</tr></thead><tbody>'
        f'{_render_table(standings)}'
        '</tbody></table></div>'
    )


def _render_overall_tables(standings):
    classes = {}
    for standing in standings:
        classes.setdefault(standing['car_class'], []).append(standing)
    return '\n'.join(
        f'<section class="elo-class-ranking" id="overall-class-{index}">'
        f'<h3>{html.escape(car_class)}</h3>'
        f'{_render_table_html(class_standings)}'
        '</section>'
        for index, (car_class, class_standings) in enumerate(classes.items())
    )


def _render_sidebar(rankings, active_slug, page_names, overall_standings=()):
    links = []
    for ranking in rankings:
        active = ' active' if ranking['slug'] == active_slug else ''
        links.append(
            f'<li><a class="{active.strip()}" href="{page_names[ranking["slug"]]}">'
            f'{html.escape(ranking["title"])}</a></li>'
        )
    overall_active = ' class="active"' if active_slug == 'overall' else ''
    overall_sublist = ''
    if active_slug == 'overall':
        overall_classes = dict.fromkeys(
            standing['car_class'] for standing in overall_standings
        )
        if overall_classes:
            category_links = ''.join(
                f'<li><a href="#overall-class-{index}">{html.escape(car_class)}</a></li>'
                for index, car_class in enumerate(overall_classes)
            )
            overall_sublist = f'<ul class="elo-subnav">{category_links}</ul>'
    links.append(
        f'<li><a{overall_active} href="elo_overall.html">'
        f'OOFS per-class rankings</a>{overall_sublist}</li>'
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
    rankings, overall_standings = _build_rankings(config_root, csv_root)
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
            '{tables}': _render_table_html(ranking['standings']),
            '{method}': (
                "1500 starting rating · first category season K=40 for gains and "
                'K=24 for losses, then K=32 · ELO difference = Race ELO minus Quali ELO'
            ),
            '{generated_at}': generated_at,
        }
        for placeholder, value in replacements.items():
            page = page.replace(placeholder, value)
        output_path = os.path.join(output_root, page_names[ranking['slug']])
        with open(output_path, 'w', encoding='utf-8') as output_file:
            output_file.write(page)
        print(f'  Generated {output_path}')

    overall_page = template
    replacements = {
        '{title}': 'OOFS per-class rankings',
        '{sidebar}': _render_sidebar(
            rankings, 'overall', page_names, overall_standings
        ),
        '{tables}': _render_overall_tables(overall_standings),
        '{method}': (
            'Ratings and ranks are independent for each car class; '
            'drivers are only compared with others in the same class.'
        ),
        '{generated_at}': generated_at,
    }
    for placeholder, value in replacements.items():
        overall_page = overall_page.replace(placeholder, value)
    overall_path = os.path.join(output_root, 'elo_overall.html')
    with open(overall_path, 'w', encoding='utf-8') as output_file:
        output_file.write(overall_page)
    print(f'  Generated {overall_path}')

    return [
        *(os.path.join(output_root, name) for name in page_names.values()),
        overall_path,
    ]