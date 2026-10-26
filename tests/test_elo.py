import json
import os
import tempfile
import unittest

import pandas as pd

import elo_lib


class EloRankingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = self.temp_dir.name
        self.config_root = os.path.join(self.root, 'json')
        self.csv_root = os.path.join(self.root, 'csv')
        os.makedirs(self.config_root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_season(self, season_id, name, races):
        with open(
            os.path.join(self.config_root, f'{season_id}.json'),
            'w',
            encoding='utf-8',
        ) as config_file:
            json.dump({'season_info': {'name': name}, **races}, config_file)

    def write_event(self, season_id, series, filename, rows):
        folder = os.path.join(self.csv_root, season_id, series)
        os.makedirs(folder, exist_ok=True)
        csv_filename = os.path.splitext(filename)[0] + '.csv'
        pd.DataFrame(rows).to_csv(os.path.join(folder, csv_filename), index=False)

    def test_two_driver_result_updates_ratings_symmetrically(self):
        ratings = elo_lib.update_event_ratings({}, {'Winner': 1, 'Loser': 2})

        self.assertEqual(ratings, {'Winner': 1516.0, 'Loser': 1484.0})

    def test_rankings_follow_first_race_and_separate_classes(self):
        self.write_season('season1', 'Season 3', {
            'sprint_races': {
                's3-sc1-r.xml': {'name': 'Portimao'},
            },
            'multiclass_races': {
                's3-mc1-r.xml': {'name': 'Portimao'},
            },
        })
        self.write_season('season2', 'Season 4', {
            'sprint_races': {
                's4-sc1-r.xml': {'name': 'Fuji'},
            },
        })
        self.write_event('season1', 'sprint', 's3-sc1-r.xml', [
            {'Driver_name': 'Sprint Winner', 'CarClass': 'GT3', 'Position': 1},
            {'Driver_name': 'Sprint Runner-up', 'CarClass': 'GT3', 'Position': 2},
        ])
        self.write_event('season1', 'multiclass', 's3-mc1-r.xml', [
            {'Driver_name': 'GT3 A', 'CarClass': 'GT3', 'Position': 3},
            {'Driver_name': 'GT3 B', 'CarClass': 'GT3', 'Position': 4},
            {'Driver_name': 'Proto A', 'CarClass': 'LMP2_ELMS', 'Position': 1},
            {'Driver_name': 'Proto B', 'CarClass': 'LMP2_ELMS', 'Position': 2},
        ])
        self.write_event('season2', 'sprint', 's4-sc1-r.xml', [
            {'Driver_name': 'Sprint Runner-up', 'CarClass': 'GT3', 'Position': 1, 'FinishStatus': 'Finished Normally'},
            {'Driver_name': 'Sprint Winner', 'CarClass': 'GT3', 'Position': 2, 'FinishStatus': 'DNF'},
            {'Driver_name': 'Prototype A', 'CarClass': 'LMP3', 'Position': 3},
            {'Driver_name': 'Prototype B', 'CarClass': 'LMP3', 'Position': 4},
        ])

        rankings = elo_lib.build_rankings(self.config_root, self.csv_root)

        self.assertEqual(
            [ranking['slug'] for ranking in rankings],
            ['sprint_gt3', 'multiclass_gt3', 'multiclass_prototype', 'sprint_lmp3'],
        )
        sprint_standings = rankings[0]['standings']
        self.assertEqual(sprint_standings[0]['driver'], 'Sprint Winner')
        self.assertEqual(sprint_standings[0]['starts'], 2)
        self.assertEqual(sprint_standings[0]['average_finish_position'], 1.5)
        self.assertAlmostEqual(sprint_standings[0]['rating'], 1513.1, places=1)
        sprint_winner = next(row for row in sprint_standings if row['driver'] == 'Sprint Winner')
        self.assertEqual(sprint_winner['dnfs'], 1)
        self.assertNotIn('GT3 A', [row['driver'] for row in sprint_standings])

    def test_first_season_k_factor_applies_to_all_races_in_that_season(self):
        self.write_season('season1', 'Season 3', {
            'sprint_races': {
                's3-sc1-r.xml': {'name': 'Portimao'},
                's3-sc2-r.xml': {'name': 'Le Mans'},
            },
        })
        self.write_event('season1', 'sprint', 's3-sc1-r.xml', [
            {'Driver_name': 'Driver A', 'CarClass': 'GT3', 'Position': 1},
            {'Driver_name': 'Driver B', 'CarClass': 'GT3', 'Position': 2},
        ])
        self.write_event('season1', 'sprint', 's3-sc2-r.xml', [
            {'Driver_name': 'Driver B', 'CarClass': 'GT3', 'Position': 1},
            {'Driver_name': 'Driver A', 'CarClass': 'GT3', 'Position': 2},
        ])

        rankings = elo_lib.build_rankings(self.config_root, self.csv_root)
        standings = {row['driver']: row for row in rankings[0]['standings']}

        self.assertAlmostEqual(standings['Driver B']['rating'], 1505.8, places=1)
        self.assertAlmostEqual(standings['Driver A']['rating'], 1494.2, places=1)

    def test_first_category_uses_elo_html_and_sidebar_links_all_pages(self):
        self.write_season('season1', 'Season 3', {
            'sprint_races': {'s3-sc1-r.xml': {'name': 'Portimao'}},
        })
        self.write_event('season1', 'sprint', 's3-sc1-r.xml', [
            {'Driver_name': 'Driver A', 'CarClass': 'GT3', 'Position': 1},
            {'Driver_name': 'Driver B', 'CarClass': 'GT3', 'Position': 2},
        ])

        output_root = os.path.join(self.root, 'docs')
        generated = elo_lib.generate_pages(
            output_root=output_root,
            config_root=self.config_root,
            csv_root=self.csv_root,
        )

        self.assertEqual(os.path.basename(generated[0]), 'elo.html')
        with open(generated[0], encoding='utf-8') as page_file:
            page = page_file.read()
        self.assertIn('Driver A', page)
        self.assertIn('<th>Avg Finish</th>', page)
        self.assertIn('<th>DNFs</th>', page)
        self.assertIn('<td>1.00</td>', page)
        self.assertIn('active', page)


if __name__ == '__main__':
    unittest.main()