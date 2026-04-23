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
"""
    Compute Rashiyanka/Rasyamsaka Dhasa - Ref: https://astrologicalmusings.com/method-of-calculating-rashiyanka-dasha/
"""
from jhora import const, utils
from jhora.horoscope.chart import charts, house
from jhora.panchanga import drik
one_year_duration = const.sidereal_year

def applicability(pp_d1):
    # lagna lord in exaltion, own or friends house
    asc_d1 = pp_d1[0][1][0]
    lord_asc_d1 = house.house_owner_from_planet_positions(pp_d1, asc_d1)
    house_lord_asc_d1 = pp_d1[lord_asc_d1+1][1][0]
    return utils.is_planet_strong(lord_asc_d1, house_lord_asc_d1)
def _dhasa_progression(planet_positions,dhasa_progression_method=1,chart_method_d9=1):
    """
        Dhasa progression direct in both cases
        dhasa method = 1 BPHS Venkateshwar Edition (Translator: Pandit Tara Chand Shastri)
            starts from navamsa rasi of rasi lagna lord
        dhasa method = 2 BPHS - (Translator: Pandit Ganesh Dutt Pathak)
            starts from navamsa rasi of rasi lagna lord
    """
    asc_d1   = planet_positions[0][1][0]
    lord_asc = const._house_owners_list[asc_d1]  # force Parāśari lords
    pp_d9    = charts.navamsa_chart(planet_positions, chart_method=chart_method_d9)
    asc_d9   = pp_d9[0][1][0]
    lord_asc_d9 = pp_d9[lord_asc+1][1][0]

    if dhasa_progression_method == 1:
        seed = lord_asc_d9  # Venkateśvara: D‑9 of Lagna‑lord
    else:
        # Pathak: stronger(Lagna, Lagna‑lord) in D‑1 → take that entity’s D‑9 sign
        stronger_in_d1 = house.stronger_rasi_from_planet_positions(planet_positions, asc_d1, planet_positions[lord_asc+1][1][0])
        seed = asc_d9 if stronger_in_d1 == asc_d1 else lord_asc_d9
    
    return [(seed + h) % 12 for h in range(12)]
def _dhasa_duration_mandooka_kn_rao(planet_positions, sign):
    lord_of_sign = const._house_owners_list[sign]
    lord_sign = planet_positions[lord_of_sign + 1][1][0]
    # Overrides first (explicit & unambiguous)
    if lord_sign == sign:
        return 12
    if lord_sign == (sign + 6) % 12:
        return 10
    # Parity-based inclusive count (Mandūka)
    if sign in const.even_signs:
        dhasa_duration = (sign - lord_sign + 1) % 12   # backward inclusive
    else:
        dhasa_duration = (lord_sign - sign + 1) % 12   # forward inclusive
    return dhasa_duration or 12  # ← map “0” (full loop) to 12def __dhasa_duration_mandooka_kn_rao(planet_positions,sign):
    """ Use standard lord in case dual lord signs """
    p_to_h = utils.get_planet_house_dictionary_from_planet_positions(planet_positions)
    lord_of_sign = const._house_owners_list[sign]#Use standard lord in case dual lord signs
    house_of_lord = p_to_h[lord_of_sign]
    dhasa_period = 0
    """ The length of a dasa is determined by the position of the lord of dasa rasi with respect to dasa rasi."""
    if sign in const.even_signs: # count back from sign to house_of_lord
        dhasa_period = (sign-house_of_lord+1)%12
    else:
        dhasa_period = (house_of_lord-sign+1)%12
    if house_of_lord==sign:
        dhasa_period = 12
    if house_of_lord==(sign+6)%12:
        dhasa_period = 10
    return dhasa_period
def _dhasa_duration_mandooka_sanjay_rath(lord):

    if lord in const.movable_signs:
        return 7
    elif lord in const.fixed_signs:
        return 8
    else:
        return 9
def _dhasa_duration_reference(planet_positions,sign):
    p_to_h = utils.get_planet_house_dictionary_from_planet_positions(planet_positions)
    lord_of_sign = house.house_owner_from_planet_positions(planet_positions, sign)
    house_of_lord = p_to_h[lord_of_sign]
    dhasa_period = 0
    """ The length of a dasa is determined by the position of the lord of dasa rasi with respect to dasa rasi."""
    if sign in const.even_signs: # count back from sign to house_of_lord
        dhasa_period = (sign-house_of_lord+1)%12
            #print('house_of_lord',house_of_lord,'> sign',sign,'dhasa_period',dhasa_period)
    else:
        dhasa_period = (house_of_lord-sign+1)%12
    if dhasa_period <=0 or const.house_strengths_of_planets[lord_of_sign][house_of_lord] == const._OWNER_RULER:# or \
            #house_of_lord==(sign+11)%12:
        dhasa_period = 12
    if house_of_lord==(sign+6)%12:
        dhasa_period = 10
    return dhasa_period
def _dhasa_duration(planet_positions,dhasa_lord,dhasa_duration_method=1):
    """
        dhasa duration similar to mandooka dhasa which has 2 methods
        method=1 - KN Rao method
            The length of a dasa is determined by the position of the lord of dasa rasi with respect to dasa rasi.
            depending on dasa rasi is even/odd footed. 10 years if lord in 7th house from sign
        method=2 - Sanjay Rath method
            movable = 7 years, Fixed=8 and dual = 9
        method=3 - Reference version
            counting indirect for even, direct for odd, 10 if lord in 7th house from sign
    """
    if dhasa_duration_method==1: return _dhasa_duration_mandooka_kn_rao(planet_positions, dhasa_lord)
    if dhasa_duration_method==2: return _dhasa_duration_mandooka_sanjay_rath(dhasa_lord)
    return _dhasa_duration_reference(planet_positions, dhasa_lord)

def get_dhasa_bhukthi(
    dob, tob, place,
    divisional_chart_factor=1,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,              # 1..6 (1=Maha only, 2=Bhukti, 3..6 deeper)
    dhasa_progression_method=1,       # 1=BPHS (Tara Chand Shastri), 2=BPHS (Ganesh Dutt Pathak)
    dhasa_duration_method=1,          # 1=KN Rao (Mandooka-like rule), 2=Sanjay Rath, 3=Reference
    chart_method=1,                   # chart method for Dx
    chart_method_for_navamsa=1,       # used inside _dhasa_progression
    sublevel_split="equal",           # "equal" | "proportional"
    round_duration=True,              # only the returned duration (display) is rounded
    **kwargs
):
    """
    Rāśyāṁśaka / Rāśiyanka Daśā (depth-enabled, 1..6).

    RETURNS (canonical flat list), each row shaped as:
      ( (L1, ..., Lk), (y,m,d,float_hours), dur_years_float )

    Mechanics:
      • Progression order (seed & cycle of 12): _dhasa_progression(...)
      • Durations per sign: _dhasa_duration(planet_positions, sign, dhasa_duration_method)
      • L1 (Maha) uses raw years; L2..N sublevels:
          - "equal"        → split parent equally into 12
          - "proportional" → scale raw 12-sign durations to exactly fill the parent
      • All JD arithmetic uses const.sidereal_year (no rounding).
      • Only the returned 'dur_years' is optionally rounded (display).
    """
    # ── 0) Validate depth & set rounding precision ───────────────────────────
    lvl = int(dhasa_level_index)
    if not (1 <= lvl <= 6):
        raise ValueError("dhasa_level_index must be in 1..6")
    ndigits = lvl if round_duration else None

    # ── 1) Epoch & chart ─────────────────────────────────────────────────────
    jd_birth = utils.julian_day_number(dob, tob)
    year_days = const.sidereal_year

    planet_positions = charts.divisional_chart(
        jd_birth,
        place,
        divisional_chart_factor,
        chart_method,**kwargs
    )[:const._pp_count_upto_ketu]

    # ── 2) Progression cycle of 12 (seeded order) ────────────────────────────
    # progression_order: list of 12 signs (0..11), starting at the seed
    progression_order = _dhasa_progression(
        planet_positions,
        dhasa_progression_method=dhasa_progression_method,
        chart_method_d9=chart_method_for_navamsa
    )

    # ── Local helpers ────────────────────────────────────────────────────────
    def _rotate(order, start_sign):
        idx = order.index(start_sign)
        return order[idx:] + order[:idx]

    def _raw_years_for(sign):
        """Raw years for a single sign at the current duration method."""
        return float(_dhasa_duration(
            planet_positions, sign, dhasa_duration_method=dhasa_duration_method
        ))

    def _raw_years_list(signs):
        return [ _raw_years_for(s) for s in signs ]

    def _children_for(parent_sign):
        """Sub-order for a parent is rotation of the same 12-sign cycle, starting at the parent."""
        return _rotate(progression_order, parent_sign)

    def _emit_row(chain_signs, start_jd, dur_years):
        # Convert JD → (y,m,d,float_hours)
        y, m, d, fh = utils.jd_to_gregorian(start_jd)
        # Round only the returned duration (if enabled)
        dur_out = round(dur_years, ndigits) if ndigits is not None else dur_years
        # Emit canonical shape: ( (L1..Lk), (y,m,d,fh), dur )
        rows.append( (tuple(chain_signs), (int(y), int(m), int(d), float(fh)), float(dur_out)) )

    rows = []

    # ── Recursive builder (for depth ≥ 2) ────────────────────────────────────
    def _recurse(level, parent_sign, parent_start_jd, parent_years, chain_prefix):
        """
        Build level=level periods under parent_sign, starting at parent_start_jd, filling parent_years.
        chain_prefix: tuple of signs from L1..(level-1).
        """
        # 12 children for this parent (rotation of the same cycle)
        child_signs = _children_for(parent_sign)

        # Child years:
        if sublevel_split == "equal":
            child_years_list = [ parent_years / 12.0 ] * 12
        else:
            # proportional to raw durations, scaled to sum to parent_years
            raw = _raw_years_list(child_signs)
            s = sum(raw) or 1.0
            scale = parent_years / s
            child_years_list = [ r * scale for r in raw ]

        # Emit at requested depth or recurse deeper
        jd_cursor = parent_start_jd
        for child_sign, cyrs in zip(child_signs, child_years_list):
            if level < lvl:
                _recurse(
                    level + 1,
                    child_sign,
                    jd_cursor,
                    cyrs,
                    chain_prefix + (child_sign,)
                )
            else:
                _emit_row(chain_prefix + (child_sign,), jd_cursor, cyrs)
            jd_cursor += cyrs * year_days

    # ── 3) L1 loop over the 12 Mahās (seed cycle) ───────────────────────────
    jd_cursor = jd_birth
    for maha_sign in progression_order:
        maha_years = _raw_years_for(maha_sign)

        if lvl == 1:
            _emit_row((maha_sign,), jd_cursor, maha_years)
            jd_cursor += maha_years * year_days
            continue

        _recurse(
            level=2,
            parent_sign=maha_sign,
            parent_start_jd=jd_cursor,
            parent_years=maha_years,
            chain_prefix=(maha_sign,)
        )
        jd_cursor += maha_years * year_days

    return rows
def raashiyanka_immediate_children(
    parent_lords,
    parent_start,                # (Y, M, D, fractional_hour)
    parent_duration=None,        # float years (provide exactly one of: duration OR end)
    parent_end=None,             # (Y, M, D, fractional_hour)
    *,
    jd_at_dob,
    place,
    # engine knobs (same names as your base)
    divisional_chart_factor: int = 1,
    dhasa_progression_method: int = 1,      # 1=BPHS(TC Shastri), 2=BPHS(GD Pathak)
    dhasa_duration_method: int = 1,         # 1=KNR, 2=SR, 3=Reference
    chart_method: int = 1,
    chart_method_for_navamsa: int = 1,
    sublevel_split: str = "equal",          # "equal" | "proportional"
    year_duration: float = const.sidereal_year,
    round_duration: bool = False,           # tiler returns exact spans; no rounding here
    **kwargs
):
    """
    Rāśyāṁśaka — return ONLY the immediate (parent -> children) splits as:
      [ (lords_tuple_{k+1}, start_tuple, end_tuple), ... ]

    Rules:
      • Child order: rotation of the seeded 12-sign progression starting at parent.
      • Child durations:
          - "equal"        -> parent_years / 12
          - "proportional" -> scale raw 12-sign durations to exactly fill the parent
      • Exact tiling on [parent_start, parent_end); zero-span parent -> [].
    """
    # ---- normalize parent path
    if isinstance(parent_lords, int):
        path = (int(parent_lords),)
    elif isinstance(parent_lords, (tuple, list)) and parent_lords:
        path = tuple(int(x) for x in parent_lords)
    else:
        raise ValueError("parent_lords must be int or non-empty tuple/list")
    parent_sign = path[-1]

    # ---- tuple <-> JD
    def _tuple_to_jd(t):
        y, m, d, fh = t
        return utils.julian_day_number(drik.Date(y, m, d), (fh, 0, 0))
    def _jd_to_tuple(jd_val):
        return utils.jd_to_gregorian(jd_val)

    # ---- parent span (use provided year_duration)
    start_jd = _tuple_to_jd(parent_start)
    if (parent_duration is None) == (parent_end is None):
        raise ValueError("Provide exactly one of parent_duration (years) or parent_end (tuple)")
    if parent_end is None:
        parent_years = float(parent_duration)
        end_jd = start_jd + parent_years * year_duration
    else:
        end_jd = _tuple_to_jd(parent_end)
        parent_years = (end_jd - start_jd) / year_duration

    # zero-span parent → no children
    if end_jd <= start_jd:
        return []

    # ---- positions (once), progression order (12 signs from seed), and children (rotation)
    planet_positions = charts.divisional_chart(
        jd_at_dob, place,
        divisional_chart_factor,
        chart_method,**kwargs
    )[:const._pp_count_upto_ketu]

    def _rotate(order, start_sign):
        idx = order.index(start_sign)
        return order[idx:] + order[:idx]

    progression_order = _dhasa_progression(
        planet_positions,
        dhasa_progression_method=dhasa_progression_method,
        chart_method_d9=chart_method_for_navamsa
    )
    child_signs = _rotate(progression_order, parent_sign)

    # ---- child years list (equal/proportional)
    if sublevel_split == "equal":
        child_years_list = [parent_years / 12.0] * 12
    else:
        def _raw_years_for(sign):
            return float(_dhasa_duration(
                planet_positions, sign, dhasa_duration_method=dhasa_duration_method
            ))
        raw = [ _raw_years_for(s) for s in child_signs ]
        total = sum(raw) or 1.0
        scale = parent_years / total
        child_years_list = [ r * scale for r in raw ]

    # ---- tile exactly within [start, end)
    rows, cursor = [], start_jd
    for i, (sgn, yrs) in enumerate(zip(child_signs, child_years_list)):
        child_end = end_jd if i == 11 else cursor + yrs * year_duration
        # skip degenerate zero-length child (robustness)
        if child_end > cursor:
            rows.append((path + (sgn,), _jd_to_tuple(cursor), _jd_to_tuple(child_end)))
        cursor = child_end
        if cursor >= end_jd:
            break

    if rows:
        rows[-1] = (rows[-1][0], rows[-1][1], _jd_to_tuple(end_jd))
    return rows
def get_running_dhasa_for_given_date(
    current_jd,
    jd_at_dob,
    place,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA,      # 1..6
    *,
    divisional_chart_factor: int = 1,
    dhasa_progression_method: int = 1,
    dhasa_duration_method: int = 1,
    chart_method: int = 1,
    chart_method_for_navamsa: int = 1,
    sublevel_split: str = "equal",
    year_duration: float = const.sidereal_year,
    round_duration: bool = False,
    **kwargs
):
    """
    Rāśyāṁśaka — running ladder at `current_jd`:
      [
        [(L1,),                  start1, end1],
        [(L1,L2),                start2, end2],
        ...
        [(L1,..,L_d),            startd, endd]
      ]

    Zero-duration safe:
      • Mahā ladder is taken from the base @ L1 and 0-year Mahās are SKIPPED
        when building selector periods (strictly increasing starts + sentinel).
    """
    # ---- depth normalization
    def _norm(x):
        try: d = int(x)
        except Exception: d = int(const.MAHA_DHASA_DEPTH.DEHA)
        lo = int(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY)
        hi = int(const.MAHA_DHASA_DEPTH.DEHA)
        return min(hi, max(lo, d))
    target = _norm(dhasa_level_index)

    # ---- tuple <-> JD
    def _tuple_to_jd(t):
        y, m, d, fh = t
        return utils.julian_day_number(drik.Date(y, m, d), (fh, 0, 0))
    def _jd_to_tuple(jd_val):
        return utils.jd_to_gregorian(jd_val)

    # ---- zero-length tests & converters
    def _is_zero_by_start_dur(start_tuple, dur_years, eps_seconds=1e-3):
        if dur_years <= 0.0:
            return True
        return (dur_years * year_duration * 86400.0) <= eps_seconds

    def _to_selector_periods_zero_safe(children_rows, parent_end_tuple, eps_seconds=1.0):
        """
        children_rows: [ (lords_tuple, start_tuple, end_tuple), ... ]
        -> strictly increasing [(lords, start), ..., sentinel(parent_end)]
        """
        if not children_rows:
            return []
        rows = []
        for lt, st, en in children_rows:
            if (_tuple_to_jd(en) - _tuple_to_jd(st)) * 86400.0 > eps_seconds:
                rows.append((lt, st))
        if not rows:
            return []
        rows.sort(key=lambda r: _tuple_to_jd(r[1]))
        proj, prev = [], None
        for lt, st in rows:
            sj = _tuple_to_jd(st)
            if prev is None or sj > prev:
                proj.append((lt, st)); prev = sj
        proj.append((proj[-1][0], parent_end_tuple))
        return proj

    # ---- L1 Mahā via base (unrounded)
    y0, m0, d0, fh0 = utils.jd_to_gregorian(jd_at_dob)
    dob = drik.Date(y0, m0, d0); tob = (fh0, 0, 0)

    base_rows = get_dhasa_bhukthi(
        dob, tob, place,
        divisional_chart_factor=divisional_chart_factor,
        dhasa_level_index=const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY,
        dhasa_progression_method=dhasa_progression_method,
        dhasa_duration_method=dhasa_duration_method,
        chart_method=chart_method,
        chart_method_for_navamsa=chart_method_for_navamsa,
        sublevel_split=sublevel_split,
        round_duration=False,**kwargs
    ) or []

    # Build (lords, start) + sentinel for selector — SKIP zero-year Mahās
    periods = []
    jd_cursor = jd_at_dob
    for row in base_rows:
        # Accept canonical: (lords_tuple, start_tuple, dur)
        if (isinstance(row, (list, tuple)) and len(row) == 3
            and isinstance(row[0], (list, tuple)) and isinstance(row[1], (list, tuple))):
            lords_tuple, start_tuple, dur = row[0], row[1], float(row[2])
        else:
            # Backward-compat: Rāśiyanka style [start, L1, ..., Lk, dur]
            start_tuple = row[0]
            dur = float(row[-1])
            lords_tuple = tuple(int(x) for x in row[1:-1])

        if _is_zero_by_start_dur(start_tuple, dur):
            continue
        # Only L1 matters at this level:
        L1 = int(lords_tuple[0]) if isinstance(lords_tuple, (list, tuple)) else int(lords_tuple)
        periods.append(((L1,), start_tuple))
        jd_cursor = _tuple_to_jd(start_tuple) + dur * year_duration

    if not periods:
        sentinel = _jd_to_tuple(jd_at_dob)
        return [[(), sentinel, sentinel]]

    periods.append((periods[-1][0], _jd_to_tuple(jd_cursor)))  # sentinel end

    # ---- Running Mahā
    rd1 = utils.get_running_dhasa_for_given_date(current_jd, periods)
    running = [tuple(rd1[0]), rd1[1], rd1[2]]
    ladder  = [running]

    if target == int(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY):
        return ladder

    # ---- Step-down using immediate children (exact tiling; zero-safe)
    for depth in range(2, target + 1):
        parent_lords, parent_start, parent_end = running

        kids = raashiyanka_immediate_children(
            parent_lords=parent_lords,
            parent_start=parent_start,
            parent_end=parent_end,
            jd_at_dob=jd_at_dob,
            place=place,
            divisional_chart_factor=divisional_chart_factor,
            dhasa_progression_method=dhasa_progression_method,
            dhasa_duration_method=dhasa_duration_method,
            chart_method=chart_method,
            chart_method_for_navamsa=chart_method_for_navamsa,
            sublevel_split=sublevel_split,
            year_duration=year_duration,
            round_duration=False,**kwargs
        )
        if not kids:
            ladder.append((parent_lords + (parent_lords[-1],), parent_end, parent_end))
            break

        child_periods = _to_selector_periods_zero_safe(kids, parent_end_tuple=parent_end)
        if not child_periods:
            ladder.append((parent_lords + (parent_lords[-1],), parent_end, parent_end))
            break

        rdk = utils.get_running_dhasa_for_given_date(current_jd, child_periods)
        running = [tuple(rdk[0]), rdk[1], rdk[2]]
        ladder.append(running)

    return ladder

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
    _dhasa_cycle_count = 1
    import time
    start_time = time.time()
    DLI = const.MAHA_DHASA_DEPTH.DEHA
    print("Maha        :", get_running_dhasa_for_given_date(current_jd, jd_at_dob, place,
                                                            dhasa_level_index=DLI))
    print('new method elapsed time',time.time()-start_time)
    start_time = time.time()
    ad = get_dhasa_bhukthi(dob,tob, place,dhasa_level_index=DLI)
    print(utils.get_running_dhasa_at_all_levels_for_given_date(current_jd, ad,DLI,
                                                               extract_running_period_for_all_levels=True,
                                                               dhasa_cycle_count=_dhasa_cycle_count))
    print('old method elapsed time',time.time()-start_time)
    exit()
    utils.set_language('en')
    dob = drik.Date(1996,12,7); tob = (10,34,0); place = drik.Place('Chennai,India',13.03862,80.261818,5.5)
    rd = get_dhasa_bhukthi(dob, tob, place,dhasa_level_index=2)
    for row in rd:
        print(row)
    