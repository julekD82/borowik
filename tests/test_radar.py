import math
from datetime import datetime, timezone

import numpy as np
import pytest

from pipeline.radar import (
    GridHeader, parse_grs_asc, parse_hour_stamp, block_slices, sample_stack,
)


def _asc(values, xll=0.0, yll=0.0, cs=1000.0, nodata=-999.0) -> bytes:
    rows, cols = len(values), len(values[0])
    head = (f"ncols {cols}\nnrows {rows}\nxllcorner {xll}\nyllcorner {yll}\n"
            f"cellsize {cs}\nNODATA_value {nodata}\n")
    body = "\n".join(" ".join(f"{v:.2f}" for v in r) for r in values)
    return (head + body + "\n").encode("ascii")


GRID_3x4 = [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]]  # row 0 = northernmost


def test_parse_grs_asc_reads_header_and_values_top_row_first():
    header, grid = parse_grs_asc(_asc(GRID_3x4, xll=50000, yll=30000))
    assert header == GridHeader(ncols=4, nrows=3, xllcorner=50000.0, yllcorner=30000.0, cellsize=1000.0)
    assert grid.shape == (3, 4)
    assert grid[0, 0] == 1.0 and grid[2, 3] == 12.0


def test_parse_grs_asc_turns_nodata_into_nan():
    _, grid = parse_grs_asc(_asc([[1, -999], [0, 2]]))
    assert math.isnan(grid[0, 1])
    assert grid[1, 0] == 0.0


def test_parse_grs_asc_rejects_html_error_page():
    # IMGW answers a missing file with HTTP 200 + an HTML page, not a 404.
    with pytest.raises(ValueError):
        parse_grs_asc(b"<!DOCTYPE html><html><body>Brak pliku</body></html>")


def test_parse_grs_asc_rejects_truncated_grid():
    raw = _asc(GRID_3x4)[:-10]
    with pytest.raises(ValueError):
        parse_grs_asc(raw)


def test_parse_hour_stamp_is_utc_hour_end():
    stamp = parse_hour_stamp("Arch/x/202609211300_acc0060_grs.asc")
    assert stamp == datetime(2026, 9, 21, 13, 0, tzinfo=timezone.utc)


def test_parse_hour_stamp_rejects_other_names():
    with pytest.raises(ValueError):
        parse_hour_stamp("202609211300_acc0060_grs.png")


HEADER_3x4 = GridHeader(ncols=4, nrows=3, xllcorner=0.0, yllcorner=0.0, cellsize=1000.0)


def test_block_slices_zero_half_size_selects_the_containing_cell():
    (sl,) = block_slices(HEADER_3x4, [(1500.0, 500.0)], half_size_m=0)
    grid = np.array(GRID_3x4, dtype=float)
    assert grid[sl].tolist() == [[10.0]]  # bottom row (southmost), second column


def test_block_slices_square_block_covers_expected_cells():
    (sl,) = block_slices(HEADER_3x4, [(2000.0, 1500.0)], half_size_m=1000)
    grid = np.array(GRID_3x4, dtype=float)
    assert grid[sl].tolist() == [[2.0, 3.0], [6.0, 7.0], [10.0, 11.0]]


def test_block_slices_point_outside_grid_is_none():
    assert block_slices(HEADER_3x4, [(10000.0, 10000.0), (-500.0, 500.0)], half_size_m=0) == [None, None]


def test_sample_stack_means_blocks_ignoring_nan_and_all_nan_gives_nan():
    stack = np.array([
        [[1.0, 3.0], [np.nan, 5.0]],
        [[np.nan, np.nan], [np.nan, np.nan]],
    ])
    header = GridHeader(ncols=2, nrows=2, xllcorner=0.0, yllcorner=0.0, cellsize=1000.0)
    slices = block_slices(header, [(1000.0, 1000.0)], half_size_m=1000) + [None]
    out = sample_stack(stack, slices)
    assert out.shape == (2, 2)
    assert out[0, 0] == pytest.approx(3.0)  # mean(1, 3, 5)
    assert math.isnan(out[1, 0])
    assert math.isnan(out[0, 1])  # point outside grid
