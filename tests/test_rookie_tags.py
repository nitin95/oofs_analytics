import os
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

import pandas as pd

import generate_descriptor_csvs as csvgen
import generate_stats_page as stats
from lmu_descriptors import LMUDescriptor


class RookieTagTests(unittest.TestCase):
    def setUp(self):
        self.original_cwd = os.getcwd()
        self.original_seasons = stats.SEASONS
        self.temp_dir = tempfile.TemporaryDirectory()
        os.chdir(self.temp_dir.name)
        stats.SEASONS = {'season1': {}, 'season2': {}, 'season3': {}}
        for season_id in stats.SEASONS:
            self.write_config(season_id, {})

    def tearDown(self):
        stats.SEASONS = self.original_seasons
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def write_config(self, season_id, config):
        folder = os.path.join('assets', 'json')
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, f'{season_id}.json'), 'w', encoding='utf-8') as config_file:
            json.dump(config, config_file)

    def write_race(self, season_id, series_type, filename, drivers):
        folder = os.path.join('assets', 'csv', season_id, series_type)
        os.makedirs(folder, exist_ok=True)
        rows = [
            {'Driver': name, 'Driver_name': stats.normalize_driver_name(name), 'CarClass': car_class}
            for name, car_class in drivers
        ]
        csv_filename = os.path.splitext(filename)[0] + '.csv'
        pd.DataFrame(rows).to_csv(os.path.join(folder, csv_filename), index=False)
        section = f'{series_type}_qualis'
        config = stats.load_season_config(season_id)
        config.setdefault(section, {})[filename] = {'name': 'Test Track'}
        self.write_config(season_id, config)

    def write_descriptor_xml(self, path, drivers):
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        root = ET.Element('Results')
        for driver_data in drivers:
            driver = ET.SubElement(root, 'Driver')
            ET.SubElement(driver, 'Name').text = driver_data['name']
            ET.SubElement(driver, 'CarType').text = 'Test Car'
            ET.SubElement(driver, 'CarClass').text = driver_data['class']
            ET.SubElement(driver, 'CarNumber').text = '1'
            ET.SubElement(driver, 'Position').text = str(driver_data['position'])
            ET.SubElement(driver, 'ClassPosition').text = str(driver_data['position'])
            ET.SubElement(driver, 'FinishStatus').text = 'Finished'
            times = driver_data['times']
            ET.SubElement(driver, 'Laps').text = str(len(times) + 1)
            ET.SubElement(driver, 'Lap', {'num': '1', 'et': '--.---'}).text = '--.----'
            for lap_num, lap_time in enumerate(times, start=2):
                elapsed = driver_data.get('elapsed', {}).get(lap_num, (lap_num - 1) * 100)
                value = '--.----' if lap_time is None else str(lap_time)
                ET.SubElement(
                    driver, 'Lap', {'num': str(lap_num), 'et': str(elapsed)}
                ).text = value
        ET.ElementTree(root).write(path, encoding='utf-8')
        return path

    def test_baseline_season_has_no_inferred_rookies(self):
        self.write_race('season1', 'sprint', 's1.xml', [('New Driver', 'GT3')])

        rookies = stats.get_rookie_driver_names('season1', 'sprint', ['New Driver'])

        self.assertEqual(rookies, set())

    def test_event_configuration_is_loaded_from_season_json(self):
        config = {
            'sprint_qualis': {
                's1-sc1.xml': {
                    'name': 'Test Track',
                    'reference_times': {'default': 100},
                },
            },
        }
        self.write_config('season1', config)

        self.assertFalse(hasattr(stats, 'SEASON_CONFIG'))
        self.assertEqual(stats.load_season_config('season1'), config)

    def test_category_change_and_name_replacement_are_detected(self):
        self.write_race('season1', 'sprint', 's1.xml', [
            ('Greg Kach', 'GT3'),
            ('Alice Driver', 'GT3'),
        ])
        self.write_race('season2', 'sprint', 's2.xml', [
            ('Greg Kach', 'GT3'),
            ('Alice Driver', 'LMP3'),
        ])

        gt3_rookies = stats.get_rookie_driver_names(
            'season2', 'sprint', ['Greg Kachadurian'], 'GT3'
        )
        lmp3_rookies = stats.get_rookie_driver_names(
            'season2', 'sprint', ['Alice Driver'], 'LMP3'
        )

        self.assertEqual(gt3_rookies, set())
        self.assertEqual(lmp3_rookies, {'Alice Driver'})

    def test_series_history_is_independent(self):
        self.write_race('season1', 'multiclass', 'mc1.xml', [('Alice Driver', 'GT3')])
        self.write_race('season2', 'sprint', 's2.xml', [('Alice Driver', 'GT3')])

        rookies = stats.get_rookie_driver_names(
            'season2', 'sprint', ['Alice Driver'], 'GT3'
        )

        self.assertEqual(rookies, {'Alice Driver'})

    def test_prototype_category_continues_from_p2ur_to_hyper(self):
        self.write_race('season1', 'multiclass', 'mc1.xml', [('Alex Driver', 'LMP2_ELMS')])
        self.write_race('season2', 'multiclass', 'mc2.xml', [('Alex Driver', 'Hyper')])

        rookies = stats.get_rookie_driver_names(
            'season2', 'multiclass', ['Alex Driver'], 'PROTOTYPE'
        )

        self.assertEqual(rookies, set())

    def test_asterisk_is_presentation_only(self):
        comparison_df = pd.DataFrame([{
            'Driver_name': 'Greg Kachadurian',
            'is_rookie': True,
            'avg_pace_pct_alien_sc1': 101.2,
            'stdev_pace_pct_sc1': 0.4,
            'laptime_pct_alien_sc1': 100.8,
        }])
        improvement_df = pd.DataFrame([{
            'Driver_name': 'Greg Kachadurian',
            'best_first_two': 101.2,
            'best_last_two': 100.8,
            'improvement': 0.4,
        }])
        avg_cols = ['avg_pace_pct_alien_sc1']
        sd_cols = ['stdev_pace_pct_sc1']
        tracks = ['Portimao']

        pace_html, improvement_html = stats.generate_html_tables(
            comparison_df, improvement_df, avg_cols, tracks
        )
        display_df, _ = stats.create_display_df(
            comparison_df, avg_cols, sd_cols, tracks
        )
        plot_data = stats.create_plotly_json(
            display_df, comparison_df, avg_cols, sd_cols, tracks,
            'Pace', 'Pace %',
        )

        self.assertIn('<td>Greg K.*</td>', pace_html)
        self.assertIn('<td>Greg K.*</td>', improvement_html)
        self.assertIn('data-driver="Greg Kachadurian"', pace_html)
        self.assertEqual(plot_data['traces'][0]['name'], 'Greg Kachadurian')
        self.assertIn('Greg Kachadurian*', plot_data['traces'][0]['customdata'][0])

    def test_pace_above_chart_ceiling_remains_in_tables(self):
        event_df = pd.DataFrame([{
            'Driver_name': 'Slow Driver',
            'laptime_pct_alien_sc1': 108.2,
            'avg_pace_pct_alien_sc1': 108.2,
            'stdev_pace_pct_sc1': 0.4,
        }])
        comparison_df, _, avg_cols, _, tracks = stats.process_races_into_comparison_df(
            {'Test Track': event_df}, ['sc1'], {'sc1': 'Test Track'}
        )
        improvement_df = pd.DataFrame([{
            'Driver_name': 'Slow Driver',
            'best_first_two': 108.2,
            'best_last_two': 108.2,
            'improvement': 0.0,
        }])

        for mode in ('race', 'quali'):
            pace_html, _ = stats.generate_html_tables(
                comparison_df, improvement_df, avg_cols, tracks, mode=mode
            )
            display_df, _ = stats.create_display_df(
                comparison_df, avg_cols, ['stdev_pace_pct_sc1'], tracks, mode=mode
            )
            plot_data = stats.create_plotly_json(
                display_df, comparison_df, avg_cols, ['stdev_pace_pct_sc1'], tracks,
                'Pace', 'Pace %', race_type=mode,
            )

            self.assertIn('<td>108.20</td>', pace_html)
            self.assertTrue(all(
                value <= 107.0
                for trace in plot_data['traces']
                for value in trace['y']
            ))

    def test_race_descriptors_are_class_scoped_and_qualifying_is_pace_only(self):
        xml_path = self.write_descriptor_xml('race.xml', [
            {'name': 'Fast Driver', 'class': 'GT3', 'position': 1, 'times': [98, 100, 100]},
            {
                'name': 'Incident Driver', 'class': 'GT3', 'position': 2,
                'times': [100, None, 100], 'elapsed': {2: 100, 3: 205, 4: 305},
            },
            {'name': 'Prototype Driver', 'class': 'Hyper', 'position': 1, 'times': [80, 80, 80]},
        ])
        descriptor = LMUDescriptor()
        race_data = descriptor.get_descriptors(xml_path)
        incident = race_data[race_data['Driver'] == 'Incident Driver'].iloc[0]
        prototype = race_data[race_data['Driver'] == 'Prototype Driver'].iloc[0]
        quali_data = descriptor.get_quali_descriptors(xml_path)

        self.assertEqual(incident['n_tracklimits'], 1)
        self.assertEqual(incident['n_inchidents'], 1)
        self.assertAlmostEqual(incident['reliability'], 1 / 3)
        self.assertAlmostEqual(incident['race_pace'], 101.6667, places=3)
        self.assertAlmostEqual(incident['pct_race_pace'], 100 * 101.6667 / 99.3333, places=2)
        self.assertEqual(prototype['pct_race_pace'], 100.0)
        self.assertTrue(quali_data['reliability'].isna().all())
        self.assertTrue(quali_data['pct_race_pace'].isna().all())

    def test_csv_generator_writes_same_stem_quali_and_race_files(self):
        config = {
            'sprint_qualis': {
                'st-sc1.xml': {
                    'name': 'Test Track',
                    'reference_times': {'gt3': 100},
                },
            },
            'sprint_races': {
                'st-sc1-r.xml': {
                    'name': 'Test Track',
                    'reference_times': {'gt3': 100},
                },
            },
        }
        for filename in ('st-sc1.xml', 'st-sc1-r.xml'):
            self.write_descriptor_xml(
                os.path.join('assets', 'xml', 'season_test', 'sprint', filename),
                [{'name': 'Greg Kach', 'class': 'GT3', 'position': 1, 'times': [100, 100, 100]}],
            )
        self.write_config('season_test', config)

        with patch.object(csvgen, 'SEASONS', {'season_test': {}}):
            generated = csvgen.generate_event_csvs(['season_test'])

        self.assertEqual(len(generated), 2)
        self.assertTrue(os.path.exists(os.path.join('assets', 'csv', 'season_test', 'sprint', 'st-sc1.csv')))
        race_data = pd.read_csv(os.path.join('assets', 'csv', 'season_test', 'sprint', 'st-sc1-r.csv'))
        self.assertEqual(race_data.loc[0, 'Driver_name'], 'Greg Kachadurian')
        self.assertIn('reliability', race_data.columns)

    def test_descriptor_tables_and_hover_are_race_only(self):
        comparison_df = pd.DataFrame([{
            'Driver_name': 'A Driver',
            'is_rookie': False,
            'avg_pace_pct_alien_sc1': 102.0,
            'stdev_pace_pct_sc1': 0.5,
            'laptime_pct_alien_sc1': 101.0,
            'position_sc1': 2,
            'pct_race_pace_sc1': 102.5,
            'consistency_sc1': 0.99,
            'reliability_sc1': 0.95,
            'n_tracklimits_sc1': 2,
            'n_inchidents_sc1': 1,
            'pct_laps_sc1': 98.0,
            'n_stops_sc1': 1,
            'pit_lane_pct_times_sc1': 0.2,
        }])
        tables = stats.generate_descriptor_tables(comparison_df, ['sc1'], ['Fuji'])
        display_df, _ = stats.create_display_df(
            comparison_df, ['avg_pace_pct_alien_sc1'], ['stdev_pace_pct_sc1'], ['Fuji']
        )
        race_plot = stats.create_plotly_json(
            display_df, comparison_df, ['avg_pace_pct_alien_sc1'], ['stdev_pace_pct_sc1'],
            ['Fuji'], 'Race pace', 'Pace %',
        )
        quali_plot = stats.create_plotly_json(
            display_df, comparison_df, ['avg_pace_pct_alien_sc1'], ['stdev_pace_pct_sc1'],
            ['Fuji'], 'Quali pace', 'Pace %', race_type='quali',
        )
        race_hover = race_plot['traces'][0]['customdata'][0]
        quali_hover = quali_plot['traces'][0]['customdata'][0]

        self.assertIn('<h3>Reliability (%)</h3>', tables)
        self.assertNotIn('<h3>Finishing Position</h3>', tables)
        self.assertNotIn('<h3>Race Pace vs Class Leader (%)</h3>', tables)
        self.assertIn('data-driver="A Driver"', tables)
        self.assertIn('Reliability: 95.00%', race_hover)
        self.assertIn('Track Limits: 2', race_hover)
        self.assertIn('Consistency: 99.00%', race_hover)
        self.assertNotIn('Reliability', quali_hover)


if __name__ == '__main__':
    unittest.main()