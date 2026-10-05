"""Generate canonical per-event descriptor CSVs from configured XML results."""

import argparse
import os

from generate_stats_page import (
    SEASONS,
    build_csv_path,
    load_season_config,
    normalize_driver_name,
)
from lmu_descriptors import LMUDescriptor


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