"""Generate normalized pace and race descriptors from LMU result XML."""

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
    'n_inchidents', 'pct_laps', 'n_stops', 'pit_lane_pct_times',
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
            if not self._matches_class(car_class):
                continue

            overall_position = self._to_int(driver.findtext('Position'))
            class_position = self._to_int(driver.findtext('ClassPosition'))
            position = class_position if class_position is not None else overall_position
            if position is None:
                continue

            all_laps = list(driver.findall('Lap'))
            valid_laps = self._valid_lap_times(all_laps)
            if not valid_laps:
                continue

            row = {
                'Driver': driver.findtext('Name', 'Unknown'),
                'Car': driver.findtext('CarType', 'Unknown'),
                'CarClass': car_class,
                'CarNumber': driver.findtext('CarNumber', 'N/A'),
                'Position': position,
                'FinishStatus': driver.findtext('FinishStatus', ''),
                'Laps': self._to_int(driver.findtext('Laps')) or len(all_laps),
                'lap_count': len(valid_laps),
                'laptime_sec': float(min(valid_laps)),
                'avg_laptime': float(np.mean(valid_laps)),
                'stdev_laptime': float(np.std(valid_laps, ddof=1)) if len(valid_laps) > 1 else 0.0,
            }
            row['laptime_pct'] = np.nan
            row['laptime_pct_alien'] = np.nan
            row['avg_pace_pct_alien'] = np.nan
            row['stdev_pace_pct'] = np.nan
            row.update({column: np.nan for column in RACE_DESCRIPTOR_COLUMNS})
            row['_reference_times'] = reference_times or {}
            drivers.append((row, all_laps))

        if not drivers:
            return pd.DataFrame(columns=PACE_COLUMNS + RACE_DESCRIPTOR_COLUMNS)

        class_best = {}
        class_leaders = {}
        class_race_pace = {}
        race_stats = {}
        for row, _ in drivers:
            class_key = self._class_key(row['CarClass'])
            class_best[class_key] = min(class_best.get(class_key, row['laptime_sec']), row['laptime_sec'])
            class_leaders[class_key] = max(class_leaders.get(class_key, 0), row['Laps'])

        if include_race:
            for row, all_laps in drivers:
                race_laps, tracklimits, in_laps, out_laps, n_stops = self._race_laps(all_laps)
                if not race_laps:
                    continue
                race_pace = float(np.mean(race_laps))
                class_key = self._class_key(row['CarClass'])
                class_race_pace[class_key] = min(
                    class_race_pace.get(class_key, race_pace), race_pace
                )
                race_stats[id(row)] = (
                    race_pace, tracklimits, in_laps, out_laps, n_stops, race_laps
                )

        output = []
        for row, all_laps in drivers:
            class_key = self._class_key(row['CarClass'])
            reference_time = self._get_reference_time(row['CarClass'], reference_times)
            row['laptime_pct'] = round(100 * class_best[class_key] / row['laptime_sec'], 2)
            row['laptime_pct_alien'] = round(100 * row['laptime_sec'] / reference_time, 2) if reference_time else np.nan
            row['avg_pace_pct_alien'] = round(100 * row['avg_laptime'] / reference_time, 2) if reference_time else np.nan
            row['stdev_pace_pct'] = round(100 * row['stdev_laptime'] / reference_time, 2) if reference_time else np.nan

            if include_race:
                stats = race_stats.get(id(row))
                if stats:
                    race_pace, tracklimits, in_laps, out_laps, n_stops, race_laps = stats
                    row['race_pace'] = race_pace
                    row['pct_race_pace'] = max(
                        100.0, 100 * race_pace / class_race_pace[class_key]
                    )
                    row['consistency'] = 1 - float(np.std(race_laps)) / race_pace
                    incidents = sum(lap > race_pace * 1.02 for lap in race_laps)
                    row['n_tracklimits'] = tracklimits
                    row['n_inchidents'] = incidents
                    row['reliability'] = max(0.0, 1 - (tracklimits + incidents) / len(race_laps))
                    leader_laps = class_leaders[class_key]
                    row['pct_laps'] = 100 * row['Laps'] / leader_laps if leader_laps else np.nan
                    row['n_stops'] = n_stops
                    if in_laps and len(in_laps) == len(out_laps):
                        row['pit_lane_pct_times'] = (
                            (sum(in_laps) + sum(out_laps) - len(in_laps) * 2 * race_pace)
                            / race_pace
                        )

            row.pop('_reference_times')
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

    @staticmethod
    def _valid_lap_times(laps):
        valid = []
        for lap in laps:
            try:
                lap_time = float(lap.text)
            except (TypeError, ValueError):
                continue
            if lap_time > 0:
                if valid and lap_time > min(valid) * 1.07:
                    continue
                valid.append(lap_time)
        return valid

    def _race_laps(self, lap_elements):
        race_laps = []
        tracklimits = 0
        in_laps = []
        out_laps = []
        n_stops = 0
        pit_lap_num = None
        previous_elapsed = None

        for lap in lap_elements:
            lap_num = self._to_int(lap.get('num'))
            if lap_num == 1:
                continue

            elapsed = self._to_float(lap.get('et'))
            lap_time = self._to_float(lap.text)
            if lap_time is None and elapsed is not None and previous_elapsed is not None:
                lap_time = elapsed - previous_elapsed
                tracklimits += 1
            if lap_time is None:
                continue

            if not self.no_pit and lap.get('pit') is not None:
                pit_lap_num = lap_num
                in_laps.append(lap_time)
                n_stops += 1
                previous_elapsed = elapsed
                continue
            if not self.no_pit and pit_lap_num is not None and lap_num == pit_lap_num + 1:
                out_laps.append(lap_time)
                pit_lap_num = None
                previous_elapsed = elapsed
                continue

            race_laps.append(lap_time)
            previous_elapsed = elapsed

        return race_laps, tracklimits, in_laps, out_laps, n_stops

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