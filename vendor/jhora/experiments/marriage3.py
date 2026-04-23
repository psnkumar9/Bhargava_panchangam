
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

# ---------- Config ----------
_marriage_age_year_range = (20, 32)

STRICT_PVR_MODE_DEFAULT = True
EXPLORATORY_TOP_K = 5

# Strict criteria thresholds (general defaults, not overfit)
STRICT_VS_TIER_MIN = 0                 # Venus–Saham @ VF start is context (not a hard criterion)
STRICT_REQUIRE_PATYAYINI = True        # require Patyayini *major* lord month
STRICT_REQUIRE_ITHASALA_OR_JUPITER = True

# Optional: month-level transiting Venus vs annual Saham proximity (OFF by default)
USE_TRANSITING_VENUS_SAHAM_PROXIMITY = False
VENUS_SAHAM_TIER2 = 2.0   # degrees
VENUS_SAHAM_TIER1 = 5.0   # degrees

# --- Debug toggle for PVR verification ---
DEBUG_PVR = True
def _dbg(*args):
    if DEBUG_PVR:
        print(*args)

# ---------------- Feature-based scoring layer ----------------

DEFAULT_WEIGHTS = {
    # Year weights
    'yr.scd_jup_match': 3.0,    # strong year confirmer (Jupiter == SCD(D9) seed)
    'yr.scd_ven_match': 1.0,    # soft year confirmer (Venus == SCD(D9) seed)
    'yr.md_viable':      2.0,
    'yr.ad_viable':      1.0,
    'yr.tajaka_year_tier': 0.5,  # annual Venus–Saham is *context*, not decider
    'yr.kcd_support':    0.5,
    'yr.nd9_support':    0.0,    # keep 0 unless you wire it

    # Month weights
    'mo.major_role':     3.0,    # 3>Saham/Muntha month > 2>Venus/7L/UL/VS-lord > 1>other MAJOR > 0
    'mo.ithasala_tier':  1.5,    # poorna/weak help crystallize month
    'mo.jupiter_transit':1.0,    # 0..3
    'mo.subslice_presence': 0.2, # small nudge (info)
    'mo.cultural':       0.1,    # placeholder

    # Optional month-level transiting Venus vs Saham proximity (OFF by default)
    'mo.vs_month_tier':  0.0     # set to 1.0/0.5 later if you enable this signal
}

def _infer_major_role_from_dt(decision_trace: dict) -> int:
    """
    Map MAJOR month → role tier (3,2,1,0), using your computed weight:
      3 = Saham-lord or Muntha-lord month
      2 = Venus/7L/UL-lord/VS-lord month
      1 = other MAJOR
      0 = no MAJOR overlap
    """
    return int(decision_trace.get('patyayini_major_weight', 0))

def _extract_features_for_candidate(c, derived, enable_vs_month=False):
    """
    Build a generic feature dict from the candidate structure.

    Expects:
      c['_rank_key'] = (year_tuple, month_rank)
      year_tuple     = (md_pass, ad_pass, scd_score, tajaka_year_strength)
      c['reasons'] contains:
          - 'scd_score', 'scd_jup_match', 'scd_ven_match' (we add these in _collect_reasons),
          - 'kcd', 'cnd9',
          - 'ithasala_orb', 'jupiter_transit', 'patyayini_hit', 'cultural',
          - 'decision_trace' with 'patyayini_major_weight'.
    """
    yr, mo = c['_rank_key']
    md_pass, ad_pass, scd_score, taj_tier = yr

    reasons = c['reasons']
    dt = reasons.get('decision_trace', {})

    # Use explicit flags (we add them in _collect_reasons to avoid guessing)
    scd_jup_match = 1 if reasons.get('scd_jup_match', 0) else 0
    scd_ven_match = 1 if reasons.get('scd_ven_match', 0) else 0

    kcd_support = int(reasons.get('kcd', 0))
    nd9_support = int(reasons.get('cnd9', 0))

    # Month-level
    ith_orb = reasons.get('ithasala_orb', 999)
    ith_tier = 2 if ith_orb == 0 else (1 if ith_orb == 1 else 0)
    jup = int(reasons.get('jupiter_transit', 0))
    subslice = 1 if reasons.get('patyayini_hit', False) else 0
    cultural = 1 if reasons.get('cultural', 0) else 0

    # MAJOR role tier (0..3) from your computed weight
    major_role = _infer_major_role_from_dt(dt)

    # Optional month-level Venus vs Saham proximity (disabled by default)
    vs_month_tier = 0
    if enable_vs_month:
        vs_month_tier = int(dt.get('vs_month_tier', 0))  # only if you wire it

    feats = {
        # Year
        'yr.scd_jup_match': scd_jup_match,
        'yr.scd_ven_match': scd_ven_match,
        'yr.md_viable': int(bool(md_pass)),
        'yr.ad_viable': int(bool(ad_pass)),
        'yr.tajaka_year_tier': int(taj_tier),
        'yr.kcd_support': kcd_support,
        'yr.nd9_support': nd9_support,

        # Month
        'mo.major_role': int(major_role),
        'mo.ithasala_tier': int(ith_tier),
        'mo.jupiter_transit': jup,
        'mo.subslice_presence': subslice,
        'mo.cultural': cultural,
        'mo.vs_month_tier': int(vs_month_tier),
    }
    return feats

def _score_from_features(feats, weights=None):
    w = weights or DEFAULT_WEIGHTS
    return sum(feats.get(k, 0) * w.get(k, 0.0) for k in feats.keys())

# ---------- Public wrapper (jd/place) ----------
def predict_marriage_windows_from_jd_place(
    jd, place, start_year=None, end_year=None, divisional_chart_factor=1,
    marriage_age_range=None, strict=None, top_k=None
):
    """
    Orchestrates over a year range with feature-model strict-first → exploratory fallback.
    Returns: list of dicts [{year, month, score, window, reasons}, ...]
             In strict mode success: 1 element (single date's month, with final_day)
             Otherwise: top-K exploratory candidates with suggested_day
    """

    # decide behavior for this call
    if strict is None:
        strict = STRICT_PVR_MODE_DEFAULT
    if top_k is None:
        top_k = EXPLORATORY_TOP_K
    # ---- Inputs / defaults ----
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

    # ---- collect chart information  ----
    rasi_planet_positions = charts.divisional_chart(jd, place, divisional_chart_factor=1)
    chart_1d_rasi = utils.get_house_planet_list_from_planet_positions(rasi_planet_positions)
    p_to_h_rasi = utils.get_planet_house_dictionary_from_planet_positions(rasi_planet_positions)

    navamsa_planet_positions = charts.divisional_chart(jd, place, divisional_chart_factor=9)
    chart_1d_d9 = utils.get_house_planet_list_from_planet_positions(navamsa_planet_positions)
    p_to_h_d9 = utils.get_planet_house_dictionary_from_planet_positions(navamsa_planet_positions)

    derived = _collect_marriage_primitives(
        jd, place,
        rasi_planet_positions, chart_1d_rasi, p_to_h_rasi,
        navamsa_planet_positions, chart_1d_d9, p_to_h_d9
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

        # Calendar-year Vimshottari slice (dominant)
        year_start = datetime(year, 1, 1, 0, 0, 0)
        year_end   = datetime(year, 12, 31, 23, 59, 59)
        md_ad_pd_year = _active_vimsottari_in_window(segments, year_start, year_end)
        md_pass = _passes_md_gate(md_ad_pd_year['md'], derived) if md_ad_pd_year else False
        ad_pass = _passes_ad_gate(md_ad_pd_year['ad'], derived) if md_ad_pd_year else False

        # Optional year confirmers (calendar-year basis)
        kcd_score = _score_kalachakra_support(jd, place, year, derived)
        nd9_score = _score_compressed_d9_narayana(jd, place, year_start, year_end, derived)

        # Year-level debug (for current VF)
        _dbg(f"[PVR-CHK][YEAR] y={year} SCD(D9)={scd_cur.get('scd_rasi_d9')} "
             f"annD9 Jup={scd_cur.get('vf_jupiter_sign_d9')} Ven={scd_cur.get('vf_venus_sign_d9')} | "
             f"D1 VS(sign)={tajaka_cur.get('vivaha_saham_sign')} Muntha_lord={tajaka_cur.get('muntha_lord')}"
             f" md_ad_pd_year:{md_ad_pd_year} md_pass:{md_pass} ad_pass:{ad_pass}")

        # --- Month loop (per-month VF selection) ---
        for month in range(1, 13):
            month_start = datetime(year, month, 1)
            month_end = _end_of_month(year, month)

            # Choose the VF year applicable to this month
            use_prev = (month_end < tajaka_cur['vf_start'])
            use_tajaka = tajaka_prev if use_prev else tajaka_cur
            use_scd    = scd_prev if use_prev else scd_cur

            # Year tuple for the *selected* VF (tajaka year strength is from the selected bundle)
            taj_year_strength, taj_year_meta = _year_strength_from_tajaka(use_tajaka, derived)
            # SCD score (weighted Jup=+3, Ven=+1)
            scd_score = _score_scd_year_support(use_scd, derived)
            year_tuple_val = (int(md_pass), int(ad_pass), int(scd_score), int(taj_year_strength))

            # --- Month-level signals ---
            md_ad_pd = _active_vimsottari_in_window(segments, month_start, month_end)
            if not md_ad_pd:
                continue

            jtransit = _get_monthly_jupiter_transit_support(jd, place, year, month, derived)
            tajaka_score, tajaka_detail = _score_tajaka_month(use_tajaka, month_start, month_end, place, derived)
            cultural = _score_cultural_month(month_start, month_end)

            # Build month tuple (we’ll still use the tuple for debug/rank transparency)
            ith_tier = _ithasala_tier_from_detail(tajaka_detail)
            vs_tier  = _venus_saham_tier_from_detail(tajaka_detail)
            paty_hit = bool(tajaka_detail.get('patyayini_hit', False))

            month_tuple_val = (int(paty_hit), int(vs_tier), int(ith_tier), int(jtransit), int(bool(cultural)))

            # Major-lord flags from detail and MAJOR-first ranking elements
            major_hit    = bool(tajaka_detail.get('patyayini_major_hit', False))
            major_lord   = tajaka_detail.get('patyayini_major_lord', None)
            major_weight = int(tajaka_detail.get('patyayini_major_weight', 0))

            # Rank tuple (for introspection/debug only)
            # (major_weight, major_hit, paty_hit, vs_tier, ithasala_tier, jupiter_transit, cultural)
            rank_month = (major_weight, int(major_hit)) + month_tuple_val

            # Explanations / reasons
            reasons = _collect_reasons(md_ad_pd, jtransit, use_scd, tajaka_detail, kcd_score, nd9_score, cultural, derived)
            reasons['decision_trace'] = {
                'year_tuple': year_tuple_val,
                'month_tuple': month_tuple_val,
                'md_gate': md_pass,
                'ad_gate_year': ad_pass,
                'tajaka_year_strength': taj_year_strength,
                'year_meta': taj_year_meta,
                'patyayini_major_lord': major_lord,
                'patyayini_major_hit': major_hit,
                'patyayini_major_weight': major_weight
            }

            # Add candidate
            candidates.append({
                'year': year,
                'month': month,
                'window': (month_start, month_end),
                'score': 0,  # legacy field; model score will be computed below
                'reasons': reasons,
                '_rank_key': (year_tuple_val, rank_month),
                '_tajaka': use_tajaka
            })

    if not candidates:
        return []

    # --------- Feature model scoring + global sort ----------
    for c in candidates:
        feats = _extract_features_for_candidate(c, derived, enable_vs_month=USE_TRANSITING_VENUS_SAHAM_PROXIMITY)
        c['_feats'] = feats
        c['_score_model'] = _score_from_features(feats, DEFAULT_WEIGHTS)

    # Sort primarily by model score, tie-break by SCD, then MD/AD if needed
    candidates.sort(
        key=lambda c: (c['_score_model'], c['reasons'].get('scd_score', 0), c['_rank_key'][0][0], c['_rank_key'][0][1]),
        reverse=True
    )

    # --- Strict attempt (scan the pool; pick best strict-passing) ---
    def _passes_strict_generic(c):
        yr, mo = c['_rank_key']
        md_pass, ad_pass, scd_score, taj_tier = yr
        reasons = c['reasons']
        dt = reasons.get('decision_trace', {})
        major_role = _infer_major_role_from_dt(dt)    # 0..3
        ith_orb = reasons.get('ithasala_orb', 999)
        ith_tier = 2 if ith_orb == 0 else (1 if ith_orb == 1 else 0)
        jup = reasons.get('jupiter_transit', 0)
        # Strong SCD(Jupiter) confirmation:
        scd_jup_confirmed = bool(reasons.get('scd_jup_match', 0))

        year_ok = bool(md_pass or scd_jup_confirmed)
        month_ok = bool(major_role >= 1)
        support_ok = bool((ith_tier >= 1) or (jup >= 1)) if STRICT_REQUIRE_ITHASALA_OR_JUPITER else True

        return (year_ok and month_ok and support_ok)

    if strict:
        strict_hits = [c for c in candidates if _passes_strict_generic(c)]
        if strict_hits:
            # pick highest model score among strict hits
            strict_hits.sort(key=lambda c: c['_score_model'], reverse=True)
            best = strict_hits[0]

            # Derive one day from Pātyāyinī sub-slices with target priority
            tajaka = best.get('_tajaka')
            annual_pp = tajaka.get('annual_planet_positions') if tajaka else None
            L7 = tajaka.get('annual_7l') if tajaka else None
            ul_sign = derived['ul_d1']
            ul_lord = house.house_owner_from_planet_positions(annual_pp, ul_sign) if annual_pp is not None else None
            vs_lord = house.house_owner_from_planet_positions(annual_pp, tajaka.get('vivaha_saham_sign')) if tajaka else None
            m_lord  = tajaka.get('muntha_lord') if tajaka else None

            targets = [const.VENUS_ID] + [x for x in [L7, ul_lord, vs_lord, m_lord] if x is not None]
            day, day_meta = _suggest_day_from_patyayini(tajaka, best['window'][0], best['window'][1], targets)

            best['reasons']['final_day'] = day
            best['reasons']['final_day_meta'] = day_meta
            best['reasons']['mode'] = 'strict_single'

            # cleanup
            best.pop('_rank_key', None); best.pop('_tajaka', None)
            best.pop('_feats', None); best.pop('_score_model', None)
            return [best]

    # --- Fallback: exploratory shortlist (top-K by model score) ---
    top = []
    for c in candidates[:top_k]:
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

        # cleanup/debug fields out
        c.pop('_rank_key', None); c.pop('_tajaka', None)
        c.pop('_feats', None); c.pop('_score_model', None)
        top.append(c)
    return top

# ---------- Calculation primitives & adapters ----------

def _collect_marriage_primitives(jd, place, pp_rasi, chart_1d_rasi, p_to_h_rasi, pp_d9, chart_1d_d9, p_to_h_d9):
    out = {}
    by, bm, bd, bh = utils.jd_to_gregorian(jd)
    out['birth_year'] = by

    # --- D1 core ---
    out['lagna_sign_d1'] = p_to_h_rasi[const._ascendant_symbol]
    out['seventh_house_sign_d1'] = (out['lagna_sign_d1'] + const.HOUSE_7) % 12
    out['seventh_lord_d1'] = house.house_owner_from_planet_positions(pp_rasi, out['seventh_house_sign_d1'])

    out['venus_sign_d1'] = p_to_h_rasi[const.VENUS_ID]
    out['seventh_from_venus_sign_d1'] = (out['venus_sign_d1'] + 6) % 12

    ck_list = house.chara_karakas(pp_rasi)
    out['dk'] = ck_list[-1] if isinstance(ck_list, (list, tuple)) else ck_list

    # UL (A12) in D1 & D9
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
    out['ul_supportive_houses_d1'] = {ul, (ul + 2) % 12, (ul + 7) % 12}  # 1st, 3rd, 8th from UL
    out['ul_terminal_houses_d1'] = {(ul + 1) % 12, (ul + 6) % 12}        # 2nd, 7th from UL

    # --- D9 core ---
    out['lagna_sign_d9'] = p_to_h_d9[const._ascendant_symbol]
    out['seventh_house_sign_d9'] = (out['lagna_sign_d9'] + const.HOUSE_7) % 12
    out['seventh_lord_d9'] = house.house_owner_from_planet_positions(pp_d9, out['seventh_house_sign_d9'])

    # Store maps
    out['p_to_h_rasi'] = p_to_h_rasi
    out['p_to_h_d9'] = p_to_h_d9

    # Night/day flag (Vivaha Saham logic) with fallback (used only for natal contexts)
    try:
        out['night_time_birth'] = drik.is_night_birth(jd, place)
    except Exception:
        y, m, d, hours_local = utils.jd_to_gregorian(jd)
        sunrise_hours = drik.sunrise(jd, place)[0]
        sunset_hours  = drik.sunset(jd, place)[0]
        out['night_time_birth'] = not (sunrise_hours <= hours_local <= sunset_hours)

    return out

def _expand_to_md_ad_segments(vdb_info):
    """
    vdb_info: [ [md:int, ad:int, 'YYYY-MM-DD ...'], ... ]  (chronological)
    Returns: [{'md':int,'ad':int,'start':datetime,'end':datetime}, ...]
    """
    segs = []
    if not vdb_info:
        return segs
    starts = []
    for row in vdb_info:
        md, ad, s = row
        s = s.split()[0].strip()  # remove time from vdb_info row
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
    """
    General validators:
      - 7th lord in D1
      - Venus / DK
      - occupying D1 7th house
      - good in D9 (Lagna/5/9 or D9 7H)
      - 7th-from-Venus (D1)
      - UL sign and UL lord (D1)
      - UL supportive houses (1/3/8) tiny nudge
    """
    if planet is None:
        return 0

    base_if_7L = {'md': 3, 'ad': 3, 'pd': 2}.get(tier, 2)
    bonus = {'md': 1, 'ad': 1, 'pd': 1}.get(tier, 1)

    p_to_h_rasi = derived['p_to_h_rasi']
    p_to_h_d9 = derived['p_to_h_d9']

    score = 0

    # 7th lord in D1
    if planet == derived['seventh_lord_d1']:
        score += base_if_7L

    # Venus / DK connections
    if planet == const.VENUS_ID:
        score += bonus
    if planet == derived['dk']:
        score += bonus

    # Occupying D1 7th house
    if p_to_h_rasi.get(planet, -99) == derived['seventh_house_sign_d1']:
        score += bonus

    # Good in D9: Lagna/5/9 and 7th house
    d9_lagna = derived['lagna_sign_d9']
    d9_good = {d9_lagna, (d9_lagna + 4) % 12, (d9_lagna + 8) % 12, derived['seventh_house_sign_d9']}
    if p_to_h_d9.get(planet, -99) in d9_good:
        score += bonus

    # 7th-from-Venus
    s7v = derived.get('seventh_from_venus_sign_d1')
    if s7v is not None and p_to_h_rasi.get(planet, -99) == s7v:
        score += bonus

    # UL sign and UL lord (natal)
    ul_sign = derived.get('ul_d1')
    if ul_sign is not None and p_to_h_rasi.get(planet, -99) == ul_sign:
        score += bonus
    if planet == derived.get('ul_lord_d1'):
        score += bonus

    # UL supportive houses (1/3/8) tiny nudge
    if p_to_h_rasi.get(planet, -99) in derived.get('ul_supportive_houses_d1', set()):
        score += 1

    return score

# ---- Monthly Jupiter transit ----
def _get_monthly_jupiter_transit_support(jd, place, year, month, derived):
    """
    Returns 0..3:
      +1 Jupiter in Lagna/5/7/9 from D1 Lagna
      +1 Jupiter aspects D1 7th house (5/7/9 from Jupiter)
      +1 Jupiter hits 7L-sign OR UL-sign OR 7th-from-Venus (or is in those signs)
    """
    start = datetime(year, month, 1, 12, 0, 0)
    end = _end_of_month(year, month)
    mid = start + (end - start) / 2

    jd_mid_local = swe.julday(mid.year, mid.month, mid.day, mid.hour + mid.minute/60.0 + mid.second/3600.0)
    jd_utc = jd_mid_local - (place.timezone / 24.0)

    jup_lon_abs = drik.sidereal_longitude(jd_utc, const._JUPITER)  # 0..360
    jup_sign, _ = drik.dasavarga_from_long(jup_lon_abs)

    lagna = derived['lagna_sign_d1']
    h7    = derived['seventh_house_sign_d1']
    l7sg  = derived['seventh_lord_sign_d1']
    ulsg  = derived['ul_d1']
    s7v   = derived.get('seventh_from_venus_sign_d1')

    score = 0

    # 1) Jupiter in Lagna/5/7/9 from Lagna
    good = {lagna, (lagna+4) % 12, (lagna+6) % 12, (lagna+8) % 12}
    if jup_sign in good:
        score += 1

    # 2) Jupiter graha drishti 5/7/9 to 7th house sign
    jup_aspects = {(jup_sign + 4) % 12, (jup_sign + 6) % 12, (jup_sign + 8) % 12}
    if h7 in jup_aspects:
        score += 1

    # 3) Hit 7L-sign OR UL-sign OR 7th-from-Venus
    s7v_hit = (s7v is not None) and (s7v in jup_aspects or jup_sign == s7v)
    if (l7sg in jup_aspects) or (ulsg in jup_aspects) or (jup_sign == ulsg) or s7v_hit:
        score += 1

    return score

# ---- SCD (D9) year info ----
def _sudarsana_chakra_year_info(jd, place, year, chart_1d_d9):
    """
    SCD (D9) year info:
      - offset = (year - birth_year) % 12 = (running_year - 1) % 12
      - seed = natal D9 Lagna + offset
      - we also compute annual D9 at Varshaphala start to read Jup/Ven signs
    """
    by, bm, bd, bh = utils.jd_to_gregorian(jd)
    years_from_dob = (year - by)
    running_year   = years_from_dob + 1
    house_offset   = years_from_dob % 12

    # Natal D9 Lagna sign from provided chart_1d_d9
    lagna_sign_d9 = 0
    for sgn, token in enumerate(chart_1d_d9):
        if token and 'L' in token.split('/'):
            lagna_sign_d9 = sgn
            break

    scd_rasi_d9 = (lagna_sign_d9 + house_offset) % 12

    # Annual D9 at VF start
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

    vf_jupiter_sign_d9 = _sign_from_pp(annual_pp_d9, const.JUPITER_ID)
    vf_venus_sign_d9   = _sign_from_pp(annual_pp_d9, const.VENUS_ID)

    _dbg(
        f"[PVR-CHK][SCD] year={year} running_year={running_year} "
        f"offset={house_offset} natal_D9_Lagna={lagna_sign_d9} SCD(D9)={scd_rasi_d9} | "
        f"annual_D9 Jup={vf_jupiter_sign_d9} Ven={vf_venus_sign_d9} vf_start={vf_start}"
    )

    return {
        'running_year': running_year,
        'house_offset': house_offset,
        'scd_rasi_d9': scd_rasi_d9,
        'vf_start': vf_start,
        'vf_jupiter_sign_d9': vf_jupiter_sign_d9,
        'vf_venus_sign_d9': vf_venus_sign_d9
    }

def _score_scd_year_support(scd_info, derived):
    """
    Weighted SCD year confirmers (generalizable default):
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
    """
    Annual (Varshaphala) bundle for the target year (running_year):
      - annual D1, Venus abs-long, Muntha, LL/7L
      - Vivaha Saham from the solar return instant
      - Patyayini schedule + MAJOR schedule
    """
    by, bm, bd, bh = utils.jd_to_gregorian(jd)
    years_from_dob = (year - by)
    running_year   = years_from_dob + 1  # e.g., 1998 -> 26th

    # Annual D1 chart for the running year
    annual_pp_d1, (vf_y_m_d, vf_hours_local) = annual_chart(
        jd_at_dob=jd, place=place, divisional_chart_factor=1, years=running_year
    )
    vf_hours = _safe_extract_float_hours(vf_hours_local)
    H, M, S = _hours_to_hms(vf_hours)
    vf_start = datetime(vf_y_m_d[0], vf_y_m_d[1], vf_y_m_d[2], H, M, S)

    # Single source of truth: solar return instant
    jd_years = drik.next_solar_date(jd, place, years=running_year)

    # Vivaha Saham (annual D1) from the annual instant (returns ABS longitude)
    vs_abs_long = vivaha_saham_from_jd_place(jd_years, place, divisional_chart_factor=1)
    vs_sign, vs_lon_in_sign = drik.dasavarga_from_long(vs_abs_long)

    # Venus absolute longitude in annual D1
    ven_abs_long = _get_planet_abs_long_from_positions(annual_pp_d1, const.VENUS_ID)

    # Annual D1: Jup/Ven signs (reference)
    jup_sign = _get_planet_sign_from_annual(annual_pp_d1, const.JUPITER_ID)
    ven_sign = _get_planet_sign_from_annual(annual_pp_d1, const.VENUS_ID)

    # Annual D1: Lagna, LL, 7L
    annual_lagna_sign = _find_lagna_sign_from_positions(annual_pp_d1)
    annual_h7_sign = (annual_lagna_sign + const.HOUSE_7) % 12
    annual_ll = house.house_owner_from_planet_positions(annual_pp_d1, annual_lagna_sign)
    annual_7l = house.house_owner_from_planet_positions(annual_pp_d1, annual_h7_sign)

    # Muntha (natal Lagna + completed years), lord in annual D1
    natal_lagna_sign = derived['lagna_sign_d1']
    muntha_sign = (natal_lagna_sign + years_from_dob) % 12
    muntha_lord = house.house_owner_from_planet_positions(annual_pp_d1, muntha_sign)

    # Patyayini anchored at the SAME solar return instant
    patyayini_raw = patyayini.get_dhasa_bhukthi(jd_years, place, divisional_chart_factor=1, chart_method=1)
    patyayini_schedule = _expand_patyayini_schedule(patyayini_raw)              # sub-slices
    patyayini_major_schedule = _expand_patyayini_major_schedule(patyayini_raw)  # majors

    _dbg(
        f"[PVR-CHK][TAJAKA] year={year} running_year={running_year} vf_start={vf_start} | "
        f"D1 Jup={jup_sign} Ven={ven_sign} | VS(sign,abs)=({vs_sign},{round(vs_abs_long,3)}) | "
        f"Muntha_sign={muntha_sign} Muntha_lord={muntha_lord} | patyayini_slices={0 if not patyayini_schedule else len(patyayini_schedule)}"
    )
    _dbg(f"[PVR-CHK][PATY-MAJOR] {[(d['lord'], d['start'].date(), d['end'].date()) for d in (patyayini_major_schedule or [])]}")

    tajaka = {
        'vf_start': vf_start,
        'years_after_dob': years_from_dob,
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
    return tajaka

# ---------- Patyayini helpers ----------

def _normalize_paty_lord(pid):
    """
    Normalize Patyayini lord IDs:
    - numpy integer -> int
    - keep 'L' (Lagna) as string
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
    Return the MAJOR lord whose period has the largest overlap with [month_start, month_end],
    or None if no major period overlaps.
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

    # Format with embedded sub-schedules
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
                flat.append((_normalize_paty_lord(sub_lord), start_dt))
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
            out.append({'lord': lord, 'start': start_dt, 'end': end_dt, 'days': days})
        return out

    # Flat format
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
    """
    Extracts MAJOR periods from Patyayini raw format:
      Input format (A): [major_lord, [[sub_lord, 'YYYY-MM-DD ...'], ...], major_duration_days]
      Returns: [{'lord': int|'L', 'start': datetime, 'end': datetime, 'days': float}, ...]
    If input is not format (A), returns None.
    """
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
        return None  # not the format with embedded sub-schedules

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
        start_dt = _parse_dt_str(bhukthi_list[0][1])  # major starts at first sub-lord start
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
    ithasala_best = 999  # 0 for poorna, 1 for weaker, 999 if none

    ven_abs = tajaka['venus_abs_long']
    vs_abs = tajaka['vivaha_saham_abs_long']
    venus_saham_delta = _angle_delta_deg(ven_abs, vs_abs)

    # Year-level Venus–Saham proximity (annual, fixed)
    if venus_saham_delta <= 2.0:
        score += 3
    elif venus_saham_delta <= 5.0:
        score += 2

    # Optional: month-level *transiting Venus* vs annual Saham proximity (mid-month)
    if USE_TRANSITING_VENUS_SAHAM_PROXIMITY:
        mid = month_start + (month_end - month_start) / 2
        jd_mid_local = swe.julday(mid.year, mid.month, mid.day, mid.hour + mid.minute/60.0 + mid.second/3600.0)
        jd_utc = jd_mid_local - (place.timezone / 24.0)
        ven_tr_abs = drik.sidereal_longitude(jd_utc, const._VENUS)
        delta_tr = _angle_delta_deg(ven_tr_abs, vs_abs)
        # If you want to reflect in month features, put vs_month_tier in decision_trace later
        if delta_tr <= VENUS_SAHAM_TIER2:
            score += 3
            venus_saham_delta = min(venus_saham_delta, delta_tr)
        elif delta_tr <= VENUS_SAHAM_TIER1:
            score += 2
            venus_saham_delta = min(venus_saham_delta, delta_tr)

    # Ithasāla conditions in annual D1
    LL = tajaka['annual_ll']
    L7 = tajaka['annual_7l']
    has_it, it_type = both_planets_within_their_deeptamsa(annual_pp, LL, L7)
    if has_it:
        if it_type == 3:
            score += 3
            ithasala_best = 0
        else:
            score += 1
            ithasala_best = min(ithasala_best, 1)

    m_lord = tajaka['muntha_lord']
    has_it, it_type = both_planets_within_their_deeptamsa(annual_pp, const.VENUS_ID, m_lord)
    if has_it:
        if it_type == 3:
            score += 2
            ithasala_best = 0
        else:
            score += 1
            ithasala_best = min(ithasala_best, 1)

    vs_sign = tajaka['vivaha_saham_sign']
    vs_lord = house.house_owner_from_planet_positions(annual_pp, vs_sign)
    has_it, it_type = both_planets_within_their_deeptamsa(annual_pp, const.VENUS_ID, vs_lord)
    if has_it:
        if it_type == 3:
            score += 2
            ithasala_best = 0
        else:
            score += 1
            ithasala_best = min(ithasala_best, 1)

    ul_sign = derived['ul_d1']
    ul_lord = house.house_owner_from_planet_positions(annual_pp, ul_sign)
    has_it, it_type = both_planets_within_their_deeptamsa(annual_pp, const.VENUS_ID, ul_lord)
    if has_it:
        score += 1
        ithasala_best = min(ithasala_best, 0 if it_type == 3 else 1)

    # --- Patyayini: sub-slice presence (info), major-lord boost & role tier (0..3) ---
    paty = tajaka.get('patyayini_schedule')
    paty_major = tajaka.get('patyayini_major_schedule')

    # Sub-slice info (info only)
    paty_hit = False
    paty_lords = []
    if paty and _patyayini_month_hit(paty, month_start, month_end):
        paty_hit = True
        paty_lords = sorted({
            _normalize_paty_lord(sl['lord']) for sl in paty
            if not (sl['end'] < month_start or sl['start'] > month_end)
        }, key=str)

    # Major lord for the month
    major_lord = _patyayini_major_lord_for_month(paty_major, month_start, month_end)

    # Target set for role classification
    vs_sign = tajaka['vivaha_saham_sign']
    annual_pp = tajaka['annual_planet_positions']
    vs_lord = house.house_owner_from_planet_positions(annual_pp, vs_sign)
    m_lord = tajaka['muntha_lord']
    L7 = tajaka['annual_7l']
    ul_sign = derived['ul_d1']
    ul_lord = house.house_owner_from_planet_positions(annual_pp, ul_sign)
    target_lords = {const.VENUS_ID, L7, ul_lord, vs_lord, m_lord}

    major_hit = (major_lord in target_lords) if (major_lord is not None) else False

    # Determine MAJOR role tier (0..3): 3 if Saham/Muntha, 2 if Venus/7L/UL/VS-lord, 1 other major
    major_weight = 0
    if major_lord is not None:
        if major_lord == m_lord or major_lord == vs_lord:
            major_weight = 3
        elif major_lord in {const.VENUS_ID, L7, ul_lord, vs_lord}:
            major_weight = 2
        else:
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
    """
    Assemble an explanation blob. We *explicitly* include scd_jup_match/scd_ven_match flags
    so feature extraction does not have to guess from the numeric SCD score.
    """
    out = {
        'md_ad_pd': md_ad_pd,
        'ithasala_orb': tajaka_detail.get('ithasala_orb', 999),
        'venus_saham_delta': tajaka_detail.get('venus_saham_delta', 999),
        'kcd': kcd_score,
        'cnd9': cnd9_score,
        'cultural': cultural
    }
    out['jupiter_transit'] = jtransit

    # SCD year confirmers
    scd_score = _score_scd_year_support(scd_info, derived)
    out['scd_score'] = scd_score
    scd_rasi = scd_info.get('scd_rasi_d9')
    out['scd_jup_match'] = 1 if scd_info.get('vf_jupiter_sign_d9') == scd_rasi else 0
    out['scd_ven_match'] = 1 if scd_info.get('vf_venus_sign_d9') == scd_rasi else 0

    if 'patyayini_hit' in tajaka_detail:
        out['patyayini_hit'] = tajaka_detail['patyayini_hit']
    if 'patyayini_lords_in_month' in tajaka_detail:
        out['patyayini_lords_in_month'] = tajaka_detail['patyayini_lords_in_month']

    planet_names = getattr(utils, 'PLANET_NAMES', None)
    def _pname(p):
        if p == 'L':
            return 'Lagna'
        if isinstance(p, int) and 0 <= p <= 8 and planet_names:
            return planet_names[p]
        return str(p)

    out['md_ad_pd_names'] = {
        'md': _pname(md_ad_pd.get('md')) if md_ad_pd else 'None',
        'ad': _pname(md_ad_pd.get('ad')) if md_ad_pd else 'None',
        'pd': _pname(md_ad_pd.get('pd')) if md_ad_pd else 'None'
    }
    if out.get('patyayini_lords_in_month'):
        out['patyayini_lords_in_month_names'] = [
            _pname(pid) for pid in out['patyayini_lords_in_month']
        ]

    return out

# ---------- Tuple → tiers ----------
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
    """
    Pick the center day of the best Patyayini sub-slice overlapping [month_start, month_end]
    preferring Venus → 7L → UL-lord → Saham-lord → Muntha-lord.
    """
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
    """
    Uses your kalachakra_dhasa(moon_longitude_at_birth, jd, include_antardhasa=True)
    Rows: [md_rasi, ad_rasi, 'YYYY-MM-DD HH:MM:SS', bhukthi_duration_years]
    Year scoring (0..2):
      +1 if MD rāśi == Venus sign (D1)
      +1 if AD rāśi ∈ {7th from Venus sign, 7th from MD rāśi, D1 7H sign}
    """
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
                y, m, d = map(int, s.split('-'))
                start_dt = datetime(y, m, d)
            except Exception:
                continue
            dur_days = float(dur_years) * const.sidereal_year
            end_dt = start_dt + timedelta(days=dur_days) - timedelta(seconds=1)
            segs.append({'md': md_rasi, 'ad': ad_rasi, 'start': start_dt, 'end': end_dt})

        if not segs:
            return 0

        win_start = datetime(year, 1, 1, 0, 0, 0)
        win_end = datetime(year, 12, 31, 23, 59, 59)

        venus_sign_d1 = derived['venus_sign_d1']
        seventh_house_sign_d1 = derived['seventh_house_sign_d1']

        best = 0
        for seg in segs:
            if (seg['end'] < win_start) or (seg['start'] > win_end):
                continue
            md_rasi = seg['md']
            ad_rasi = seg['ad']
            score = 0
            if md_rasi == venus_sign_d1:
                score += 1
            if ad_rasi is not None:
                if ad_rasi == ((venus_sign_d1 + 6) % 12):
                    score += 1
                elif ad_rasi == ((md_rasi + 6) % 12):
                    score += 1
                elif ad_rasi == seventh_house_sign_d1:
                    score += 1
            best = max(best, min(score, 2))
            if best >= 2:
                break
        return best

    except Exception:
        return 0

# ---------- (Optional) Adaptors ----------
def to_chart_1_from_positions(planet_positions):
    slots = [""] * 12
    for pl, (sg, lon) in planet_positions:
        if pl == 'L':
            slots[sg] = ("L" if slots[sg] == "" else slots[sg] + "/L")
        else:
            token = str(pl)
            slots[sg] = token if slots[sg] == "" else (slots[sg] + "/" + token)
    return slots

def to_chart_1d_from_positions(planet_positions):
    return to_chart_1_from_positions(planet_positions)

def to_p_to_h_from_positions(planet_positions):
    out = {}
    for pl, (sg, lon) in planet_positions:
        if pl == 'L':
            out['L'] = sg
        else:
            out[pl] = sg
    return out

# ---------- Main (ad-hoc test harness) ----------
if __name__ == "__main__":
    utils.set_language('en')

    # Example 1 (PVR 1973-07-26) – expected Feb 1999 month
    #dob = (1973,7,26); tob = (21,41,0); place = drik.Place('UNK',16+13/60,80+28/60,5.5)
    dob = (1968,5,21); tob = (23,5,0); place = drik.Place('UNK',18+40/60,78+10/60,5.5)
    jd = utils.julian_day_number(dob, tob)
    results = predict_marriage_windows_from_jd_place(
        jd, place, start_year=None, end_year=None, marriage_age_range=(20,40),
        strict=False, top_k = 10
    )
    from pprint import pprint
    print("Top-3 results for Example-1:")
    pprint(results[:3])
