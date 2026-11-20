"""Smoke tests with real numeric assertions for the CI acceptance gates."""

import pytest

import futures_divergence
import firstproject.main


def test_calc_ema_empty_input():
    assert futures_divergence.calc_ema([], 12) == []


def test_calc_ema_constant_series_stays_constant():
    ema = futures_divergence.calc_ema([5.0] * 10, 12)
    assert len(ema) == 10
    assert all(value == pytest.approx(5.0) for value in ema)


def test_calc_macd_constant_series_is_zero():
    dif, dea, hist = futures_divergence.calc_macd([3.0] * 40)
    assert len(dif) == len(dea) == len(hist) == 40
    for series in (dif, dea, hist):
        assert all(value == pytest.approx(0.0, abs=1e-9) for value in series)


def test_find_local_extrema_single_peak():
    values = [0.0, 1.0, 2.0, 3.0, 2.0, 1.0, 0.0]
    peaks, troughs = futures_divergence.find_local_extrema(values, window=2)
    assert peaks == [(3, 3.0)]
    assert troughs == []


def _record(index, close):
    return {"date": f"d{index}", "close": close}


def test_detect_divergence_needs_at_least_60_records():
    records = [_record(i, 100.0 + i) for i in range(10)]
    assert futures_divergence.detect_divergence(records) is None


def _two_peaks_series(first_peak, valley, second_peak):
    """60-point piecewise-linear series with strict peaks at 20 and 50 and one trough at 35."""
    values = []
    for i in range(60):
        if i <= 20:
            values.append(first_peak * i / 20.0)
        elif i <= 35:
            values.append(first_peak + (valley - first_peak) * (i - 20) / 15.0)
        elif i <= 50:
            values.append(valley + (second_peak - valley) * (i - 35) / 15.0)
        else:
            values.append(second_peak - (i - 50) * 0.5)
    return values


def test_detect_divergence_top_divergence(monkeypatch):
    # Price makes higher highs at index 20 (110.0) and index 50 (117.5),
    # while DIF makes lower highs at the same points (5.0 then 3.0).
    closes = _two_peaks_series(110.0, 102.5, 117.5)
    records = [_record(i, close) for i, close in enumerate(closes)]
    dif = _two_peaks_series(5.0, 1.0, 3.0)

    def fake_calc_macd(series, fast=12, slow=26, signal=9):
        assert series == closes
        return dif, [0.0] * len(series), [0.0] * len(series)

    monkeypatch.setattr(futures_divergence, "calc_macd", fake_calc_macd)
    assert futures_divergence.detect_divergence(records) == ("顶背离", "d50")


def test_firstproject_main_prints_hello_world(capsys):
    firstproject.main.main()
    captured = capsys.readouterr()
    assert captured.out == "Hello, World!\n"
