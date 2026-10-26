import json
import os
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

import csv_lib
import generate_driver_pages


class DriverPagesTests(unittest.TestCase):
    def test_generate_driver_pages_builds_canonical_category_profile(self):
        config = {
            'season_info': {'name': 'Season 1'},
            'sprint_qualis': {'s1-sc1.xml': {'name': 'Test Circuit'}},
            'sprint_races': {'s1-sc1-r.xml': {'name': 'Test Circuit'}},
        }

        with tempfile.TemporaryDirectory() as root:
            config_root = os.path.join(root, 'json')
            data_root = os.path.join(root, 'csv')
            output_dir = os.path.join(root, 'profiles')
            os.makedirs(config_root)
            with open(os.path.join(config_root, 'season1.json'), 'w', encoding='utf-8') as config_file:
                json.dump(config, config_file)

            qualifying_path = csv_lib.build_csv_path(
                'season1', 'sprint', 's1-sc1.xml', data_root
            )
            race_path = csv_lib.build_csv_path(
                'season1', 'sprint', 's1-sc1-r.xml', data_root
            )
            os.makedirs(os.path.dirname(qualifying_path), exist_ok=True)
            qualifying = {
                'Driver': 'Greg Kach', 'Driver_name': 'Greg Kach',
                'Car': 'GT3 car', 'CarClass': 'GT3', 'CarNumber': 44,
                'Position': 1, 'FinishStatus': 'Finished Normally', 'Laps': 1,
                'avg_pace_pct_alien': 101.25, 'consistency': 1, 'reliability': 1,
                'n_inchidents': 0, 'n_tracklimits': 0, 'n_stops': 0,
            }
            race = dict(qualifying, Position=2, Laps=20)
            pd.DataFrame([qualifying]).to_csv(qualifying_path, index=False)
            pd.DataFrame([race]).to_csv(race_path, index=False)

            with patch.dict(csv_lib.SEASONS, {'season1': {'name': 'Season 1'}}, clear=True):
                driver_count = generate_driver_pages.generate_driver_pages(
                    output_dir, data_root, config_root, generated_date='2026-10-26'
                )
            self.assertEqual(driver_count, 1)
            with open(os.path.join(output_dir, 'greg-kachadurian.html'), encoding='utf-8') as page_file:
                page = page_file.read()
            with open(os.path.join(output_dir, 'index.html'), encoding='utf-8') as index_file:
                index = index_file.read()

            self.assertIn('Overall career stats', page)
            self.assertIn('Sprint GT3', page)
            self.assertIn('Average quali pace vs alien', page)
            self.assertIn('101.25%', page)
            self.assertIn('<strong>1</strong>', page)
            self.assertIn('greg-kachadurian.html', index)
            self.assertIn('id="profileSearch"', index)
            self.assertIn('data-letter="A"', index)
            self.assertIn('data-letter="Z"', index)
            self.assertIn("profileSearch.addEventListener('input', () => {", index)
            self.assertIn("activeLetter = 'all';", index)
            self.assertIn("button.disabled = button.dataset.letter !== 'all'", index)


if __name__ == '__main__':
    unittest.main()