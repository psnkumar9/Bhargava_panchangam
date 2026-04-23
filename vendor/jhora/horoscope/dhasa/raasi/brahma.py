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
""" Also called Brahma Grahashrita Dasa """
from jhora import const, utils
from jhora.panchanga import drik
from jhora.horoscope.chart import charts, house
year_duration = const.sidereal_year

def _dhasa_duration(planet_positions, sign):
    lord_of_6th = house.house_owner_from_planet_positions(planet_positions, (sign+const.HOUSE_6)%12)
    lord_house = planet_positions[lord_of_6th+1][1][0]
    _dd = (lord_house+13-sign)%12
    if sign in const.even_signs:
        _dd = (sign+13-lord_house)%12
    _dd -= 1
    if lord_house == sign:
        _dd = 0
    elif const.house_strengths_of_planets[lord_of_6th][lord_house] == const._DEBILITATED_NEECHAM:
        _dd -= 1
    elif const.house_strengths_of_planets[lord_of_6th][lord_house] == const._EXALTED_UCCHAM:
        _dd += 1
    return _dd

def get_dhasa_antardhasa(
    dob, tob, place,
    divisional_chart_factor=1,
    years=1, months=1, sixty_hours=1,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,  # 1..6 (1=Maha only, 2=+Antara [default], 3..6 deeper)
    round_duration=True,                               # round only the returned durations; JD math stays full precision
    **kwargs
):
    """
        Compute Brahma-based sign daśā with depth control (Maha → Antara → …)

        This function generalizes your original `get_dhasa_antardhasa`:
        - Depth is controlled by `dhasa_level_index` instead of include_antardhasa.
        - Default depth = 2 (Antara) preserves your legacy output shape and values.

        Depth levels (output tuples):
          1 = MAHA_DHASA_ONLY     -> (l1,               start_str, dur_years)
          2 = ANTARA              -> (l1, l2,           start_str, dur_years)        [DEFAULT]
          3 = PRATYANTARA         -> (l1, l2, l3,       start_str, dur_years)
          4 = SOOKSHMA            -> (l1, l2, l3, l4,   start_str, dur_years)
          5 = PRANA               -> (l1, l2, l3, l4, l5, start_str, dur_years)
          6 = DEHA                -> (l1, l2, l3, l4, l5, l6, start_str, dur_years)

        Duration policy:
          - Maha duration (years) comes from _dhasa_duration(...) exactly as before.
          - At every deeper level, the IMMEDIATE parent is split into 12 equal parts
            (same logic you used for Antara). This guarantees Σ(children) = parent at each level.

        Ordering:
          - Maha sequence is 12 signs starting from dhasa_seed, or reverse if seed is even.
          - At each node, children are the 12 signs in cyclic order starting from the parent sign
            (identical to your `bn = d` wraparound).

        Rounding:
          - Only the returned 'dur_years' is rounded (when `round_duration=True`, using
            const.DHASA_DURATION_ROUNDING_TO if available). All JD math uses unrounded values.
    """
    # --- Safety: ensure depth is valid ---------------------------------------------------------
    if not (1 <= dhasa_level_index <= 6):
        raise ValueError("dhasa_level_index must be in 1..6 (1=Maha .. 6=Deha).")

    # --- Build the base chart once (unchanged) ------------------------------------------------
    jd_at_dob = utils.julian_day_number(dob, tob)
    planet_positions = charts.divisional_chart(
        jd_at_dob, place,
        divisional_chart_factor=divisional_chart_factor,
        years=years, months=months, sixty_hours=sixty_hours, **kwargs
    )[:const._pp_count_upto_ketu]

    # Brahma seed sign / daśā seed (unchanged)
    brahma = house.brahma(planet_positions)
    dhasa_seed = planet_positions[brahma + 1][1][0]

    # Maha sequence (12 signs), forward when odd, reverse when even (unchanged)
    dhasa_lords = [(dhasa_seed + h) % 12 for h in range(12)]
    if dhasa_seed in const.even_signs:
        dhasa_lords = [(dhasa_seed + 6 - h + 12) % 12 for h in range(12)]

    # Control rounding precision (fallback to 2 if constant is absent)
    _round_ndigits = getattr(const, 'DHASA_DURATION_ROUNDING_TO', 2)

    # --- Helpers ------------------------------------------------------------------------------

    def _children_signs(parent_sign):
        """
        Children order for a given parent:
          12 signs in cyclic order starting from the *parent* sign itself,
          i.e., [parent, parent+1, ..., wrap].
        """
        return [(parent_sign + k) % 12 for k in range(12)]

    def _equal_split(parent_years):
        """
        Antara / deeper split: 12 equal parts of the immediate parent duration (years).
        """
        return parent_years / 12.0

    def _recurse(level, parent_sign, parent_start_jd, parent_years, prefix, out_rows):
        """
        Recursive builder for depth >= 3. At each node:
          - Child duration = parent_years / 12
          - Children order = cyclic from `parent_sign`
          - Σ(children) = parent (by construction)
        """
        bhuktis = _children_signs(parent_sign)
        child_unrounded = _equal_split(parent_years)
        jd_cursor = parent_start_jd

        if level < dhasa_level_index:
            for child_sign in bhuktis:
                _recurse(level + 1, child_sign, jd_cursor, child_unrounded, prefix + (child_sign,), out_rows)
                jd_cursor += child_unrounded * year_duration
        else:
            for child_sign in bhuktis:
                start_str = utils.jd_to_gregorian(jd_cursor)
                dur_ret = round(child_unrounded, dhasa_level_index+1) if round_duration else child_unrounded
                out_rows.append((prefix + (child_sign,), start_str, dur_ret))
                jd_cursor += child_unrounded * year_duration

    # --- Main loop: build rows at requested depth ---------------------------------------------

    dhasa_info = []
    start_jd = jd_at_dob

    for d, dhasa_lord in enumerate(dhasa_lords):
        # 1) Maha duration in YEARS (kept exactly as before)
        duration_years = float(_dhasa_duration(planet_positions, dhasa_lord))

        # Guard against negative/zero (rare, but keep math safe)
        # (If you prefer strict original behavior, remove the max(); I’m leaving the clamp commented)
        # duration_years = max(duration_years, 0.0)

        if dhasa_level_index == const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY:
            # ---- L1: Maha only ----
            dhasa_info.append((
                (dhasa_lord,),
                utils.jd_to_gregorian(start_jd),
                round(duration_years, dhasa_level_index+1) if round_duration else duration_years
            ))
            start_jd += duration_years * year_duration
            continue

        if dhasa_level_index == const.MAHA_DHASA_DEPTH.ANTARA:
            # ---- L2: Antara (legacy equal-split into 12) ----
            bhukthis = _children_signs(dhasa_lord)     # identical ordering to your original (bn=d logic)
            dd = duration_years / 12.0                  # equal split (years)
            jd_cursor = start_jd

            for bhukthi_lord in bhukthis:
                dhasa_info.append((
                    (dhasa_lord,bhukthi_lord),
                    utils.jd_to_gregorian(jd_cursor),
                    round(dd, dhasa_level_index+1) if round_duration else dd
                ))
                jd_cursor += dd * year_duration

            # Advance Maha cursor by full Maha duration
            start_jd += duration_years * year_duration
            continue

        # ---- L3..L6: recursive equal-split under immediate parent ----
        _recurse(
            level=const.MAHA_DHASA_DEPTH.ANTARA,   # = 2; children built at 3..N
            parent_sign=dhasa_lord,
            parent_start_jd=start_jd,
            parent_years=duration_years,
            prefix=(dhasa_lord,),
            out_rows=dhasa_info
        )
        start_jd += duration_years * year_duration

    return dhasa_info
def brahma_immediate_children(
    parent_lords,
    parent_start,                # (Y, M, D, fractional_hour)
    parent_duration=None,        # float years (one of duration or end must be provided)
    parent_end=None,             # (Y, M, D, fractional_hour)
    *,
    jd_at_dob,
    place,
    divisional_chart_factor: int = 1,
    years: int = 1, months: int = 1, sixty_hours: int = 1,
    round_duration: bool = False,     # tiler tiles exact spans; rounding not needed here
    **kwargs
):
    """
    Brahma Daśā — return ONLY the immediate (p -> p+1) children under the given parent span.

    Matches your base get_dhasa_antardhasa():
      • Children = 12 signs in cyclic order starting from the *parent sign* itself
      • Sama: child_years = parent_years / 12
      • Exact tiling within [parent_start, parent_end)
      • Labels are signs 0..11
    """
    # ---- normalize lords path
    if isinstance(parent_lords, int):
        path = (parent_lords,)
    elif isinstance(parent_lords, (list, tuple)) and parent_lords:
        path = tuple(parent_lords)
    else:
        raise ValueError("parent_lords must be int or non-empty tuple/list")
    parent_sign = path[-1]

    # ---- canonical tuple <-> JD
    def _tuple_to_jd(t):
        y, m, d, fh = t
        return utils.julian_day_number(drik.Date(y, m, d), (fh, 0, 0))
    def _jd_to_tuple(jd_val):
        return utils.jd_to_gregorian(jd_val)

    # ---- resolve parent span
    start_jd = _tuple_to_jd(parent_start)
    if (parent_duration is None) == (parent_end is None):
        raise ValueError("Provide exactly one of parent_duration (years) or parent_end (tuple).")

    YEAR_DAYS = const.sidereal_year

    if parent_end is None:
        parent_years = float(parent_duration)
        end_jd = start_jd + parent_years * YEAR_DAYS
    else:
        end_jd = _tuple_to_jd(parent_end)
        parent_years = (end_jd - start_jd) / YEAR_DAYS

    if end_jd <= start_jd:
        return []  # instantaneous parent → no children

    # ---- children order: 12 signs cyclic from parent_sign
    children_signs = [(parent_sign + k) % 12 for k in range(12)]

    # ---- equal split at this level
    child_years = parent_years / 12.0

    # ---- tile children
    children = []
    cursor = start_jd
    for i, sgn in enumerate(children_signs):
        if i == len(children_signs) - 1:
            child_end = end_jd
        else:
            child_end = cursor + child_years * YEAR_DAYS
        children.append([
            path + (sgn,),
            _jd_to_tuple(cursor),
            _jd_to_tuple(child_end),
        ])
        cursor = child_end
        if cursor >= end_jd:
            break

    if children:
        children[-1][2] = _jd_to_tuple(end_jd)

    return children
def get_running_dhasa_for_given_date(
    current_jd,
    jd_at_dob,
    place,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA,
    *,
    divisional_chart_factor: int = 1,
    years: int = 1, months: int = 1, sixty_hours: int = 1,
    round_duration: bool = False,    # runner uses exact start/end; not needed
    **kwargs
):
    """
    Brahma Daśā — narrow Mahā -> … -> target depth and return the full running ladder:

      [
        [(l1,),              start1, end1],
        [(l1,l2),            start2, end2],
        [(l1,l2,l3),         start3, end3],
        [(l1,l2,l3,l4),      start4, end4],
        [(l1,l2,l3,l4,l5),   start5, end5],
        [(l1,l2,l3,l4,l5,l6),start6, end6],
      ]
    """

    # ---- depth normalization (Enum-friendly)
    def _normalize_depth(depth_val):
        try:
            depth = int(depth_val)
        except Exception:
            depth = int(const.MAHA_DHASA_DEPTH.DEHA)
        lo = int(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY)
        hi = int(const.MAHA_DHASA_DEPTH.DEHA)
        return min(hi, max(lo, depth))
    target_depth = _normalize_depth(dhasa_level_index)

    # ---- tuple -> JD & zero-length helpers
    def _tuple_to_jd(t):
        y, m, d, fh = t
        return utils.julian_day_number(drik.Date(y, m, d), (fh, 0, 0))

    def _is_zero_length(s, e, eps_seconds=1.0):
        return (_tuple_to_jd(e) - _tuple_to_jd(s)) * 86400.0 <= eps_seconds

    def _to_utils_periods(children_rows, parent_end_tuple, eps_seconds=1.0):
        """
        children_rows: [ [lords_tuple, start_tuple, end_tuple], ... ]
        Returns: list of (lords_tuple, start_tuple) + sentinel(parent_end_tuple),
        filtering zero-length rows and enforcing strictly increasing starts.
        """
        filtered = [r for r in children_rows if not _is_zero_length(r[1], r[2], eps_seconds)]
        if not filtered:
            return []
        filtered.sort(key=lambda r: _tuple_to_jd(r[1]))
        proj, prev = [], None
        for lords, st, _ in filtered:
            sjd = _tuple_to_jd(st)
            if prev is None or sjd > prev:
                proj.append((lords, st)); prev = sjd
        proj.append((proj[-1][0], parent_end_tuple))  # sentinel
        return proj

    def _as_tuple_lords(x):
        return (x,) if isinstance(x, int) else tuple(x)

    # ---- derive dob/tob for L1 base call
    y, m, d, fh = utils.jd_to_gregorian(jd_at_dob)
    dob = drik.Date(y, m, d)
    tob = (fh, 0, 0)

    running_all = []

    # ---- L1: Mahā via your base Brahma generator (depth=1)
    maha_rows = get_dhasa_antardhasa(
        dob, tob, place,
        divisional_chart_factor=divisional_chart_factor,
        years=years, months=months, sixty_hours=sixty_hours,
        dhasa_level_index=const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY,
        round_duration=False,
        **kwargs
    )
    # normalize: (lords_tuple, start_tuple)
    maha_for_utils = [(_as_tuple_lords(row[0]), row[1]) for row in maha_rows]

    # Running Mahā
    rd1 = utils.get_running_dhasa_for_given_date(current_jd, maha_for_utils)
    running = [_as_tuple_lords(rd1[0]), rd1[1], rd1[2]]
    running_all.append(running)

    if target_depth == int(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY):
        return running_all

    # ---- Levels 2..target
    for depth in range(2, target_depth + 1):
        parent_lords, parent_start, parent_end = running

        children = brahma_immediate_children(
            parent_lords=parent_lords,
            parent_start=parent_start,
            parent_end=parent_end,
            jd_at_dob=jd_at_dob,
            place=place,
            divisional_chart_factor=divisional_chart_factor,
            years=years, months=months, sixty_hours=sixty_hours,
            **kwargs
        )
        if not children:
            # represent as zero-length at parent_end (no children under this parent)
            running = [parent_lords + (parent_lords[-1],), parent_end, parent_end]
            running_all.append(running)
            break

        periods_for_utils = _to_utils_periods(children, parent_end_tuple=parent_end)
        if not periods_for_utils:
            # all zero-length → represent boundary
            last = children[-1]
            running = [last[0], last[1], last[1]]
        else:
            rdk = utils.get_running_dhasa_for_given_date(current_jd, periods_for_utils)
            running = [_as_tuple_lords(rdk[0]), rdk[1], rdk[2]]

        running_all.append(running)

    return running_all

if __name__ == "__main__":
    utils.set_language('en')
    dob = drik.Date(1996,12,7); tob = (10,34,0)
    place = drik.Place('Chennai,IN', 13.0389, 80.2619, +5.5)    
    jd_at_dob  = utils.julian_day_number(dob, tob)
    from datetime import datetime
    current_date_str,current_time_str = datetime.now().strftime('%Y,%m,%d;%H:%M:%S').split(';')
    y,m,d = map(int,current_date_str.split(','))
    hh,mm,ss = map(int,current_time_str.split(':')); fh = hh+mm/60+ss/3600
    print(utils.date_time_tuple_to_date_time_string(y, m, d, fh))
    current_jd = utils.julian_day_number(drik.Date(y,m,d),(hh,mm,ss))
    import time
    start_time = time.time()
    print("Dehā        :", get_running_dhasa_for_given_date(current_jd, jd_at_dob, place,
                                                            dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA))
    print('new method elapsed time',time.time()-start_time)
    start_time = time.time()
    ad = get_dhasa_antardhasa(dob,tob, place,dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA)
    print(utils.get_running_dhasa_at_all_levels_for_given_date(current_jd, ad,const.MAHA_DHASA_DEPTH.DEHA,
                                                               extract_running_period_for_all_levels=True))
    print('old method elapsed time',time.time()-start_time)
    exit()
    from jhora.tests import pvr_tests
    pvr_tests._STOP_IF_ANY_TEST_FAILED = True
    pvr_tests.brahma_dhasa_test()