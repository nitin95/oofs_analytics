import os
import sys
import tempfile
import types
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

import pandas as pd

# The generator's color palette is unrelated to rookie detection and may not be
# installed in lightweight test environments.
seaborn = types.ModuleType('seaborn')
setattr(seaborn, 'color_palette', lambda *args, **kwargs: lambda value: (0.1, 0.2, 0.3))
matplotlib = types.ModuleType('matplotlib')
matplotlib_colors = types.ModuleType('matplotlib.colors')
setattr(matplotlib_colors, 'to_hex', lambda color: '#19334c')
setattr(matplotlib, 'colors', matplotlib_colors)
with patch.dict(sys.modules, {
    'seaborn': seaborn,
    'matplotlib': matplotlib,
    'matplotlib.colors': matplotlib_colors,
}):
    import generate_stats_page as stats


class RookieTagTests(unittest.TestCase):
    def setUp(self):
        self.original_cwd = os.getcwd()
        self.original_seasons = stats.SEASONS
        self.original_config = stats.SEASON_CONFIG
        self.temp_dir = tempfile.TemporaryDirectory()
        os.chdir(self.temp_dir.name)
        stats.SEASONS = {'season1': {}, 'season2': {}, 'season3': {}}
        stats.SEASON_CONFIG = {
            'season1': {},
            'season2': {},
            'season3': {},
        }

    def tearDown(self):
        stats.SEASONS = self.original_seasons
        stats.SEASON_CONFIG = self.original_config
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def write_race(self, season_id, series_type, filename, drivers):
        folder = os.path.join('xml', season_id, series_type)
        os.makedirs(folder, exist_ok=True)
        root = ET.Element('Results')
        for name, car_class in drivers:
            driver = ET.SubElement(root, 'Driver')
            ET.SubElement(driver, 'Name').text = name
            ET.SubElement(driver, 'CarClass').text = car_class

        ET.ElementTree(root).write(os.path.join(folder, filename), encoding='utf-8')
        section = f'{series_type}_qualis'
        stats.SEASON_CONFIG[season_id].setdefault(section, {})[filename] = {}

    def test_baseline_season_has_no_inferred_rookies(self):
        self.write_race('season1', 'sprint', 's1.xml', [('New Driver', 'GT3')])

        rookies = stats.get_rookie_driver_names('season1', 'sprint', ['New Driver'])

        self.assertEqual(rookies, set())

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


if __name__ == '__main__':
    unittest.main()