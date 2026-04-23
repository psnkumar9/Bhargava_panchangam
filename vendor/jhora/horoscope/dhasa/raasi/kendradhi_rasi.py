#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (C) Open Astro Technologies, USA.
# Modified by Sundar Sundaresan, USA. carnaticmusicguru2015@comcast.net
# Downloaded from https://github.com/naturalstupid/PyJHora

# This file is part of the "PyJHora" Python library
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
from jhora import const, utils
from jhora.horoscope.chart import charts, house
from jhora.horoscope.dhasa.raasi import narayana
year_duration = const.sidereal_year
""" Also called Lagna Kendradi Raasi Dhasa """
""" This file also finds Karaka Kendraddi Rasi Dasa - See karaka_kendradhi_rasi_dhasa() """
def lagna_kendradhi_rasi_dhasa(
    dob, tob, place,
    divisional_chart_factor=1,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,  # 1..6 (1=Maha only, 2=+Antara [default], 3..6 deeper)
    round_duration=True,
    **kwargs
):

    return kendradhi_rasi_dhasa(dob, tob, place, divisional_chart_factor, dhasa_level_index, round_duration,**kwargs)

def kendradhi_rasi_dhasa(
    dob, tob, place,
    divisional_chart_factor=1,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,  # 1..6 (1=Maha only, 2=+Antara [default], 3..6 deeper)
    round_duration=True,**kwargs
):
    """
    Kendraadhi Rāśi Daśā with multi-level depth (Maha → Antara → …)

    Depth control:
      1 = MAHA_DHASA_ONLY          -> (l1,                 start_str, dur_years)
      2 = ANTARA                   -> (l1, l2,             start_str, dur_years)  [DEFAULT]
      3 = PRATYANTARA              -> (l1, l2, l3,         start_str, dur_years)
      4 = SOOKSHMA                 -> (l1, l2, l3, l4,     start_str, dur_years)
      5 = PRANA                    -> (l1, l2, l3, l4, l5, start_str, dur_years)
      6 = DEHA                     -> (l1, l2, l3, l4, l5, l6, start_str, dur_years)

    Seed & Direction (unchanged):
      • Seed: stronger of Asc & 7th (house.stronger_rasi_from_planet_positions).
      • Direction: Saturn in seed ⇒ forward; Ketu in seed ⇒ backward; else odd forward / even backward.
      • Progression: by first 3 kendras (house.kendras()[:3]) mapped from seed in the chosen direction.

    Durations (updated to match your new rules):
      • Mahā duration (cycle 1): narayana._dhasa_duration(planet_positions, rasi).
      • Two cycles **always**:
          – Cycle 1: use first duration.
          – Cycle 2: duration = max(12.0 − first_duration, 0.0).
      • **No life-span cutoff**; **do not stop early**.
      • **If duration is 0.0** at any level, still include the period in the output with:
          (lords_tuple, dhasa_start, 0.0). Start date does NOT advance for zero periods.

    Antara ordering:
      • At any node: _antardhasa(parent_sign, p_to_h).
    """
    if not (1 <= dhasa_level_index <= 6):
        raise ValueError("dhasa_level_index must be in 1..6")

    jd_at_dob = utils.julian_day_number(dob, tob)
    planet_positions = charts.divisional_chart(
        jd_at_dob, place, divisional_chart_factor=divisional_chart_factor,**kwargs
    )[:const._pp_count_upto_ketu]
    p_to_h = utils.get_planet_house_dictionary_from_planet_positions(planet_positions)

    asc_house = p_to_h[const._ascendant_symbol]
    seventh_house = (asc_house + const.HOUSE_7) % 12
    dhasa_seed_sign = house.stronger_rasi_from_planet_positions(
        planet_positions, asc_house, seventh_house
    )

    # Direction
    if p_to_h[const.SATURN_ID] == dhasa_seed_sign:
        direction = 1
    elif p_to_h[const.KETU_ID] == dhasa_seed_sign:
        direction = -1
    elif dhasa_seed_sign in const.odd_signs:
        direction = 1
    else:
        direction = -1

    # Progression from first 3 kendras (1,4,7), mapped from seed
    ks = sum(house.kendras()[:3], [])
    dhasa_progression = [ (dhasa_seed_sign + direction * (k - 1)) % 12 for k in ks ]

    # Helpers
    def _children(parent_sign):
        """12 children from parent sign using antar ordering."""
        return _antardhasa(parent_sign, p_to_h)

    def _emit_period(lords_tuple, start_jd, dur_years, out_rows):
        """Append output row and advance cursor by duration (even if 0)."""
        start_str = utils.jd_to_gregorian(start_jd)
        dur_out = round(dur_years, dhasa_level_index + 1) if round_duration else dur_years
        out_rows.append((lords_tuple, start_str, dur_out))
        return start_jd + dur_years * year_duration  # advances 0 for zero durations

    def _recurse(level, parent_sign, parent_start_jd, parent_years, prefix, out_rows):
        child_years = parent_years / 12.0
        jd_cursor = parent_start_jd
        for child_sign in _children(parent_sign):
            if level < dhasa_level_index:
                _recurse(level + 1, child_sign, jd_cursor, child_years, prefix + (child_sign,), out_rows)
                jd_cursor += child_years * year_duration
            else:
                jd_cursor = _emit_period(prefix + (child_sign,), jd_cursor, child_years, out_rows)
        # jd_cursor implicitly advanced (or not) by child_years each step

    rows = []
    start_jd = jd_at_dob

    # ---------------------- Cycle #1 ----------------------
    for dhasa_lord in dhasa_progression:
        dd = float(narayana._dhasa_duration(planet_positions, dhasa_lord))

        if dhasa_level_index == const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY:
            start_jd = _emit_period((dhasa_lord,), start_jd, dd, rows)

        elif dhasa_level_index == const.MAHA_DHASA_DEPTH.ANTARA:
            ddb = dd / 12.0
            jd_b = start_jd
            for bhukthi_lord in _children(dhasa_lord):
                jd_b = _emit_period((dhasa_lord, bhukthi_lord), jd_b, ddb, rows)
            start_jd = jd_b  # equals start_jd + dd*year_duration

        else:
            _recurse(const.MAHA_DHASA_DEPTH.ANTARA, dhasa_lord, start_jd, dd, (dhasa_lord,), rows)
            start_jd += dd * year_duration

    # ---------------------- Cycle #2 ----------------------
    for dhasa_lord in dhasa_progression:
        first_dd = float(narayana._dhasa_duration(planet_positions, dhasa_lord))
        dd2 = 12.0 - first_dd
        if dd2 < 0.0:
            dd2 = 0.0  # include as zero-duration; do not skip

        if dhasa_level_index == const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY:
            start_jd = _emit_period((dhasa_lord,), start_jd, dd2, rows)

        elif dhasa_level_index == const.MAHA_DHASA_DEPTH.ANTARA:
            ddb = dd2 / 12.0
            jd_b = start_jd
            for bhukthi_lord in _children(dhasa_lord):
                jd_b = _emit_period((dhasa_lord, bhukthi_lord), jd_b, ddb, rows)
            start_jd = jd_b  # equals start_jd + dd2*year_duration

        else:
            _recurse(const.MAHA_DHASA_DEPTH.ANTARA, dhasa_lord, start_jd, dd2, (dhasa_lord,), rows)
            start_jd += dd2 * year_duration

    return rows

def karaka_kendradhi_rasi_dhasa(
    dob, tob, place,
    divisional_chart_factor=1,
    karaka_index=1,                         # 1..8
    dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,
    round_duration=True,**kwargs
):
    """
    Kāraka Kendraadhi Rāśi Daśā with multi-level depth.

    Same rules as Kendraadhi Rāśi Daśā, except:
      • Seed is stronger of (AK house) & (7th from AK house).
      • Direction uses the same Saturn/Ketu/odd-even logic.
      • Progression uses kendrasas above.

    Depth shapes and recursion are identical to kendradhi_rasi_dhasa.
    """
    if karaka_index not in range(1, 9):
        # keep your friendly fallback
        print('Karaka Index should be in the range (1..8). Index 1 assumed')
        karaka_index = 1

    if not (1 <= dhasa_level_index <= 6):
        raise ValueError("dhasa_level_index must be in 1..6 (1=Maha .. 6=Deha).")

    jd_at_dob = utils.julian_day_number(dob, tob)
    planet_positions = charts.divisional_chart(jd_at_dob, place, divisional_chart_factor=divisional_chart_factor
                                               ,**kwargs)[:const._pp_count_upto_ketu]

    p_to_h = utils.get_planet_house_dictionary_from_planet_positions(planet_positions)
    ak = house.chara_karakas(planet_positions)[karaka_index - 1]
    ak_house = p_to_h[ak]
    seventh_house = (ak_house + const.HOUSE_7) % 12
    dhasa_seed_sign = house.stronger_rasi_from_planet_positions(planet_positions, ak_house, seventh_house)

    # Direction
    if p_to_h[const.SATURN_ID] == dhasa_seed_sign:
        direction = 1
    elif p_to_h[const.KETU_ID] == dhasa_seed_sign:
        direction = -1
    elif dhasa_seed_sign in const.odd_signs:
        direction = 1
    else:
        direction = -1

    ks = sum(house.kendras()[:3], [])
    dhasa_progression = [ (dhasa_seed_sign + direction * (k - 1)) % 12 for k in ks ]

    _round_ndigits = getattr(const, 'DHASA_DURATION_ROUNDING_TO', 2)

    def _children(parent_sign):
        return _antardhasa(parent_sign, p_to_h)

    def _recurse(level, parent_sign, parent_start_jd, parent_years, prefix, out_rows):
        child_years = parent_years / 12.0
        jd_cursor = parent_start_jd
        for child_sign in _children(parent_sign):
            if level < dhasa_level_index:
                _recurse(level + 1, child_sign, jd_cursor, child_years, prefix + (child_sign,), out_rows)
            else:
                start_str = utils.jd_to_gregorian(jd_cursor)
                dur_ret   = round(child_years, dhasa_level_index+1) if round_duration else child_years
                out_rows.append((prefix + (child_sign,), start_str, dur_ret))
            jd_cursor += child_years * year_duration

    rows = []
    start_jd = jd_at_dob
    total_years = 0.0

    # ----- Cycle #1 ------------------------------------------------------------
    for dhasa_lord in dhasa_progression:
        dd = float(narayana._dhasa_duration(planet_positions, dhasa_lord))
        total_years += dd

        if dhasa_level_index == const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY:
            rows.append(((dhasa_lord,), utils.jd_to_gregorian(start_jd),
                         round(dd, dhasa_level_index+1) if round_duration else dd))
            start_jd += dd * year_duration
        elif dhasa_level_index == const.MAHA_DHASA_DEPTH.ANTARA:
            ddb = dd / 12.0
            jd_b = start_jd
            for bhukthi_lord in _children(dhasa_lord):
                rows.append(((dhasa_lord, bhukthi_lord), utils.jd_to_gregorian(jd_b),
                             round(ddb, dhasa_level_index+1) if round_duration else ddb))
                jd_b += ddb * year_duration
            start_jd += dd * year_duration
        else:
            _recurse(const.MAHA_DHASA_DEPTH.ANTARA, dhasa_lord, start_jd, dd, (dhasa_lord,), rows)
            start_jd += dd * year_duration

    # ----- Cycle #2 (12 − first) ----------------------------------------------
    for idx, dhasa_lord in enumerate(dhasa_progression):
        first_dd = float(narayana._dhasa_duration(planet_positions, dhasa_lord))
        dd2 = 12.0 - first_dd
        if dd2 <= 0:
            dd2 = 0.0
        total_years += dd2

        if dhasa_level_index == const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY:
            rows.append(((dhasa_lord,), utils.jd_to_gregorian(start_jd),
                         round(dd2, dhasa_level_index+1) if round_duration else dd2))
            start_jd += dd2 * year_duration
        elif dhasa_level_index == const.MAHA_DHASA_DEPTH.ANTARA:
            ddb = dd2 / 12.0
            jd_b = start_jd
            for bhukthi_lord in _children(dhasa_lord):
                rows.append(((dhasa_lord, bhukthi_lord), utils.jd_to_gregorian(jd_b),
                             round(ddb, dhasa_level_index+1) if round_duration else ddb))
                jd_b += ddb * year_duration
            start_jd += dd2 * year_duration
        else:
            _recurse(const.MAHA_DHASA_DEPTH.ANTARA, dhasa_lord, start_jd, dd2, (dhasa_lord,), rows)
            start_jd += dd2 * year_duration

    return rows
def _antardhasa(antardhasa_seed_rasi,p_to_h):
    direction = -1
    if p_to_h[const.SATURN_ID]==antardhasa_seed_rasi or antardhasa_seed_rasi in const.odd_signs: # Forward
        direction = 1
    if p_to_h[const.KETU_ID]==antardhasa_seed_rasi:
        direction *= -1
    return [(antardhasa_seed_rasi+direction*i)%12 for i in range(12)]
if __name__ == "__main__":
    from jhora.tests import pvr_tests
    pvr_tests._STOP_IF_ANY_TEST_FAILED = True
    pvr_tests.kendradhi_rasi_test()