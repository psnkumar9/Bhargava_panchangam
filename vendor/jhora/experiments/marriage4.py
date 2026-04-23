
#!/usr/bin/env python
"""
        STILL  UNDER EXPERIMENTATION - DO NOT USE THIS YET
"""
# -*- coding: UTF-8 -*-
# GNU Affero General Public License v3 or later
# See <http://www.gnu.org/licenses/>.

from datetime import datetime, timedelta
import swisseph as swe

# PyJHora stack
from jhora import const, utils
from jhora.panchanga import drik
from jhora.horoscope.chart import charts, house, arudhas
from jhora.horoscope.dhasa.graha import vimsottari
from jhora.horoscope.dhasa.raasi import kalachakra
from jhora.horoscope.dhasa.annual import patyayini
from jhora.horoscope.transit.tajaka import annual_chart, both_planets_within_their_deeptamsa
from jhora.horoscope.transit.saham import vivaha_saham_from_jd_place

# ---------- Config: strict-first → fallback ----------
_marriage_age_year_range = (20, 32)

STRICT_PVR_MODE_DEFAULT = True
EXPLORATORY_TOP_K = 5

# Strict criteria thresholds (PVR Example-1 friendly)
STRICT_VS_TIER_MIN = 0                 # Venus–Saham proximity at VF start is NOT required here
STRICT_REQUIRE_PATYAYINI = True        # require Patyayini *major* lord match to targets
STRICT_REQUIRE_ITHASALA_OR_JUPITER = True

# Optional: add a booster if *transiting* Venus is within δ of annual Vivaha Saham mid-month
USE_TRANSITING_VENUS_SAHAM_PROXIMITY = False
VENUS_SAHAM_TIER2 = 2.0   # degrees
VENUS_SAHAM_TIER1 = 5.0   # degrees

# --- Debug toggle for PVR verification ---
DEBUG_PVR = True
def _dbg(*args):
    if DEBUG_PVR:
        print(*args)

# ---------- Public wrapper (jd/place) ----------
def predict_marriage_windows_from_jd_place(
    jd, place, start_year=None, end_year=None, divisional_chart_factor=1,
    marriage_age_range=None
):
    marriage_age_range = _marriage_age_year_range if marriage_age_range is None else marriage_age_range
    yb, _, _, _ = utils.jd_to_gregorian(jd)

    allowed_min_year = yb + marriage_age_range[0]
    allowed_max_year = yb + marriage_age_range[1]

    if start_year is None:
        start_year = allowed_min_year
    if end_year is None:
        end_year = allowed_max_year

    iter_start_year = max(start_year, allowed_min_year)
    iter_end_year   = min(end_year, allowed_max_year)
    if iter_start_year > iter_end_year:
        return []

    # Natal D1/D9 primitives
    rasi_pp = charts.divisional_chart(jd, place, divisional_chart_factor=1)
    chart_1d_rasi = utils.get_house_planet_list_from_planet_positions(rasi_pp)
    p_to_h_rasi = utils.get_planet_house_dictionary_from_planet_positions(rasi_pp)

    d9_pp = charts.divisional_chart(jd, place, divisional_chart_factor=9)
    chart_1d_d9 = utils.get_house_planet_list_from_planet_positions(d9_pp)
    p_to_h_d9 = utils.get_planet_house_dictionary_from_planet_positions(d9_pp)

    derived = _collect_marriage_primitives(
        jd, place,
        rasi_pp, chart_1d_rasi, p_to_h_rasi,
        d9_pp, chart_1d_d9, p_to_h_d9
    )

    # Vimshottari segments (MD/AD time ranges)
    _, vdb_info = vimsottari.get_vimsottari_dhasa_bhukthi(jd, place, divisional_chart_factor=divisional_chart_factor)
    segments = _expand_to_md_ad_segments(vdb_info)

    candidates = []

    for year in range(iter_start_year, iter_end_year + 1):
        # Build both VF contexts (current and previous) for this calendar year
        scd_cur  = _sudarsana_chakra_year_info(jd, place, year,   chart_1d_d9)
        scd_prev = _sudarsana_chakra_year_info(jd, place, year-1, chart_1d_d9)

        tajaka_cur  = _get_varshaphala_marriage_triggers(jd, place, year,   derived)
        tajaka_prev = _get_varshaphala_marriage_triggers(jd, place, year-1, derived)

        taj_year_strength_cur,  taj_year_meta_cur  = _year_strength_from_tajaka(tajaka_cur,  derived)
        taj_year_strength_prev, taj_year_meta_prev = _year_strength_from_tajaka(tajaka_prev, derived)

        scd_score_cur  = _score_scd_year_support(scd_cur,  derived)   # weighted (Jup≡SCD: +3, Ven≡SCD: +1)
        scd_score_prev = _score_scd_year_support(scd_prev, derived)

        # Calendar-year Vimshottari slice
        year_start = datetime(year, 1, 1, 0, 0, 0)
        year_end   = datetime(year, 12, 31, 23, 59, 59)
        md_ad_pd_year = _active_vimsottari_in_window(segments, year_start, year_end)
        md_pass = _passes_md_gate(md_ad_pd_year['md'], derived) if md_ad_pd_year else False
        ad_pass = _passes_ad_gate(md_ad_pd_year['ad'], derived) if md_ad_pd_year else False

        # Optional year confirmers (kept as calendar-year)
        kcd_score = _score_kalachakra_support(jd, place, year, derived)
        nd9_score = _score_compressed_d9_narayana(jd, place, year_start, year_end, derived)

        # Year tuples per VF
        year_tuple_cur  = _year_tuple(md_pass, ad_pass, scd_score_cur,  kcd_score, nd9_score, taj_year_strength_cur)
        year_tuple_prev = _year_tuple(md_pass, ad_pass, scd_score_prev, kcd_score, nd9_score, taj_year_strength_prev)

        # Current VF debug (convenience)
        _dbg(f"[PVR-CHK][YEAR] y={year} SCD(D9)={scd_cur.get('scd_rasi_d9')} "
             f"annD9 Jup={scd_cur.get('vf_jupiter_sign_d9')} Ven={scd_cur.get('vf_venus_sign_d9')} | "
             f"D1 VS(sign)={tajaka_cur.get('vivaha_saham_sign')} Muntha_lord={tajaka_cur.get('muntha_lord')}")

        # Month loop (per-month VF selection)
        for month in range(1, 13):
            month_start = datetime(year, month, 1)
            month_end = _end_of_month(year, month)

            # Decide which VF applies to this calendar month
            use_prev = (month_end < tajaka_cur['vf_start'])
            use_tajaka = tajaka_prev if use_prev else tajaka_cur
            use_scd    = scd_prev if use_prev else scd_cur
            use_year_tuple = year_tuple_prev if use_prev else year_tuple_cur
            use_year_meta  = taj_year_meta_prev if use_prev else taj_year_meta_cur
            use_taj_year_strength = taj_year_strength_prev if use_prev else taj_year_strength_cur

            md_ad_pd = _active_vimsottari_in_window(segments, month_start, month_end)
            if not md_ad_pd:
                continue

            jtransit = _get_monthly_jupiter_transit_support(jd, place, year, month, derived)
            tajaka_score, tajaka_detail = _score_tajaka_month(use_tajaka, month_start, month_end, place, derived)
            cultural = _score_cultural_month(month_start, month_end)

            ith_tier = _ithasala_tier_from_detail(tajaka_detail)
            vs_tier  = _venus_saham_tier_from_detail(tajaka_detail)
            paty_hit = bool(tajaka_detail.get('patyayini_hit', False))

            month_tuple_val = _month_tuple(
                paty_hit, vs_tier,
                ithasala_tier=ith_tier, jupiter_transit_score=jtransit, cultural_hit=cultural
            )

            # MAJOR-first: weight + flag
            major_hit    = bool(tajaka_detail.get('patyayini_major_hit', False))
            major_lord   = tajaka_detail.get('patyayini_major_lord', None)
            major_weight = int(tajaka_detail.get('patyayini_major_weight', 0))

            # rank_month = (major_weight, major_hit, paty_hit, vs_tier, ithasala_tier, jupiter, cultural)
            rank_month = (major_weight, int(major_hit)) + month_tuple_val

            reasons = _collect_reasons(md_ad_pd, jtransit, use_scd, tajaka_detail, kcd_score, nd9_score, cultural, derived)
            reasons['decision_trace'] = {
                'year_tuple': use_year_tuple,
                'month_tuple': month_tuple_val,
                'md_gate': md_pass,
                'ad_gate_year': ad_pass,
                'tajaka_year_strength': use_taj_year_strength,
                'year_meta': use_year_meta,
                'patyayini_major_lord': major_lord,
                'patyayini_major_hit': major_hit,
                'patyayini_major_weight': major_weight
            }

            total = (
                (use_year_tuple[0]*1000) + (use_year_tuple[1]*200) + (use_year_tuple[2]*50) + (use_year_tuple[3]*10) +
                (major_weight*10) +
                (month_tuple_val[0]*5) + (month_tuple_val[1]*3) + (month_tuple_val[2]*2) + (month_tuple_val[3]*1) + (month_tuple_val[4]*1)
            )

            candidates.append({
                'year': year,
                'month': month,
                'window': (month_start, month_end),
                'score': total,
                'reasons': reasons,
                '_rank_key': (use_year_tuple, rank_month),
                '_tajaka': use_tajaka
            })

    if not candidates:
        return []

    # Sort: year_tuple + MAJOR-first month rank, then scalar, then tie-breakers
    candidates.sort(key=_strict_sort_key, reverse=True)

    # --- Strict attempt (PVR-style) ---
    
    # --- Strict attempt (scan the pool, not just the first row) ---
    if STRICT_PVR_MODE_DEFAULT:
        strict_hits = []
        for c in candidates:
            yr, mo = c['_rank_key']
            dt = c['reasons']['decision_trace']
            major_hit_first = bool(dt.get('patyayini_major_hit', False))
            if _passes_strict_gate_from_tuple(yr, mo, major_hit_first):
                strict_hits.append(c)
    
        if strict_hits:
            # Pick the best strict hit using the same sort order
            strict_hits.sort(key=_strict_sort_key, reverse=True)
            best = strict_hits[0]
    
            # --- derive a single day as you already do ---
            tajaka = best.get('_tajaka')
            annual_pp = tajaka.get('annual_planet_positions') if tajaka else None
            L7 = tajaka.get('annual_7l') if tajaka else None
            ul_sign = derived['ul_d1']
            ul_lord = house.house_owner_from_planet_positions(annual_pp, ul_sign) if annual_pp is not None else None
            vs_lord = house.house_owner_from_planet_positions(annual_pp, tajaka.get('vivaha_saham_sign')) if tajaka else None
            m_lord  = tajaka.get('muntha_lord') if tajaka else None
    
            targets = [const.VENUS_ID] + [x for x in [L7, ul_lord, vs_lord, m_lord] if x is not None]
            final_day, day_meta = _suggest_day_from_patyayini(tajaka, best['window'][0], best['window'][1], targets)
            best['reasons']['final_day'] = final_day
            best['reasons']['final_day_meta'] = day_meta
            best['reasons']['mode'] = 'strict_single'
    
            best.pop('_rank_key', None); best.pop('_tajaka', None)
            return [best]


    # --- Fallback: exploratory shortlist ---
    top = []
    for c in candidates[:EXPLORATORY_TOP_K]:
        tajaka = c.get('_tajaka')
        annual_pp = tajaka.get('annual_planet_positions') if tajaka else None
        L7 = tajaka.get('annual_7l') if tajaka else None
        ul_sign = derived['ul_d1']
        ul_lord = house.house_owner_from_planet_positions(annual_pp, ul_sign) if annual_pp is not None else None
        vs_lord = house.house_owner_from_planet_positions(annual_pp, tajaka.get('vivaha_saham_sign')) if tajaka else None
        m_lord  = tajaka.get('muntha_lord') if tajaka else None
        targets = [const.VENUS_ID] + [x for x in [L7, ul_lord, vs_lord, m_lord] if x is not None]

        day, day_meta = _suggest_day_from_patyayini(tajaka, c['window'][0], c['window'][1], targets)
        c['reasons']['suggested_day'] = day
        c['reasons']['suggested_day_meta'] = day_meta
        c['reasons']['mode'] = 'fallback_exploratory'
        c.pop('_rank_key', None); c.pop('_tajaka', None)
        top.append(c)
    return top

def _passes_strict_gate_from_tuple(yr, mo, major_hit_first):
    """
    yr = (md, ad, scd, taj)
    mo = (major_weight, major_hit, paty_hit, vs_tier, ithasala_tier, jupiter_transit, cultural)
    """
    md, ad, scd, taj = yr
    major_weight, major_hit, paty_hit, vs_tier, ith, jup, cult = mo

    ok = True
    # YEAR: (MD viable) OR (Independent year confirmer strong enough → SCD Jupiter)
    ok &= bool(md == 1 or scd >= 2)

    # MONTH: require Patyayini MAJOR-lord month
    ok &= major_hit_first if STRICT_REQUIRE_PATYAYINI else True

    # Venus–Saham tier relaxed (PVR Example-1)
    ok &= (vs_tier >= STRICT_VS_TIER_MIN)

    # Require Ithasala or Jupiter month support
    ok &= (ith >= 1 or jup >= 1) if STRICT_REQUIRE_ITHASALA_OR_JUPITER else True
    return ok

def _strict_sort_key(c):
    """
    Sorting priority tuned to PVR funnel:
      1) Year SCD (Jupiter≡SCD stronger than anything else),
      2) MD gate,
      3) Patyayini MAJOR priority (Mars/Saham/Muntha > Venus/7L/UL/VS-lord > others),
      4) Ithasala tier, 5) Jupiter transit, 6) VS tier, then AD and Tajaka year strength,
      7) scalar score as a final tiebreaker.
    Structure expected:
      c['_rank_key'] = (year_tuple, month_rank)
      year_tuple     = (md_pass, ad_pass, scd_score, tajaka_year_strength)
      month_rank     = (major_weight, major_hit, paty_hit, vs_tier, ithasala_tier, jupiter_transit, cultural)
    """
    yr, mo = c['_rank_key']
    md, ad, scd, taj = yr
    major_weight, major_hit, paty_hit, vs_tier, ith, jup, cult = mo
    return (scd, md, major_weight, ith, jup, vs_tier, ad, taj, c['score'])

# ---------- Calculation primitives & adapters ----------
def _collect_marriage_primitives(jd, place, pp_rasi, chart_1d_rasi, p_to_h_rasi, pp_d9, chart_1d_d9, p_to_h_d9):
    out = {}
    by, bm, bd, bh = utils.jd_to_gregorian(jd)
    out['birth_year'] = by

    # D1
    out['lagna_sign_d1'] = p_to_h_rasi[const._ascendant_symbol]
    out['seventh_house_sign_d1'] = (out['lagna_sign_d1'] + const.HOUSE_7) % 12
    out['seventh_lord_d1'] = house.house_owner_from_planet_positions(pp_rasi, out['seventh_house_sign_d1'])

    out['venus_sign_d1'] = p_to_h_rasi[const.VENUS_ID]
    out['seventh_from_venus_sign_d1'] = (out['venus_sign_d1'] + 6) % 12

    ck_list = house.chara_karakas(pp_rasi)
    out['dk'] = ck_list[-1] if isinstance(ck_list, (list, tuple)) else ck_list

    # UL in D1/D9
    al_ul_d1 = arudhas.bhava_arudhas_from_planet_positions(pp_rasi)
    out['ul_d1'] = al_ul_d1[-1]
    al_ul_d9 = arudhas.bhava_arudhas_from_planet_positions(pp_d9)
    out['ul_d9'] = al_ul_d9[-1]

    out['seventh_lord_sign_d1'] = p_to_h_rasi[out['seventh_lord_d1']]
    try:
        out['ul_lord_d1'] = house.house_owner_from_planet_positions(pp_rasi, out['ul_d1'])
    except Exception:
        out['ul_lord_d1'] = None

    ul = out['ul_d1']
    out['ul_supportive_houses_d1'] = {ul, (ul + 2) % 12, (ul + 7) % 12}
    out['ul_terminal_houses_d1'] = {(ul + 1) % 12, (ul + 6) % 12}

    # D9
    out['lagna_sign_d9'] = p_to_h_d9[const._ascendant_symbol]
    out['seventh_house_sign_d9'] = (out['lagna_sign_d9'] + const.HOUSE_7) % 12
    out['seventh_lord_d9'] = house.house_owner_from_planet_positions(pp_d9, out['seventh_house_sign_d9'])

    out['p_to_h_rasi'] = p_to_h_rasi
    out['p_to_h_d9'] = p_to_h_d9

    # Natal night/day (natal context only)
    try:
        out['night_time_birth'] = drik.is_night_birth(jd, place)
    except Exception:
        y, m, d, hours_local = utils.jd_to_gregorian(jd)
        sunrise_hours = drik.sunrise(jd, place)[0]
        sunset_hours  = drik.sunset(jd, place)[0]
        out['night_time_birth'] = not (sunrise_hours <= hours_local <= sunset_hours)

    return out

def _expand_to_md_ad_segments(vdb_info):
    segs = []
    if not vdb_info:
        return segs
    starts = []
    for row in vdb_info:
        md, ad, s = row
        s = s.split()[0].strip()
        y, m, d = map(int, s.split('-'))
        starts.append((md, ad, datetime(y, m, d)))

    for i, (md, ad, start_dt) in enumerate(starts):
        if i < len(starts) - 1:
            end_dt = starts[i+1][2] - timedelta(seconds=1)
        else:
            end_dt = datetime(9999, 12, 31, 23, 59, 59)
        segs.append({'md': md, 'ad': ad, 'pd': None, 'start': start_dt, 'end': end_dt})
    return segs

def _active_vimsottari_in_window(segments, win_start, win_end):
    hits = [s for s in segments if not (s['end'] < win_start or s['start'] > win_end)]
    if not hits:
        return None
    best = max(hits, key=lambda s: (min(s['end'], win_end) - max(s['start'], win_start)).total_seconds())
    return {'md': best['md'], 'ad': best['ad'], 'pd': best.get('pd')}

# ---- Vimshottari gating/scoring ----
def _passes_md_gate(md, derived):
    if md is None:
        return False
    return score_planet_marriage_capability(md, derived, tier='md') >= 3

def _passes_ad_gate(ad, derived):
    if ad is None:
        return False
    return score_planet_marriage_capability(ad, derived, tier='ad') >= 2

def _score_vimsottari_capability(md_ad_pd, derived):
    if not md_ad_pd:
        return 0
    score = 0
    score += score_planet_marriage_capability(md_ad_pd['md'], derived, tier='md')
    score += score_planet_marriage_capability(md_ad_pd['ad'], derived, tier='ad')
    if md_ad_pd.get('pd') is not None:
        score += score_planet_marriage_capability(md_ad_pd['pd'], derived, tier='pd')
    return score

def score_planet_marriage_capability(planet, derived, tier='md'):
    if planet is None:
        return 0
    base_if_7L = {'md': 3, 'ad': 3, 'pd': 2}.get(tier, 2)
    bonus = {'md': 1, 'ad': 1, 'pd': 1}.get(tier, 1)
    p_to_h_rasi = derived['p_to_h_rasi']
    p_to_h_d9 = derived['p_to_h_d9']
    score = 0
    if planet == derived['seventh_lord_d1']:
        score += base_if_7L
    if planet == const.VENUS_ID:
        score += bonus
    if planet == derived['dk']:
        score += bonus
    if p_to_h_rasi.get(planet, -99) == derived['seventh_house_sign_d1']:
        score += bonus
    d9_lagna = derived['lagna_sign_d9']
    d9_good = {d9_lagna, (d9_lagna + 4) % 12, (d9_lagna + 8) % 12, derived['seventh_house_sign_d9']}
    if p_to_h_d9.get(planet, -99) in d9_good:
        score += bonus
    s7v = derived.get('seventh_from_venus_sign_d1')
    if s7v is not None and p_to_h_rasi.get(planet, -99) == s7v:
        score += bonus
    ul_sign = derived.get('ul_d1')
    if ul_sign is not None and p_to_h_rasi.get(planet, -99) == ul_sign:
        score += bonus
    if planet == derived.get('ul_lord_d1'):
        score += bonus
    if p_to_h_rasi.get(planet, -99) in derived.get('ul_supportive_houses_d1', set()):
        score += 1
    return score

# ---- Monthly Jupiter transit ----
def _get_monthly_jupiter_transit_support(jd, place, year, month, derived):
    start = datetime(year, month, 1, 12, 0, 0)
    end = _end_of_month(year, month)
    mid = start + (end - start) / 2
    jd_mid_local = swe.julday(mid.year, mid.month, mid.day, mid.hour + mid.minute/60.0 + mid.second/3600.0)
    jd_utc = jd_mid_local - (place.timezone / 24.0)
    jup_lon_abs = drik.sidereal_longitude(jd_utc, const._JUPITER)
    jup_sign, _ = drik.dasavarga_from_long(jup_lon_abs)
    lagna = derived['lagna_sign_d1']
    h7    = derived['seventh_house_sign_d1']
    l7sg  = derived['seventh_lord_sign_d1']
    ulsg  = derived['ul_d1']
    s7v   = derived.get('seventh_from_venus_sign_d1')
    score = 0
    good = {lagna, (lagna+4) % 12, (lagna+6) % 12, (lagna+8) % 12}
    if jup_sign in good: score += 1
    jup_aspects = {(jup_sign + 4) % 12, (jup_sign + 6) % 12, (jup_sign + 8) % 12}
    if h7 in jup_aspects: score += 1
    s7v_hit = (s7v is not None) and (s7v in jup_aspects or jup_sign == s7v)
    if (l7sg in jup_aspects) or (ulsg in jup_aspects) or (jup_sign == ulsg) or s7v_hit:
        score += 1
    return score

# ---- SCD (D9) year info ----
def _sudarsana_chakra_year_info(jd, place, year, chart_1d_d9):
    by, bm, bd, bh = utils.jd_to_gregorian(jd)
    years_from_dob = (year - by)
    running_year   = years_from_dob + 1
    house_offset   = years_from_dob % 12
    lagna_sign_d9 = 0
    for sgn, token in enumerate(chart_1d_d9):
        if token and 'L' in token.split('/'):
            lagna_sign_d9 = sgn
            break
    scd_rasi_d9 = (lagna_sign_d9 + house_offset) % 12
    annual_pp_d9, (vf_y_m_d, vf_hours_local) = annual_chart(
        jd_at_dob=jd, place=place, divisional_chart_factor=9, years=running_year
    )
    vf_hours = _safe_extract_float_hours(vf_hours_local)
    H, M, S = _hours_to_hms(vf_hours)
    vf_start = datetime(vf_y_m_d[0], vf_y_m_d[1], vf_y_m_d[2], H, M, S)
    def _sign_from_pp(pp, pid):
        for pl, (sg, lon) in pp:
            if pl == pid:
                return sg
        return None
    vf_jup_d9 = _sign_from_pp(annual_pp_d9, const.JUPITER_ID)
    vf_ven_d9 = _sign_from_pp(annual_pp_d9, const.VENUS_ID)
    _dbg(
        f"[PVR-CHK][SCD] year={year} running_year={running_year} "
        f"offset={house_offset} natal_D9_Lagna={lagna_sign_d9} SCD(D9)={scd_rasi_d9} | "
        f"annual_D9 Jup={vf_jup_d9} Ven={vf_ven_d9} vf_start={vf_start}"
    )
    return {
        'running_year': running_year,
        'house_offset': house_offset,
        'scd_rasi_d9': scd_rasi_d9,
        'vf_start': vf_start,
        'vf_jupiter_sign_d9': vf_jup_d9,
        'vf_venus_sign_d9': vf_ven_d9
    }

def _score_scd_year_support(scd_info, derived):
    """
    Weighted SCD year confirmers (PVR-style priority):
      +3 if (annual D9) Jupiter == SCD(D9) seed
      +1 if (annual D9) Venus  == SCD(D9) seed
    """
    if not scd_info:
        return 0
    scd_rasi = scd_info.get('scd_rasi_d9')
    if scd_rasi is None:
        return 0
    score = 0
    if scd_info.get('vf_jupiter_sign_d9') == scd_rasi:
        score += 3
    if scd_info.get('vf_venus_sign_d9') == scd_rasi:
        score += 1
    return score

# ---------- Tajaka (Varshaphala) bundle ----------
def _get_varshaphala_marriage_triggers(jd, place, year, derived):
    by, bm, bd, bh = utils.jd_to_gregorian(jd)
    years_from_dob = (year - by)
    running_year   = years_from_dob + 1

    annual_pp_d1, (vf_y_m_d, vf_hours_local) = annual_chart(
        jd_at_dob=jd, place=place, divisional_chart_factor=1, years=running_year
    )
    vf_hours = _safe_extract_float_hours(vf_hours_local)
    H, M, S = _hours_to_hms(vf_hours)
    vf_start = datetime(vf_y_m_d[0], vf_y_m_d[1], vf_y_m_d[2], H, M, S)

    jd_years = drik.next_solar_date(jd, place, years=running_year)

    vs_abs_long = vivaha_saham_from_jd_place(jd_years, place, divisional_chart_factor=1)
    vs_sign, vs_lon_in_sign = drik.dasavarga_from_long(vs_abs_long)

    ven_abs_long = _get_planet_abs_long_from_positions(annual_pp_d1, const.VENUS_ID)
    jup_sign = _get_planet_sign_from_annual(annual_pp_d1, const.JUPITER_ID)
    ven_sign = _get_planet_sign_from_annual(annual_pp_d1, const.VENUS_ID)

    annual_lagna_sign = _find_lagna_sign_from_positions(annual_pp_d1)
    annual_h7_sign = (annual_lagna_sign + const.HOUSE_7) % 12
    annual_ll = house.house_owner_from_planet_positions(annual_pp_d1, annual_lagna_sign)
    annual_7l = house.house_owner_from_planet_positions(annual_pp_d1, annual_h7_sign)

    natal_lagna_sign = derived['lagna_sign_d1']
    muntha_sign = (natal_lagna_sign + years_from_dob) % 12
    muntha_lord = house.house_owner_from_planet_positions(annual_pp_d1, muntha_sign)

    patyayini_raw = patyayini.get_dhasa_bhukthi(jd_years, place, divisional_chart_factor=1, chart_method=1)
    patyayini_schedule = _expand_patyayini_schedule(patyayini_raw)
    patyayini_major_schedule = _expand_patyayini_major_schedule(patyayini_raw)

    _dbg(
        f"[PVR-CHK][TAJAKA] year={year} running_year={running_year} vf_start={vf_start} | "
        f"D1 Jup={jup_sign} Ven={ven_sign} | VS(sign,abs)=({vs_sign},{round(vs_abs_long,3)}) | "
        f"Muntha_sign={muntha_sign} Muntha_lord={muntha_lord} | patyayini_slices={0 if not patyayini_schedule else len(patyayini_schedule)}"
    )
    _dbg(f"[PVR-CHK][PATY-MAJOR] {[(d['lord'], d['start'].date(), d['end'].date()) for d in (patyayini_major_schedule or [])]}")

    return {
        'vf_start': vf_start,
        'years_after_dob': years_from_dob,             # used to compute running year
        'annual_planet_positions': annual_pp_d1,
        'jupiter_sign': jup_sign,
        'venus_sign': ven_sign,
        'annual_lagna_sign': annual_lagna_sign,
        'annual_ll': annual_ll,
        'annual_7l': annual_7l,
        'vivaha_saham_sign': vs_sign,
        'vivaha_saham_abs_long': vs_abs_long,
        'venus_abs_long': ven_abs_long,
        'muntha_sign': muntha_sign,
        'muntha_lord': muntha_lord,
        'patyayini_schedule': patyayini_schedule,
        'patyayini_major_schedule': patyayini_major_schedule,
        'retro_flags': None,
    }

# ---------- Patyayini helpers ----------
def _normalize_paty_lord(pid):
    """
    Normalize Patyayini lord IDs coming from different sources:
    - numpy scalar -> int
    - keep 'L' (Lagna) as string
    - pass through plain ints unchanged
    """
    try:
        import numpy as np
        if isinstance(pid, (np.integer,)):
            return int(pid)
    except Exception:
        pass
    return pid

def _patyayini_month_hit(paty_schedule, month_start, month_end, targets=None):
    """
    True if ANY Patyayini sub-slice overlaps [month_start, month_end].
    If 'targets' is provided (set of lords), restrict to those lords.
    """
    if not paty_schedule:
        return False
    for sl in paty_schedule:
        lord = _normalize_paty_lord(sl.get('lord'))
        s = sl.get('start'); e = sl.get('end')
        if s is None or e is None:
            continue
        if e < month_start or s > month_end:
            continue
        if (targets is None) or (lord in targets):
            return True
    return False

def _patyayini_major_lord_for_month(paty_major, month_start, month_end):
    """
    Return the MAJOR lord whose period has the largest overlap with [month_start, month_end].
    If no major period overlaps, return None.
    """
    if not paty_major:
        return None

    best_lord = None
    best_overlap = -1.0

    for sl in paty_major:
        s = sl.get('start'); e = sl.get('end')
        if s is None or e is None:
            continue
        if e < month_start or s > month_end:
            continue

        lord = _normalize_paty_lord(sl.get('lord'))
        overlap = (min(e, month_end) - max(s, month_start)).total_seconds()
        if overlap > best_overlap:
            best_overlap = overlap
            best_lord = lord

    return best_lord

# ---------- Expand schedules ----------
def _expand_patyayini_schedule(patyayini_raw):
    if not patyayini_raw:
        return None
    first = patyayini_raw[0]
    out = []
    def _parse_dt_str(s):
        try:
            return datetime.fromisoformat(s)
        except Exception:
            try:
                return datetime.strptime(s.strip(), "%Y-%m-%d %H:%M:%S")
            except Exception:
                return datetime.strptime(s.strip().split()[0], "%Y-%m-%d")
    if (
        isinstance(first, (list, tuple))
        and len(first) == 3
        and isinstance(first[1], list)
        and first[1]
        and isinstance(first[1][0], (list, tuple))
        and len(first[1][0]) == 2
        and isinstance(first[1][0][1], str)
    ):
        flat = []
        total_days = 0.0
        for major_lord, bhukthi_list, major_days in patyayini_raw:
            total_days += float(major_days)
            for (sub_lord, start_str) in bhukthi_list:
                start_dt = _parse_dt_str(start_str)
                flat.append((sub_lord, start_dt))
        flat.sort(key=lambda t: t[1])
        if not flat:
            return None
        first_start = flat[0][1]
        for i, (lord, start_dt) in enumerate(flat):
            if i < len(flat) - 1:
                end_dt = flat[i+1][1] - timedelta(seconds=1)
            else:
                candidate_end = first_start + timedelta(days=total_days)
                end_dt = max(candidate_end, start_dt + timedelta(seconds=1))
            days = (end_dt - start_dt).total_seconds() / 86400.0
            out.append({'lord': _normalize_paty_lord(lord), 'start': start_dt, 'end': end_dt, 'days': days})
        return out
    else:
        starts = []
        for row in patyayini_raw:
            try:
                planet, (y, m, d), days = row
                start_dt = datetime(int(y), int(m), int(d), 0, 0, 0)
                starts.append((_normalize_paty_lord(planet), start_dt, float(days)))
            except Exception:
                continue
        starts.sort(key=lambda t: t[1])
        for i, (planet, start_dt, days) in enumerate(starts):
            if i < len(starts) - 1:
                end_dt = starts[i+1][1] - timedelta(seconds=1)
            else:
                end_dt = start_dt + timedelta(days=days)
            out.append({'lord': planet, 'start': start_dt, 'end': end_dt, 'days': (end_dt - start_dt).total_seconds() / 86400.0})
        return out

def _expand_patyayini_major_schedule(patyayini_raw):
    if not patyayini_raw:
        return None
    first = patyayini_raw[0]
    if not (
        isinstance(first, (list, tuple))
        and len(first) == 3
        and isinstance(first[1], list)
        and first[1]
        and isinstance(first[1][0], (list, tuple))
        and len(first[1][0]) == 2
        and isinstance(first[1][0][1], str)
    ):
        return None
    def _parse_dt_str(s):
        try:
            return datetime.fromisoformat(s)
        except Exception:
            try:
                return datetime.strptime(s.strip(), "%Y-%m-%d %H:%M:%S")
            except Exception:
                return datetime.strptime(s.strip().split()[0], "%Y-%m-%d")
    majors = []
    for major_lord, bhukthi_list, major_days in patyayini_raw:
        if not bhukthi_list:
            continue
        start_dt = _parse_dt_str(bhukthi_list[0][1])
        end_dt   = start_dt + timedelta(days=float(major_days))
        majors.append({'lord': _normalize_paty_lord(major_lord), 'start': start_dt, 'end': end_dt, 'days': float(major_days)})
    majors.sort(key=lambda d: d['start'])
    return majors

# ---------- Tajaka month scoring ----------
def _score_tajaka_month(tajaka, month_start, month_end, place, derived):
    if not tajaka:
        return 0, {'ithasala_orb': 999, 'venus_saham_delta': 999}

    annual_pp = tajaka['annual_planet_positions']
    score = 0
    ithasala_best = 999

    ven_abs = tajaka['venus_abs_long']
    vs_abs = tajaka['vivaha_saham_abs_long']
    venus_saham_delta = _angle_delta_deg(ven_abs, vs_abs)

    # Year-level Venus–Saham proximity (annual, fixed)
    if venus_saham_delta <= 2.0: score += 3
    elif venus_saham_delta <= 5.0: score += 2

    # Optional: month-level *transiting Venus* vs annual Saham proximity (mid-month)
    if USE_TRANSITING_VENUS_SAHAM_PROXIMITY:
        mid = month_start + (month_end - month_start) / 2
        jd_mid_local = swe.julday(mid.year, mid.month, mid.day, mid.hour + mid.minute/60.0 + mid.second/3600.0)
        jd_utc = jd_mid_local - (place.timezone / 24.0)
        ven_tr_abs = drik.sidereal_longitude(jd_utc, const._VENUS)
        delta_tr = _angle_delta_deg(ven_tr_abs, vs_abs)
        if delta_tr <= VENUS_SAHAM_TIER2: score += 3; venus_saham_delta = min(venus_saham_delta, delta_tr)
        elif delta_tr <= VENUS_SAHAM_TIER1: score += 2; venus_saham_delta = min(venus_saham_delta, delta_tr)

    # Ithasāla conditions in annual D1
    LL = tajaka['annual_ll']; L7 = tajaka['annual_7l']
    has_it, it_type = both_planets_within_their_deeptamsa(annual_pp, LL, L7)
    if has_it:
        score += 3 if it_type == 3 else 1
        ithasala_best = 0 if it_type == 3 else min(ithasala_best, 1)

    m_lord = tajaka['muntha_lord']
    has_it, it_type = both_planets_within_their_deeptamsa(annual_pp, const.VENUS_ID, m_lord)
    if has_it:
        score += 2 if it_type == 3 else 1
        ithasala_best = 0 if it_type == 3 else min(ithasala_best, 1)

    vs_sign = tajaka['vivaha_saham_sign']
    vs_lord = house.house_owner_from_planet_positions(annual_pp, vs_sign)
    has_it, it_type = both_planets_within_their_deeptamsa(annual_pp, const.VENUS_ID, vs_lord)
    if has_it:
        score += 2 if it_type == 3 else 1
        ithasala_best = 0 if it_type == 3 else min(ithasala_best, 1)

    ul_sign = derived['ul_d1']
    ul_lord = house.house_owner_from_planet_positions(annual_pp, ul_sign)
    has_it, it_type = both_planets_within_their_deeptamsa(annual_pp, const.VENUS_ID, ul_lord)
    if has_it:
        score += 1
        ithasala_best = 0 if it_type == 3 else min(ithasala_best, 1)

    # Patyayini: sub-slice info; MAJOR-lord for gating; add priority weight
    paty = tajaka.get('patyayini_schedule')
    paty_major = tajaka.get('patyayini_major_schedule')

    paty_hit = False
    paty_lords = []
    if paty and _patyayini_month_hit(paty, month_start, month_end):
        paty_hit = True
        paty_lords = sorted({
            _normalize_paty_lord(sl['lord']) for sl in paty
            if not (sl['end'] < month_start or sl['start'] > month_end)
        }, key=str)

    major_lord = _patyayini_major_lord_for_month(paty_major, month_start, month_end)

    L7 = tajaka['annual_7l']; m_lord = tajaka['muntha_lord']
    vs_lord = house.house_owner_from_planet_positions(annual_pp, vs_sign)
    ul_sign = derived['ul_d1']
    ul_lord = house.house_owner_from_planet_positions(annual_pp, ul_sign)
    target_lords = {const.VENUS_ID, L7, ul_lord, vs_lord, m_lord}

    major_hit = (major_lord in target_lords) if (major_lord is not None) else False

    # Priority weight for MAJOR-lord (Mars as Saham/Muntha lord gets strongest)
    major_weight = 0
    if major_lord is not None:
        if major_lord == m_lord or major_lord == vs_lord:
            major_weight = 3  # strongest: Saham or Muntha lord month
        elif major_lord in {const.VENUS_ID, L7, ul_lord, vs_lord}:
            major_weight = 2
        elif major_hit:
            major_weight = 1
    score += major_weight

    detail = {
        'ithasala_orb': ithasala_best,
        'venus_saham_delta': round(venus_saham_delta, 2),
        'patyayini_major_lord': major_lord,
        'patyayini_major_hit': major_hit,
        'patyayini_major_weight': major_weight,
        'patyayini_hit': paty_hit,
        'patyayini_lords_in_month': paty_lords
    }
    return score, detail

# ---------- Helpers ----------
def _get_planet_sign_from_annual(annual_pp, planet_id):
    for pl, (sg, lon) in annual_pp:
        if pl == planet_id:
            return sg
    return None

def _get_planet_abs_long_from_positions(pp, planet_id):
    for pl, (sg, lon) in pp:
        if pl == planet_id:
            return (sg * 30.0) + float(lon)
    return None

def _find_lagna_sign_from_positions(pp):
    for pl, (sg, lon) in pp:
        if pl == 'L':
            return sg
    return 0

def _angle_delta_deg(a, b):
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)

def _end_of_month(y, m):
    if m == 12:
        return datetime(y, 12, 31, 23, 59, 59)
    return datetime(y, m+1, 1) - timedelta(seconds=1)

def _hours_to_hms(hours_float):
    h = int(hours_float); m = int((hours_float - h) * 60.0)
    s = int(round((((hours_float - h) * 60.0) - m) * 60.0))
    if s == 60: s = 0; m += 1
    if m == 60: m = 0; h += 1
    return h, m, s

def _safe_extract_float_hours(vf_time):
    if isinstance(vf_time, (int, float)):
        return float(vf_time)
    t = str(vf_time).strip().replace('°', ':').replace(' ', ':')
    parts = [p for p in t.split(':') if p != '']
    try:
        h = float(parts[0]) if len(parts) > 0 else 0.0
        m = float(parts[1]) if len(parts) > 1 else 0.0
        s = float(parts[2]) if len(parts) > 2 else 0.0
    except Exception:
        return 0.0
    return h + (m / 60.0) + (s / 3600.0)

def _collect_reasons(md_ad_pd, jtransit, scd_info, tajaka_detail, kcd_score, cnd9_score, cultural, derived):
    out = {
        'md_ad_pd': md_ad_pd,
        'ithasala_orb': tajaka_detail.get('ithasala_orb', 999),
        'venus_saham_delta': tajaka_detail.get('venus_saham_delta', 999),
        'kcd': kcd_score,
        'cnd9': cnd9_score,
        'cultural': cultural
    }
    out['jupiter_transit'] = jtransit
    out['scd_score'] = _score_scd_year_support(scd_info, derived)
    if 'patyayini_hit' in tajaka_detail:
        out['patyayini_hit'] = tajaka_detail['patyayini_hit']
    if 'patyayini_lords_in_month' in tajaka_detail:
        out['patyayini_lords_in_month'] = tajaka_detail['patyayini_lords_in_month']
    planet_names = getattr(utils, 'PLANET_NAMES', None)
    def _pname(p):
        if p == 'L': return 'Lagna'
        if isinstance(p, int) and 0 <= p <= 8 and planet_names: return planet_names[p]
        return str(p)
    out['md_ad_pd_names'] = {'md': _pname(md_ad_pd.get('md')), 'ad': _pname(md_ad_pd.get('ad')), 'pd': _pname(md_ad_pd.get('pd'))}
    if out.get('patyayini_lords_in_month'):
        out['patyayini_lords_in_month_names'] = [_pname(pid) for pid in out['patyayini_lords_in_month']]
    return out

# ---------- Tuple builders ----------
def _year_tuple(md_pass, ad_pass, scd_score, kcd_score, nd9_score, tajaka_year_strength):
    return (int(md_pass), int(ad_pass), int(max(scd_score, kcd_score, nd9_score)), int(tajaka_year_strength))

def _month_tuple(paty_hit, venus_saham_tier, ithasala_tier, jupiter_transit_score, cultural_hit):
    return (int(bool(paty_hit)), int(venus_saham_tier), int(ithasala_tier), int(jupiter_transit_score), int(bool(cultural_hit)))

def _year_strength_from_tajaka(tajaka, derived):
    if not tajaka:
        return 0, {}
    ven_abs = tajaka.get('venus_abs_long')
    vs_abs  = tajaka.get('vivaha_saham_abs_long')
    if ven_abs is None or vs_abs is None:
        return 0, {}
    delta = _angle_delta_deg(ven_abs, vs_abs)
    tier  = 2 if delta <= 2.0 else (1 if delta <= 5.0 else 0)
    return tier, {'venus_saham_delta_at_vf': round(delta, 2)}

def _ithasala_tier_from_detail(tajaka_detail):
    orb = tajaka_detail.get('ithasala_orb', 999)
    if orb == 0: return 2
    if orb == 1: return 1
    return 0

def _venus_saham_tier_from_detail(tajaka_detail):
    delta = tajaka_detail.get('venus_saham_delta', 999)
    if delta <= 2.0: return 2
    if delta <= 5.0: return 1
    return 0

def _suggest_day_from_patyayini(tajaka, month_start, month_end, targets_priority):
    paty = tajaka.get('patyayini_schedule') if tajaka else None
    if not paty:
        return None, {'reason': 'no_patyayini'}
    overlapping = [sl for sl in paty if not (sl['end'] < month_start or sl['start'] > month_end)]
    if not overlapping:
        return None, {'reason': 'no_overlap'}
    for pid in targets_priority:
        slices = [sl for sl in overlapping if sl['lord'] == pid]
        if slices:
            best = max(slices, key=lambda sl: (min(sl['end'], month_end) - max(sl['start'], month_start)).total_seconds())
            center = max(best['start'], month_start) + (min(best['end'], month_end) - max(best['start'], month_start)) / 2
            return center.date(), {'reason': 'patyayini_center', 'lord': pid, 'slice': {'start': best['start'], 'end': best['end']}}
    return None, {'reason': 'no_target_lord'}

# ---------- Optional TODOs ----------
def _score_compressed_d9_narayana(jd, place, month_start, month_end, derived):
    return 0

def _score_cultural_month(month_start, month_end):
    return 0

# ---------- Kalachakra Dasha support ----------
def _score_kalachakra_support(jd, place, year, derived):
    try:
        jd_utc_birth = jd - (place.timezone / 24.0)
        moon_long = drik.sidereal_longitude(jd_utc_birth, const._MOON)
        rows = kalachakra.kalachakra_dhasa(moon_long, jd, include_antardhasa=True)
        if not rows:
            return 0
        segs = []
        for md_rasi, ad_rasi, start_str, dur_years in rows:
            s = start_str.split()[0].strip()
            try:
                y, m, d = map(int, s.split('-')); start_dt = datetime(y, m, d)
            except Exception:
                continue
            dur_days = float(dur_years) * const.sidereal_year
            end_dt = start_dt + timedelta(days=dur_days) - timedelta(seconds=1)
            segs.append({'md': md_rasi, 'ad': ad_rasi, 'start': start_dt, 'end': end_dt})
        if not segs:
            return 0
        win_start = datetime(year, 1, 1, 0, 0, 0); win_end = datetime(year, 12, 31, 23, 59, 59)
        venus_sign_d1 = derived['venus_sign_d1']; seventh_house_sign_d1 = derived['seventh_house_sign_d1']
        best = 0
        for seg in segs:
            if (seg['end'] < win_start) or (seg['start'] > win_end): continue
            md_rasi = seg['md']; ad_rasi = seg['ad']; score = 0
            if md_rasi == venus_sign_d1: score += 1
            if ad_rasi is not None:
                if ad_rasi == ((venus_sign_d1 + 6) % 12): score += 1
                elif ad_rasi == ((md_rasi + 6) % 12):    score += 1
                elif ad_rasi == seventh_house_sign_d1:  score += 1
            best = max(best, min(score, 2))
            if best >= 2: break
        return best
    except Exception:
        return 0

# ---------- (Optional) Adaptors ----------
def to_chart_1_from_positions(planet_positions):
    slots = [""] * 12
    for pl, (sg, lon) in planet_positions:
        if pl == 'L': slots[sg] = ("L" if slots[sg] == "" else slots[sg] + "/L")
        else:
            token = str(pl)
            slots[sg] = token if slots[sg] == "" else (slots[sg] + "/" + token)
    return slots

def to_chart_1d_from_positions(planet_positions):
    return to_chart_1_from_positions(planet_positions)

def to_p_to_h_from_positions(planet_positions):
    out = {}
    for pl, (sg, lon) in planet_positions:
        if pl == 'L': out['L'] = sg
        else: out[pl] = sg
    return out

# ---------- Main (PVR Example-1 Litmus) ----------
if __name__ == "__main__":
    utils.set_language('en')
    # PVR Real-life Example-1
    dob = (1973,7,26); tob = (21,41,0); place = drik.Place('UNK',16+13/60,80+28/60,5.5)
    #dob = (1968,5,21); tob = (23,5,0); place = drik.Place('UNK',18+40/60,78+10/60,5.5)
    jd = utils.julian_day_number(dob, tob)

    # Full window: NO start/end clamp → still should converge to Feb-1999
    results = predict_marriage_windows_from_jd_place(
        jd, place, start_year=None, end_year=None, marriage_age_range=(20,40)
    )
    from pprint import pprint
    pprint(results[:3])
    exit()
    utils.set_language('en')
    # dob = (1996,12,7); tob = (10,34,0); place = drik.Place('Chennai',13.0878,80.2785,5.5)
    #dob = (1964,11,16); tob = (4,30,0); place = drik.Place('Karamadai',11.18,76.57,5.5)
    #dob = (1969,6,22); tob = (21,41,0); place = drik.Place('Trichy',10.49,78.41,5.5)
    dob = (1973,7,26); tob = (21,41,0); place = drik.Place('UNK',16+13/60,80+28/60,5.5)
    #dob = (1968,5,21); tob = (23,5,0); place = drik.Place('UNK',18+40/60, 78+10/60,5.5)
    jd = utils.julian_day_number(dob, tob)
    SHOW_PVR_OUTPUT_FOR_VERIFICATION = False
    if SHOW_PVR_OUTPUT_FOR_VERIFICATION:
        rasi_pp = charts.divisional_chart(jd, place, divisional_chart_factor=1)
        print('rasi planet positions',rasi_pp)
        chart_rasi = utils.get_house_planet_list_from_planet_positions(rasi_pp)
        print('rasi chart', chart_rasi)
        ba = arudhas.bhava_arudhas_from_planet_positions(rasi_pp)
        print('Bhava Lagnas',{"A"+str(l+1):ba[l] for l in range(12)})
        nava_pp = charts.divisional_chart(jd, place, divisional_chart_factor=9)
        chart_d9 = utils.get_house_planet_list_from_planet_positions(nava_pp)
        print('navamsa chart', chart_d9,'matches PVR chart')
        ba = arudhas.bhava_arudhas_from_planet_positions(nava_pp)
        print('Bhava Lagnas Navamsa',{"A"+str(l+1):ba[l] for l in range(12)},'matches PVR chart')
        from jhora.horoscope.dhasa.graha import vimsottari
        _,vdb = vimsottari.get_vimsottari_dhasa_bhukthi(jd, place)
        print('vimosottari',vdb)
        years_from_dob = 25
        from jhora.horoscope.dhasa import sudharsana_chakra
        scdl,_,_ = sudharsana_chakra.sudharsana_chakra_dhasa_for_divisional_chart(jd, place, dob, 
                                                    years_from_dob=years_from_dob, divisional_chart_factor=9)
        print('sudarsana chakra dhasa for 1998-1999\n',scdl[0])
        jd_years = drik.next_solar_date(jd, place, years=26)
        pd = patyayini.get_dhasa_bhukthi(jd_years, place, divisional_chart_factor=1)
        print('patyayini dhasa',pd)
        td_pp,td = annual_chart(jd, place, divisional_chart_factor=1, years=26)
        td_chart = utils.get_house_planet_list_from_planet_positions(td_pp)
        print('tajaka annual chart 1998-99',td_chart)
        from jhora.horoscope.transit.saham import vivaha_saham
        _vivaha_saham_at_tajaka = vivaha_saham(td_pp,night_time_birth=False)
        print('vivaha_saham_at_tajaka',drik.dasavarga_from_long(_vivaha_saham_at_tajaka))
        td_pp_d9,td_d9 = annual_chart(jd, place, divisional_chart_factor=9, years=26)
        td_chart_d9 = utils.get_house_planet_list_from_planet_positions(td_pp_d9)
        print('tajaka annual Navamsa chart 1998-99',td_chart_d9)
        exit()
    results = predict_marriage_windows_from_jd_place(
        jd, place, start_year=1998, end_year=1999, marriage_age_range=(20,40)
    )
    from pprint import pprint
    pprint(results[:3])
