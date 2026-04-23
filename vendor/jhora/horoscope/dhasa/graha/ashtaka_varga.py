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
from jhora.panchanga import drik
from jhora.horoscope.chart import charts, ashtakavarga

# -----------------------------------------------------------------------------
# Ashtakavarga-based Dasha (documented variants only)
# Methods:
#   - BAV_PLANET  → Graha Dasha; Sun..Saturn carriers; weights = BAV totals
#   - SAV_SIGN    → Rasi Dasha; 12-sign carriers; weights = SAV per sign (SAV sum = 337)
#   - PINDA_PLANET→ Graha Dasha; Sun..Saturn carriers; weights = Sodhya Pinda per planet
# Ref: https://astrosutras.in/index.php/2025/03/04/ashtakavarga-dasha-system/. 
# Ref: https://astronidan.com/dashas/ashtakavarga-dasha
# -----------------------------------------------------------------------------

def validate_av_dasha_options(
    dhasa_method: str,
    start_rule: str,
    sequence_rule: str,
    user_defined_first: int | None = None
) -> None:
    """
    Enforces the dhasa_method/start/sequence compatibility matrix and checks user_defined_first.
    Raises ValueError with a clear message if invalid.
    """

    # 1) Method membership
    if dhasa_method not in (const.ASHTAKAVARGA_DHASA_METHOD.BAV_PLANET,
                      const.ASHTAKAVARGA_DHASA_METHOD.SAV_SIGN,
                      const.ASHTAKAVARGA_DHASA_METHOD.PINDA_PLANET):
        raise ValueError(f"Unsupported dhasa_method: {dhasa_method}")

    # 2) Start-rule compatibility
    allowed_starts = const.ASHTAKAVARGA_DHASA_ALLOWED_START_RULES[dhasa_method]
    if start_rule not in allowed_starts:
        raise ValueError(
            f"Invalid start_rule={start_rule} for dhasa_method={dhasa_method}. "
            f"Allowed: {sorted(allowed_starts)}"
        )

    # 3) Sequence-rule compatibility
    allowed_sequences = const.ASHTAKAVARGA_DHASA_ALLOWED_SEQUENCE_RULES[dhasa_method]
    if sequence_rule not in allowed_sequences:
        raise ValueError(
            f"Invalid sequence_rule={sequence_rule} for dhasa_method={dhasa_method}. "
            f"Allowed: {sorted(allowed_sequences)}"
        )

    # 4) User-defined starts
    if start_rule == const.ASHTAKAVARGA_DHASA_START_RULE.USER_DEFINED_PLANET:
        if dhasa_method not in (const.ASHTAKAVARGA_DHASA_METHOD.BAV_PLANET, const.ASHTAKAVARGA_DHASA_METHOD.PINDA_PLANET):
            raise ValueError("USER_DEFINED_PLANET is valid only for graha methods.")
        if user_defined_first is None or user_defined_first not in const.SUN_TO_SATURN:
            raise ValueError("USER_DEFINED_PLANET requires user_defined_first in const.SUN_TO_SATURN (0..6).")

    if start_rule == const.ASHTAKAVARGA_DHASA_START_RULE.USER_DEFINED_SIGN:
        if dhasa_method != const.ASHTAKAVARGA_DHASA_METHOD.SAV_SIGN:
            raise ValueError("USER_DEFINED_SIGN is valid only for SAV_SIGN.")
        if user_defined_first is None or user_defined_first not in range(12):
            raise ValueError("USER_DEFINED_SIGN requires user_defined_first in 0..11 (Ar..Pi).")

    # 5) Method-specific starts (explicit)
    if (start_rule in (const.ASHTAKAVARGA_DHASA_START_RULE.LAGNA_SIGN, const.ASHTAKAVARGA_DHASA_START_RULE.JANMA_RASI) 
                    and dhasa_method != const.ASHTAKAVARGA_DHASA_METHOD.SAV_SIGN):
        raise ValueError(f"{start_rule} is only valid with SAV_SIGN.")

    # 6) Method-specific sequences (explicit)
    if sequence_rule == const.ASHTAKAVARGA_DHASA_SEQUENCE_RULE.FIXED_SUN_SATURN and dhasa_method == const.ASHTAKAVARGA_DHASA_METHOD.SAV_SIGN:
        raise ValueError("FIXED_SUN_SATURN is only valid for graha (planet) methods.")

    if sequence_rule == const.ASHTAKAVARGA_DHASA_SEQUENCE_RULE.ZODIACAL_ORDER and dhasa_method != const.ASHTAKAVARGA_DHASA_METHOD.SAV_SIGN:
        raise ValueError("ZODIACAL is only valid for SAV_SIGN dhasa_method.")
    
def get_ashtaka_varga_dhasa_bhukthi(
    dob, tob, place,
    *,
    divisional_chart_factor: int = 1,
    chart_method: int = 1,

    dhasa_method: str = const.ASHTAKAVARGA_DHASA_METHOD.BAV_PLANET,
    dhasa_level_index: int = const.MAHA_DHASA_DEPTH.ANTARA,

    start_rule: str = const.ASHTAKAVARGA_DHASA_START_RULE.MAX_STRENGTH,
    sequence_rule: str = const.ASHTAKAVARGA_DHASA_SEQUENCE_RULE.STRENGTH_ORDER,
    user_defined_first: int | None = None,
    round_duration: bool = True,
    rounding_mode: str = "decimals",
    year_length_days: float = const.sidereal_year,
):
    """
    Returns a flat list of rows:
        [
          [ (lords_tuple), (year, month, day, fractional_hours), duration_years ],
          ...
        ]

    lords_tuple length = dhasa_level_index:
        level=1 → (M,)
        level=2 → (M, A)
        level=3 → (M, A, P)
        ...

    Encoding:
        - Graha carriers (planet methods): 0..6 = Sun..Saturn
        - Rasi carriers (sign dhasa_method):     0..11 = Aries..Pisces
        - 'L' denotes Lagna only in the internal house_to_planet_chart strings
    """
    # Enforce the matrix up front
    validate_av_dasha_options(dhasa_method, start_rule, sequence_rule, user_defined_first)

    # 1) Build birth JD and varga chart
    jd_birth = utils.julian_day_number(dob, tob)
    pp = charts.divisional_chart(
        jd_birth,
        place,
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method
    )[:const._pp_count_upto_ketu]

    # House→planet list and planet→sign dictionary helpers
    house_to_planet_list = utils.get_house_planet_list_from_planet_positions(pp)
    planet_to_sign = utils.get_planet_to_house_dict_from_chart(house_to_planet_list)
    # planet_to_sign example: {'L': 11, 0:0, 1:1, ...}  (no strings for planets, 'L' for Lagna)

    # 2) Compute AV tables
    # get_ashtaka_varga returns: bav, sav, pav; where bav indices 0..7 (7 = Lagna)
    bav, sav, pav = ashtakavarga.get_ashtaka_varga(house_to_planet_list)

    # 3) Prepare house_to_planet_chart (12 strings Ar→Pi in "p1/p2/.../L")
    house_bins = {s: [] for s in range(12)}
    for p, s in planet_to_sign.items():
        # Accept classic 0..6 planets and also 7.. for Rahu/Ketu/Outers if present; include 'L'
        if s is None or not (0 <= int(s) < 12):
            continue
        # Keep keys as ints 0..?? or 'L'
        if isinstance(p, int) or p == 'L':
            house_bins[s].append(p)
    house_to_planet_chart = []
    for s in range(12):
        # sort numerically for stability, but keep 'L' at end if present
        ints = sorted([x for x in house_bins[s] if isinstance(x, int)])
        lag = [x for x in house_bins[s] if x == 'L']
        tokens = [str(x) for x in ints] + lag  # 'L' last for readability
        house_to_planet_chart.append("/".join(tokens))

    # 4) Build carriers and weight vector by dhasa_method
    if dhasa_method == const.ASHTAKAVARGA_DHASA_METHOD.BAV_PLANET:
        carriers = list(range(7))  # Sun..Saturn only
        weights = {p: float(sum(bav[p])) for p in carriers}  # sum across 12 signs
    elif dhasa_method == const.ASHTAKAVARGA_DHASA_METHOD.SAV_SIGN:
        carriers = list(range(12))  # Aries..Pisces
        # Ensure sav is a 12-length vector
        sign_weights = [float(sav[i]) for i in range(12)]
        weights = {i: sign_weights[i] for i in carriers}
    elif dhasa_method == const.ASHTAKAVARGA_DHASA_METHOD.PINDA_PLANET:
        carriers = list(const.SUN_TO_SATURN)  # Sun..Saturn only
        _rp, _gp, sodhya_pindas = ashtakavarga.sodhaya_pindas(bav, house_to_planet_chart)
        weights = {p: float(sodhya_pindas[p]) for p in carriers}
    else:
        raise ValueError(f"Unsupported dhasa_method: {dhasa_method}")

    # 5) Sequence rule → base order
    def _base_order(seq_rule: str, method_local: str):
        if seq_rule == const.ASHTAKAVARGA_DHASA_SEQUENCE_RULE.STRENGTH_ORDER:
            return sorted(carriers, key=lambda c: (weights.get(c, 0.0), -c), reverse=True)
        if seq_rule == const.ASHTAKAVARGA_DHASA_SEQUENCE_RULE.ZODIACAL_ORDER:
            # Signs 0..11 or planets 0..6
            return sorted(carriers)
        if seq_rule == const.ASHTAKAVARGA_DHASA_SEQUENCE_RULE.FIXED_SUN_SATURN:
            if method_local not in (const.ASHTAKAVARGA_DHASA_METHOD.BAV_PLANET, const.ASHTAKAVARGA_DHASA_METHOD.PINDA_PLANET):
                raise ValueError("FIXED_SUN_SATURN sequence is valid only for planet methods.")
            return [0,1,2,3,4,5,6]
        raise ValueError(f"Unsupported sequence_rule: {seq_rule}")

    order = _base_order(sequence_rule, dhasa_method)

    # 6) Start rule → rotate order accordingly
    def _choose_start(s_rule: str):
        # For "MAX_STRENGTH" pick item with max weight; ties broken deterministically.
        if s_rule == const.ASHTAKAVARGA_DHASA_START_RULE.MAX_STRENGTH:
            return max(order, key=lambda c: (weights.get(c, 0.0), -c))
        if s_rule == const.ASHTAKAVARGA_DHASA_START_RULE.LAGNA_SIGN:
            if dhasa_method != const.ASHTAKAVARGA_DHASA_METHOD.SAV_SIGN:
                raise ValueError("LAGNA_SIGN start is valid only for SAV_SIGN (rasi) dhasa_method.")
            lag_sign = planet_to_sign.get('L', None)
            return lag_sign if (lag_sign in order) else order[0]
        if s_rule == const.ASHTAKAVARGA_DHASA_START_RULE.JANMA_RASI:
            if dhasa_method != const.ASHTAKAVARGA_DHASA_METHOD.SAV_SIGN:
                raise ValueError("JANMA_RASI start is valid only for SAV_SIGN (rasi) dhasa_method.")
            moon_sign = planet_to_sign.get(1, None)  # 1 = Moon
            return moon_sign if (moon_sign in order) else order[0]
        if s_rule == const.ASHTAKAVARGA_DHASA_START_RULE.USER_DEFINED_SIGN:
            if dhasa_method != const.ASHTAKAVARGA_DHASA_METHOD.SAV_SIGN:
                raise ValueError("USER_DEFINED_SIGN start is valid only for SAV_SIGN.")
            if user_defined_first in order:
                return user_defined_first
            return order[0]
        if s_rule == const.ASHTAKAVARGA_DHASA_START_RULE.USER_DEFINED_PLANET:
            if dhasa_method not in (const.ASHTAKAVARGA_DHASA_METHOD.BAV_PLANET, const.ASHTAKAVARGA_DHASA_METHOD.PINDA_PLANET):
                raise ValueError("USER_DEFINED_PLANET start is valid only for graha methods.")
            if user_defined_first in order:
                return user_defined_first
            return order[0]
        raise ValueError(f"Unsupported start_rule: {s_rule}")

    # For generality, if user picked a start rule incompatible with dhasa_method, raise earlier
    start_item = _choose_start(start_rule)
    if start_item in order:
        idx = order.index(start_item)
        order = order[idx:] + order[:idx]

    # 7) Duration splitter (proportional), with sum conservation
    def _split_durations(parent_duration: float, order_local: list[int]) -> list[float]:
        total_w = sum(max(weights.get(c, 0.0), 0.0) for c in order_local)
        if total_w <= 0:
            # If all zero (pathological), divide equally to maintain continuity
            n = len(order_local)
            raw = [parent_duration / n for _ in range(n)]
        else:
            raw = [(max(weights.get(c, 0.0), 0.0) / total_w) * parent_duration for c in order_local]
        # Sum conservation: absorb tiny float drift in the last item
        drift = parent_duration - sum(raw)
        if raw:
            raw[-1] += drift
        return raw

    # 8) Recursion
    results = []
    jd_tracker = jd_birth
    lifespan_years = float(const.human_life_span_for_vimsottari_dhasa)

    def _round_for_output(val: float) -> float:
        if not round_duration:
            return val
        if rounding_mode == "decimals":
            return round(val, dhasa_level_index)
        return val  # "none"

    def _recurse(depth: int, parent_duration: float, lords_stack: tuple[int, ...]):
        nonlocal jd_tracker
        # Split the parent duration among the carriers using the precomputed order
        child_durs = _split_durations(parent_duration, order)
        for c, dur in zip(order, child_durs):
            if dur <= 0:
                continue
            next_stack = lords_stack + (c,)
            if depth == dhasa_level_index:
                # Emit a terminal row
                y, m, d, fh = utils.jd_to_gregorian(jd_tracker)
                results.append([next_stack, (y, m, d, fh), _round_for_output(dur)])
                # Advance the JD by the *unrounded* duration to keep time continuity
                jd_tracker += (dur * year_length_days)
            else:
                _recurse(depth + 1, dur, next_stack)

    _recurse(1, lifespan_years, tuple())
    return results
def ashtakavarga_immediate_children(
    parent_lords,
    parent_start,                # (Y, M, D, fractional_hour)
    parent_duration=None,        # float years (optional)
    parent_end=None,             # (Y, M, D, fractional_hour) (optional)
    *,
    dob, tob, place,
    divisional_chart_factor: int = 1,
    chart_method: int = 1,

    dhasa_method: str = const.ASHTAKAVARGA_DHASA_METHOD.BAV_PLANET,
    start_rule: str = const.ASHTAKAVARGA_DHASA_START_RULE.MAX_STRENGTH,
    sequence_rule: str = const.ASHTAKAVARGA_DHASA_SEQUENCE_RULE.STRENGTH_ORDER,
    user_defined_first: int | None = None,

    year_length_days: float = const.sidereal_year,
):
    """
    Returns ONLY the immediate (p->p+1) Aṣṭakavarga children under a given parent span.

    Output rows:
        [ (lords_tuple_with_child), child_start_tuple, child_end_tuple ]

    Notes
    -----
    - Child order is computed ONCE from the birth AV (carriers + weights) with
      the given dhasa_method & rules (no per-parent rotation), matching your
      get_ashtaka_varga_dhasa_bhukthi().
    - Child durations are proportional to weights; equal-split fallback if all weights=0.
    - Time math uses `year_length_days` for years→days conversion.
    - The last child end is forced to `parent_end` for perfect tiling.
    """

    # --- normalize lords path
    if isinstance(parent_lords, int):
        path = (parent_lords,)
    elif isinstance(parent_lords, (list, tuple)):
        if len(parent_lords) == 0:
            raise ValueError("parent_lords cannot be empty")
        path = tuple(parent_lords)
    else:
        raise TypeError("parent_lords must be int or tuple/list of ints")

    # --- tuple <-> JD helpers (canonical)
    def _tuple_to_jd(t):
        y, m, d, fh = t
        return utils.julian_day_number(drik.Date(y, m, d), (fh, 0, 0))

    def _jd_to_tuple(jd_val):
        return utils.jd_to_gregorian(jd_val)

    # --- parent start/end in JD
    start_jd = _tuple_to_jd(parent_start)
    if (parent_duration is None) == (parent_end is None):
        raise ValueError("Provide exactly one of parent_duration (years) or parent_end (tuple)")

    if parent_end is None:
        parent_years = float(parent_duration)
        end_jd = start_jd + parent_years * year_length_days
    else:
        end_jd = _tuple_to_jd(parent_end)
        parent_years = (end_jd - start_jd) / year_length_days

    if end_jd <= start_jd:
        return []

    # --- reuse your option validation if available
    # validate_av_dasha_options(dhasa_method, start_rule, sequence_rule, user_defined_first)

    # 1) Build birth JD & planetary positions
    jd_birth = utils.julian_day_number(dob, tob)
    pp = charts.divisional_chart(
        jd_birth,
        place,
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method
    )[:const._pp_count_upto_ketu]

    # house→planet list and planet→sign dict
    house_to_planet_list = utils.get_house_planet_list_from_planet_positions(pp)
    planet_to_sign = utils.get_planet_to_house_dict_from_chart(house_to_planet_list)

    # 2) Compute AV tables
    bav, sav, pav = ashtakavarga.get_ashtaka_varga(house_to_planet_list)

    # Build carriers & weights per dhasa_method
    if dhasa_method == const.ASHTAKAVARGA_DHASA_METHOD.BAV_PLANET:
        carriers = list(range(7))  # Sun..Saturn
        weights = {p: float(sum(bav[p])) for p in carriers}
    elif dhasa_method == const.ASHTAKAVARGA_DHASA_METHOD.SAV_SIGN:
        carriers = list(range(12))  # Aries..Pisces
        weights = {i: float(sav[i]) for i in range(12)}
    elif dhasa_method == const.ASHTAKAVARGA_DHASA_METHOD.PINDA_PLANET:
        carriers = list(const.SUN_TO_SATURN)
        _rp, _gp, sodhya_pindas = ashtakavarga.sodhaya_pindas(bav,house_to_planet_list)# _house_to_planet_chart_from_pp(planet_to_sign))
        weights = {p: float(sodhya_pindas[p]) for p in carriers}
    else:
        raise ValueError(f"Unsupported dhasa_method: {dhasa_method}")

    # sequence rule → base order
    def _base_order(seq_rule: str):
        if seq_rule == const.ASHTAKAVARGA_DHASA_SEQUENCE_RULE.STRENGTH_ORDER:
            return sorted(carriers, key=lambda c: (weights.get(c, 0.0), -c), reverse=True)
        if seq_rule == const.ASHTAKAVARGA_DHASA_SEQUENCE_RULE.ZODIACAL_ORDER:
            return sorted(carriers)
        if seq_rule == const.ASHTAKAVARGA_DHASA_SEQUENCE_RULE.FIXED_SUN_SATURN:
            if dhasa_method not in (const.ASHTAKAVARGA_DHASA_METHOD.BAV_PLANET, const.ASHTAKAVARGA_DHASA_METHOD.PINDA_PLANET):
                raise ValueError("FIXED_SUN_SATURN valid only for planet methods.")
            return [0, 1, 2, 3, 4, 5, 6]
        raise ValueError(f"Unsupported sequence_rule: {seq_rule}")

    order = _base_order(sequence_rule)

    # start rule → rotate order
    def _choose_start(s_rule: str):
        if s_rule == const.ASHTAKAVARGA_DHASA_START_RULE.MAX_STRENGTH:
            return max(order, key=lambda c: (weights.get(c, 0.0), -c))
        if s_rule == const.ASHTAKAVARGA_DHASA_START_RULE.LAGNA_SIGN:
            if dhasa_method != const.ASHTAKAVARGA_DHASA_METHOD.SAV_SIGN:
                raise ValueError("LAGNA_SIGN start is valid only for SAV_SIGN.")
            lag_sign = planet_to_sign.get('L', None)
            return lag_sign if (lag_sign in order) else order[0]
        if s_rule == const.ASHTAKAVARGA_DHASA_START_RULE.JANMA_RASI:
            if dhasa_method != const.ASHTAKAVARGA_DHASA_METHOD.SAV_SIGN:
                raise ValueError("JANMA_RASI start is valid only for SAV_SIGN.")
            moon_sign = planet_to_sign.get(1, None)
            return moon_sign if (moon_sign in order) else order[0]
        if s_rule == const.ASHTAKAVARGA_DHASA_START_RULE.USER_DEFINED_SIGN:
            if dhasa_method != const.ASHTAKAVARGA_DHASA_METHOD.SAV_SIGN:
                raise ValueError("USER_DEFINED_SIGN start is valid only for SAV_SIGN.")
            return user_defined_first if (user_defined_first in order) else order[0]
        if s_rule == const.ASHTAKAVARGA_DHASA_START_RULE.USER_DEFINED_PLANET:
            if dhasa_method not in (const.ASHTAKAVARGA_DHASA_METHOD.BAV_PLANET, const.ASHTAKAVARGA_DHASA_METHOD.PINDA_PLANET):
                raise ValueError("USER_DEFINED_PLANET start is valid only for graha methods.")
            return user_defined_first if (user_defined_first in order) else order[0]
        raise ValueError(f"Unsupported start_rule: {s_rule}")

    start_item = _choose_start(start_rule)
    if start_item in order:
        idx = order.index(start_item)
        order = order[idx:] + order[:idx]

    # duration splitter (proportional) with equal-split fallback + sum closure
    def _split_durations(parent_duration: float, order_local: list[int]) -> list[float]:
        total_w = sum(max(weights.get(c, 0.0), 0.0) for c in order_local)
        if total_w <= 0:
            n = len(order_local)
            raw = [parent_duration / n for _ in range(n)]
        else:
            raw = [(max(weights.get(c, 0.0), 0.0) / total_w) * parent_duration for c in order_local]
        drift = parent_duration - sum(raw)
        if raw:
            raw[-1] += drift
        return raw

    # Tile children inside the parent
    children = []
    jd_cursor = start_jd
    child_years_list = _split_durations(parent_years, order)
    for idx, (c, dur_y) in enumerate(zip(order, child_years_list)):
        # for last child, clamp end to parent_end
        if idx == len(order) - 1:
            child_end_jd = end_jd
        else:
            child_end_jd = jd_cursor + dur_y * year_length_days

        children.append([
            path + (c,),
            _jd_to_tuple(jd_cursor),
            _jd_to_tuple(child_end_jd),
        ])
        jd_cursor = child_end_jd
        if jd_cursor >= end_jd:
            break

    if children:
        children[-1][2] = _jd_to_tuple(end_jd)

    return children


def _house_to_planet_chart_from_pp(planet_to_sign: dict) -> list[str]:
    """
    Helper for Pinda method: builds house_to_planet_chart (12 strings "p1/p2/.../L").
    """
    house_bins = {s: [] for s in range(12)}
    for p, s in planet_to_sign.items():
        if s is None or not (0 <= int(s) < 12):
            continue
        if isinstance(p, int) or p == 'L':
            house_bins[int(s)].append(p)

    chart = []
    for s in range(12):
        ints = sorted([x for x in house_bins[s] if isinstance(x, int)])
        lag = [x for x in house_bins[s] if x == 'L']
        tokens = [str(x) for x in ints] + lag
        chart.append("/".join(tokens))
    return chart
def get_running_dhasa_for_given_date(
    current_jd,
    jd_at_dob, place,
    dhasa_level_index: int = const.MAHA_DHASA_DEPTH.DEHA,
    *,
    divisional_chart_factor: int = 1,
    chart_method: int = 1,

    dhasa_method: str = const.ASHTAKAVARGA_DHASA_METHOD.BAV_PLANET,
    dhasa_level_for_base: int = 1,  # internal: Mahā list
    start_rule: str = const.ASHTAKAVARGA_DHASA_START_RULE.MAX_STRENGTH,
    sequence_rule: str = const.ASHTAKAVARGA_DHASA_SEQUENCE_RULE.STRENGTH_ORDER,
    user_defined_first: int | None = None,
    year_length_days: float = const.sidereal_year,
):
    """
    Aṣṭakavarga runner: narrows Mahā → … → target depth and returns the full ladder:

        [
          [(l1,),              start1, end1],
          [(l1,l2),            start2, end2],
          ...,
          [(l1,...,lN),        startN, endN],
        ]
    """
    y,m,d,fh = utils.jd_to_gregorian(jd_at_dob); dob=drik.Date(y,m,d); tob=(fh,0,0)
    # --- helpers
    def _as_tuple_lords(x):
        return (x,) if isinstance(x, int) else tuple(x)

    def _tuple_to_jd(t):
        y, m, d, fh = t
        return utils.julian_day_number(drik.Date(y, m, d), (fh, 0, 0))

    def _is_zero_length(s, e, eps_seconds=1.0):
        return (_tuple_to_jd(e) - _tuple_to_jd(s)) * 86400.0 <= eps_seconds

    def _to_utils_periods(children_rows, parent_end_tuple, eps_seconds=1.0):
        """
        children_rows: [ [lords_tuple, start_tuple, end_tuple], ... ]
        Returns: list of (lords_tuple, start_tuple) + sentinel (any_lords, parent_end_tuple),
        filtering zero-length rows and enforcing strictly increasing starts.
        """
        # filter zero-length
        filtered = [r for r in children_rows if not _is_zero_length(r[1], r[2], eps_seconds=eps_seconds)]
        if not filtered:
            return []

        # sort by start
        filtered.sort(key=lambda r: _tuple_to_jd(r[1]))

        proj = []
        prev = None
        for lords, st, _en in filtered:
            sjd = _tuple_to_jd(st)
            if prev is None or sjd > prev:
                proj.append((lords, st))
                prev = sjd
            # else skip duplicates

        # sentinel
        proj.append((proj[-1][0], parent_end_tuple))
        return proj

    # --- clamp depth
    try:
        target_depth = int(dhasa_level_index)
    except Exception:
        target_depth = const.MAHA_DHASA_DEPTH.DEHA
    target_depth = max(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY, min(const.MAHA_DHASA_DEPTH.DEHA, target_depth))

    # --- Level 1: Mahā via your base function (returns full list at requested depth)
    mahā_rows = get_ashtaka_varga_dhasa_bhukthi(
        dob, tob, place,
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method,
        dhasa_method=dhasa_method,
        dhasa_level_index=const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY,
        start_rule=start_rule,
        sequence_rule=sequence_rule,
        user_defined_first=user_defined_first,
        round_duration=False,       # runner operates on start/end, no rounding
        year_length_days=year_length_days,
    )

    # normalize level-1 rows to (lords,start) for utils
    maha_for_utils = []
    for row in mahā_rows:
        lords_any, start_t, *_ = row
        maha_for_utils.append((_as_tuple_lords(lords_any), start_t))

    # Running Mahā
    rd = utils.get_running_dhasa_for_given_date(current_jd, maha_for_utils)
    lords = _as_tuple_lords(rd[0])
    running = [lords, rd[1], rd[2]]
    running_all = [running]

    if target_depth == 1:
        return running_all

    # --- Levels 2..target
    for depth in range(2, target_depth + 1):
        parent_lords, parent_start, parent_end = running

        # Expand only this parent
        children = ashtakavarga_immediate_children(
            parent_lords=parent_lords,
            parent_start=parent_start,
            parent_end=parent_end,
            dob=dob, tob=tob, place=place,
            divisional_chart_factor=divisional_chart_factor,
            chart_method=chart_method,
            dhasa_method=dhasa_method,
            start_rule=start_rule,
            sequence_rule=sequence_rule,
            user_defined_first=user_defined_first,
            year_length_days=year_length_days,
        )
        if not children:
            raise ValueError("No children generated for the Aṣṭakavarga parent period.")

        # prepare (lords,start)+sentinel for utils
        periods_for_utils = _to_utils_periods(children, parent_end_tuple=parent_end)
        if not periods_for_utils:
            # all zeros at this level → treat as instantaneous block
            # fall back: pick the last child & return zero-length block at parent_end
            last = children[-1]
            running = [last[0], last[1], last[1]]
        else:
            rd_k = utils.get_running_dhasa_for_given_date(current_jd, periods_for_utils)
            lords_k = _as_tuple_lords(rd_k[0])
            running = [lords_k, rd_k[1], rd_k[2]]

        running_all.append(running)

    return running_all

# ---------------------------------------------------------------------
# Example usage (kept minimal; feels like your current invocation style)
# ---------------------------------------------------------------------
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
    _method = const.ASHTAKAVARGA_DHASA_METHOD.PINDA_PLANET
    print("Dehā        :", get_running_dhasa_for_given_date(current_jd, jd_at_dob, place,
                                                            dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA,
                                                            dhasa_method=_method))
    print('new method elapsed time',time.time()-start_time)
    start_time = time.time()
    ad = get_ashtaka_varga_dhasa_bhukthi(dob, tob, place,dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA,dhasa_method=_method)
    print(utils.get_running_dhasa_at_all_levels_for_given_date(current_jd, ad,const.MAHA_DHASA_DEPTH.DEHA,
                                                               extract_running_period_for_all_levels=True))
    print('old method elapsed time',time.time()-start_time)
    exit()
