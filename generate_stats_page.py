"""
Generate GitHub Pages HTML report from XML pace data
This script processes XML files and generates an interactive multi-page dashboard.
"""

import os
import pandas as pd
import xml.etree.ElementTree as ET
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
}

# Season-based race configurations
SEASON_CONFIG = {
    'season1': {
        'sprint_qualis': {
            's3-sc1.xml': {'name': 'Portimao', 'ref_time': 103.23},
            's3-sc2.xml': {'name': 'Le Mans', 'ref_time': 235.4},
            's3-sc3.xml': {'name': 'Interlagos', 'ref_time': 93.46},
            's3-sc4.xml': {'name': 'Monza', 'ref_time': 99.01},
            's3-sc5.xml': {'name': 'Sebring', 'ref_time': 119.96},
            's3-sc6.xml': {'name': 'Paul Ricard', 'ref_time': 123.35},
            's3-sc7.xml': {'name': 'COTA', 'ref_time': 125.58},
            's3-sc8.xml': {'name': 'Spa', 'ref_time': 137.32},
        },
        'sprint_races': {
            's3-sc1-r.xml': {'name': 'Portimao', 'ref_time': 103.75},
            's3-sc2-r.xml': {'name': 'Le Mans', 'ref_time': 236.58},
            's3-sc3-r.xml': {'name': 'Interlagos', 'ref_time': 93.93},
            's3-sc4-r.xml': {'name': 'Monza', 'ref_time': 99.51},
            's3-sc5-r.xml': {'name': 'Sebring', 'ref_time': 120.56},
            's3-sc6-r.xml': {'name': 'Paul Ricard', 'ref_time': 123.97},
            's3-sc7-r.xml': {'name': 'COTA', 'ref_time': 126.20},
            's3-sc8-r.xml': {'name': 'Spa', 'ref_time': 138.01},
        },
        'multiclass_qualis': {
            's3-mc1.xml': {'name': 'Portimao', 'ref_time_p2ur': 91.53, 'ref_time_gt3': 103.23},
            's3-mc2.xml': {'name': 'Le Mans', 'ref_time_p2ur': 206.83, 'ref_time_gt3': 235.4},
            's3-mc3.xml': {'name': 'Interlagos', 'ref_time_p2ur': 82.86, 'ref_time_gt3': 93.46},
            's3-mc4.xml': {'name': 'Monza', 'ref_time_p2ur': 87.27, 'ref_time_gt3': 99.01},
            's3-mc5.xml': {'name': 'Sebring', 'ref_time_p2ur': 105.53, 'ref_time_gt3': 119.96},
            's3-mc6.xml': {'name': 'Paul Ricard', 'ref_time_p2ur': 109.24, 'ref_time_gt3': 123.44},
            's3-mc7.xml': {'name': 'COTA', 'ref_time_p2ur': 112.81, 'ref_time_gt3': 125.61},
            's3-mc8.xml': {'name': 'Spa', 'ref_time_p2ur': 120.98, 'ref_time_gt3': 137.32},
        },
        'multiclass_races': {
            's3-mc1-r.xml': {'name': 'Portimao', 'ref_time_p2ur': 91.99, 'ref_time_gt3': 103.75},
            's3-mc2-r.xml': {'name': 'Le Mans', 'ref_time_p2ur': 207.86, 'ref_time_gt3': 236.58},
            's3-mc3-r.xml': {'name': 'Interlagos', 'ref_time_p2ur': 83.27, 'ref_time_gt3': 93.93},
            's3-mc4-r.xml': {'name': 'Monza', 'ref_time_p2ur': 87.70, 'ref_time_gt3': 99.51},
            's3-mc5-r.xml': {'name': 'Sebring', 'ref_time_p2ur': 106.06, 'ref_time_gt3': 120.56},
            's3-mc6-r.xml': {'name': 'Paul Ricard', 'ref_time_p2ur': 109.79, 'ref_time_gt3': 123.97},
            's3-mc7-r.xml': {'name': 'COTA', 'ref_time_p2ur': 113.37, 'ref_time_gt3': 126.20},
            's3-mc8-r.xml': {'name': 'Spa', 'ref_time_p2ur': 121.59, 'ref_time_gt3': 138.01},
        },
    },
    'season2': {
        'sprint_qualis': {
            's4-sc1.xml': {'name': 'Imola', 'ref_time': 101.82},
            's4-sc2.xml': {'name': 'Barcelona', 'ref_time': 100.60},
            's4-sc3.xml': {'name': 'Silverstone', 'ref_time': 117.76},
            's4-sc4.xml': {'name': 'Fuji', 'ref_time': 105.0},
            's4-sc5.xml': {'name': 'Bahrain (outer)', 'ref_time': 72.01}
        },
        'sprint_races': {
            's4-sc1-r.xml': {'name': 'Imola', 'ref_time': 102.33},
            's4-sc2-r.xml': {'name': 'Barcelona', 'ref_time': 101.10},
            's4-sc3-r.xml': {'name': 'Silverstone', 'ref_time': 133.72},
            's4-sc4-r.xml': {'name': 'Fuji', 'ref_time': 106.5},
            's4-sc5-r.xml': {'name': 'Bahrain (outer)', 'ref_time': 72.37}
        },
        'multiclass_qualis': {
            's4-mc1.xml': {'name': 'Imola', 'ref_time_hyper': 89.45, 'ref_time_gt3': 101.82},
            's4-mc2.xml': {'name': 'Barcelona', 'ref_time_hyper': 88.59, 'ref_time_gt3': 100.60},
            's4-mc3.xml': {'name': 'Silverstone', 'ref_time_hyper': 102.23, 'ref_time_gt3': 117.76},
            's4-mc4.xml': {'name': 'Fuji', 'ref_time_hyper': 93.4, 'ref_time_gt3': 105.0},
            's4-mc5.xml': {'name': 'Bahrain (outer)', 'ref_time_hyper': 63.94, 'ref_time_gt3': 72.01}
        },
        'multiclass_races': {
            's4-mc1-r.xml': {'name': 'Imola', 'ref_time_hyper': 89.89, 'ref_time_gt3': 102.33},
            's4-mc2-r.xml': {'name': 'Barcelona', 'ref_time_hyper': 89.04, 'ref_time_gt3': 101.10},
            's4-mc3-r.xml': {'name': 'Silverstone', 'ref_time_hyper': 111.20, 'ref_time_gt3': 127.40},
            's4-mc4-r.xml': {'name': 'Fuji', 'ref_time_hyper': 91.0, 'ref_time_gt3': 103.5},
            's4-mc5-r.xml': {'name': 'Bahrain (outer)', 'ref_time_hyper': 64.26, 'ref_time_gt3': 72.37}
        }
    },
    # Add more seasons here as needed
}

DRIVER_REPLACEMENTS = {
    'Greg Kach': 'Greg Kachadurian',
    'R McLean': 'Ross McLean',
    'Ricky Swaby': 'Ricardo Swaby',
    'p thomas': 'Parker Thomas',
    'David Carter': 'Dave Carter',
    'David Carter#5529': 'Dave Carter',
    'John P': 'John Pflibsen',
    'Ayrton Senna': 'Ayrton Torres',
    'Avi Ganti': 'Avinash Ganti',
    'p thom': 'Parker Thomas',
    'J P#2423': 'J.P.',
    'G Wulf': 'Gene Wulf',
    'C M Wilson': 'Chris Wilson',
}

# TRACK_NAMES = ['Portimao', 'Le Mans', 'Interlagos', 'Monza', 'Sebring', 'Paul Ricard', 'COTA', 'Spa']


def calculate_lap_stats(laps_data):
    """
    Calculate statistics from list of lap times.
    
    Args:
        laps_data: List of lap time floats
        
    Returns:
        Dict with 'best', 'avg', 'stdev', 'count' keys
    """
    if not laps_data or len(laps_data) == 0:
        return {'best': 0.0, 'avg': 0.0, 'stdev': 0.0, 'count': 0}
    
    laps_array = np.array(laps_data)
    return {
        'best': float(np.min(laps_array)),
        'avg': float(np.mean(laps_array)),
        'stdev': float(np.mean(laps_array)-np.min(laps_array)) if len(laps_array) > 1 else 0.0,  # Use mean-min as a simple consistency metric
        'count': len(laps_data)
    }


def build_xml_path(season_id, series_type, filename):
    """
    Build XML file path for a season.
    
    Args:
        season_id: Season identifier (e.g., 'season1')
        series_type: 'sprint' or 'multiclass'
        filename: XML filename
        
    Returns:
        Full path to XML file
    """
    return os.path.join('xml', season_id, series_type, filename)


def get_sidebar_html(active_page, season_id='season1'):
    """Generate sidebar navigation HTML with season selector"""
    pages = {
        'sprint_race': ('Sprint', 'Race Pace'),
        'sprint_quali': ('Sprint', 'Quali Pace'),
        'multiclass_p2ur_race': ('Multiclass P2UR', 'Race Pace'),
        'multiclass_p2ur_quali': ('Multiclass P2UR', 'Quali Pace'),
        'multiclass_gt3_race': ('Multiclass GT3', 'Race Pace'),
        'multiclass_gt3_quali': ('Multiclass GT3', 'Quali Pace'),
    }
    
    sidebar_html = '<nav class="sidebar"><div class="sidebar-content">'
    
    # Season selector dropdown
    sidebar_html += '<div class="season-selector-wrapper"><label for="seasonSelector" style="color: #ccfc00; display: block; margin-bottom: 8px; font-size: 0.9em; font-weight: 600;">📅 Season</label>'
    sidebar_html += '<select id="seasonSelector" style="width: 100%; padding: 8px; background: #333; color: #ccfc00; border: 1px solid #ccfc00; border-radius: 5px; font-size: 0.9em;">'
    
    for s_id, s_info in SEASONS.items():
        selected = 'selected' if s_id == season_id else ''
        sidebar_html += f'<option value="{s_id}" {selected}>{s_info["name"]}</option>'
    
    sidebar_html += '</select></div>'
    sidebar_html += '<hr style="border: none; border-top: 1px solid #555; margin: 15px 0;">'
    sidebar_html += '<h3 style="color: #ccfc00; margin-bottom: 20px; margin-top: 15px;">📊 Dashboard</h3>'
    
    current_section = None
    for page_key, (section, subsection) in pages.items():
        if section != current_section:
            if current_section is not None:
                sidebar_html += '</ul></div>'
            current_section = section
            sidebar_html += f'<div class="section-group"><h4>{section}</h4><ul>'
        
        is_active = 'active' if page_key == active_page else ''
        file_name = page_key.replace('_', '_') + '.html'
        sidebar_html += f'<li><a href="{file_name}" class="{is_active}">{subsection}</a></li>'
    
    sidebar_html += '</ul></div></nav>'
    return sidebar_html


def extract_xml_drivers(xml_path):
    """Parse XML file and extract driver lap time data including all individual laps"""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    child = root[0]
    subchild = child[-1]
    drivers_data = []
    
    for driver_elem in subchild.findall('Driver'):
        driver_info = {}
        driver_info['Driver'] = driver_elem.findtext('Name', 'Unknown')
        driver_info['Car'] = driver_elem.findtext('CarType', 'Unknown')
        driver_info['CarClass'] = driver_elem.findtext('CarClass', 'Unknown')
        driver_info['CarNumber'] = driver_elem.findtext('CarNumber', 'N/A')
        driver_info['Position'] = driver_elem.findtext('Position', 'N/A')
        driver_info['BestLapTime'] = driver_elem.findtext('BestLapTime', '')
        driver_info['Laps'] = driver_elem.findtext('Laps', '0')
        driver_info['FinishStatus'] = driver_elem.findtext('FinishStatus', '')
        
        # Extract all lap times
        lap_elements = driver_elem.findall('Lap')
        laps_data = []
        for lap_elem in lap_elements:
            try:
                lap_time = float(lap_elem.text) if lap_elem.text else 0.0
                if len(laps_data)>0 and lap_time > min(laps_data)*1.04:  # Filter out outlier lap times (e.g., pit stops, crashes)
                    continue
                if lap_time > 0:
                    laps_data.append(lap_time)
            except (ValueError, TypeError):
                pass
        
        driver_info['laps_data'] = laps_data
        
        # Calculate lap statistics
        lap_stats = calculate_lap_stats(laps_data)
        driver_info['best_laptime'] = lap_stats['best']
        driver_info['avg_laptime'] = lap_stats['avg']
        driver_info['stdev_laptime'] = lap_stats['stdev']
        driver_info['lap_count'] = lap_stats['count']
        
        # Format best lap time for display
        try:
            best_lap_float = float(driver_info['BestLapTime'])
            minutes = int(best_lap_float // 60)
            seconds = best_lap_float % 60
            driver_info['Best Lap'] = f"{minutes}:{seconds:06.3f}"
            driver_info['Best Lap  Laps'] = f"{minutes}:{seconds:06.3f}"
        except (ValueError, TypeError):
            if driver_info['BestLapTime']:
                driver_info['Best Lap'] = driver_info['BestLapTime']
                driver_info['Best Lap  Laps'] = driver_info['BestLapTime']
            else:
                driver_info['Best Lap'] = 'DNF'
                driver_info['Best Lap  Laps'] = 'DNF'
        
        drivers_data.append(driver_info)
    
    if drivers_data:
        return [pd.DataFrame(drivers_data)]
    else:
        return []


def convert_laptime_to_seconds(laptime_str):
    """Convert laptime string (MM:SS.SSS or float) to seconds"""
    if pd.isna(laptime_str) or laptime_str == '' or laptime_str == 'DNF':
        return 0.0
    
    str_val = str(laptime_str).strip()
    
    if ':' in str_val:
        try:
            parts = str_val.split(':')
            minutes = float(parts[0])
            seconds = float(parts[1])
            return minutes * 60 + seconds
        except (ValueError, IndexError):
            return 0.0
    
    try:
        return float(str_val)
    except ValueError:
        return 0.0


def process_race_data(xml_path, ref_laptime):
    """Process a single race XML file with lap statistics"""
    tables = extract_xml_drivers(xml_path)
    if not tables:
        return None
    
    df = tables[0].copy()
    df['laptime_sec'] = df['Best Lap  Laps'].apply(convert_laptime_to_seconds)
    df['Driver_name'] = df['Driver'].apply(
        lambda x: str(x).split('LMGT3')[0].strip() if 'LMGT3' in str(x) else str(x).strip()
    )
    
    # Apply driver name replacements
    for old, new in DRIVER_REPLACEMENTS.items():
        df['Driver_name'] = df['Driver_name'].replace(old, new)
    
    # Calculate pace percentages from best lap
    min_laptime = df[df['laptime_sec'] > 0]['laptime_sec'].min()
    df['laptime_pct'] = round(min_laptime / df['laptime_sec'] * 100, 2) if min_laptime > 0 else 100
    df['laptime_pct_alien'] = round(df['laptime_sec'] / ref_laptime * 100, 2) if ref_laptime > 0 else 100
    
    # Calculate pace percentages from average lap
    df['avg_pace_pct_alien'] = round(df['avg_laptime'] / ref_laptime * 100, 2) if ref_laptime > 0 else 100
    df['stdev_pace_pct'] = round(df['stdev_laptime'] / ref_laptime * 100, 2) if ref_laptime > 0 else 0
    
    return df


def process_multiclass_race_data(xml_path, car_class, ref_laptime):
    """Process a single multiclass race XML file, filtered by car class (P2UR or GT3)"""
    tables = extract_xml_drivers(xml_path)
    if not tables:
        return None
    
    df = tables[0].copy()
    
    # Filter by car class
    if car_class.upper() == 'P2UR':
        df = df[df['CarClass'].str.contains('LMP2_ELMS', case=False, na=False)]
    elif car_class.upper() == 'GT3':
        df = df[df['CarClass'].str.contains('GT3', case=False, na=False)]
    elif car_class.upper() == 'HYPER':
        df = df[df['CarClass'].str.contains('Hyper', case=False, na=False)]
    
    if df.empty:
        return None
    
    df['laptime_sec'] = df['Best Lap  Laps'].apply(convert_laptime_to_seconds)
    df['Driver_name'] = df['Driver'].apply(
        lambda x: str(x).split('LMGT3')[0].strip() if 'LMGT3' in str(x) else str(x).strip()
    )
    
    # Apply driver name replacements
    for old, new in DRIVER_REPLACEMENTS.items():
        df['Driver_name'] = df['Driver_name'].replace(old, new)
    
    # Calculate pace percentages from best lap
    min_laptime = df[df['laptime_sec'] > 0]['laptime_sec'].min()
    df['laptime_pct'] = round(min_laptime / df['laptime_sec'] * 100, 2) if min_laptime > 0 else 100
    df['laptime_pct_alien'] = round(df['laptime_sec'] / ref_laptime * 100, 2) if ref_laptime > 0 else 100

    # Calculate pace percentages from average lap
    df['avg_pace_pct_alien'] = round(df['avg_laptime'] / ref_laptime * 100, 2) if ref_laptime > 0 else 100
    df['stdev_pace_pct'] = round(df['stdev_laptime'] / ref_laptime * 100, 2) if ref_laptime > 0 else 0
    
    return df


def extract_code_from_filename(filename, prefix):
    """Extract race code from filename (e.g., 's3-sc1-r.xml' -> 'sc1')"""
    # Remove prefix and extensions
    name = filename.replace(f'{prefix}-', '').replace('-r.xml', '').replace('.xml', '')
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
        xml_path = os.path.join(xml_folder, filename)
        if os.path.exists(xml_path):
            track_name = race_info['name']
            
            # Extract code from filename
            code = extract_code_from_filename(filename, prefix)
            
            race_codes.append(code)
            track_names.append(track_name)
            code_to_track[code] = track_name
    
    return race_codes, track_names, code_to_track


def process_races_into_comparison_df(dfs_dict, race_codes, code_to_track):
    """
    Build a comparison dataframe from loaded race dataframes.
    
    Args:
        dfs_dict: Dictionary of {track_name: dataframe}
        race_codes: List of race codes in order (e.g., ['sc1', 'sc2', 'sc3'])
        code_to_track: Dict mapping code to track name
    
    Returns:
        - comparison_df: Merged dataframe with all races
        - pace_cols: List of pace column names (best lap basis)
        - avg_pace_cols: List of average pace column names
    """
    if not race_codes:
        return None, [], []
    
    # Start with first race
    first_code = race_codes[0]
    first_track = code_to_track[first_code]
    
    if first_track not in dfs_dict:
        print(f"    DEBUG: first_track '{first_track}' not in dfs_dict keys: {list(dfs_dict.keys())}")
        return None, [], []
    
    print(f"    DEBUG: Starting comparison_df from {first_track} with shape {dfs_dict[first_track].shape}")
    comparison_df = dfs_dict[first_track][['Driver_name', 'laptime_sec', 'laptime_pct', 'laptime_pct_alien', 'avg_laptime', 'avg_pace_pct_alien', 'stdev_laptime', 'stdev_pace_pct']].rename(
        columns={
            'laptime_sec': f'laptime_sec_{first_code}',
            'laptime_pct': f'laptime_pct_{first_code}',
            'laptime_pct_alien': f'laptime_pct_alien_{first_code}',
            'avg_laptime': f'avg_laptime_{first_code}',
            'avg_pace_pct_alien': f'avg_pace_pct_alien_{first_code}',
            'stdev_laptime': f'stdev_laptime_{first_code}',
            'stdev_pace_pct': f'stdev_pace_pct_{first_code}',
        }
    ).copy()
    
    pace_cols = [f'laptime_pct_alien_{first_code}']
    avg_pace_cols = [f'avg_pace_pct_alien_{first_code}']
    
    print(f"    DEBUG: After first race, comparison_df shape: {comparison_df.shape}")
    
    # Merge remaining races
    for code in race_codes[1:]:
        track_name = code_to_track[code]
        if track_name in dfs_dict:
            print(f"    DEBUG: Merging {track_name}...")
            comparison_df = comparison_df.merge(
                dfs_dict[track_name][['Driver_name', 'laptime_sec', 'laptime_pct', 'laptime_pct_alien', 'avg_laptime', 'avg_pace_pct_alien', 'stdev_laptime', 'stdev_pace_pct']].rename(
                    columns={
                        'laptime_sec': f'laptime_sec_{code}',
                        'laptime_pct': f'laptime_pct_{code}',
                        'laptime_pct_alien': f'laptime_pct_alien_{code}',
                        'avg_laptime': f'avg_laptime_{code}',
                        'avg_pace_pct_alien': f'avg_pace_pct_alien_{code}',
                        'stdev_laptime': f'stdev_laptime_{code}',
                        'stdev_pace_pct': f'stdev_pace_pct_{code}',
                    }
                ),
                on='Driver_name',
                how='outer'
            )
            print(f"    DEBUG: After merge with {track_name}, shape: {comparison_df.shape}")
            pace_cols.append(f'laptime_pct_alien_{code}')
            avg_pace_cols.append(f'avg_pace_pct_alien_{code}')
    
    # Clean up - use average pace columns for filtering
    print(f"    DEBUG: Before cleanup, comparison_df shape: {comparison_df.shape}, avg_pace_cols: {avg_pace_cols}")
    comparison_df = comparison_df.replace(0.00, np.nan).dropna(subset=avg_pace_cols, how='all')
    print(f"    DEBUG: After dropna(how='all'), comparison_df shape: {comparison_df.shape}")
    # Replace any entries over 107% with NaN to filter out outliers (use avg pace for filtering)
    for col in avg_pace_cols:
        comparison_df[col] = comparison_df[col].apply(lambda x: x if pd.isna(x) or x <= 107.0 else np.nan)
    print(f"    DEBUG: After filtering 107% outliers, comparison_df shape: {comparison_df.shape}")
    comparison_df = comparison_df.sort_values('Driver_name').reset_index(drop=True)
    
    if comparison_df.empty:
        print("    DEBUG: comparison_df is EMPTY after cleanup!")
        return None, pace_cols, avg_pace_cols
    
    return comparison_df, pace_cols, avg_pace_cols


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


def create_display_df(comparison_df, avg_pace_cols, stdev_pace_cols, track_names, mode='race'):
    """Create display dataframe with renamed columns using average pace"""
    display_df = comparison_df[['Driver_name'] + avg_pace_cols + stdev_pace_cols].copy()
    display_df = display_df.replace(0.00, np.nan).dropna(subset=avg_pace_cols, how='all')
    display_df['best_pct'] = display_df[avg_pace_cols].min(axis=1)
    display_df = display_df.sort_values('best_pct')
    
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
        lambda x: f"{x.split()[0]} {x.split()[-1][0]}." if len(x.split()) > 1 else x
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
        lambda x: f"{x.split()[0]} {x.split()[-1][0]}." if len(x.split()) > 1 else x
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
    
    # Build plot_df using average pace columns, standard deviation columns, and fastest lap columns
    plot_df = comparison_df[['Driver_name'] + avg_pace_cols + stdev_pace_cols + fastest_lap_cols].copy()
    
    # Filter drivers who attended more than 2 races
    races_attended = plot_df[avg_pace_cols].notna().sum(axis=1)
    plot_df = plot_df[races_attended > 1].reset_index(drop=True)
    
    # Calculate best average pace
    plot_df['best'] = plot_df[avg_pace_cols].min(axis=1, skipna=True)
    plot_df = plot_df.sort_values('best').reset_index(drop=True)
    
    # Create traces for Plotly
    traces = []
    x_positions = list(range(len(track_names)))
    
    for _, (_, row) in enumerate(plot_df.iterrows()):
        driver_name = row['Driver_name']

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
                f"{driver_name}<br>Fastest Lap: {fl:.2f}%"
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
                'line': {'width': 2},
                'marker': {'size': 8},
                'opacity': 1.0,
                # No ci_lower / ci_upper — JS drawConfidenceInterval will skip this trace
            }

        else:
            # Race mode: plot average pace with confidence intervals, fastest lap in hover
            pts = []
            ci_lower = []
            ci_upper = []
            fastest_laps = []

            for xi, (avg_col, sd_col, fastest_col) in enumerate(zip(avg_pace_cols, stdev_pace_cols, fastest_lap_cols)):
                avg_val = row.get(avg_col)
                sd_val = row.get(sd_col)
                fastest_val = row.get(fastest_col)

                if pd.notna(avg_val):
                    pts.append((xi, avg_val))
                    lower_bound = avg_val - sd_val if pd.notna(sd_val) else avg_val
                    upper_bound = avg_val + sd_val if pd.notna(sd_val) else avg_val
                    ci_lower.append(lower_bound)
                    ci_upper.append(upper_bound)
                    fastest_laps.append(fastest_val if pd.notna(fastest_val) else avg_val)
                else:
                    ci_lower.append(None)
                    ci_upper.append(None)
                    fastest_laps.append(None)

            if not pts:
                continue

            xs, ys = zip(*pts)
            hover_data = []
            for avg_pace, fastest_lap in zip(ys, fastest_laps):
                if fastest_lap is None or (isinstance(fastest_lap, float) and pd.isna(fastest_lap)):
                    fastest_lap_str = f"{avg_pace:.2f}%"
                else:
                    fastest_lap_str = f"{fastest_lap:.2f}%"
                hover_data.append(f"{driver_name}<br>Avg Pace: {avg_pace:.2f}%<br>Fastest Lap: {fastest_lap_str}")

            # Display lines if more than 2 points, regardless of NaN at the end
            mode_race = 'lines+markers' 
            trace = {
                'x': list(xs),
                'y': list(ys),
                'mode': mode_race,
                'name': driver_name,
                'hovertemplate': "%{customdata}<extra></extra>",
                'customdata': hover_data,
                'line': {'width': 2},
                'marker': {'size': 8},
                'opacity': 1.0,
                'ci_lower': ci_lower,
                'ci_upper': ci_upper,
            }

        traces.append(trace)
    
    return {
        'traces': traces,
        'layout': {
            'title': chart_title,
            'xaxis': {
                'tickmode': 'array',
                'ticktext': track_names,
                'tickvals': x_positions
            },
            'yaxis': {
                'title': y_axis_title,
                'range': [time_lower, time_upper]
            },
            'hovermode': 'closest',
            'plot_bgcolor': 'rgba(240, 240, 240, 0.5)',
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



def generate_page(title, sidebar_file, season_id, pace_html, improvement_html, plotly_data):
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
    print("[*] OOFS S3 Stats Page Generator\n")
    print("=" * 60)
    
    # Create top-level docs folder
    os.makedirs('docs', exist_ok=True)

    # NEW: Copy the CSS file into the docs folder so GitHub Pages can see it
    try:
        shutil.copy(os.path.join(TEMPLATES_DIR, 'styles.css'), os.path.join('docs', 'styles.css'))
        print("  Copied styles.css to docs/")
    except FileNotFoundError:
        print("  WARNING: templates/styles.css not found!")

    # Generate top-level season index page
    print("\n[Index] Generating docs/index.html...")
    card_html = ''
    for s_id, s_info in SEASONS.items():
        card_html += (
            f'\n        <a class="season-card" href="{s_id}/sprint_race.html">'
            f'\n            <span class="season-label">Season</span>'
            f'\n            <span class="season-name">{s_info["name"]}</span>'
            f'\n            <span class="season-year">{s_info["year"]}</span>'
            f'\n            <span class="season-desc">{s_info["description"]}</span>'
            f'\n        </a>'
        )

    index_template_path = os.path.join(TEMPLATES_DIR, 'index.html')
    with open(index_template_path, 'r', encoding='utf-8') as f:
        index_template = f.read()
    index_html = index_template.replace('{season_cards}', card_html)

    with open(os.path.join('docs', 'index.html'), 'w', encoding='utf-8-sig') as f:
        f.write(index_html)
    print("  Generated docs/index.html")

    # Loop through all configured seasons
    for season_id, season_info in SEASONS.items():
        print(f"\n[Season] Processing {season_info['name']}...")
        season_config = SEASON_CONFIG[season_id]
        
        # Create season-specific output folder
        season_output_dir = os.path.join('docs', season_id)
        os.makedirs(season_output_dir, exist_ok=True)
        
        # ===== SPRINT RACE PACE =====
        print("  [Sprint] Race Pace...")
        sprint_race_dfs = {}
        xml_folder = os.path.join('xml', season_id, 'sprint')
        
        for filename, race_info in season_config['sprint_races'].items():
            xml_path = os.path.join(xml_folder, filename)
            if os.path.exists(xml_path):
                df = process_race_data(xml_path, race_info['ref_time'])
                if df is not None:
                    sprint_race_dfs[race_info['name']] = df
            else:
                print(f"    Not found: {xml_path}")
        
        print(f"    DEBUG: After loading, sprint_race_dfs={list(sprint_race_dfs.keys()) if sprint_race_dfs else 'EMPTY'}")
        
        if sprint_race_dfs:
            print(f"    DEBUG: sprint_race_dfs has {len(sprint_race_dfs)} entries: {list(sprint_race_dfs.keys())}")
            race_codes, track_names, code_to_track = load_races_dynamically(season_config['sprint_races'], xml_folder)
            print(f"    DEBUG: race_codes={race_codes}, code_to_track={code_to_track}")
            comparison_df, _, avg_pace_cols = process_races_into_comparison_df(sprint_race_dfs, race_codes, code_to_track)
            
            if comparison_df is not None:
                improvement_df = build_improvement_df(comparison_df, avg_pace_cols)
                stdev_pace_cols = [f'stdev_pace_pct_{code}' for code in race_codes]
                df_display_renamed, _ = create_display_df(comparison_df, avg_pace_cols, stdev_pace_cols, track_names, mode='race')
                pace_html, improvement_html = generate_html_tables(comparison_df, improvement_df, avg_pace_cols, track_names)
                
                num_rounds = len(track_names)
                plotly_data = create_plotly_json(df_display_renamed, comparison_df, avg_pace_cols, stdev_pace_cols, track_names,
                    f'Sprint Race Pace Trend: After {num_rounds} Rounds', 'Race Pace % (vs Alien)', race_type='race')
                
                html_content = generate_page('🏁 Sprint Race Pace Data',
                    'sprint_race.html', season_id, pace_html, improvement_html, plotly_data)
                
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
        
        # ===== SPRINT QUALI PACE =====
        print("  [Sprint] Quali Pace...")
        sprint_quali_dfs = {}
        
        for filename, quali_info in season_config['sprint_qualis'].items():
            xml_path = os.path.join(xml_folder, filename)
            if os.path.exists(xml_path):
                df = process_race_data(xml_path, quali_info['ref_time'])
                if df is not None:
                    sprint_quali_dfs[quali_info['name']] = df
        
        if sprint_quali_dfs:
            race_codes, track_names, code_to_track = load_races_dynamically(season_config['sprint_qualis'], xml_folder)
            comparison_df, _, avg_pace_cols = process_races_into_comparison_df(sprint_quali_dfs, race_codes, code_to_track)
            
            if comparison_df is not None:
                # Create fastest lap column names and pass instead of average pace 
                fastest_lap_cols = [col.replace('avg_pace_pct_alien_', 'laptime_pct_alien_') for col in avg_pace_cols]
                improvement_df = build_improvement_df(comparison_df, fastest_lap_cols)
                # improvement_df = build_improvement_df(comparison_df, avg_pace_cols)
                stdev_pace_cols = [f'stdev_pace_pct_{code}' for code in race_codes]
                df_display_renamed, _ = create_display_df(comparison_df, avg_pace_cols, stdev_pace_cols, track_names, mode='quali')
                pace_html, improvement_html = generate_html_tables(comparison_df, improvement_df, avg_pace_cols, track_names, mode='quali')
                
                num_rounds = len(track_names)
                plotly_data = create_plotly_json(df_display_renamed, comparison_df, avg_pace_cols, stdev_pace_cols, track_names,
                    f'Sprint Quali Pace Trend: After {num_rounds} Rounds', 'Quali Pace % (vs Alien)', race_type='quali')
                
                html_content = generate_page('🏁 Sprint Quali Pace Data',
                    'sprint_quali.html', season_id, pace_html, improvement_html, plotly_data)
                
                with open(os.path.join(season_output_dir, 'sprint_quali.html'), 'w', encoding='utf-8-sig') as f:
                    f.write(html_content)
                print("    Generated sprint_quali.html")
        else:
            print("    No sprint quali data found")
        
        # ===== MULTICLASS P2UR/Hyper RACE PACE =====
        proto_class = 'P2UR' if season_id == 'season1' else 'Hyper'
        print(f"  [Multiclass] {proto_class}/GT3 Race Pace...")
        mc_p2ur_race_dfs = {}
        xml_folder_mc = os.path.join('xml', season_id, 'multiclass')
        
        for filename, mc_info in season_config['multiclass_races'].items():
            xml_path = os.path.join(xml_folder_mc, filename)
            if os.path.exists(xml_path):
                if season_id == 'season1':
                    df = process_multiclass_race_data(xml_path, 'P2UR', mc_info['ref_time_p2ur'])
                else:
                    df = process_multiclass_race_data(xml_path, 'Hyper', mc_info['ref_time_hyper'])
                if df is not None:
                    mc_p2ur_race_dfs[mc_info['name']] = df
            else:
                print(f"    Not found: {xml_path}")
        
        if mc_p2ur_race_dfs:
            race_codes, track_names, code_to_track = load_races_dynamically(season_config['multiclass_races'], xml_folder_mc)
            comparison_df, _, avg_pace_cols = process_races_into_comparison_df(mc_p2ur_race_dfs, race_codes, code_to_track)
            
            if comparison_df is not None:
                improvement_df = build_improvement_df(comparison_df, avg_pace_cols)
                stdev_pace_cols = [f'stdev_pace_pct_{code}' for code in race_codes]
                df_display_renamed, _ = create_display_df(comparison_df, avg_pace_cols, stdev_pace_cols, track_names, mode='race')
                pace_html, improvement_html = generate_html_tables(comparison_df, improvement_df, avg_pace_cols, track_names)
                
                num_rounds = len(track_names)
                proto_class = 'P2UR' if season_id == 'season1' else 'Hyper'
                plotly_data = create_plotly_json(df_display_renamed, comparison_df, avg_pace_cols, stdev_pace_cols, track_names,
                    f'Multiclass {proto_class} Race Pace Trend: After {num_rounds} Rounds', 'Race Pace % (vs Alien)', race_type='race')
                
                html_content = generate_page(f'🏆 Multiclass {proto_class} Race Pace Data',
                    'multiclass_p2ur_race.html', season_id, pace_html, improvement_html, plotly_data)
                
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
                    df = process_multiclass_race_data(xml_path, 'P2UR', mc_info['ref_time_p2ur'])
                else:
                    df = process_multiclass_race_data(xml_path, 'Hyper', mc_info['ref_time_hyper'])
                if df is not None:
                    mc_p2ur_quali_dfs[mc_info['name']] = df
            else:
                print(f"    Not found: {xml_path}")
        
        if not mc_p2ur_quali_dfs:
            print(f"    No {proto_class_label} data found for qualies")
        else:
            race_codes, track_names, code_to_track = load_races_dynamically(season_config['multiclass_qualis'], xml_folder_mc)
            comparison_df, _, avg_pace_cols = process_races_into_comparison_df(mc_p2ur_quali_dfs, race_codes, code_to_track)
            
            if comparison_df is not None:
                # Create fastest lap column names and pass instead of average pace
                fastest_lap_cols = [col.replace('avg_pace_pct_alien_', 'laptime_pct_alien_') for col in avg_pace_cols]
                improvement_df = build_improvement_df(comparison_df, fastest_lap_cols)

                # improvement_df = build_improvement_df(comparison_df, avg_pace_cols)
                stdev_pace_cols = [f'stdev_pace_pct_{code}' for code in race_codes]
                df_display_renamed, _ = create_display_df(comparison_df, avg_pace_cols, stdev_pace_cols, track_names, mode='quali')
                pace_html, improvement_html = generate_html_tables(comparison_df, improvement_df, avg_pace_cols, track_names, mode='quali')
                
                num_rounds = len(track_names)
                proto_class = 'P2UR' if season_id == 'season1' else 'Hyper'
                plotly_data = create_plotly_json(df_display_renamed, comparison_df, avg_pace_cols, stdev_pace_cols, track_names,
                    f'Multiclass {proto_class} Quali Pace Trend: After {num_rounds} Rounds', 'Quali Pace % (vs Alien)', race_type='quali')
                
                html_content = generate_page(f'🏆 Multiclass {proto_class} Quali Pace Data',
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
                df = process_multiclass_race_data(xml_path, 'GT3', mc_info['ref_time_gt3'])
                if df is not None:
                    mc_gt3_race_dfs[mc_info['name']] = df
        
        if mc_gt3_race_dfs:
            race_codes, track_names, code_to_track = load_races_dynamically(season_config['multiclass_races'], xml_folder_mc)
            comparison_df, _, avg_pace_cols = process_races_into_comparison_df(mc_gt3_race_dfs, race_codes, code_to_track)
            
            if comparison_df is not None:
                improvement_df = build_improvement_df(comparison_df, avg_pace_cols)
                stdev_pace_cols = [f'stdev_pace_pct_{code}' for code in race_codes]
                df_display_renamed, _ = create_display_df(comparison_df, avg_pace_cols, stdev_pace_cols, track_names, mode='race')
                pace_html, improvement_html = generate_html_tables(comparison_df, improvement_df, avg_pace_cols, track_names)
                
                num_rounds = len(track_names)
                plotly_data = create_plotly_json(df_display_renamed, comparison_df, avg_pace_cols, stdev_pace_cols, track_names,
                    f'Multiclass GT3 Race Pace Trend: After {num_rounds} Rounds', 'Race Pace % (vs Alien)', race_type='race')
                
                html_content = generate_page('🏆 Multiclass GT3 Race Pace Data',
                    'multiclass_gt3_race.html', season_id, pace_html, improvement_html, plotly_data)
                
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
                df = process_multiclass_race_data(xml_path, 'GT3', mc_info['ref_time_gt3'])
                if df is not None:
                    mc_gt3_quali_dfs[mc_info['name']] = df
        
        if mc_gt3_quali_dfs:
            race_codes, track_names, code_to_track = load_races_dynamically(season_config['multiclass_qualis'], xml_folder_mc)
            comparison_df, _, avg_pace_cols = process_races_into_comparison_df(mc_gt3_quali_dfs, race_codes, code_to_track)
            
            if comparison_df is not None:

                # Create fastest lap column names and pass instead of average pace
                fastest_lap_cols = [col.replace('avg_pace_pct_alien_', 'laptime_pct_alien_') for col in avg_pace_cols]
                improvement_df = build_improvement_df(comparison_df, fastest_lap_cols)

                # improvement_df = build_improvement_df(comparison_df, avg_pace_cols)
                stdev_pace_cols = [f'stdev_pace_pct_{code}' for code in race_codes]
                df_display_renamed, _ = create_display_df(comparison_df, avg_pace_cols, stdev_pace_cols, track_names, mode='quali')
                pace_html, improvement_html = generate_html_tables(comparison_df, improvement_df, avg_pace_cols, track_names, mode='quali')
                
                num_rounds = len(track_names)
                plotly_data = create_plotly_json(df_display_renamed, comparison_df, avg_pace_cols, stdev_pace_cols, track_names,
                    f'Multiclass GT3 Quali Pace Trend: After {num_rounds} Rounds', 'Quali Pace % (vs Alien)', race_type='quali')
                
                html_content = generate_page('🏆 Multiclass GT3 Quali Pace Data',
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