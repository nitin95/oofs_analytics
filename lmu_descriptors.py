"""Generate normalized pace and race descriptors from LMU result XML."""

import re
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd


PACE_COLUMNS = [
    'Driver', 'Car', 'CarClass', 'CarNumber', 'Position', 'FinishStatus', 'Laps',
    'laptime_sec', 'laptime_pct', 'laptime_pct_alien', 'avg_laptime',
    'avg_pace_pct_alien', 'stdev_laptime', 'stdev_pace_pct', 'lap_count',
]
RACE_DESCRIPTOR_COLUMNS = [
    'race_pace', 'pct_race_pace', 'consistency', 'reliability', 'n_tracklimits',
    'n_inchidents', 'n_incidents_vehicle', 'n_incidents_object', 'pct_laps',
    'n_stops', 'pit_lane_pct_times',
]


class LMUDescriptor:
    """Calculate page-ready pace values and race descriptors for an XML event."""

    def __init__(self, xml_file=None, no_pit=False, car_class=None):
        self.xml_file = xml_file
        self.no_pit = no_pit
        self.car_class = car_class

    def get_descriptors(self, xml_file=None, reference_times=None):
        """Return one row per driver with pace and race-specific descriptors."""
        return self._get_event_descriptors(xml_file, reference_times, include_race=True)

    def get_quali_descriptors(self, xml_file=None, reference_times=None):
        """Return qualifying pace fields without race-only descriptor values."""
        return self._get_event_descriptors(xml_file, reference_times, include_race=False)

    def _get_event_descriptors(self, xml_file, reference_times, include_race):
        xml_file = xml_file or self.xml_file
        if not xml_file:
            raise ValueError('xml_file must be provided')

        root = ET.parse(xml_file).getroot()
        drivers = []
        for driver in root.iter('Driver'):
            car_class = driver.findtext('CarClass', '') or ''
            overall_position = self._to_int(driver.findtext('Position'))
            class_position = self._to_int(driver.findtext('ClassPosition'))
            position = class_position if class_position is not None else overall_position
            if position is None:
                continue

            all_laps = [self._lap_record(lap, position) for lap in driver.findall('Lap')]
            row = {
                'Driver': driver.findtext('Name', 'Unknown'),
                'Car': driver.findtext('CarType', 'Unknown'),
                'CarClass': car_class,
                'CarNumber': driver.findtext('CarNumber', 'N/A'),
                'Position': position,
                'FinishStatus': driver.findtext('FinishStatus', ''),
                'Laps': self._to_int(driver.findtext('Laps')) or len(all_laps),
                'lap_count': 0,
                'laptime_sec': np.nan,
                'avg_laptime': np.nan,
                'stdev_laptime': np.nan,
            }
            row['laptime_pct'] = np.nan
            row['laptime_pct_alien'] = np.nan
            row['avg_pace_pct_alien'] = np.nan
            row['stdev_pace_pct'] = np.nan
            row.update({column: np.nan for column in RACE_DESCRIPTOR_COLUMNS})
            drivers.append({'row': row, 'laps': all_laps})

        if not drivers:
            return pd.DataFrame(columns=PACE_COLUMNS + RACE_DESCRIPTOR_COLUMNS)

        if include_race:
            event_metrics = self._race_event_metrics(root, drivers)
            reference_by_lap = self._build_race_references(
                drivers, reference_times, event_metrics
            )
        else:
            reference_by_class = self._build_quali_references(drivers, reference_times)
            reference_by_lap = None

        class_fastest_pct = {}
        class_race_pace = {}
        class_lap_leaders = {}
        for entry in drivers:
            row = entry['row']
            if not self._matches_class(row['CarClass']):
                continue

            class_key = self._class_key(row['CarClass'])
            if include_race:
                source_laps = entry['clean_laps']
                tracklimits = entry['tracklimits']
                in_laps = entry['in_laps']
                out_laps = entry['out_laps']
                n_stops = entry['n_stops']
                class_lap_leaders[class_key] = max(
                    class_lap_leaders.get(class_key, 0), row['Laps']
                )
            else:
                source_laps = self._qualifying_laps(entry['laps'])

            pace_samples = []
            for lap in source_laps:
                if include_race:
                    reference_time = reference_by_lap.get((lap['num'], class_key))
                else:
                    reference_time = reference_by_class.get(class_key)
                if reference_time is None or reference_time <= 0:
                    continue
                if lap['time'] > reference_time * 1.07:
                    continue
                pace_samples.append({
                    'num': lap['num'],
                    'time': lap['time'],
                    'reference': reference_time,
                    'pct': 100 * lap['time'] / reference_time,
                })

            entry['pace_samples'] = pace_samples
            pace_values = [sample['pct'] for sample in pace_samples]
            raw_values = [sample['time'] for sample in pace_samples]
            row['lap_count'] = len(pace_samples)
            if pace_samples:
                fastest_pct = min(pace_values)
                class_fastest_pct[class_key] = min(
                    class_fastest_pct.get(class_key, fastest_pct), fastest_pct
                )
                row['laptime_sec'] = float(min(raw_values))
                row['avg_laptime'] = float(np.mean(raw_values))
                row['stdev_laptime'] = (
                    float(np.std(raw_values, ddof=1)) if len(raw_values) > 1 else 0.0
                )
                row['laptime_pct_alien'] = round(fastest_pct, 2)
                row['avg_pace_pct_alien'] = round(float(np.mean(pace_values)), 2)
                row['stdev_pace_pct'] = round(
                    float(np.std(pace_values, ddof=1)) if len(pace_values) > 1 else 0.0,
                    2,
                )

            if include_race:
                race_values = [sample['pct'] for sample in pace_samples]
                incident_metrics = event_metrics[self._event_name_key(row['Driver'])]
                tracklimits = incident_metrics['tracklimits']
                incidents = (
                    incident_metrics['vehicle_incidents']
                    + incident_metrics['object_incidents']
                )
                row['n_tracklimits'] = tracklimits
                row['n_inchidents'] = incidents
                row['n_incidents_vehicle'] = incident_metrics['vehicle_incidents']
                row['n_incidents_object'] = incident_metrics['object_incidents']
                row['n_stops'] = n_stops
                race_mean = float(np.mean(race_values)) if race_values else np.nan
                entry['race_mean'] = race_mean
                if race_values:
                    class_race_pace[class_key] = min(
                        class_race_pace.get(class_key, race_mean), race_mean
                    )
                    race_std = float(np.std(race_values))
                    row['race_pace'] = race_mean
                    row['consistency'] = 1 - race_std / race_mean if race_mean else np.nan
                    row['reliability'] = max(
                        0.0, 1 - (tracklimits + incidents) / (2*len(race_values))
                    )
                    leader_laps = class_lap_leaders.get(class_key, 0)
                    row['pct_laps'] = (
                        100 * row['Laps'] / leader_laps if leader_laps else np.nan
                    )

                if in_laps and len(in_laps) == len(out_laps) and race_values:
                    clean_mean = float(np.mean(race_values))
                    pit_values = []
                    for lap in in_laps + out_laps:
                        reference_time = reference_by_lap.get((lap['num'], class_key))
                        if reference_time is None or reference_time <= 0:
                            pit_values = []
                            break
                        pit_values.append(100 * lap['time'] / reference_time)
                    if len(pit_values) == len(in_laps) + len(out_laps):
                        row['pit_lane_pct_times'] = sum(
                            value / clean_mean - 1 for value in pit_values
                        )

        output = []
        for entry in drivers:
            row = entry['row']
            if not self._matches_class(row['CarClass']):
                continue
            class_key = self._class_key(row['CarClass'])
            if entry['pace_samples']:
                row['laptime_pct'] = round(
                    100 * class_fastest_pct[class_key] / row['laptime_pct_alien'], 2
                )
            if include_race and pd.notna(entry.get('race_mean')):
                row['pct_race_pace'] = max(
                    100.0, 100 * entry['race_mean'] / class_race_pace[class_key]
                )
            if not include_race and not any(
                lap['time'] is not None for lap in entry['laps']
            ):
                continue
            output.append(row)

        return pd.DataFrame(output, columns=PACE_COLUMNS + RACE_DESCRIPTOR_COLUMNS)

    def _matches_class(self, driver_class):
        if self.car_class is None:
            return True
        requested = str(self.car_class).lower()
        actual = str(driver_class).lower()
        if requested in ('p2ur', 'lmp2_elms', 'prototype'):
            return 'lmp2_elms' in actual or 'p2ur' in actual or 'hyper' in actual
        return requested in actual

    @staticmethod
    def _class_key(driver_class):
        value = str(driver_class).lower()
        if 'gt3' in value:
            return 'gt3'
        if 'lmp3' in value or value.strip() == 'p3':
            return 'lmp3'
        if 'hyper' in value:
            return 'hyper'
        if 'lmp2' in value or 'p2ur' in value:
            return 'p2ur'
        return value

    @classmethod
    def _get_reference_time(cls, driver_class, reference_times):
        if not reference_times:
            return None
        key = cls._class_key(driver_class)
        aliases = {
            'gt3': ('gt3', 'ref_time_gt3'),
            'lmp3': ('lmp3', 'ref_time_lmp3'),
            'hyper': ('hyper', 'ref_time_hyper'),
            'p2ur': ('p2ur', 'ref_time_p2ur'),
        }
        for candidate in aliases.get(key, (key,)):
            if candidate in reference_times:
                return reference_times[candidate]
        return reference_times.get('default')

    @classmethod
    def _lap_record(cls, lap, fallback_position):
        front = lap.get('fcompound')
        rear = lap.get('rcompound')
        front = front.strip() if front else None
        rear = rear.strip() if rear else None
        lap_time = cls._to_float(lap.text)
        return {
            'num': cls._to_int(lap.get('num')),
            'time': lap_time if lap_time is not None and lap_time > 0 else None,
            'elapsed': cls._to_float(lap.get('et')),
            'position': cls._to_int(lap.get('p')) or fallback_position,
            'front_compound': front,
            'rear_compound': rear,
            'compound_known': bool(front and rear),
            'wet': front == '1,Wet' and rear == '1,Wet',
            'pit': lap.get('pit') == '1',
        }

    @classmethod
    def _rounded_reference(cls, lap_time, divisor):
        if lap_time is None or lap_time <= 0:
            return None
        return float(np.floor((lap_time / divisor) * 10) / 10)

    def _qualifying_laps(self, lap_records):
        pit_laps = {
            lap['num'] for lap in lap_records
            if lap['num'] is not None and lap['pit'] and not self.no_pit
        }
        out_laps = {lap_num + 1 for lap_num in pit_laps}
        return [
            lap for lap in lap_records
            if lap['time'] is not None
            and lap['time'] > 0
            and not (lap['num'] in pit_laps or lap['num'] in out_laps)
        ]

    def _build_quali_references(self, drivers, reference_times):
        fastest_by_driver = []
        fastest_by_class = {}
        wet_votes = 0
        known_votes = 0

        for entry in drivers:
            laps = self._qualifying_laps(entry['laps'])
            if not laps:
                continue
            fastest = min(laps, key=lambda lap: lap['time'])
            fastest_by_driver.append((entry, fastest))
            class_key = self._class_key(entry['row']['CarClass'])
            current = fastest_by_class.get(class_key)
            if current is None or fastest['time'] < current['time']:
                fastest_by_class[class_key] = fastest
            if fastest['compound_known']:
                known_votes += 1
                wet_votes += int(fastest['wet'])

        wet_session = known_votes > 0 and wet_votes > known_votes / 2
        references = {}
        for entry, _ in fastest_by_driver:
            class_key = self._class_key(entry['row']['CarClass'])
            if class_key in references:
                continue
            if wet_session:
                fastest = fastest_by_class.get(class_key)
                reference_time = self._rounded_reference(
                    fastest['time'], 1.015
                ) if fastest else None
            else:
                reference_time = self._get_reference_time(
                    entry['row']['CarClass'], reference_times
                )
            references[class_key] = reference_time
        return references

    def _build_race_references(self, drivers, reference_times, event_metrics):
        votes_by_lap = {}
        leaders_by_lap = {}
        completed_lap_numbers = set()
        class_names = {}
        class_keys = set()

        for entry in drivers:
            row = entry['row']
            class_key = self._class_key(row['CarClass'])
            class_keys.add(class_key)
            class_names.setdefault(class_key, row['CarClass'])
            clean_laps, in_laps, out_laps, n_stops = self._race_laps(
                entry['laps']
            )
            tracklimits = event_metrics[self._event_name_key(row['Driver'])]['tracklimits']
            entry.update({
                'clean_laps': clean_laps,
                'tracklimits': tracklimits,
                'in_laps': in_laps,
                'out_laps': out_laps,
                'n_stops': n_stops,
            })

            for lap in entry['laps']:
                lap_num = lap['num']
                if lap_num is None or lap_num <= 1:
                    continue
                completed_lap_numbers.add(lap_num)
                if not lap['compound_known']:
                    continue
                vote = votes_by_lap.setdefault(lap_num, {'known': 0, 'wet': 0})
                vote['known'] += 1
                vote['wet'] += int(lap['wet'])

            for lap in clean_laps:
                leaders = leaders_by_lap.setdefault(lap['num'], {})
                current = leaders.get(class_key)
                if current is None or lap['position'] < current['position']:
                    leaders[class_key] = lap

        references = {}
        lap_numbers = sorted(
            completed_lap_numbers | set(votes_by_lap) | set(leaders_by_lap)
        )
        greasy_active = False
        activation_streak = 0
        recovery_streak = 0

        for lap_num in lap_numbers:
            votes = votes_by_lap.get(lap_num, {'known': 0, 'wet': 0})
            wet_majority = votes['known'] > 0 and votes['wet'] > votes['known'] / 2
            leaders = leaders_by_lap.get(lap_num, {})
            any_leader_over = False
            all_leaders_under = bool(class_keys)

            for class_key in class_keys:
                leader = leaders.get(class_key)
                json_reference = self._get_reference_time(
                    class_names[class_key], reference_times
                )
                if leader is None or not json_reference or json_reference <= 0:
                    all_leaders_under = False
                    continue
                over_threshold = leader['time'] > json_reference * 1.04
                any_leader_over = any_leader_over or over_threshold
                all_leaders_under = all_leaders_under and not over_threshold

            if wet_majority:
                condition = 'wet'
                activation_streak = 0
                recovery_streak = 0
            elif greasy_active:
                condition = 'greasy'
                if all_leaders_under:
                    recovery_streak += 1
                    if recovery_streak >= 2:
                        greasy_active = False
                        recovery_streak = 0
                else:
                    recovery_streak = 0
            else:
                condition = 'dry'
                if votes['wet'] > 0 and any_leader_over:
                    activation_streak += 1
                else:
                    activation_streak = 0
                if activation_streak >= 2:
                    greasy_active = True
                    condition = 'greasy'
                    activation_streak = 0

            for class_key in class_keys:
                if condition in ('wet', 'greasy'):
                    leader = leaders.get(class_key)
                    reference_time = self._rounded_reference(
                        leader['time'], 1.025
                    ) if leader else None
                else:
                    reference_time = self._get_reference_time(
                        class_names[class_key], reference_times
                    )
                references[(lap_num, class_key)] = reference_time

        return references

    def _race_event_metrics(self, root, drivers):
        metrics = {
            self._event_name_key(entry['row']['Driver']): {
                'tracklimits': 0,
                'vehicle_incidents': 0,
                'object_incidents': 0,
            }
            for entry in drivers
        }

        seen_tracklimits = set()
        for element in root.iter('TrackLimits'):
            driver_key = self._event_name_key(element.get('Driver', ''))
            warning_points = self._to_float(element.get('WarningPoints'))
            if driver_key not in metrics or warning_points is None or warning_points <= 0:
                continue

            signature = (
                tuple(sorted(element.attrib.items())),
                (element.text or '').strip(),
            )
            if signature in seen_tracklimits:
                continue
            seen_tracklimits.add(signature)
            metrics[driver_key]['tracklimits'] += 1

        driver_keys = set(metrics)
        reports = []
        for index, element in enumerate(root.iter('Incident')):
            text = (element.text or '').strip()
            actor_match = re.match(r'^(.+?)\(\d+\)\s+reported\b', text, re.IGNORECASE)
            if not actor_match:
                continue

            reporter = self._event_name_key(actor_match.group(1))
            if reporter not in metrics:
                continue

            vehicle_match = re.search(
                r'\bwith\s+another vehicle\s+(.+?)\(\d+\)\s*$',
                text,
                re.IGNORECASE,
            )
            target = self._event_name_key(vehicle_match.group(1)) if vehicle_match else None
            reports.append({
                'index': index,
                'reporter': reporter,
                'target': target if target in driver_keys else None,
                'category': 'vehicle' if 'another vehicle' in text.lower() else 'object',
                'time': self._to_float(element.get('et')),
            })

        possible_pairs = []
        for left_index, left in enumerate(reports):
            if left['target'] is None or left['time'] is None:
                continue
            for right_index in range(left_index + 1, len(reports)):
                right = reports[right_index]
                if (
                    right['target'] == left['reporter']
                    and right['reporter'] == left['target']
                    and right['time'] is not None
                ):
                    time_delta = abs(left['time'] - right['time'])
                    if time_delta <= 0.2:
                        possible_pairs.append((time_delta, left['index'], right['index'], left_index, right_index))

        paired = set()
        for _, _, _, left_index, right_index in sorted(possible_pairs):
            if left_index in paired or right_index in paired:
                continue
            left = reports[left_index]
            right = reports[right_index]
            metrics[left['reporter']]['vehicle_incidents'] += 1
            metrics[right['reporter']]['vehicle_incidents'] += 1
            paired.update((left_index, right_index))

        for report_index, report in enumerate(reports):
            if report_index in paired:
                continue
            category = 'vehicle_incidents' if report['category'] == 'vehicle' else 'object_incidents'
            metrics[report['reporter']][category] += 1

        return metrics

    @staticmethod
    def _event_name_key(name):
        name = str(name).strip()
        if 'LMGT3' in name:
            name = name.split('LMGT3')[0].strip()
        return name.casefold()

    def _race_laps(self, lap_elements):
        race_laps = []
        in_laps = []
        out_laps = []
        n_stops = 0
        pit_lap_num = None

        for lap in lap_elements:
            lap_num = lap['num']
            if lap_num is None or lap_num == 1:
                continue

            is_pit_lap = lap['pit'] and not self.no_pit
            is_out_lap = (
                not self.no_pit
                and pit_lap_num is not None
                and lap_num == pit_lap_num + 1
            )
            if is_pit_lap:
                pit_lap_num = lap_num
                n_stops += 1
            elif is_out_lap:
                pit_lap_num = None

            lap_time = lap['time']
            if lap_time is None:
                continue

            lap_with_time = {**lap, 'time': lap_time}
            if is_pit_lap:
                in_laps.append(lap_with_time)
            elif is_out_lap:
                out_laps.append(lap_with_time)
            else:
                race_laps.append(lap_with_time)
        return race_laps, in_laps, out_laps, n_stops

    @staticmethod
    def _to_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_float(value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if np.isfinite(number) else None