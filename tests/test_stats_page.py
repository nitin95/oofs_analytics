import os
import tempfile
import unittest
from unittest.mock import patch

import generate_stats_page
import html_lib


class StatsPageTests(unittest.TestCase):
    def test_clear_generated_html_removes_nested_html_only(self):
        with tempfile.TemporaryDirectory() as output_dir:
            season_dir = os.path.join(output_dir, 'season1')
            profile_dir = os.path.join(season_dir, 'profiles')
            os.makedirs(profile_dir)
            html_paths = [
                os.path.join(output_dir, 'index.html'),
                os.path.join(season_dir, 'sprint_race.html'),
                os.path.join(profile_dir, 'driver.html'),
            ]
            other_paths = [
                os.path.join(output_dir, 'README.md'),
                os.path.join(output_dir, 'styles.css'),
                os.path.join(season_dir, 'data.json'),
            ]
            for path in html_paths + other_paths:
                with open(path, 'w', encoding='utf-8'):
                    pass

            generate_stats_page.clear_generated_html(output_dir)

            self.assertTrue(all(not os.path.exists(path) for path in html_paths))
            self.assertTrue(all(os.path.isfile(path) for path in other_paths))

    def test_generate_index_page_renders_season_links_and_rankings(self):
        seasons = {
            'season1': {'name': 'Season 3'},
            'season2': {'name': 'Season 4 & 5'},
        }
        with tempfile.TemporaryDirectory() as output_dir:
            for season_id, page_name in (
                ('season1', 'sprint_race.html'),
                ('season2', 'multiclass_gt3_race.html'),
            ):
                season_dir = os.path.join(output_dir, season_id)
                os.makedirs(season_dir)
                with open(os.path.join(season_dir, page_name), 'w', encoding='utf-8'):
                    pass
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
        self.assertIn('href="season2/multiclass_gt3_race.html"', page)
        self.assertNotIn('href="season2/sprint_lmp3_race.html"', page)
        self.assertIn('Season 4 &amp; 5', page)
        self.assertIn('href="elo.html"', page)

    def test_sidebar_refresh_omits_missing_report_links(self):
        with tempfile.TemporaryDirectory() as output_dir:
            season_dir = os.path.join(output_dir, 'season1')
            os.makedirs(season_dir)
            page_path = os.path.join(season_dir, 'sprint_race.html')
            with open(page_path, 'w', encoding='utf-8') as page_file:
                page_file.write('<nav class="sidebar">old links</nav>')

            with (
                patch.object(html_lib, 'season_has_sprint_class_data', return_value=False),
                patch.object(html_lib, 'get_multiclass_prototype_class', return_value='P2UR'),
                patch.object(html_lib, 'get_multiclass_championship_name', return_value='Multiclass'),
            ):
                html_lib.refresh_sidebar_links(output_dir, ['season1'])

            with open(page_path, encoding='utf-8-sig') as page_file:
                page = page_file.read()

        self.assertIn('href="sprint_race.html"', page)
        self.assertNotIn('multiclass_', page)


if __name__ == '__main__':
    unittest.main()
