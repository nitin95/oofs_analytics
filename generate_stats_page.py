"""Generate GitHub Pages reports from precomputed event descriptor CSVs."""

import os
import colorsys
import pandas as pd
import numpy as np
import json

# ===== MULTI-SEASON CONFIGURATION =====
# Season metadata
SEASONS = {
    'season1': {
        'name': 'Season 3',
        'year': 2026,
        'description': 'OOFS S3'
    },
    'season2': {
        'name': 'Season 4',
        'year': 2026,
        'description': 'OOFS S4'
    },
    'season3': {
        'name': 'Season 5',
        'year': 2026,
        'description': 'OOFS S5'
    },
    'season4': {
        'name': 'Season 6',
        'year': 2026,
        'description': 'OOFS S6'
    },
}

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


# TRACK_NAMES = ['Portimao', 'Le Mans', 'Interlagos', 'Monza', 'Sebring', 'Paul Ricard', 'COTA', 'Spa']


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


def format_driver_name(driver_name, rookie_names=(), abbreviated=True):
    """Format a visible driver name, adding a rookie marker when applicable."""
    name = str(driver_name)
    if abbreviated:
        name_parts = name.split()
        if len(name_parts) > 1:
            name = f'{name_parts[0]} {name_parts[-1][0]}.'
    if driver_name in rookie_names:
        name += '*'
    return name


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


def get_sidebar_html(active_page, season_id='season1'):
    """Generate sidebar navigation HTML with season selector"""
    pages = {}
    has_split_sprint_classes = season_has_sprint_class_data(season_id)

    if not has_split_sprint_classes:
        pages.update({
            'sprint_race': ('Sprint', 'Race Pace'),
            'sprint_quali': ('Sprint', 'Quali Pace'),
        })
        print('DEBUG: Sidebar pages:', pages)
    else:
        pages.update({
            'sprint_lmp3_race': ('Sprint LMP3', 'Race Pace'),
            'sprint_lmp3_quali': ('Sprint LMP3', 'Quali Pace'),
            'sprint_gt3_race': ('Sprint GT3', 'Race Pace'),
            'sprint_gt3_quali': ('Sprint GT3', 'Quali Pace'),
        })

    pages.update({
        'multiclass_p2ur_race': ('Multiclass P2UR/Hypercar', 'Race Pace'),
        'multiclass_p2ur_quali': ('Multiclass P2UR/Hypercar', 'Quali Pace'),
        'multiclass_gt3_race': ('Multiclass GT3', 'Race Pace'),
        'multiclass_gt3_quali': ('Multiclass GT3', 'Quali Pace'),
    })
    

    sidebar_html = '<nav class="sidebar"><div class="sidebar-content">'
    
    # Season selector dropdown
    # sidebar_html += '<div class="season-selector-wrapper"><label for="seasonSelector" style="color: #ccfc00; display: block; margin-bottom: 8px; font-size: 0.9em; font-weight: 600;">📅 Season</label>'
    # sidebar_html += '<select id="seasonSelector" style="width: 100%; padding: 8px; background: #333; color: #ccfc00; border: 1px solid #ccfc00; border-radius: 5px; font-size: 0.9em;">'
    
    # for s_id, s_info in SEASONS.items():
    #     selected = 'selected' if s_id == season_id else ''
    #     sidebar_html += f'<option value="{s_id}" {selected}>{s_info["name"]}</option>'
    
    sidebar_html += '</select></div>'
    # sidebar_html += '<hr style="border: none; border-top: 1px solid #555; margin: 15px 0;">'
    # sidebar_html += '<h3 style="color: #ccfc00; margin-bottom: 20px; margin-top: 15px;">📊 Dashboard</h3>'
    sidebar_html += '<a href="../index.html" aria-label="OOFS Analytics home"><img src="../logo.png" alt="OOFS Analytics" class="header-logo"></a>'
    
    current_section = None
    active_page_id = os.path.splitext(active_page)[0]
    for page_key, (section, subsection) in pages.items():
        if section != current_section:
            if current_section is not None:
                sidebar_html += '</ul></div>'
            current_section = section
            sidebar_html += f'<div class="section-group"><h4>{section}</h4><ul>'
        
        is_active = 'active' if page_key == active_page_id else ''
        file_name = f'{page_key}.html'
        sidebar_html += f'<li><a href="{file_name}" class="{is_active}">{subsection}</a></li>'
    
    sidebar_html += '</ul></div></nav>'
    return sidebar_html


def load_event_csv(csv_path, car_class=None):
    """Load one event CSV and optionally filter it to a requested class."""
    if not os.path.exists(csv_path):
        return None
    frame = pd.read_csv(csv_path)
    if car_class:
        class_name = car_class.upper()
        if class_name in ('P2UR', 'PROTOTYPE'):
            class_pattern = 'LMP2_ELMS|P2UR|Hyper'
        elif class_name == 'HYPER':
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


def process_race_data(csv_path, ref_laptime=None):
    """Load precomputed event statistics from a CSV."""
    return load_event_csv(csv_path)


def process_multiclass_race_data(csv_path, car_class, ref_laptime=None):
    """Load precomputed multiclass event statistics for one class."""
    return load_event_csv(csv_path, car_class)


def process_sprint_race_data(csv_path, car_class, ref_laptime=None):
    """Load precomputed sprint event statistics for one class."""
    return load_event_csv(csv_path, car_class)


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
    for column in avg_pace_cols:
        comparison_df.loc[comparison_df[column] > 107.0, column] = np.nan
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


def build_driver_color_map(driver_names):
    """Build a stable color map for drivers based on alphabetical name order."""
    unique_names = sorted(pd.Series(driver_names).dropna().unique().tolist())
    if not unique_names:
        return {}

    return {
        driver_name: '#{:02x}{:02x}{:02x}'.format(
            *(int(channel * 255) for channel in colorsys.hsv_to_rgb(
                index / len(unique_names), 0.72, 0.9
            ))
        )
        for index, driver_name in enumerate(unique_names)
    }


def create_display_df(comparison_df, avg_pace_cols, stdev_pace_cols, track_names, mode='race'):
    """Create display dataframe with renamed columns using average pace"""
    display_df = comparison_df[['Driver_name'] + avg_pace_cols + stdev_pace_cols].copy()
    display_df = display_df.replace(0.00, np.nan).dropna(subset=avg_pace_cols, how='all')
    display_df['best_pct'] = display_df[avg_pace_cols].min(axis=1)
    display_df = display_df.sort_values('best_pct')

    # Use the canonical driver ordering from the full comparison set so the same driver
    # keeps the same color on race and quali charts even when a specific plot filters out
    # some drivers due to missing data.
    driver_color_map = build_driver_color_map(comparison_df['Driver_name'])
    display_df['color'] = display_df['Driver_name'].map(driver_color_map)

    # Build rename mapping
    rename_map = {'Driver_name': 'Driver_name'}
    for _, (avg_col, sd_col, track) in enumerate(zip(avg_pace_cols, stdev_pace_cols, track_names)):
        pace_type = 'Race' if mode == 'race' else 'Quali'
        rename_map[avg_col] = f'{track} {pace_type} Avg Pace % (vs Alien)'
        rename_map[sd_col] = f'{track} {pace_type} Pace SD %'

    display_df_renamed = display_df.rename(columns=rename_map)
    return display_df_renamed, list(rename_map.values())[1:]  # Return column names minus Driver_name


def generate_html_tables(comparison_df, improvement_df, avg_pace_cols, track_names, mode='race'):
    """Generate HTML table representations of dataframes with average pace and stats"""
    rookie_names = set(
        comparison_df.loc[comparison_df['is_rookie'], 'Driver_name']
    ) if 'is_rookie' in comparison_df else set()

    if mode == 'race':  # Pace vs Alien table (using average pace)
        pace_table_df = comparison_df[['Driver_name'] + avg_pace_cols].copy()
        table_cols = avg_pace_cols
    else:  # quali: Pace vs Alien table (using fastest lap pace)
        fastest_lap_cols = [col.replace('avg_pace_pct_alien_', 'laptime_pct_alien_') for col in avg_pace_cols]
        pace_table_df = comparison_df[['Driver_name'] + fastest_lap_cols].copy()
        table_cols = fastest_lap_cols
    full_driver_names_pace = pace_table_df['Driver_name'].copy()
    
    # Convert driver names to "Firstname L." format for space efficiency
    pace_table_df['Driver_name'] = pace_table_df['Driver_name'].apply(
        lambda name: format_driver_name(name, rookie_names)
    )
    
    # Build rename mapping for pace table
    pace_rename = {'Driver_name': 'Driver'}
    for track, col in zip(track_names, table_cols):
        pace_rename[col] = track
    
    pace_table_df = pace_table_df.rename(columns=pace_rename).dropna(subset=track_names, how='all')
    pace_html = pace_table_df.to_html(index=False, float_format=lambda x: f'{x:.2f}' if pd.notna(x) else '')
    
    # Inject full driver names as data attributes
    full_names_in_pace = full_driver_names_pace[pace_table_df.index].tolist()
    for _, full_name in enumerate(full_names_in_pace):
        pace_html = pace_html.replace('<tr>', f'<tr data-driver="{full_name}">', 1)
    
    # Improvement table (using average pace)
    improvement_cols = ['Driver_name', 'best_first_two', 'best_last_two', 'improvement']
    improvement_table_df = improvement_df[improvement_cols].dropna(subset=['improvement'])
    full_driver_names_improvement = improvement_table_df['Driver_name'].copy()
    
    # Convert driver names to "Firstname L." format for space efficiency
    improvement_table_df['Driver_name'] = improvement_table_df['Driver_name'].apply(
        lambda name: format_driver_name(name, rookie_names)
    )
    
    improvement_table_df = improvement_table_df.rename(columns={
        'Driver_name': 'Driver',
        'best_first_two': 'Best Avg (First 2)',
        'best_last_two': 'Best Avg (Last 2)',
        'improvement': 'Improvement'
    })
    
    improvement_html = improvement_table_df.to_html(index=False, float_format=lambda x: f'{x:.2f}' if pd.notna(x) else '')
    
    # Inject full driver names as data attributes
    full_names_in_improvement = full_driver_names_improvement.tolist()
    for _, full_name in enumerate(full_names_in_improvement):
        improvement_html = improvement_html.replace('<tr>', f'<tr data-driver="{full_name}">', 1)
    
    return pace_html, improvement_html


def generate_descriptor_tables(comparison_df, race_codes, track_names):
    """Build round-by-round tables for race descriptors present in the data."""
    descriptor_specs = [
        ('race_pace', 'Clean Race Pace (s)', 'number'),
        ('consistency', 'Consistency (%)', 'fraction'),
        ('reliability', 'Reliability (%)', 'fraction'),
        ('n_tracklimits', 'Track Limits', 'integer'),
        ('n_inchidents', 'Incidents', 'integer'),
        ('pct_laps', 'Laps Completed (%)', 'number'),
        ('n_stops', 'Pit Stops', 'integer'),
        ('pit_lane_pct_times', 'Pit Lane Loss (lap equivalents)', 'number'),
    ]
    rookie_names = set(
        comparison_df.loc[comparison_df['is_rookie'], 'Driver_name']
    ) if 'is_rookie' in comparison_df else set()
    tables = []

    for metric, title, format_type in descriptor_specs:
        columns = [f'{metric}_{code}' for code in race_codes]
        available = [column for column in columns if column in comparison_df.columns]
        if not available:
            continue

        table_df = comparison_df[['Driver_name'] + available].copy()
        table_df = table_df.dropna(subset=available, how='all').reset_index(drop=True)
        if table_df.empty:
            continue

        full_driver_names = table_df['Driver_name'].tolist()
        table_df['Driver_name'] = table_df['Driver_name'].apply(
            lambda name: format_driver_name(name, rookie_names)
        )
        column_names = {'Driver_name': 'Driver'}
        for column, track in zip(columns, track_names):
            if column in table_df.columns:
                column_names[column] = track
        table_df = table_df.rename(columns=column_names)

        if format_type == 'fraction':
            for track in column_names.values():
                if track != 'Driver' and track in table_df.columns:
                    table_df[track] = table_df[track] * 100
        float_format = (lambda value: f'{value:.0f}') if format_type == 'integer' else (
            lambda value: f'{value:.2f}'
        )
        table_html = table_df.to_html(
            index=False,
            float_format=lambda value: float_format(value) if pd.notna(value) else '',
        )
        for full_name in full_driver_names:
            table_html = table_html.replace(
                '<tr>', f'<tr data-driver="{full_name}">', 1
            )
        tables.append(f'<h3>{title}</h3><div class="table-container">{table_html}</div>')

    if not tables:
        return ''
    return (
        '<div class="section descriptor-tables"><h2>Race Descriptors by Round</h2>'
        + '\n'.join(tables)
        + '</div>'
    )


def create_plotly_json(df_display_renamed, comparison_df, avg_pace_cols, stdev_pace_cols, track_names, chart_title, y_axis_title, race_type='race', time_lower=100.0, time_upper=107.0):
    """Create Plotly JSON data for the interactive chart.
    
    For quali (race_type='quali'): Shows fastest lap only
    For race (race_type='race'): Shows average pace with stddev confidence intervals, fastest lap in hover
    """
    # Get pace columns from display df (excluding Driver_name and best_pct)
    pace_col_names = [col for col in df_display_renamed.columns if 'Avg Pace %' in col or 'Pace %' in col]
    
    # Build column mapping from renamed columns back to track names
    col_mapping = {}
    for _, (track, col) in enumerate(zip(track_names, pace_col_names)):
        col_mapping[col] = track
    
    # Extract fastest lap columns from comparison_df
    # Replace avg_pace_pct_alien_ with laptime_pct_alien_ to get fastest lap columns
    fastest_lap_cols = [col.replace('avg_pace_pct_alien_', 'laptime_pct_alien_') for col in avg_pace_cols]
    
    descriptor_metrics = [
        'position', 'race_pace', 'pct_race_pace', 'consistency', 'reliability',
        'n_tracklimits', 'n_inchidents', 'pct_laps', 'n_stops',
        'pit_lane_pct_times',
    ]
    descriptor_cols = [
        f'{metric}_{avg_col.replace("avg_pace_pct_alien_", "")}'
        for avg_col in avg_pace_cols for metric in descriptor_metrics
        if f'{metric}_{avg_col.replace("avg_pace_pct_alien_", "")}' in comparison_df.columns
    ]
    plot_columns = list(dict.fromkeys(
        ['Driver_name'] + avg_pace_cols + stdev_pace_cols + fastest_lap_cols + descriptor_cols
    ))
    plot_df = comparison_df[plot_columns].copy()
    rookie_names = set(
        comparison_df.loc[comparison_df['is_rookie'], 'Driver_name']
    ) if 'is_rookie' in comparison_df else set()
    
    # Filter drivers dynamically: if only 1 race, include all; if 2+ races, include those with 2+ races
    races_attended = plot_df[avg_pace_cols].notna().sum(axis=1)
    min_races = 1 if len(avg_pace_cols) == 1 else 2
    plot_df = plot_df[races_attended >= min_races].reset_index(drop=True)

    # Reuse a stable driver-to-color mapping generated from the full comparison set so race
    # and quali plots keep the same color for the same driver even when each subplot filters
    # a different subset of drivers.
    canonical_color_map = build_driver_color_map(comparison_df['Driver_name'])
    if 'color' in df_display_renamed.columns:
        canonical_color_map.update(dict(zip(df_display_renamed['Driver_name'], df_display_renamed['color'])))

    plot_df['color'] = plot_df['Driver_name'].map(canonical_color_map)

    # Calculate best average pace
    plot_df['best'] = plot_df[avg_pace_cols].min(axis=1, skipna=True)
    plot_df = plot_df.sort_values('best').reset_index(drop=True)

    # Calculate consistency metric (inverse of stdev: 100 - stdev_pct)
    for sd_col in stdev_pace_cols:
        consistency_col = sd_col.replace('stdev_pace_pct_', 'consistency_')
        if consistency_col not in plot_df:
            plot_df[consistency_col] = 1 - plot_df[sd_col] / 100
    # print(plot_df.head(3))  # Debug: Show first 3 rows of plot_df
    # exit(0)  # Debug: Exit after showing plot_df to inspect the data
    # plot_df.to_csv('debug_plot_df.csv', index=False)  # Debug: Save plot_df to CSV for inspection
    # Create traces for Plotly
    traces = []
    x_positions = list(range(len(track_names)))
    
    for _, (_, row) in enumerate(plot_df.iterrows()):
        driver_name = row['Driver_name']
        display_driver_name = format_driver_name(
            driver_name, rookie_names, abbreviated=False
        )

        if race_type == 'quali':
            # Quali mode: plot fastest lap only — no average pace, no variance shading
            fastest_lap_pts = []
            for xi, fastest_col in enumerate(fastest_lap_cols):
                fastest_val = row.get(fastest_col)
                if pd.notna(fastest_val) and fastest_val > 0:
                    fastest_lap_pts.append((xi, fastest_val))

            if not fastest_lap_pts:
                continue

            xs_fl, ys_fl = zip(*fastest_lap_pts)
            hover_data = [
                f"{display_driver_name}<br>Fastest Lap: {fl:.2f}%"
                for fl in ys_fl
            ]

            # Display lines if more than 2 points, regardless of NaN at the end
            mode_fl = 'lines+markers'
            trace = {
                'x': list(xs_fl),
                'y': list(ys_fl),
                'mode': mode_fl,
                'name': driver_name,
                'hovertemplate': "%{customdata}<extra></extra>",
                'customdata': hover_data,
                'line': {'color': row.get('color'), 'width': 2},
                'marker': {'color': row.get('color'), 'size': 8},
                'opacity': 1.0,
                # No ci_lower / ci_upper — JS drawConfidenceInterval will skip this trace
            }

        else:
            # Race mode: plot average pace with confidence intervals, fastest lap in hover
            pts = []
            hover_data = []

            for xi, (avg_col, sd_col, fastest_col) in enumerate(zip(avg_pace_cols, stdev_pace_cols, fastest_lap_cols)):
                avg_val = row.get(avg_col)
                fastest_val = row.get(fastest_col)

                if not pd.notna(avg_val):
                    continue

                pts.append((xi, avg_val))

                fastest_lap = fastest_val if pd.notna(fastest_val) else avg_val
                if pd.isna(fastest_lap):
                    fastest_lap_str = f"{avg_val:.2f}%"
                else:
                    fastest_lap_str = f"{fastest_lap:.2f}%"

                race_code = avg_col.replace('avg_pace_pct_alien_', '')
                consistency_col = f'consistency_{race_code}'
                consistency_value = row.get(consistency_col)
                if pd.isna(consistency_value):
                    consistency_value = 1 - row.get(sd_col, np.nan) / 100
                hover_text = f"{display_driver_name}<br>Avg Pace: {avg_val:.2f}%<br>Fastest Lap: {fastest_lap_str}"

                if pd.notna(consistency_value):
                    hover_text += f"<br>Consistency: {float(consistency_value) * 100:.2f}%"

                descriptor_specs = [
                    ('position', 'Finishing Position', 'integer'),
                    ('race_pace', 'Clean Race Pace', 'seconds'),
                    ('pct_race_pace', 'Race Pace vs Class Leader', 'percent'),
                    ('reliability', 'Reliability', 'fraction'),
                    ('n_tracklimits', 'Track Limits', 'integer'),
                    ('n_inchidents', 'Incidents', 'integer'),
                    ('pct_laps', 'Laps Completed', 'percent'),
                    ('n_stops', 'Pit Stops', 'integer'),
                    ('pit_lane_pct_times', 'Pit Lane Loss (lap equivalents)', 'number'),
                ]
                for descriptor, label, value_format in descriptor_specs:
                    value = row.get(f'{descriptor}_{race_code}')
                    if pd.isna(value):
                        continue
                    if value_format == 'integer':
                        formatted = f'{int(value)}'
                    elif value_format == 'fraction':
                        formatted = f'{float(value) * 100:.2f}%'
                    elif value_format == 'percent':
                        formatted = f'{float(value):.2f}%'
                    elif value_format == 'seconds':
                        formatted = f'{float(value):.3f}s'
                    else:
                        formatted = f'{float(value):.2f}'
                    hover_text += f'<br>{label}: {formatted}'

                hover_data.append(hover_text)

            if not pts:
                continue

            xs, ys = zip(*pts)

            # Display lines if more than 2 points, regardless of NaN at the end
            mode_race = 'lines+markers' 
            trace = {
                'x': list(xs),
                'y': list(ys),
                'mode': mode_race,
                'name': driver_name,
                'hovertemplate': "%{customdata}<extra></extra>",
                'customdata': hover_data,
                'line': {'color': row.get('color'), 'width': 2},
                'marker': {'color': row.get('color'), 'size': 8},
                'opacity': 1.0,
                # 'ci_lower': ci_lower,
                # 'ci_upper': ci_upper,
            }

        traces.append(trace)
    
    return {
        'traces': traces,
        'layout': {
            'title': {'text': chart_title, 'font': {'color': '#ccfc00'}}, # Changed title structure here
            'xaxis': {
                'tickmode': 'array',
                'ticktext': track_names,
                'tickvals': x_positions,
                'titlefont': {'color': '#fafafa'}, # Color for the X-axis Title
                'tickfont': {'color': '#fafafa'},  # Color for the Tick Labels on X-axis
                'linecolor': '#ccfc00', # Dark axis line color
                'gridcolor': '#fafafa', # Dark grid line color
            },
            'yaxis': {
                'title': y_axis_title,
                'range': [time_lower, time_upper],
                'titlefont': {'color': '#fafafa'}, # Color for the Y-axis Title
                'tickfont': {'color': '#fafafa'},  # Color for the Tick Labels on Y-axis
                'linecolor': '#ccfc00', # Dark axis line color
                'gridcolor': '#fafafa', # Dark grid line color
            },
            'hovermode': 'closest',
            'plot_bgcolor': '#14161ff2',
            'paper_bgcolor': '#14161ff2', # Set paper background to match plot area
            'height': 500,
            'autosize': True,
            'showlegend': False,
            'xaxis_range': [-0.6, len(track_names) - 1 + 0.6],
            'margin': {'l': 50, 'r': 20, 'b': 50, 't': 60}
        }
    }


TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'templates')


def get_css_styles():
    """Return shared CSS styles for all pages (loaded from templates/styles.css)"""
    css_path = os.path.join(TEMPLATES_DIR, 'styles.css')
    with open(css_path, 'r', encoding='utf-8') as f:
        return f.read()



def generate_page(
    title, sidebar_file, season_id, pace_html, improvement_html, plotly_data,
    descriptor_tables_html='',
):
    """Generate an HTML page with sidebar and season selector (loaded from templates/page.html)"""
    sidebar = get_sidebar_html(sidebar_file, season_id)

    sidebar_section = f"""
    <button class="sidebar-toggle" id="sidebarToggle" aria-label="Toggle menu">
        <span></span>
        <span></span>
        <span></span>
    </button>
    {sidebar}
    """

    template_path = os.path.join(TEMPLATES_DIR, 'page.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()

    replacements = {
        '{title}': title,
        '{sidebar_section}': sidebar_section,
        '{pace_html}': pace_html,
        '{improvement_html}': improvement_html,
        '{descriptor_tables_html}': descriptor_tables_html,
        '{plot_traces_json}': json.dumps(plotly_data['traces']),
        '{plot_layout_json}': json.dumps(plotly_data['layout']),
        '{generated_at}': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    return template


def main():
    import shutil
    """Main execution function - process all seasons and generate pages"""
    print("[*] OOFS Stats Page Generator\n")
    print("=" * 60)

    from generate_descriptor_csvs import generate_event_csvs

    generated_csvs = generate_event_csvs()
    print(f"  Generated {len(generated_csvs)} event descriptor CSVs")
    
    # Create top-level docs folder
    os.makedirs('docs', exist_ok=True)

    # NEW: Copy the CSS file into the docs folder so GitHub Pages can see it
    try:
        shutil.copy(os.path.join(TEMPLATES_DIR, 'styles.css'), os.path.join('docs', 'styles.css'))
        print("  Copied styles.css to docs/")
    except FileNotFoundError:
        print("  WARNING: templates/styles.css not found!")

    # Generate top-level season index page
    # print("\n[Index] Generating docs/index.html...")
    # card_html = ''
    # for s_id, s_info in SEASONS.items():
    #     card_html += (
    #         f'\n        <a class="season-card" href="{s_id}/sprint_race.html">'
    #         f'\n            <span class="season-label">Season</span>'
    #         f'\n            <span class="season-name">{s_info["name"]}</span>'
    #         f'\n            <span class="season-year">{s_info["year"]}</span>'
    #         f'\n            <span class="season-desc">{s_info["description"]}</span>'
    #         f'\n        </a>'
    #     )

    # index_template_path = os.path.join(TEMPLATES_DIR, 'index.html')
    # with open(index_template_path, 'r', encoding='utf-8') as f:
    #     index_template = f.read()
    # index_html = index_template.replace('{season_cards}', card_html)

    # with open(os.path.join('docs', 'index.html'), 'w', encoding='utf-8-sig') as f:
    #     f.write(index_html)
    # print("  Generated docs/index.html")

    # Loop through all configured seasons
    for season_id, season_info in SEASONS.items():
        print(f"\n[Season] Processing {season_info['name']}...")
        season_config = {
            section_name: {
                f'{os.path.splitext(filename)[0]}.csv': race_info
                for filename, race_info in events.items()
            }
            for section_name, events in load_season_config(season_id).items()
        }
        
        # Create season-specific output folder
        season_output_dir = os.path.join('docs', season_id)
        os.makedirs(season_output_dir, exist_ok=True)
        
        has_split_sprint_classes = season_has_sprint_class_data(season_id)

        # ===== SPRINT RACE PACE =====
        if not has_split_sprint_classes:
            print("  [Sprint] Race Pace...")
            sprint_race_dfs = {}
            xml_folder = os.path.join('assets', 'csv', season_id, 'sprint')
            
            for filename, race_info in season_config['sprint_races'].items():
                xml_path = os.path.join(xml_folder, filename)
                if os.path.exists(xml_path):
                    df = process_race_data(xml_path)
                    if df is not None:
                        sprint_race_dfs[race_info['name']] = df
                else:
                    print(f"    Not found: {xml_path}")
            
            print(f"    DEBUG: After loading, sprint_race_dfs={list(sprint_race_dfs.keys()) if sprint_race_dfs else 'EMPTY'}")
            
            if sprint_race_dfs:
                print(f"    DEBUG: sprint_race_dfs has {len(sprint_race_dfs)} entries: {list(sprint_race_dfs.keys())}")
                race_codes, track_names, code_to_track = load_races_dynamically(season_config['sprint_races'], xml_folder)
                print(f"    DEBUG: race_codes={race_codes}, code_to_track={code_to_track}")
                comparison_df, _, avg_pace_cols, used_race_codes, track_names = process_races_into_comparison_df(sprint_race_dfs, race_codes, code_to_track, season_id, 'sprint')
                
                if comparison_df is not None:
                    improvement_df = build_improvement_df(comparison_df, avg_pace_cols)
                    stdev_pace_cols = [f'stdev_pace_pct_{code}' for code in used_race_codes]
                    df_display_renamed, _ = create_display_df(comparison_df, avg_pace_cols, stdev_pace_cols, track_names, mode='race')
                    pace_html, improvement_html = generate_html_tables(comparison_df, improvement_df, avg_pace_cols, track_names)
                    descriptor_tables_html = generate_descriptor_tables(comparison_df, used_race_codes, track_names)
                    
                    num_rounds = len(track_names)
                    plotly_data = create_plotly_json(df_display_renamed, comparison_df, avg_pace_cols, stdev_pace_cols, track_names,
                        f'Sprint Race Pace Trend: After {num_rounds} Rounds', 'Race Pace % (vs Alien)', race_type='race')
                    
                    html_content = generate_page('Sprint Race Pace Data',
                        'sprint_race.html', season_id, pace_html, improvement_html, plotly_data,
                        descriptor_tables_html)
                    
                    output_file = os.path.join(season_output_dir, 'sprint_race.html')
                    with open(output_file, 'w', encoding='utf-8-sig') as f:
                        f.write(html_content)
                    if season_id == list(SEASONS.keys())[0]:  # Create index.html for first season
                        with open(os.path.join(season_output_dir, 'index.html'), 'w', encoding='utf-8-sig') as f:
                            f.write(html_content)
                    print("    Generated sprint_race.html")
                else:
                    print("    Comparison DF is None for sprint races")
            else:
                print("    No sprint race data found")
        else:
            print("  [Sprint] Skipping aggregate race pace page because split sprint classes are present")
            output_file = os.path.join(season_output_dir, 'sprint_race.html')
            if os.path.exists(output_file):
                os.remove(output_file)
        
            # ===== SPRINT LMP3 RACE PACE (Class-filtered) =====
            print("  [Sprint] LMP3 Race Pace...")
            sprint_lmp3_race_dfs = {}
            xml_folder = os.path.join('assets', 'csv', season_id, 'sprint')
            
            for filename, race_info in season_config['sprint_races'].items():
                xml_path = os.path.join(xml_folder, filename)
                if os.path.exists(xml_path):
                    df = process_sprint_race_data(xml_path, 'LMP3')
                    if df is not None:
                        sprint_lmp3_race_dfs[race_info['name']] = df
                else:
                    print(f"    Not found: {xml_path}")
            
            if sprint_lmp3_race_dfs:
                race_codes, track_names, code_to_track = load_races_dynamically(season_config['sprint_races'], xml_folder)
                comparison_df, _, avg_pace_cols, used_race_codes, track_names = process_races_into_comparison_df(sprint_lmp3_race_dfs, race_codes, code_to_track, season_id, 'sprint', 'LMP3')
                
                if comparison_df is not None:
                    improvement_df = build_improvement_df(comparison_df, avg_pace_cols)
                    stdev_pace_cols = [f'stdev_pace_pct_{code}' for code in used_race_codes]
                    df_display_renamed, _ = create_display_df(comparison_df, avg_pace_cols, stdev_pace_cols, track_names, mode='race')
                    pace_html, improvement_html = generate_html_tables(comparison_df, improvement_df, avg_pace_cols, track_names)
                    descriptor_tables_html = generate_descriptor_tables(comparison_df, used_race_codes, track_names)
                    
                    num_rounds = len(track_names)
                    plotly_data = create_plotly_json(df_display_renamed, comparison_df, avg_pace_cols, stdev_pace_cols, track_names,
                        f'Sprint LMP3 Race Pace Trend: After {num_rounds} Rounds', 'Race Pace % (vs Alien)', race_type='race')
                    
                    html_content = generate_page('Sprint LMP3 Race Pace Data',
                        'sprint_lmp3_race.html', season_id, pace_html, improvement_html, plotly_data,
                        descriptor_tables_html)
                    
                    with open(os.path.join(season_output_dir, 'sprint_lmp3_race.html'), 'w', encoding='utf-8-sig') as f:
                        f.write(html_content)
                    print("    Generated sprint_lmp3_race.html")
                else:
                    print("    Comparison DF is None for LMP3 races")
            else:
                print("    No LMP3 sprint race data found")
            
            # ===== SPRINT GT3 RACE PACE (Class-filtered) =====
            print("  [Sprint] GT3 Race Pace...")
            sprint_gt3_race_dfs = {}
            
            for filename, race_info in season_config['sprint_races'].items():
                xml_path = os.path.join(xml_folder, filename)
                print(f"    DEBUG: Processing GT3 race CSV: {xml_path}")
                if os.path.exists(xml_path):
                    df = process_sprint_race_data(xml_path, 'GT3')
                    if df is not None:
                        sprint_gt3_race_dfs[race_info['name']] = df
                else:
                    print(f"    Not found: {xml_path}")
            
            if sprint_gt3_race_dfs:
                race_codes, track_names, code_to_track = load_races_dynamically(season_config['sprint_races'], xml_folder)
                comparison_df, _, avg_pace_cols, used_race_codes, track_names = process_races_into_comparison_df(sprint_gt3_race_dfs, race_codes, code_to_track, season_id, 'sprint', 'GT3')
                
                if comparison_df is not None:
                    improvement_df = build_improvement_df(comparison_df, avg_pace_cols)
                    stdev_pace_cols = [f'stdev_pace_pct_{code}' for code in used_race_codes]
                    df_display_renamed, _ = create_display_df(comparison_df, avg_pace_cols, stdev_pace_cols, track_names, mode='race')
                    pace_html, improvement_html = generate_html_tables(comparison_df, improvement_df, avg_pace_cols, track_names)
                    descriptor_tables_html = generate_descriptor_tables(comparison_df, used_race_codes, track_names)
                    
                    num_rounds = len(track_names)
                    plotly_data = create_plotly_json(df_display_renamed, comparison_df, avg_pace_cols, stdev_pace_cols, track_names,
                        f'Sprint GT3 Race Pace Trend: After {num_rounds} Rounds', 'Race Pace % (vs Alien)', race_type='race')
                    
                    html_content = generate_page('Sprint GT3 Race Pace Data',
                        'sprint_gt3_race.html', season_id, pace_html, improvement_html, plotly_data,
                        descriptor_tables_html)
                    
                    with open(os.path.join(season_output_dir, 'sprint_gt3_race.html'), 'w', encoding='utf-8-sig') as f:
                        f.write(html_content)
                    print("    Generated sprint_gt3_race.html")
                else:
                    print("    Comparison DF is None for GT3 races")
            else:
                print("    No GT3 sprint race data found")
        
        # ===== SPRINT QUALI PACE =====
        if not has_split_sprint_classes:
            print("  [Sprint] Quali Pace...")
            sprint_quali_dfs = {}
            
            for filename, quali_info in season_config['sprint_qualis'].items():
                xml_path = os.path.join(xml_folder, filename)
                if os.path.exists(xml_path):
                    df = process_race_data(xml_path)
                    if df is not None:
                        sprint_quali_dfs[quali_info['name']] = df
            
            if sprint_quali_dfs:
                race_codes, track_names, code_to_track = load_races_dynamically(season_config['sprint_qualis'], xml_folder)
                comparison_df, _, avg_pace_cols, used_race_codes, track_names = process_races_into_comparison_df(sprint_quali_dfs, race_codes, code_to_track, season_id, 'sprint')
                
                if comparison_df is not None:
                    # Create fastest lap column names and pass instead of average pace 
                    fastest_lap_cols = [col.replace('avg_pace_pct_alien_', 'laptime_pct_alien_') for col in avg_pace_cols]
                    improvement_df = build_improvement_df(comparison_df, fastest_lap_cols)
                    # improvement_df = build_improvement_df(comparison_df, avg_pace_cols)
                    stdev_pace_cols = [f'stdev_pace_pct_{code}' for code in used_race_codes]
                    df_display_renamed, _ = create_display_df(comparison_df, avg_pace_cols, stdev_pace_cols, track_names, mode='quali')
                    pace_html, improvement_html = generate_html_tables(comparison_df, improvement_df, avg_pace_cols, track_names, mode='quali')
                    
                    num_rounds = len(track_names)
                    plotly_data = create_plotly_json(df_display_renamed, comparison_df, avg_pace_cols, stdev_pace_cols, track_names,
                        f'Sprint Quali Pace Trend: After {num_rounds} Rounds', 'Quali Pace % (vs Alien)', race_type='quali')
                    
                    html_content = generate_page('Sprint Quali Pace Data',
                        'sprint_quali.html', season_id, pace_html, improvement_html, plotly_data)
                    
                    with open(os.path.join(season_output_dir, 'sprint_quali.html'), 'w', encoding='utf-8-sig') as f:
                        f.write(html_content)
                    print("    Generated sprint_quali.html")
            else:
                print("    No sprint quali data found")
        else:
            print("  [Sprint] Skipping aggregate quali page because split sprint classes are present")
            output_file = os.path.join(season_output_dir, 'sprint_quali.html')
            if os.path.exists(output_file):
                os.remove(output_file)
        
            # ===== SPRINT LMP3 QUALI PACE (Class-filtered) =====
            print("  [Sprint] LMP3 Quali Pace...")
            sprint_lmp3_quali_dfs = {}
            
            for filename, quali_info in season_config['sprint_qualis'].items():
                xml_path = os.path.join(xml_folder, filename)
                if os.path.exists(xml_path):
                    df = process_sprint_race_data(xml_path, 'LMP3')
                    if df is not None:
                        sprint_lmp3_quali_dfs[quali_info['name']] = df
                else:
                    print(f"    Not found: {xml_path}")
            
            if sprint_lmp3_quali_dfs:
                race_codes, track_names, code_to_track = load_races_dynamically(season_config['sprint_qualis'], xml_folder)
                comparison_df, _, avg_pace_cols, used_race_codes, track_names = process_races_into_comparison_df(sprint_lmp3_quali_dfs, race_codes, code_to_track, season_id, 'sprint', 'LMP3')
                
                if comparison_df is not None:
                    # Create fastest lap column names and pass instead of average pace
                    fastest_lap_cols = [col.replace('avg_pace_pct_alien_', 'laptime_pct_alien_') for col in avg_pace_cols]
                    improvement_df = build_improvement_df(comparison_df, fastest_lap_cols)
                    stdev_pace_cols = [f'stdev_pace_pct_{code}' for code in used_race_codes]
                    df_display_renamed, _ = create_display_df(comparison_df, avg_pace_cols, stdev_pace_cols, track_names, mode='quali')
                    pace_html, improvement_html = generate_html_tables(comparison_df, improvement_df, avg_pace_cols, track_names, mode='quali')
                    
                    num_rounds = len(track_names)
                    plotly_data = create_plotly_json(df_display_renamed, comparison_df, avg_pace_cols, stdev_pace_cols, track_names,
                        f'Sprint LMP3 Quali Pace Trend: After {num_rounds} Rounds', 'Quali Pace % (vs Alien)', race_type='quali')
                    
                    html_content = generate_page('Sprint LMP3 Quali Pace Data',
                        'sprint_lmp3_quali.html', season_id, pace_html, improvement_html, plotly_data)
                    
                    with open(os.path.join(season_output_dir, 'sprint_lmp3_quali.html'), 'w', encoding='utf-8-sig') as f:
                        f.write(html_content)
                    print("    Generated sprint_lmp3_quali.html")
                else:
                    print("    Comparison DF is None for LMP3 qualies")
            else:
                print("    No LMP3 sprint quali data found")
            
            # ===== SPRINT GT3 QUALI PACE (Class-filtered) =====
            print("  [Sprint] GT3 Quali Pace...")
            sprint_gt3_quali_dfs = {}
            
            for filename, quali_info in season_config['sprint_qualis'].items():
                xml_path = os.path.join(xml_folder, filename)
                if os.path.exists(xml_path):
                    df = process_sprint_race_data(xml_path, 'GT3')
                    if df is not None:
                        sprint_gt3_quali_dfs[quali_info['name']] = df
                else:
                    print(f"    Not found: {xml_path}")
            
            if sprint_gt3_quali_dfs:
                race_codes, track_names, code_to_track = load_races_dynamically(season_config['sprint_qualis'], xml_folder)
                comparison_df, _, avg_pace_cols, used_race_codes, track_names = process_races_into_comparison_df(sprint_gt3_quali_dfs, race_codes, code_to_track, season_id, 'sprint', 'GT3')
                
                if comparison_df is not None:
                    # Create fastest lap column names and pass instead of average pace
                    fastest_lap_cols = [col.replace('avg_pace_pct_alien_', 'laptime_pct_alien_') for col in avg_pace_cols]
                    improvement_df = build_improvement_df(comparison_df, fastest_lap_cols)
                    stdev_pace_cols = [f'stdev_pace_pct_{code}' for code in used_race_codes]
                    df_display_renamed, _ = create_display_df(comparison_df, avg_pace_cols, stdev_pace_cols, track_names, mode='quali')
                    pace_html, improvement_html = generate_html_tables(comparison_df, improvement_df, avg_pace_cols, track_names, mode='quali')
                    
                    num_rounds = len(track_names)
                    plotly_data = create_plotly_json(df_display_renamed, comparison_df, avg_pace_cols, stdev_pace_cols, track_names,
                        f'Sprint GT3 Quali Pace Trend: After {num_rounds} Rounds', 'Quali Pace % (vs Alien)', race_type='quali')
                    
                    html_content = generate_page('Sprint GT3 Quali Pace Data',
                        'sprint_gt3_quali.html', season_id, pace_html, improvement_html, plotly_data)
                    
                    with open(os.path.join(season_output_dir, 'sprint_gt3_quali.html'), 'w', encoding='utf-8-sig') as f:
                        f.write(html_content)
                    print("    Generated sprint_gt3_quali.html")
                else:
                    print("    Comparison DF is None for GT3 qualies")
            else:
                print("    No GT3 sprint quali data found")
        
        # ===== MULTICLASS P2UR/Hyper RACE PACE =====
        proto_class = 'P2UR' if season_id == 'season1' else 'Hyper'
        print(f"  [Multiclass] {proto_class}/GT3 Race Pace...")
        mc_p2ur_race_dfs = {}
        xml_folder_mc = os.path.join('assets', 'csv', season_id, 'multiclass')
        
        for filename, mc_info in season_config['multiclass_races'].items():
            xml_path = os.path.join(xml_folder_mc, filename)
            if os.path.exists(xml_path):
                if season_id == 'season1':
                    df = process_multiclass_race_data(xml_path, 'P2UR')
                else:
                    df = process_multiclass_race_data(xml_path, 'Hyper')
                if df is not None:
                    mc_p2ur_race_dfs[mc_info['name']] = df
            else:
                print(f"    Not found: {xml_path}")
        
        if mc_p2ur_race_dfs:
            race_codes, track_names, code_to_track = load_races_dynamically(season_config['multiclass_races'], xml_folder_mc)
            comparison_df, _, avg_pace_cols, used_race_codes, track_names = process_races_into_comparison_df(mc_p2ur_race_dfs, race_codes, code_to_track, season_id, 'multiclass', 'PROTOTYPE')
            
            if comparison_df is not None:
                improvement_df = build_improvement_df(comparison_df, avg_pace_cols)
                stdev_pace_cols = [f'stdev_pace_pct_{code}' for code in used_race_codes]
                df_display_renamed, _ = create_display_df(comparison_df, avg_pace_cols, stdev_pace_cols, track_names, mode='race')
                pace_html, improvement_html = generate_html_tables(comparison_df, improvement_df, avg_pace_cols, track_names)
                descriptor_tables_html = generate_descriptor_tables(comparison_df, used_race_codes, track_names)
                
                num_rounds = len(track_names)
                proto_class = 'P2UR' if season_id == 'season1' else 'Hyper'
                plotly_data = create_plotly_json(df_display_renamed, comparison_df, avg_pace_cols, stdev_pace_cols, track_names,
                    f'Multiclass {proto_class} Race Pace Trend: After {num_rounds} Rounds', 'Race Pace % (vs Alien)', race_type='race')
                
                html_content = generate_page(f'Multiclass {proto_class} Race Pace Data',
                    'multiclass_p2ur_race.html', season_id, pace_html, improvement_html, plotly_data,
                    descriptor_tables_html)
                
                with open(os.path.join(season_output_dir, 'multiclass_p2ur_race.html'), 'w', encoding='utf-8-sig') as f:
                    f.write(html_content)
                print(f"    Generated multiclass_{proto_class.lower()}_race.html")
            else:
                print(f"    Comparison DF is None for {proto_class} races")
        else:
            print(f"    No {proto_class} data found for races")

        # ===== MULTICLASS P2UR/Hyper QUALI PACE =====
        proto_class_label = 'P2UR' if season_id == 'season1' else 'Hyper'
        print(f"  [Multiclass] {proto_class_label} Quali Pace...")
        mc_p2ur_quali_dfs = {}
        
        for filename, mc_info in season_config['multiclass_qualis'].items():
            xml_path = os.path.join(xml_folder_mc, filename)
            if os.path.exists(xml_path):
                if season_id == 'season1':
                    df = process_multiclass_race_data(xml_path, 'P2UR')
                else:
                    df = process_multiclass_race_data(xml_path, 'Hyper')
                if df is not None:
                    mc_p2ur_quali_dfs[mc_info['name']] = df
            else:
                print(f"    Not found: {xml_path}")
        
        if not mc_p2ur_quali_dfs:
            print(f"    No {proto_class_label} data found for qualies")
        else:
            race_codes, track_names, code_to_track = load_races_dynamically(season_config['multiclass_qualis'], xml_folder_mc)
            comparison_df, _, avg_pace_cols, used_race_codes, track_names = process_races_into_comparison_df(mc_p2ur_quali_dfs, race_codes, code_to_track, season_id, 'multiclass', 'PROTOTYPE')
            
            if comparison_df is not None:
                # Create fastest lap column names and pass instead of average pace
                fastest_lap_cols = [col.replace('avg_pace_pct_alien_', 'laptime_pct_alien_') for col in avg_pace_cols]
                improvement_df = build_improvement_df(comparison_df, fastest_lap_cols)

                # improvement_df = build_improvement_df(comparison_df, avg_pace_cols)
                stdev_pace_cols = [f'stdev_pace_pct_{code}' for code in used_race_codes]
                df_display_renamed, _ = create_display_df(comparison_df, avg_pace_cols, stdev_pace_cols, track_names, mode='quali')
                pace_html, improvement_html = generate_html_tables(comparison_df, improvement_df, avg_pace_cols, track_names, mode='quali')
                
                num_rounds = len(track_names)
                proto_class = 'P2UR' if season_id == 'season1' else 'Hyper'
                plotly_data = create_plotly_json(df_display_renamed, comparison_df, avg_pace_cols, stdev_pace_cols, track_names,
                    f'Multiclass {proto_class} Quali Pace Trend: After {num_rounds} Rounds', 'Quali Pace % (vs Alien)', race_type='quali')
                
                html_content = generate_page(f'Multiclass {proto_class} Quali Pace Data',
                    'multiclass_p2ur_quali.html', season_id, pace_html, improvement_html, plotly_data)
                
                with open(os.path.join(season_output_dir, 'multiclass_p2ur_quali.html'), 'w', encoding='utf-8-sig') as f:
                    f.write(html_content)
                print(f"    Generated multiclass_{proto_class.lower()}_quali.html")
            else:
                print(f"    Comparison DF is None for {proto_class} qualies")
        
        # ===== MULTICLASS GT3 RACE PACE =====
        print("  [Multiclass] GT3 Race Pace...")
        mc_gt3_race_dfs = {}
        
        for filename, mc_info in season_config['multiclass_races'].items():
            xml_path = os.path.join(xml_folder_mc, filename)
            if os.path.exists(xml_path):
                df = process_multiclass_race_data(xml_path, 'GT3')
                if df is not None:
                    mc_gt3_race_dfs[mc_info['name']] = df
        
        if mc_gt3_race_dfs:
            race_codes, track_names, code_to_track = load_races_dynamically(season_config['multiclass_races'], xml_folder_mc)
            comparison_df, _, avg_pace_cols, used_race_codes, track_names = process_races_into_comparison_df(mc_gt3_race_dfs, race_codes, code_to_track, season_id, 'multiclass', 'GT3')
            
            if comparison_df is not None:
                improvement_df = build_improvement_df(comparison_df, avg_pace_cols)
                stdev_pace_cols = [f'stdev_pace_pct_{code}' for code in used_race_codes]
                df_display_renamed, _ = create_display_df(comparison_df, avg_pace_cols, stdev_pace_cols, track_names, mode='race')
                pace_html, improvement_html = generate_html_tables(comparison_df, improvement_df, avg_pace_cols, track_names)
                descriptor_tables_html = generate_descriptor_tables(comparison_df, used_race_codes, track_names)
                
                num_rounds = len(track_names)
                plotly_data = create_plotly_json(df_display_renamed, comparison_df, avg_pace_cols, stdev_pace_cols, track_names,
                    f'Multiclass GT3 Race Pace Trend: After {num_rounds} Rounds', 'Race Pace % (vs Alien)', race_type='race')
                
                html_content = generate_page('Multiclass GT3 Race Pace Data',
                    'multiclass_gt3_race.html', season_id, pace_html, improvement_html, plotly_data,
                    descriptor_tables_html)
                
                with open(os.path.join(season_output_dir, 'multiclass_gt3_race.html'), 'w', encoding='utf-8-sig') as f:
                    f.write(html_content)
                print("    Generated multiclass_gt3_race.html")
            else:
                print("    Comparison DF is None for GT3 races")
        else:
            print("    No GT3 data found for races")
        
        # ===== MULTICLASS GT3 QUALI PACE =====
        print("  [Multiclass] GT3 Quali Pace...")
        mc_gt3_quali_dfs = {}
        
        for filename, mc_info in season_config['multiclass_qualis'].items():
            xml_path = os.path.join(xml_folder_mc, filename)
            if os.path.exists(xml_path):
                df = process_multiclass_race_data(xml_path, 'GT3')
                if df is not None:
                    mc_gt3_quali_dfs[mc_info['name']] = df
        
        if mc_gt3_quali_dfs:
            race_codes, track_names, code_to_track = load_races_dynamically(season_config['multiclass_qualis'], xml_folder_mc)
            comparison_df, _, avg_pace_cols, used_race_codes, track_names = process_races_into_comparison_df(mc_gt3_quali_dfs, race_codes, code_to_track, season_id, 'multiclass', 'GT3')
            
            if comparison_df is not None:

                # Create fastest lap column names and pass instead of average pace
                fastest_lap_cols = [col.replace('avg_pace_pct_alien_', 'laptime_pct_alien_') for col in avg_pace_cols]
                improvement_df = build_improvement_df(comparison_df, fastest_lap_cols)

                # improvement_df = build_improvement_df(comparison_df, avg_pace_cols)
                stdev_pace_cols = [f'stdev_pace_pct_{code}' for code in used_race_codes]
                df_display_renamed, _ = create_display_df(comparison_df, avg_pace_cols, stdev_pace_cols, track_names, mode='quali')
                pace_html, improvement_html = generate_html_tables(comparison_df, improvement_df, avg_pace_cols, track_names, mode='quali')
                
                num_rounds = len(track_names)
                plotly_data = create_plotly_json(df_display_renamed, comparison_df, avg_pace_cols, stdev_pace_cols, track_names,
                    f'Multiclass GT3 Quali Pace Trend: After {num_rounds} Rounds', 'Quali Pace % (vs Alien)', race_type='quali')
                
                html_content = generate_page('Multiclass GT3 Quali Pace Data',
                    'multiclass_gt3_quali.html', season_id, pace_html, improvement_html, plotly_data)
                
                with open(os.path.join(season_output_dir, 'multiclass_gt3_quali.html'), 'w', encoding='utf-8-sig') as f:
                    f.write(html_content)
                print("    Generated multiclass_gt3_quali.html")
            else:
                print("    Comparison DF is None for GT3 qualies")
        else:
            print("    No GT3 data found for qualies")
    
    # All seasons processed - print summary
    print("\n" + "=" * 60)
    print("All pages generated successfully!")


if __name__ == '__main__':
    main()