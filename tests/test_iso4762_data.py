import pytest

from standardparts.standards.iso4762_data import LENGTH_SERIES, SIZES

# ls min / lg max values printed in ISO 4762:2004 Table 1 (M1.6 to M12).
# Every length of a size below its first entry is threaded to the head.
TABLE_1 = {
    "M2": {20: (2, 4)},
    "M2.5": {25: (5.75, 8)},
    "M3": {25: (4.5, 7), 30: (9.5, 12)},
    "M4": {30: (6.5, 10), 35: (11.5, 15), 40: (16.5, 20)},
    "M5": {30: (4, 8), 35: (9, 13), 40: (14, 18), 45: (19, 23), 50: (24, 28)},
    "M6": {35: (6, 11), 40: (11, 16), 45: (16, 21), 50: (21, 26), 55: (26, 31), 60: (31, 36)},
    "M8": {40: (5.75, 12), 45: (10.75, 17), 50: (15.75, 22), 55: (20.75, 27),
           60: (25.75, 32), 65: (30.75, 37), 70: (35.75, 42), 80: (45.75, 52)},
    "M10": {45: (5.5, 13), 50: (10.5, 18), 55: (15.5, 23), 60: (20.5, 28), 65: (25.5, 33),
            70: (30.5, 38), 80: (40.5, 48), 90: (50.5, 58), 100: (60.5, 68)},
    "M12": {55: (10.25, 19), 60: (15.25, 24), 65: (20.25, 29), 70: (25.25, 34),
            80: (35.25, 44), 90: (45.25, 54), 100: (55.25, 64), 110: (65.25, 74),
            120: (75.25, 84)},
}


@pytest.mark.parametrize("size", ["M1.6", *TABLE_1])
def test_thread_geometry_matches_table_1(size):
    sd = SIZES[size]
    expected = TABLE_1.get(size, {})
    for l in sd.standard_lengths():
        assert sd.thread_geometry(l) == expected.get(l, (None, None)), (size, l)


def test_lengths_cover_table_1_rows():
    for size, rows in TABLE_1.items():
        assert max(rows) == SIZES[size].l_max


@pytest.mark.parametrize("sd", SIZES.values(), ids=list(SIZES))
def test_size_rows_are_consistent(sd):
    assert sd.k_max == sd.d
    assert sd.dk_min < sd.dk_max < sd.dk_max_knurled
    assert sd.ds_min < sd.d < sd.da_max
    assert sd.d + 2 * sd.r_min <= sd.da_max
    assert sd.dw_min < sd.dk_min
    # e min is close to the corners of an exact hexagon of width s (the
    # standard checks it against s max, so it can sit slightly above).
    assert 0.9 < sd.e_min / (sd.s_nom / 0.8660254) < 1.01
    # Head wall under the socket.
    assert sd.k_max - sd.t_min >= sd.w_min
    assert sd.v_max == pytest.approx(0.1 * sd.d)
    assert sd.l_min in LENGTH_SERIES and sd.l_max in LENGTH_SERIES
