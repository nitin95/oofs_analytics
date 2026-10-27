import os
import tempfile
import unittest
from unittest.mock import patch

import generate_stats_page


class StatsPageTests(unittest.TestCase):
    def test_generate_index_page_renders_season_links_and_rankings(self):
        seasons = {
            'season1': {'name': 'Season 3'},
            'season2': {'name': 'Season 4 & 5'},
        }
        with tempfile.TemporaryDirectory() as output_dir:
            with (
                patch.dict(generate_stats_page.csv_lib.SEASONS, seasons, clear=True),
                patch.object(
                    generate_stats_page.csv_lib,
                    'season_has_sprint_class_data',
                    side_effect=[False, True],
                ),
            ):
                index_path = generate_stats_page.generate_index_page(output_dir)

            with open(index_path, encoding='utf-8-sig') as index_file:
                page = index_file.read()

        self.assertIn('href="season1/sprint_race.html"', page)
        self.assertIn('href="season2/sprint_lmp3_race.html"', page)
        self.assertIn('Season 4 &amp; 5', page)
        self.assertIn('href="elo.html"', page)


if __name__ == '__main__':
    unittest.main()
