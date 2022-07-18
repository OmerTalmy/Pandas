from pandas import IntervalIndex
import pandas._testing as tm


class TestPickle:
    def test_pickle_round_trip_inclusive(self, closed):
        # https://github.com/pandas-dev/pandas/issues/35658
        idx = IntervalIndex.from_tuples([(1, 2), (2, 3)], inclusive=closed)
        result = tm.round_trip_pickle(idx)
        tm.assert_index_equal(result, idx)
