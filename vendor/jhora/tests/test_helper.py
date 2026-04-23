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
# test_helper.py
# ==========================
# Simple Baseline Utilities
# ==========================
# test_helper.py
# ==========================
# Simple Baseline Utilities
# ==========================
import json
import os
import re
from jhora import utils
# -----------------------------
# Internal test/run flags
# -----------------------------
_assert_result = True
_tolerance = 1.0
_dhasa_duration_tolerance = 10
_total_tests = 0
_failed_tests = 0
_failed_tests_str = ''
_STOP_IF_ANY_TEST_FAILED = False
# --- Subset filter controls ---
_subset_enabled = False
_subset_numbers = None          # e.g., {63, 2217}
_subset_ranges = None           # e.g., [(2200, 2300)]
_subset_desc_contains = None    # e.g., ["Chapter 27", "Varsha"]
_subset_verbose_skip = False
# -----------------------------
# Baseline configuration
# -----------------------------
_BASELINE_MODE = 'none'              # 'none' | 'record' | 'compare'
_BASELINE_FILE = 'tests_baseline.json'
_BASELINE_WRITE_MODE = 'expected'    # 'expected' | 'actual'

# -----------------------------
# Public setters/getters
# -----------------------------
def set_subset(numbers=None, ranges=None, desc_contains=None, enabled=True, verbose_skip=False):
    """
    Configure a subset filter.
      numbers:       iterable of exact test numbers (e.g., {63, 2217})
      ranges:        iterable of (start, end) inclusive pairs (e.g., [(2200, 2300)])
      desc_contains: iterable of substrings to match in test_description
      enabled:       True to enable, False to disable
      verbose_skip:  True to print 'Skip Test#...' when skipping
    """
    global _subset_enabled, _subset_numbers, _subset_ranges, _subset_desc_contains, _subset_verbose_skip
    _subset_enabled = bool(enabled)
    _subset_numbers = set(numbers) if numbers else None
    _subset_ranges = [(int(a), int(b)) for (a, b) in ranges] if ranges else None
    _subset_desc_contains = [str(s) for s in desc_contains] if desc_contains else None
    _subset_verbose_skip = bool(verbose_skip)

def clear_subset():
    set_subset(enabled=False)

def _subset_should_run(next_num, description: str) -> bool:
    if not _subset_enabled:
        return True
    ok = False
    if _subset_numbers and next_num in _subset_numbers:
        ok = True
    if _subset_ranges and any(lo <= next_num <= hi for (lo, hi) in _subset_ranges):
        ok = True
    if _subset_desc_contains and any(s in description for s in _subset_desc_contains):
        ok = True
    return ok
    
def set_baseline(mode='none', file='tests_baseline.json'):
    """
    Minimal config:
      mode:  'record'  -> write per test to JSON
             'compare' -> read per test from JSON
             'none'    -> baseline disabled
      file:  JSON file path
    """
    global _BASELINE_MODE, _BASELINE_FILE
    if mode.lower() not in ('none', 'record', 'compare'):
        raise ValueError("mode must be 'none', 'record', or 'compare'")
    _BASELINE_MODE = mode
    _BASELINE_FILE = file

def set_baseline_write_mode(mode='expected'):
    """Control what gets written during 'record': 'expected' or 'actual'."""
    global _BASELINE_WRITE_MODE
    if mode not in ('expected', 'actual'):
        raise ValueError("baseline write mode must be 'expected' or 'actual'")
    _BASELINE_WRITE_MODE = mode

def set_stop_on_fail(value: bool):
    """If True, stop on first failed test (raises SystemExit)."""
    global _STOP_IF_ANY_TEST_FAILED
    _STOP_IF_ANY_TEST_FAILED = bool(value)

def set_assert_result(value: bool):
    """If False, just prints without asserting pass/fail."""
    global _assert_result
    _assert_result = bool(value)

def set_default_tolerance(value: float):
    """Set the default tolerance used by compare_lists_within_tolerance."""
    global _tolerance
    _tolerance = float(value)

def reset_test_stats():
    """Reset test counters (useful if you run multiple subsets in one process)."""
    global _total_tests, _failed_tests, _failed_tests_str
    _total_tests = 0
    _failed_tests = 0
    _failed_tests_str = ''

def get_test_stats():
    """Return (total_tests, failed_tests, failed_tests_str, pass_percent)."""
    total = _total_tests
    failed = _failed_tests
    failed_str = _failed_tests_str
    pass_pct = (100.0 * (total - failed) / total) if total else 100.0
    return total, failed, failed_str, pass_pct

# -----------------------------
# Internal JSON I/O helpers
# -----------------------------
def _simple_read_json():
    """Load JSON dict from _BASELINE_FILE, or {} if missing/empty/unreadable."""
    try:
        if os.path.exists(_BASELINE_FILE) and os.path.getsize(_BASELINE_FILE) > 0:
            with open(_BASELINE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        # Keep it simple—ignore decode errors and start fresh
        pass
    return {}

def _simple_write_json(data: dict):
    """Overwrite _BASELINE_FILE directly (no temp, no retries)."""
    os.makedirs(os.path.dirname(_BASELINE_FILE) or '.', exist_ok=True)
    with open(_BASELINE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _to_jsonable(obj):
    """
    Convert to JSON-serializable native types; handle numpy scalars/arrays and common containers.
    Fallback to repr() for unknown types.
    """
    # Fast path primitives
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj

    # --- NumPy handling (if installed) ---
    try:
        import numpy as np  # noqa: F401
        # numpy scalar -> native python scalar
        if hasattr(np, 'generic') and isinstance(obj, np.generic):
            return obj.item()
        # numpy array -> list
        if hasattr(np, 'ndarray') and isinstance(obj, np.ndarray):
            return obj.tolist()
    except Exception:
        pass

    # Containers
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, dict):
        # JSON requires string keys
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (set, frozenset)):
        return sorted(_to_jsonable(v) for v in obj)

    # Last resort: a readable string
    return repr(obj)

# -----------------------------
# Compare-time coercion helpers
# -----------------------------
# Handle legacy strings like "np.int64(77)" / "np.float64(1.23)" / "np.True_"
_np_int_pat = re.compile(r"^np\.int(?:\d+)?\(\s*([-+]?\d+)\s*\)$")
_np_float_pat = re.compile(r"^np\.float(?:\d+)?\(\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s*\)$")
_np_bool_map = {"np.True_": True, "np.False_": False, "True": True, "False": False}

def _coerce_scalar_like_for_compare(expected, actual):
    """
    If 'expected' is a string artifact like 'np.int64(77)' / 'np.True_', coerce to a native type
    compatible with 'actual'. Only used in compare mode.
    """
    if not isinstance(expected, str):
        return expected

    s = expected.strip()

    # np boolean or plain boolean as string
    if s in _np_bool_map:
        return _np_bool_map[s]

    # np.intXX(#)
    m = _np_int_pat.match(s)
    if m:
        try:
            val = int(m.group(1))
            # Align to float if actual is float to reduce type-only mismatches
            if isinstance(actual, float):
                return float(val)
            return val
        except Exception:
            return expected

    # np.floatXX(#)
    m = _np_float_pat.match(s)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return expected

    # fallback: numeric literal as string if actual is numeric
    if isinstance(actual, (int, float)):
        try:
            f = float(s)
            if isinstance(actual, int) and f.is_integer():
                return int(f)
            return f
        except Exception:
            pass

    return expected

def _align_structure_for_compare(expected, actual):
    """
    Recursively align 'expected' (loaded from JSON) to match the container and key types of 'actual'.
    Only call in 'compare' mode so 'none' and 'record' behavior stays the same.
    """
    # Tuples: convert list<->tuple to mirror actual, recurse
    if isinstance(actual, tuple):
        if isinstance(expected, (list, tuple)) and len(expected) == len(actual):
            return tuple(_align_structure_for_compare(e, a) for e, a in zip(expected, actual))
        return expected

    # Lists: mirror list container, recurse
    if isinstance(actual, list):
        if isinstance(expected, (list, tuple)) and len(expected) == len(actual):
            return [_align_structure_for_compare(e, a) for e, a in zip(expected, actual)]
        return expected

    # Dicts: look up expected using actual's key; try ak and str(ak)
    if isinstance(actual, dict) and isinstance(expected, dict):
        out = {}
        for ak, av in actual.items():
            if ak in expected:
                ev = expected[ak]
            elif str(ak) in expected:
                ev = expected[str(ak)]
            else:
                ev = None
                if isinstance(ak, str):
                    # Optional numeric coercions if your actual keys are str
                    try:
                        ai = int(ak)
                        if ai in expected:
                            ev = expected[ai]
                    except Exception:
                        pass
                    if ev is None:
                        try:
                            af = float(ak)
                            if af in expected:
                                ev = expected[af]
                        except Exception:
                            pass
            out[ak] = _align_structure_for_compare(ev, av)
        return out

    # Scalars or mismatched: attempt to coerce string artifacts to match actual's type
    return _coerce_scalar_like_for_compare(expected, actual)

# ==========================
# Test functions (exported)
# ==========================
def test_example(test_description, expected_result, actual_result, *extra_data_info, convert_date_tuple_to_string=True):
    global _total_tests, _failed_tests, _failed_tests_str, _STOP_IF_ANY_TEST_FAILED, _assert_result

    # ---- helpers (REPLACE your previous helpers with these) ----
    def _is_int(n):
        # Avoid bools (since bool is a subclass of int)
        return isinstance(n, int) and not isinstance(n, bool)

    def _is_num(n):
        return (isinstance(n, (int, float)) and not isinstance(n, bool))

    def _looks_like_date_tuple(value):
        """
        Strictly validate a (y, m, d, h) structure:
        - year: 4-digit integer, 1000..9999
        - month: integer 1..12
        - day: integer 1..31
        - hour: numeric 0 <= h < 24 (float allowed)
        """
        if not (isinstance(value, (list, tuple)) and len(value) == 4):
            return False
        y, m, d, h = value
        if not (_is_int(y) and 1000 <= y <= 9999):
            return False
        if not (_is_int(m) and 1 <= m <= 12):
            return False
        if not (_is_int(d) and 1 <= d <= 31):
            return False
        if not (_is_num(h) and 0 <= float(h) < 24):
            return False
        return True

    def _convert_date_like(value):
        """Convert (y,m,d,h) -> string via utils.date_time_tuple_to_date_time_string, using strict guards."""
        if not convert_date_tuple_to_string:
            return value
        try:
            if _looks_like_date_tuple(value):
                y, m, d, h = value
                return utils.date_time_tuple_to_date_time_string(int(y), int(m), int(d), float(h))
        except Exception:
            # Fail-safe: if conversion fails, leave as-is
            pass
        return value

    def _normalize_dates(obj):
        """Recursively convert any (y,m,d,h) date-like tuple/list into the required string form."""
        converted = _convert_date_like(obj)
        if converted is not obj:
            return converted

        if isinstance(obj, dict):
            return {k: _normalize_dates(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_normalize_dates(v) for v in obj]
        elif isinstance(obj, tuple):
            return tuple(_normalize_dates(v) for v in obj)
        elif isinstance(obj, set):
            return {_normalize_dates(v) for v in obj}
        else:
            return obj
    # ---- end helpers ----

    # ... keep the rest of your function exactly as in the previous version ...
    next_num = _total_tests + 1
    should_run = _subset_should_run(next_num, str(test_description))
    _total_tests = next_num

    if not should_run:
        if _subset_verbose_skip:
            print(f"Skip Test#:{next_num} {test_description}")
        return

    key = str(next_num)

    normalized_expected = _normalize_dates(expected_result)
    normalized_actual = _normalize_dates(actual_result)
    normalized_extra = _normalize_dates(list(extra_data_info)) if extra_data_info else ""

    if _BASELINE_MODE.lower() == 'record':
        data = _simple_read_json()
        to_write = normalized_actual if _BASELINE_WRITE_MODE == 'actual' else normalized_expected
        data[key] = [
            str(test_description),
            _to_jsonable(to_write),
            _to_jsonable(normalized_extra) if normalized_extra != "" else ""
        ]
        _simple_write_json(data)
        print(f"Writing {test_description} ({_BASELINE_WRITE_MODE}) Test#:{_total_tests} -> BASELINE_FILE")
        return

    if _BASELINE_MODE.lower() == 'compare':
        data = _simple_read_json()
        if key in data:
            _, expected_from_file, _ = data[key]
            normalized_expected = _normalize_dates(expected_from_file)
            normalized_actual = _normalize_dates(actual_result)
            normalized_expected = _align_structure_for_compare(normalized_expected, normalized_actual)

    expected_result = normalized_expected
    actual_result = normalized_actual

    assert_result = _assert_result
    if len(extra_data_info) == 0:
        extra_data_info = ''

    if assert_result:
        if expected_result == actual_result:
            print('Test#:'+str(_total_tests), test_description, "Expected:", expected_result, "Actual:", actual_result, 'Test Passed', extra_data_info)
        else:
            _failed_tests += 1
            _failed_tests_str += str(_total_tests) + ';'
            print('Test#:'+str(_total_tests), test_description, "Expected:", expected_result, "Actual:", actual_result, 'Test Failed', extra_data_info)
            if _STOP_IF_ANY_TEST_FAILED:
                print("Stopping the execution due to the failed test")
                raise SystemExit(1)
    else:
        print('Test#:'+str(_total_tests), test_description, "Expected:", expected_result, "Actual:", actual_result, extra_data_info)

def compare_lists_within_tolerance(test_description, expected_list, actual_list, tolerance=_tolerance, *extra_data_info):
    """
    Baseline behavior:
      - 'record': write expected/actual list per test number
      - 'compare': override expected list, align structure to actual (if needed), then compare with tolerance
      - 'none': behave like original
    """
    global _total_tests, _failed_tests, _failed_tests_str, _STOP_IF_ANY_TEST_FAILED, _assert_result

    next_num = _total_tests + 1
    should_run = _subset_should_run(next_num, str(test_description))

    # Always consume the test number to preserve alignment (important for compare mode keyed by numbers)
    _total_tests = next_num

    if not should_run:
        if _subset_verbose_skip:
            print(f"Skip Test#:{next_num} {test_description}")
        return
    # ... (rest of your function continues unchanged; use 'key = str(next_num)' now)
    key = str(next_num)

    # RECORD mode
    if _BASELINE_MODE.lower() == 'record':
        data = _simple_read_json()
        to_write = actual_list if _BASELINE_WRITE_MODE == 'actual' else expected_list
        data[key] = [
            str(test_description),
            _to_jsonable(to_write),
            _to_jsonable(list(extra_data_info)) if extra_data_info else ""
        ]
        _simple_write_json(data)
        print(f"Writing {test_description} ({_BASELINE_WRITE_MODE}) Test#:{_total_tests} -> BASELINE_FILE")
        return

    # COMPARE mode: override and align structure
    if _BASELINE_MODE.lower() == 'compare':
        data = _simple_read_json()
        if key in data:
            _, expected_from_file, _ = data[key]
            expected_list = _align_structure_for_compare(expected_from_file, actual_list)

    # Compare within tolerance (use <= boundary and cast to float)
    assert len(expected_list) == len(actual_list), \
        f"Length mismatch for test '{test_description}': expected {len(expected_list)} vs actual {len(actual_list)}"

    try:
        test_passed = all(abs(float(expected_list[i]) - float(actual_list[i])) <= float(tolerance)
                          for i in range(len(actual_list)))
    except Exception as e:
        # If any element fails float conversion, surface a meaningful error
        raise AssertionError(
            f"Non-numeric element encountered in '{test_description}' during tolerance comparison: {e}\n"
            f"expected_list={expected_list}\nactual_list={actual_list}"
        )

    status_str = f"Test Passed within tolerance={tolerance}" if test_passed else f"Test Failed within tolerance={tolerance}"

    if not test_passed:
        _failed_tests += 1
        _failed_tests_str += str(_total_tests) + ';'
        print('Test#:'+str(_total_tests), test_description, "Expected:", expected_list, "Actual:", actual_list, status_str, extra_data_info)
        if _STOP_IF_ANY_TEST_FAILED:
            print("Stopping the execution due to the failed test")
            raise SystemExit(1)
    else:
        print('Test#:'+str(_total_tests), test_description, "Expected:", expected_list, "Actual:", actual_list, status_str, extra_data_info)

import re

def compare_longitudes_within_tolerance(test_description, expected_list, actual_list, tolerance=_tolerance, *extra_data_info):
    """
    Compare lists of longitudes within a tolerance (in DEGREES), supporting:
      - Zodiac string:
          "23Aq03"              -> 23° Aquarius + 03'
          "23Aq03'12.13"        -> 23° Aquarius + 03' + 12.13"
          "23Aq03.12.13"        -> 23° Aquarius + 03' + 12.13" (dot form)
          '23Aq03.12.13"'       -> same, trailing double-quote accepted
      - Plain numeric degrees in [0, 360) as float or numeric string, e.g., 172.376576 or "172.376576"

    Behavior mirrors `compare_lists_within_tolerance`:
      - 'record': write expected/actual list per test number (as-is)
      - 'compare': override expected list from baseline, align structure, then compare circularly
      - 'none': behave like original

    Tolerance is in degrees. Circular difference is used: min(|a-b|, 360-|a-b|).
    """
    # ---- globals from your test harness ----
    global _total_tests, _failed_tests, _failed_tests_str, _STOP_IF_ANY_TEST_FAILED, _assert_result
    # Expects these to exist:
    #   _subset_should_run, _subset_verbose_skip, _simple_read_json, _simple_write_json,
    #   _to_jsonable, _align_structure_for_compare, _BASELINE_MODE, _BASELINE_WRITE_MODE

    # ----------------- helpers -----------------
    _SIGN_OFFSETS = {
        # Aries .. Pisces (0..330 by 30°)
        "ar": 0,     "ari": 0,     "aries": 0,
        "ta": 30,    "tau": 30,    "taurus": 30,
        "ge": 60,    "gem": 60,    "gemini": 60,
        "cn": 90,    "can": 90,    "cancer": 90,
        "le": 120,   "leo": 120,
        "vi": 150,   "vir": 150,   "virgo": 150,
        "li": 180,   "lib": 180,   "libra": 180,
        "sc": 210,   "sco": 210,   "scorpio": 210,
        "sg": 240,   "sag": 240,   "sagittarius": 240,
        "cp": 270,   "cap": 270,   "capricorn": 270,
        "aq": 300,   "aqu": 300,   "aquarius": 300,
        "pi": 330,   "pis": 330,   "pisces": 330,
    }

    def _normalize_0_360(x):
        x = float(x) % 360.0
        return x if x >= 0 else x + 360.0

    def _circular_abs_diff(a, b):
        diff = (abs(float(a) - float(b)) % 360.0)
        return diff if diff <= 180.0 else 360.0 - diff

    def _strip_trailing_quotes(s):
        # Remove common seconds quotes if present: "  or Unicode ″ (U+2033)
        return s.rstrip().rstrip('"').rstrip('″').rstrip()

    def _parse_longitude_value(v):
        """
        Convert a single value into degrees [0,360).
        Accepts:
          - float/int
          - numeric string "172.376576"
          - "<deg><Sign><min>"
          - "<deg><Sign><min>'<sec>"
          - "<deg><Sign><min>.<sec>" or "<deg><Sign><min>.<ss>.<frac>"
            (e.g., "23Aq03.12.13" -> min=3, sec=12.13)
          - Optional trailing double-quote in dot form is tolerated: ...12.13"
        """
        # Numeric fast path
        if isinstance(v, (int, float)):
            return _normalize_0_360(float(v))

        if not isinstance(v, str):
            raise ValueError(f"Unsupported longitude type: {type(v)} -> {v}")

        s = v.strip()
        # Try numeric string
        try:
            num = float(s)
            return _normalize_0_360(num)
        except Exception:
            pass

        # Find the sign token (letters)
        m = re.search(r'([A-Za-z]{2,})', s)
        if not m:
            raise ValueError(f"Cannot parse longitude (no sign, not numeric): '{v}'")

        deg_str = s[:m.start()].strip()
        sign_str = s[m.start():m.end()].strip().lower()
        rest = s[m.end():].strip()

        if not deg_str:
            raise ValueError(f"Missing degrees before sign in '{v}'")
        try:
            deg_in_sign = int(deg_str)
        except Exception:
            raise ValueError(f"Invalid degrees portion before sign in '{v}'")

        if sign_str not in _SIGN_OFFSETS:
            raise ValueError(f"Unknown zodiac sign in '{v}': '{sign_str}'")
        base = _SIGN_OFFSETS[sign_str]

        # Defaults
        minutes = 0
        seconds = 0.0

        if rest:
            # Normalize trailing quotes first (for dot form)
            rest_clean = _strip_trailing_quotes(rest).replace('"', '').replace('″', '').strip()

            if "'" in rest_clean:
                # Apostrophe form: "<min>'<sec>"
                mins_part, sec_part = rest_clean.split("'", 1)
                mins_part = mins_part.strip()
                sec_part = sec_part.strip()
                if mins_part:
                    minutes = int(mins_part)
                if sec_part:
                    seconds = float(sec_part)
            elif "." in rest_clean:
                # Dot form: "<min>.<sec>" or "<min>.<ss>.<frac>"
                parts = [p for p in rest_clean.split('.') if p != '']
                if len(parts) >= 1:
                    minutes = int(parts[0])
                if len(parts) >= 2:
                    # Reconstruct seconds possibly with fractional portion
                    seconds = float(parts[1] + ('.' + ''.join(parts[2:]) if len(parts) > 2 else ''))
            else:
                # Minutes only
                minutes = int(rest_clean)

        # Normalize minutes/seconds overflow (tolerant)
        total_in_sign = float(deg_in_sign) + (float(minutes) / 60.0) + (float(seconds) / 3600.0)
        if total_in_sign < 0:
            raise ValueError(f"Negative longitude component in '{v}' leads to negative total within sign.")

        abs_deg = base + total_in_sign
        return _normalize_0_360(abs_deg)

    # --------------- main body (mirrors your baseline flow) ----------------
    next_num = _total_tests + 1
    should_run = _subset_should_run(next_num, str(test_description))
    _total_tests = next_num  # always consume number to preserve alignment
    key = str(next_num)

    if not should_run:
        if _subset_verbose_skip:
            print(f"Skip Test#:{next_num} {test_description}")
        return

    # RECORD mode
    if _BASELINE_MODE.lower() == 'record':
        data = _simple_read_json()
        to_write = actual_list if _BASELINE_WRITE_MODE == 'actual' else expected_list
        data[key] = [
            str(test_description),
            _to_jsonable(to_write),
            _to_jsonable(list(extra_data_info)) if extra_data_info else ""
        ]
        _simple_write_json(data)
        print(f"Writing {test_description} ({_BASELINE_WRITE_MODE}) Test#:{_total_tests} -> BASELINE_FILE")
        return

    # COMPARE mode: override expected and align if needed
    if _BASELINE_MODE.lower() == 'compare':
        data = _simple_read_json()
        if key in data:
            _, expected_from_file, _ = data[key]
            expected_list = _align_structure_for_compare(expected_from_file, actual_list)

    # Length check
    assert len(expected_list) == len(actual_list), \
        f"Length mismatch for test '{test_description}': expected {len(expected_list)} vs actual {len(actual_list)}"

    # Parse to normalized degrees
    try:
        exp_deg = [_parse_longitude_value(x) for x in expected_list]
        act_deg = [_parse_longitude_value(x) for x in actual_list]
    except Exception as e:
        raise AssertionError(
            f"Parsing error in '{test_description}': {e}\n"
            f"expected_list={expected_list}\nactual_list={actual_list}"
        )

    # Circular comparison
    try:
        diffs = [_circular_abs_diff(exp_deg[i], act_deg[i]) for i in range(len(act_deg))]
        test_passed = all(d <= float(tolerance) for d in diffs)
    except Exception as e:
        raise AssertionError(
            f"Comparison error in '{test_description}': {e}\n"
            f"parsed_expected={exp_deg}\nparsed_actual={act_deg}"
        )

    status_str = f"Test Passed within tolerance={tolerance}°" if test_passed \
                 else f"Test Failed within tolerance={tolerance}°"

    if not test_passed:
        _failed_tests += 1
        _failed_tests_str += str(_total_tests) + ';'
        print('Test#:' + str(_total_tests), test_description,
              "Expected:", expected_list,
              "Actual:", actual_list,
              status_str,
              f"diffs(deg)={['{:.6f}'.format(d) for d in diffs]}",
              extra_data_info)
        if _STOP_IF_ANY_TEST_FAILED:
            print("Stopping the execution due to the failed test")
            raise SystemExit(1)
    else:
        print('Test#:' + str(_total_tests), test_description,
              "Expected:", expected_list,
              "Actual:", actual_list,
              status_str,
              extra_data_info)

# -----------------------------
# Optional: One-time sanitizer
# -----------------------------
def _sanitize_value(v):
    """Recursively sanitize values that look like numpy-scalar strings into native types."""
    if isinstance(v, dict):
        return {k: _sanitize_value(vv) for k, vv in v.items()}
    if isinstance(v, list):
        return [_sanitize_value(x) for x in v]
    if isinstance(v, str):
        s = v.strip()
        if s in _np_bool_map:
            return _np_bool_map[s]
        m = _np_int_pat.match(s)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                return v
        m = _np_float_pat.match(s)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                return v
        return v
    return v

def sanitize_baseline_file(backup=True):
    """
    Read the baseline JSON, sanitize numpy-scalar string artifacts to native types,
    and rewrite the file (with an optional backup).
    """
    data = _simple_read_json()
    if not data:
        print(f"[sanitize] Nothing to sanitize (empty or missing): {_BASELINE_FILE}")
        return
    cleaned = {}
    for k, entry in data.items():
        if isinstance(entry, list) and len(entry) == 3:
            desc, exp, extra = entry
            cleaned[k] = [desc, _sanitize_value(exp), _sanitize_value(extra)]
        else:
            cleaned[k] = _sanitize_value(entry)
    if backup and os.path.exists(_BASELINE_FILE):
        bak = _BASELINE_FILE + ".bak"
        try:
            if os.path.exists(bak):
                os.remove(bak)
            os.replace(_BASELINE_FILE, bak)
            print(f"[sanitize] Backup written: {bak}")
        except Exception:
            print("[sanitize] Could not write backup; proceeding without.")
    _simple_write_json(cleaned)
    print(f"[sanitize] Baseline sanitized: {_BASELINE_FILE}")
def set_starting_test_number(n: int):
    """Set the internal counter so the next test becomes n+1."""
    global _total_tests
    _total_tests = int(n)
def append_tests(baseline_file):
    global _total_tests
    data = json.load(open(baseline_file)) if os.path.exists(baseline_file) and os.path.getsize(baseline_file) > 0 else {}
    _total_tests = max((int(k) for k in data if str(k).isdigit()), default=0)
# --- Add near other public getters/setters in test_helper.py ---
def get_subset_config():
    """Return the current subset filter config for display/logging."""
    return {
        "enabled": _subset_enabled,
        "numbers": sorted(_subset_numbers) if _subset_numbers else None,
        "ranges": _subset_ranges,
        "desc_contains": _subset_desc_contains,
        "verbose_skip": _subset_verbose_skip,
    }
def show_configuration_summary(summary_lines):
    if summary_lines:
        print("\n=== Test Run Confirmation ===")
        for line in summary_lines:
            print(line)
        print("=============================")
    
def confirm_before_run(summary_lines=None, default_no=True, auto_env_var="PYJHORA_TEST_AUTO_CONFIRM"):
    """
    Print a summary and prompt the user to confirm before running tests.
    - If environment variable `auto_env_var` is truthy (e.g., "1", "true", "yes"), auto-confirms.
    - If stdin is non-interactive (e.g., CI), auto-declines unless env var is set.
    - Returns True to proceed, False to abort.
    """
    import sys, os

    # Auto-confirm via env var (useful for CI or scripted runs)
    if str(os.getenv(auto_env_var, "")).strip().lower() in {"1", "true", "yes", "y"}:
        return True

    show_configuration_summary(summary_lines)
    prompt = "Proceed? [y/N]: " if default_no else "Proceed? [Y/n]: "
    try:
        ans = input(prompt).strip().lower()
    except EOFError:
        return False  # no input available

    if default_no:
        return ans in {"y", "yes"}
    else:
        return ans not in {"n", "no", ""}
    
if __name__ == "__main__":
    # No direct execution; used as a helper module.
    pass