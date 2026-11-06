import json
import os
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

import csv_lib
import driver_blacklist
import generate_driver_pages


class DriverPagesTests(unittest.TestCase):
    def setUp(self):
        self.blacklist_patcher = patch.object(
            driver_blacklist, 'load_blacklisted_names', return_value=set()
        )
        self.blacklist_patcher.start()
        self.addCleanup(self.blacklist_patcher.stop)

    def test_dnf_metric_lists_only_five_latest_races(self):
        records = [
            {
                'season_id': 'season1',
                'season_name': 'Season 1',
                'event': f'Race {index}',
                'category_label': 'Sprint GT3',
                'finish_status': 'DNF',
                'session': 'race',
                'series': 'sprint',
                'category': 'GT3',
                'position': None,
                'laps': 10,
                'car': 'GT3 car',
                'car_number': '44',
                'avg_pace_pct_alien': None,
                'consistency': None,
                'reliability': None,
                'incidents': 0,
                'vehicle_incidents': 0,
                'object_incidents': 0,
                'track_limits': 0,
            }
            for index in range(1, 7)
        ]

        page = generate_driver_pages.render_driver_page(
            'Test Driver', {'race': records, 'qualifying': []}, '2026-10-26'
        )
        popover = page.split('id="career-dnfs-details"', 1)[1].split('</div>', 1)[0]

        self.assertIn('<table class="profile-table">', page)
        self.assertIn('<span>DNFs</span><strong>6</strong>', page)
        self.assertIn('Race 6', popover)
        self.assertIn('Race 2', popover)
        self.assertNotIn('Race 1', popover)
        self.assertLess(popover.index('Race 6'), popover.index('Race 5'))

    def test_dns_wins_and_podiums_show_last_five_matching_races(self):
        records = [
            {
                'season_id': 'season1',
                'season_name': 'Season 1',
                'event': f'Race {index}',
                'category_label': 'Sprint GT3',
                'finish_status': 'Finished Normally' if index <= 6 else 'DNF',
                'session': 'race',
                'series': 'sprint',
                'category': 'GT3',
                'position': 1 if index <= 6 else 4,
                'laps': 12 if index <= 6 else 0,
                'car': 'GT3 car',
                'car_number': '44',
                'avg_pace_pct_alien': None,
                'consistency': None,
                'reliability': None,
                'incidents': 0,
                'vehicle_incidents': 0,
                'object_incidents': 0,
                'track_limits': 0,
            }
            for index in range(1, 14)
        ]

        page = generate_driver_pages.render_driver_page(
            'Test Driver', {'race': records, 'qualifying': []}, '2026-10-26'
        )

        self.assertIn('<span>DNS</span><strong>7</strong>', page)
        self.assertIn('<span>Wins</span><strong>6</strong>', page)
        self.assertIn('<span>Podiums</span><strong>6</strong>', page)
        dns_popover = page.split('id="career-dns-details"', 1)[1].split('</div>', 1)[0]
        self.assertIn('Race 13', dns_popover)
        self.assertIn('Race 9', dns_popover)
        self.assertNotIn('Race 8', dns_popover)
        for identifier in ('career-wins', 'career-podiums'):
            popover = page.split(f'id="{identifier}-details"', 1)[1].split('</div>', 1)[0]
            self.assertIn('Race 6', popover)
            self.assertIn('Race 2', popover)
            self.assertNotIn('Race 1', popover)
            self.assertLess(popover.index('Race 6'), popover.index('Race 5'))

    def test_dns_does_not_count_as_start_or_dnf(self):
        common = {
            'season_id': 'season1',
            'season_name': 'Season 1',
            'category_label': 'Sprint GT3',
            'session': 'race',
            'series': 'sprint',
            'category': 'GT3',
            'position': 2,
            'finish_status': 'DNF',
            'car': 'GT3 car',
            'car_number': '44',
            'avg_pace_pct_alien': None,
            'consistency': None,
            'reliability': None,
            'incidents': 0,
            'vehicle_incidents': 0,
            'object_incidents': 0,
            'track_limits': 0,
        }
        records = [
            dict(common, event='Started DNF', laps=1),
            dict(common, event='Zero-lap DNS', position=19, laps=0),
        ]

        page = generate_driver_pages.render_driver_page(
            'Test Driver', {'race': records, 'qualifying': []}, '2026-10-26'
        )
        dnf_popover = page.split('id="career-dnfs-details"', 1)[1].split('</div>', 1)[0]

        self.assertIn('<span>Race starts</span><strong>1</strong>', page)
        self.assertIn('<span>DNFs</span><strong>1</strong>', page)
        self.assertIn('<span>DNS</span><strong>1</strong>', page)
        self.assertIn('Started DNF', dnf_popover)
        self.assertNotIn('Zero-lap DNS', dnf_popover)

    def test_driver_with_only_dns_records_has_no_profile_page(self):
        profiles = {
            'DNS Only Driver': {
                'race': [{'laps': 0, 'category_label': 'Sprint GT3'}],
                'qualifying': [],
            },
            'Started Driver': {
                'race': [{'laps': 1, 'category_label': 'Sprint GT3'}],
                'qualifying': [],
            },
        }

        with tempfile.TemporaryDirectory() as output_dir, (
            patch.object(
                generate_driver_pages, 'collect_driver_records', return_value=profiles
            ),
            patch.object(generate_driver_pages, '_build_elo_lookup', return_value={}),
            patch.object(
                generate_driver_pages,
                'render_driver_page',
                side_effect=lambda name, *_args: f'<h1>{name}</h1>',
            ),
        ):
            count = generate_driver_pages.generate_driver_pages(
                output_dir, generated_date='2026-10-26'
            )

            with open(os.path.join(output_dir, 'index.html'), encoding='utf-8') as index_file:
                index = index_file.read()

            self.assertEqual(count, 1)
            self.assertFalse(os.path.exists(os.path.join(output_dir, 'dns-only-driver.html')))
            self.assertTrue(os.path.exists(os.path.join(output_dir, 'started-driver.html')))
            self.assertNotIn('DNS Only Driver', index)
            self.assertIn('Started Driver', index)

    def test_generate_driver_pages_builds_canonical_category_profile(self):
        config = {
            'season_info': {'name': 'Season 1'},
            'sprint_qualis': {'s1-sc1.xml': {'name': 'Test Circuit'}},
            'sprint_races': {
                's1-sc1-r.xml': {'name': 'Test Circuit'},
                's1-sc2-r.xml': {'name': 'Second Circuit'},
            },
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
            second_race_path = csv_lib.build_csv_path(
                'season1', 'sprint', 's1-sc2-r.xml', data_root
            )
            os.makedirs(os.path.dirname(qualifying_path), exist_ok=True)
            qualifying = {
                'Driver': 'Greg Kach', 'Driver_name': 'Greg Kach',
                'Car': 'GT3 car', 'CarClass': 'GT3', 'CarNumber': 44,
                'Position': 1, 'FinishStatus': 'Finished Normally', 'Laps': 1,
                'avg_pace_pct_alien': 101.25, 'consistency': 1, 'reliability': 1,
                'n_inchidents': 0, 'n_tracklimits': 0, 'n_stops': 0,
            }
            race = dict(
                qualifying,
                Position=2,
                Laps=20,
                n_tracklimits=4,
                n_inchidents=3,
                n_incidents_vehicle=2,
                n_incidents_object=1,
            )
            second_race = dict(
                qualifying,
                Position=3,
                Laps=18,
                n_tracklimits=2,
                n_inchidents=5,
                n_incidents_vehicle=3,
                n_incidents_object=2,
            )
            pd.DataFrame([qualifying]).to_csv(qualifying_path, index=False)
            pd.DataFrame([race]).to_csv(race_path, index=False)
            pd.DataFrame([second_race]).to_csv(second_race_path, index=False)

            with (
                patch.dict(csv_lib.SEASONS, {'season1': {'name': 'Season 1'}}, clear=True),
                patch.object(
                    generate_driver_pages.elo_lib,
                    'build_rankings',
                    return_value=[{
                        'slug': 'sprint_gt3',
                        'standings': [
                            {
                                'driver': 'Greg Kachadurian',
                                'race_rating': 1612.3,
                                'quali_rating': 1580.0,
                            },
                            {'driver': 'Another Driver', 'rating': 1498.7},
                        ],
                    }],
                ),
            ):
                driver_count = generate_driver_pages.generate_driver_pages(
                    output_dir, data_root, config_root, generated_date='2026-10-26'
                )
            self.assertEqual(driver_count, 1)
            with open(os.path.join(output_dir, 'greg-kachadurian.html'), encoding='utf-8') as page_file:
                page = page_file.read()
            with open(os.path.join(output_dir, 'index.html'), encoding='utf-8') as index_file:
                index = index_file.read()

            self.assertIn('Overall career stats', page)
            self.assertIn('<title>Greg K. | Driver Profile</title>', page)
            self.assertIn('<h1>Greg K.</h1>', page)
            self.assertIn('Sprint GT3', page)
            self.assertIn('Average quali pace vs alien', page)
            self.assertIn('<span>Track limits</span><strong>6</strong>', page)
            self.assertIn(
                '<span>Average track limits per race</span><strong>3.00</strong>',
                page,
            )
            self.assertNotIn('Average incidents per race', page)
            self.assertNotIn('Vehicle incidents</span>', page)
            self.assertNotIn('Object incidents</span>', page)
            self.assertIn('Vehicle: 5 (62.5%)', page)
            self.assertIn('Object: 3 (37.5%)', page)
            self.assertIn('101.25%', page)
            self.assertIn('Category ELO', page)
            self.assertIn('1,612.3', page)
            self.assertIn('Driver rank', page)
            self.assertIn('#1', page)
            self.assertNotIn('Pit stops</span>', page)
            self.assertIn('<strong>1</strong>', page)
            self.assertIn('greg-kachadurian.html', index)
            self.assertIn('>Greg K.<small>', index)
            self.assertIn('id="profileSearch"', index)
            self.assertIn('data-letter="A"', index)
            self.assertIn('data-letter="Z"', index)
            self.assertIn("profileSearch.addEventListener('input', () => {", index)
            self.assertIn("activeLetter = 'all';", index)
            self.assertIn("button.disabled = button.dataset.letter !== 'all'", index)

    def test_blacklisted_driver_is_omitted_from_profiles_and_index(self):
        config = {
            'season_info': {'name': 'Season 1'},
            'sprint_races': {'s1-sc1-r.xml': {'name': 'Test Circuit'}},
        }

        with tempfile.TemporaryDirectory() as root:
            config_root = os.path.join(root, 'json')
            data_root = os.path.join(root, 'csv')
            output_dir = os.path.join(root, 'profiles')
            os.makedirs(config_root)
            with open(os.path.join(config_root, 'season1.json'), 'w', encoding='utf-8') as config_file:
                json.dump(config, config_file)

            race_path = csv_lib.build_csv_path(
                'season1', 'sprint', 's1-sc1-r.xml', data_root
            )
            os.makedirs(os.path.dirname(race_path), exist_ok=True)
            pd.DataFrame([{
                'Driver': 'Greg Kach', 'Driver_name': 'Greg Kach',
                'CarClass': 'GT3', 'Position': 1,
            }]).to_csv(race_path, index=False)

            with (
                patch.dict(csv_lib.SEASONS, {'season1': {'name': 'Season 1'}}, clear=True),
                patch.object(
                    driver_blacklist,
                    'load_blacklisted_names',
                    return_value={'Greg Kachadurian'},
                ),
                patch.object(generate_driver_pages.elo_lib, 'build_rankings', return_value=[]),
            ):
                driver_count = generate_driver_pages.generate_driver_pages(
                    output_dir, data_root, config_root, generated_date='2026-10-26'
                )

            with open(os.path.join(output_dir, 'index.html'), encoding='utf-8') as index_file:
                index = index_file.read()

        self.assertEqual(driver_count, 0)
        self.assertNotIn('Greg K.', index)
        self.assertFalse(os.path.exists(os.path.join(output_dir, 'greg-kachadurian.html')))


if __name__ == '__main__':
    unittest.main()