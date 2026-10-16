"""HTML, table, and chart rendering helpers for season reports."""

import colorsys
import json
import os

import numpy as np
import pandas as pd

from csv_lib import (
    build_improvement_df,
    get_multiclass_championship_name,
    get_multiclass_prototype_class,
    season_has_sprint_class_data,
)


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

def get_sidebar_html(active_page, season_id='season1'):
    """Generate sidebar navigation HTML with season selector"""
    pages = {}
    has_split_sprint_classes = season_has_sprint_class_data(season_id)
    prototype_class = get_multiclass_prototype_class(season_id)
    championship_name = get_multiclass_championship_name(season_id)

    if not has_split_sprint_classes:
        pages.update({
            'sprint_race': ('Sprint', 'Race'),
            'sprint_quali': ('Sprint', 'Quali'),
        })
        print('DEBUG: Sidebar pages:', pages)
    else:
        pages.update({
            'sprint_lmp3_race': ('Sprint LMP3', 'Race'),
            'sprint_lmp3_quali': ('Sprint LMP3', 'Quali'),
            'sprint_gt3_race': ('Sprint GT3', 'Race'),
            'sprint_gt3_quali': ('Sprint GT3', 'Quali'),
        })

    pages.update({
        'multiclass_p2ur_race': (f'{championship_name} {prototype_class}', 'Race'),
        'multiclass_p2ur_quali': (f'{championship_name} {prototype_class}', 'Quali'),
        'multiclass_gt3_race': (f'{championship_name} GT3', 'Race'),
        'multiclass_gt3_quali': (f'{championship_name} GT3', 'Quali'),
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
                if pd.notna(fastest_val) and 0 < fastest_val <= time_upper:
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

                if not pd.notna(avg_val) or avg_val > time_upper:
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


def generate_comparison_page(
    comparison_df,
    avg_pace_cols,
    used_race_codes,
    track_names,
    title,
    sidebar_file,
    season_id,
    chart_title_prefix,
    y_axis_title,
    mode='race',
):
    """Render a complete race or qualifying comparison page."""
    improvement_cols = avg_pace_cols
    if mode == 'quali':
        improvement_cols = [
            column.replace('avg_pace_pct_alien_', 'laptime_pct_alien_')
            for column in avg_pace_cols
        ]

    improvement_df = build_improvement_df(comparison_df, improvement_cols)
    stdev_pace_cols = [f'stdev_pace_pct_{code}' for code in used_race_codes]
    display_df, _ = create_display_df(
        comparison_df, avg_pace_cols, stdev_pace_cols, track_names, mode=mode
    )
    pace_html, improvement_html = generate_html_tables(
        comparison_df, improvement_df, avg_pace_cols, track_names, mode=mode
    )
    descriptor_tables_html = (
        generate_descriptor_tables(comparison_df, used_race_codes, track_names)
        if mode == 'race' else ''
    )
    plotly_data = create_plotly_json(
        display_df,
        comparison_df,
        avg_pace_cols,
        stdev_pace_cols,
        track_names,
        f'{chart_title_prefix}: After {len(track_names)} Rounds',
        y_axis_title,
        race_type=mode,
    )
    return generate_page(
        title,
        sidebar_file,
        season_id,
        pace_html,
        improvement_html,
        plotly_data,
        descriptor_tables_html,
    )
