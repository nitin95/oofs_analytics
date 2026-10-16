"""Configuration, event CSV generation, and season comparison helpers."""

import argparse
import json
import os

import numpy as np
import pandas as pd

from lmu_descriptors import LMUDescriptor


SEASON_INFO_KEY = 'season_info'
DEFAULT_SEASON_CONFIG_ROOT = os.path.join(
    os.path.dirname(__file__), 'assets', 'json'
)

DRIVER_REPLACEMENTS = {
    'Greg Kach': 'Greg Kachadurian',
    'R McLean': 'Ross McLean',
    'Ricky Swaby': 'Ricardo Swaby',
    'p thomas': 'Parker Thomas',
    'DAN POULIN': 'Dan Jr Poulin',
    'David Carter': 'Dave Carter',
    'David Carter#5529': 'Dave Carter',
    'John P': 'John Pflibsen',
    'Ayrton Senna': 'Ayrton Torres',
    'Avi Ganti': 'Avinash Ganti',
    'p thom': 'Parker Thomas',
    'J P#2423': 'J.P.',
    'G Wulf': 'Gene Wulf',
    'C M Wilson': 'Chris Wilson',
    'T Ducharme': 'Tim Ducharme',
}

def load_season_config(season_id, config_root='assets/json'):
    """Load event metadata and pace references from a season JSON file."""
    config_path = os.path.join(config_root, f'{season_id}.json')
    with open(config_path, 'r', encoding='utf-8') as config_file:
        return json.load(config_file)


def load_season_metadata(config_root=DEFAULT_SEASON_CONFIG_ROOT):
    """Load display metadata for every season JSON in the configuration folder."""
    seasons = {}
    for filename in sorted(os.listdir(config_root)):
        if not filename.endswith('.json'):
            continue
        season_id = os.path.splitext(filename)[0]
        config = load_season_config(season_id, config_root)
        if SEASON_INFO_KEY in config:
            seasons[season_id] = config[SEASON_INFO_KEY]
    return seasons


SEASONS = load_season_metadata()

def normalize_driver_name(driver_name):
    """Normalize an XML driver name to the canonical name used by the reports."""
    name = str(driver_name)
    if 'LMGT3' in name:
        name = name.split('LMGT3')[0].strip()
    else:
        name = name.strip()

    for old_name, new_name in DRIVER_REPLACEMENTS.items():
        if name == old_name:
            name = new_name
    return name

def get_driver_category(car_class, series_type):
    """Map XML car classes to stable categories for rookie history."""
    car_class = str(car_class).lower()
    if 'gt3' in car_class:
        return 'GT3'
    if series_type == 'sprint' and ('lmp3' in car_class or car_class == 'p3'):
        return 'LMP3'
    if series_type == 'multiclass' and ('hyper' in car_class or 'lmp2' in car_class):
        return 'PROTOTYPE'
    return None

def get_configured_event_csvs(season_id, series_type):
    """Return configured event CSV paths for a series, including quali and races."""
    season_config = load_season_config(season_id)
    return [
        build_csv_path(season_id, series_type, filename)
        for section_name, races in season_config.items()
        if section_name.startswith(series_type)
        for filename in races
    ]

def iter_series_driver_records(season_id, series_type):
    """Yield canonical driver names and categories from configured event CSVs."""
    for csv_path in get_configured_event_csvs(season_id, series_type):
        if not os.path.exists(csv_path):
            continue
        try:
            event_data = pd.read_csv(csv_path)
        except (OSError, pd.errors.ParserError):
            continue

        for _, driver in event_data.iterrows():
            name = normalize_driver_name(driver.get('Driver_name', driver.get('Driver', 'Unknown')))
            car_class = driver.get('CarClass', '')
            yield name, get_driver_category(car_class, series_type)

def get_rookie_driver_names(season_id, series_type, current_driver_names, category=None):
    """Find drivers new to this series or to their current category."""
    season_ids = list(SEASONS)
    if season_id not in season_ids or season_ids.index(season_id) == 0:
        return set()

    current_names = {normalize_driver_name(name) for name in current_driver_names}
    previous_names = set()
    previous_categories = {}
    for previous_season in season_ids[:season_ids.index(season_id)]:
        for name, driver_category in iter_series_driver_records(previous_season, series_type):
            previous_names.add(name)
            if driver_category:
                previous_categories.setdefault(name, set()).add(driver_category)

    current_categories = {}
    if category:
        if category == 'P2UR' or category == 'Hyper':
            category = 'PROTOTYPE'
        for name in current_names:
            current_categories[name] = {category}
    else:
        for name, driver_category in iter_series_driver_records(season_id, series_type):
            if name in current_names and driver_category:
                current_categories.setdefault(name, set()).add(driver_category)

    return {
        name for name in current_names
        if name not in previous_names
        or any(
            driver_category not in previous_categories.get(name, set())
            for driver_category in current_categories.get(name, set())
        )
    }

def mark_rookies(comparison_df, season_id, series_type, category=None):
    """Add a presentation flag without changing canonical driver names."""
    comparison_df = comparison_df.copy()
    rookie_names = get_rookie_driver_names(
        season_id, series_type, comparison_df['Driver_name'], category
    )
    comparison_df['is_rookie'] = comparison_df['Driver_name'].isin(rookie_names)
    return comparison_df

def build_csv_path(season_id, series_type, xml_filename, output_root='assets/csv'):
    """Return the CSV path corresponding to a configured XML event filename."""
    csv_filename = os.path.splitext(xml_filename)[0] + '.csv'
    return os.path.join(output_root, season_id, series_type, csv_filename)

def season_has_sprint_class_data(season_id, class_names=('LMP3', 'P3')):
    """Return True if any sprint event CSV contains the requested class."""
    if season_id not in SEASONS:
        return False

    season_config = load_season_config(season_id)
    sprint_files = []
    sprint_files.extend(season_config.get('sprint_qualis', {}).keys())
    sprint_files.extend(season_config.get('sprint_races', {}).keys())

    for filename in sprint_files:
        csv_path = build_csv_path(season_id, 'sprint', filename)
        if not os.path.exists(csv_path):
            continue

        try:
            event_data = pd.read_csv(csv_path, usecols=['CarClass'])
        except (OSError, pd.errors.ParserError, ValueError):
            continue

        if event_data['CarClass'].fillna('').str.contains(
            '|'.join(class_names), case=False, regex=True
        ).any():
            return True

    return False

def get_multiclass_prototype_class(season_id):
    """Return the prototype label represented by configured multiclass CSV data."""
    class_counts = {'P2UR': 0, 'Hypercar': 0}
    for csv_path in get_configured_event_csvs(season_id, 'multiclass'):
        if not os.path.exists(csv_path):
            continue
        try:
            classes = pd.read_csv(csv_path, usecols=['CarClass'])['CarClass'].fillna('').str.lower()
        except (OSError, pd.errors.ParserError, ValueError):
            continue

        class_counts['P2UR'] += classes.str.contains('p2ur|lmp2', regex=True).sum()
        class_counts['Hypercar'] += classes.str.contains('hyper', regex=False).sum()

    if not any(class_counts.values()):
        return 'Hypercar'
    return max(class_counts, key=lambda class_name: class_counts[class_name])

def get_multiclass_championship_name(season_id):
    """Return the championship name used for this season's multiclass reports."""
    season_ids = list(SEASONS)
    if season_id in season_ids and season_ids.index(season_id) >= 2:
        return 'Endurance'
    return 'Multiclass'

def load_event_csv(csv_path, car_class=None):
    """Load one event CSV and optionally filter it to a requested class."""
    if not os.path.exists(csv_path):
        return None
    frame = pd.read_csv(csv_path)
    if car_class:
        class_name = car_class.upper()
        if class_name == 'P2UR':
            class_pattern = 'LMP2_ELMS|P2UR'
        elif class_name == 'PROTOTYPE':
            class_pattern = 'LMP2_ELMS|P2UR|Hyper'
        elif class_name in ('HYPER', 'HYPERCAR'):
            class_pattern = 'Hyper'
        elif class_name == 'LMP3':
            class_pattern = 'LMP3|^P3$'
        elif class_name == 'GT3':
            class_pattern = 'GT3'
        else:
            class_pattern = car_class
        frame = frame[frame['CarClass'].fillna('').str.contains(
            class_pattern, case=False, regex=True
        )].copy()
    return frame if not frame.empty else None

def extract_code_from_filename(filename, prefix):
    """Extract race code from filename (e.g., 's3-sc1-r.xml' -> 'sc1')"""
    # Remove prefix and extensions
    name = filename.replace(f'{prefix}-', '').replace('-r.xml', '').replace('-r.csv', '')
    name = name.replace('.xml', '').replace('.csv', '')
    return name

def load_races_dynamically(config_dict, xml_folder):
    """
    Load available races from config and return ordered lists.
    
    Returns:
        - race_codes: List of race codes in order
        - track_names: List of track names in order
        - code_to_track: Dict mapping code to track name
    """
    # loaded_races = {}
    race_codes = []
    track_names = []
    code_to_track = {}
    
    # Get prefix from first filename for code extraction
    if not config_dict:
        return race_codes, track_names, code_to_track
    first_filename = list(config_dict.keys())[0]
    if 'sc' in first_filename.split('-')[1]:
        prefix = 'sc'
    elif 'mc' in first_filename.split('-')[1]:
        prefix = 'mc'
    else:
        return race_codes, track_names, code_to_track
    
    # Sort config by filename to maintain order (s3-sc1, s3-sc2, etc.)
    sorted_items = sorted(config_dict.items(), key=lambda x: x[0])
    
    for filename, race_info in sorted_items:
        csv_path = os.path.join(xml_folder, filename)
        if os.path.exists(csv_path):
            track_name = race_info['name']
            
            # Extract code from filename
            code = extract_code_from_filename(filename, prefix)
            
            race_codes.append(code)
            track_names.append(track_name)
            code_to_track[code] = track_name
    
    return race_codes, track_names, code_to_track

def process_races_into_comparison_df(
    dfs_dict, race_codes, code_to_track, season_id=None, series_type=None, category=None
):
    """Merge per-event pace and descriptor columns into a season comparison."""
    if not race_codes:
        return None, [], [], [], []

    legacy_columns = [
        'laptime_sec', 'laptime_pct', 'laptime_pct_alien', 'avg_laptime',
        'avg_pace_pct_alien', 'stdev_laptime', 'stdev_pace_pct',
    ]
    descriptor_columns = [
        'Position', 'race_pace', 'pct_race_pace', 'consistency', 'reliability',
        'n_tracklimits', 'n_inchidents', 'pct_laps', 'n_stops',
        'pit_lane_pct_times',
    ]

    def event_frame(track_name, code):
        frame = dfs_dict[track_name]
        available = ['Driver_name'] + [
            column for column in legacy_columns + descriptor_columns
            if column in frame.columns
        ]
        renamed = {
            column: f'{column.lower()}_{code}'
            for column in descriptor_columns
            if column in frame.columns
        }
        renamed.update({
            column: f'{column}_{code}'
            for column in legacy_columns if column in frame.columns
        })
        return frame[available].rename(columns=renamed).copy()

    first_code = race_codes[0]
    first_track = code_to_track[first_code]
    if first_track not in dfs_dict:
        return None, [], [], [], []

    comparison_df = event_frame(first_track, first_code)
    pace_cols = [f'laptime_pct_alien_{first_code}']
    avg_pace_cols = [f'avg_pace_pct_alien_{first_code}']
    used_race_codes = [first_code]
    used_track_names = [first_track]

    for code in race_codes[1:]:
        track_name = code_to_track[code]
        if track_name not in dfs_dict:
            continue
        comparison_df = comparison_df.merge(
            event_frame(track_name, code), on='Driver_name', how='outer'
        )
        pace_cols.append(f'laptime_pct_alien_{code}')
        avg_pace_cols.append(f'avg_pace_pct_alien_{code}')
        used_race_codes.append(code)
        used_track_names.append(track_name)

    for column in avg_pace_cols:
        comparison_df[column] = comparison_df[column].replace(0.0, np.nan)
    comparison_df = comparison_df.dropna(subset=avg_pace_cols, how='all')
    comparison_df = comparison_df.sort_values('Driver_name').reset_index(drop=True)

    if season_id and series_type:
        comparison_df = mark_rookies(comparison_df, season_id, series_type, category)
    if comparison_df.empty:
        return None, pace_cols, avg_pace_cols, used_race_codes, used_track_names

    return comparison_df, pace_cols, avg_pace_cols, used_race_codes, used_track_names

def build_improvement_df(comparison_df, pace_cols):
    """Build improvement dataframe by comparing the season's early races vs late races"""
    improvement_df = comparison_df[['Driver_name'] + pace_cols].copy()
    improvement_df = improvement_df.replace(0.00, np.nan).dropna(subset=pace_cols, how='all')
    
    n_races = len(pace_cols)
    
    def calculate_improvement(row):
        # For very short seasons (<= 3), compare the absolute first round to the absolute last round
        if n_races <= 3:
            best_early = row[pace_cols[0]]
            best_late = row[pace_cols[-1]]
        # Standard: Compare the best of Rounds 1 & 2 vs the best of the Penultimate & Final Rounds
        else:
            best_early = row[pace_cols[:2]].min()
            best_late = row[pace_cols[-2:]].min()
            
        return pd.Series({
            'best_first_two': best_early, 
            'best_last_two': best_late, 
            'improvement': best_early - best_late
        })

    stats = improvement_df.apply(calculate_improvement, axis=1)
    
    final_improvement_df = pd.concat([improvement_df[['Driver_name']], stats], axis=1)
    return final_improvement_df.dropna(subset=['improvement']).sort_values('improvement', ascending=False)


def generate_event_csvs(
    season_ids=None,
    input_root='assets/xml',
    output_root='assets/csv',
    config_root='assets/json',
):
    """Generate one CSV for each configured quali and race XML file."""
    selected_seasons = season_ids or list(SEASONS)
    generated = []

    for season_id in selected_seasons:
        if season_id not in SEASONS:
            raise ValueError(f'Unknown season: {season_id}')
        season_config = load_season_config(season_id, config_root)
        config_path = os.path.join(config_root, f'{season_id}.json')

        for section_name, events in season_config.items():
            if section_name.startswith('sprint'):
                series_type = 'sprint'
            elif section_name.startswith('multiclass'):
                series_type = 'multiclass'
            else:
                continue

            is_quali = section_name.endswith('_qualis')
            for xml_filename, event_info in events.items():
                xml_path = os.path.join(input_root, season_id, series_type, xml_filename)
                if not os.path.exists(xml_path):
                    print(f'Not found: {xml_path}')
                    continue

                reference_times = event_info.get('reference_times')
                if not reference_times:
                    raise ValueError(
                        f'Missing reference times for {xml_filename} in {config_path}'
                    )

                descriptor = LMUDescriptor()
                if is_quali:
                    frame = descriptor.get_quali_descriptors(xml_path, reference_times)
                else:
                    frame = descriptor.get_descriptors(xml_path, reference_times)

                if frame.empty:
                    print(f'No driver data: {xml_path}')
                    continue

                frame['Driver_name'] = frame['Driver'].map(normalize_driver_name)
                frame['season_id'] = season_id
                frame['series_type'] = series_type
                frame['session_type'] = 'quali' if is_quali else 'race'

                csv_path = build_csv_path(season_id, series_type, xml_filename, output_root)
                os.makedirs(os.path.dirname(csv_path), exist_ok=True)
                frame.to_csv(csv_path, index=False)
                generated.append(csv_path)
                print(f'Generated: {csv_path} ({len(frame)} drivers)')

    return generated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--season', action='append', dest='seasons', choices=SEASONS)
    parser.add_argument('--input-root', default='assets/xml')
    parser.add_argument('--output-root', default='assets/csv')
    parser.add_argument('--config-root', default='assets/json')
    args = parser.parse_args()
    generate_event_csvs(
        args.seasons, args.input_root, args.output_root, args.config_root
    )


if __name__ == '__main__':
    main()
