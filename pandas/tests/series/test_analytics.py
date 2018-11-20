# coding=utf-8
# pylint: disable-msg=E1101,W0612

from distutils.version import LooseVersion
from itertools import product
import operator

import numpy as np
from numpy import nan
import pytest

from pandas.compat import PY35, lrange, range
import pandas.util._test_decorators as td

import pandas as pd
from pandas import (
    Categorical, CategoricalIndex, DataFrame, Series, bdate_range, compat,
    date_range, isna, notna)
from pandas.core.index import MultiIndex
from pandas.core.indexes.datetimes import Timestamp
from pandas.core.indexes.timedeltas import Timedelta
import pandas.core.nanops as nanops
import pandas.util.testing as tm
from pandas.util.testing import (
    assert_almost_equal, assert_frame_equal, assert_index_equal,
    assert_series_equal)


class TestSeriesAnalytics(object):

    @pytest.mark.parametrize("use_bottleneck", [True, False])
    @pytest.mark.parametrize("method, unit", [
        ("sum", 0.0),
        ("prod", 1.0)
    ])
    def test_empty(self, method, unit, use_bottleneck):
        with pd.option_context("use_bottleneck", use_bottleneck):
            # GH 9422 / 18921
            # Entirely empty
            s = Series([])
            # NA by default
            result = getattr(s, method)()
            assert result == unit

            # Explicit
            result = getattr(s, method)(min_count=0)
            assert result == unit

            result = getattr(s, method)(min_count=1)
            assert isna(result)

            # Skipna, default
            result = getattr(s, method)(skipna=True)
            result == unit

            # Skipna, explicit
            result = getattr(s, method)(skipna=True, min_count=0)
            assert result == unit

            result = getattr(s, method)(skipna=True, min_count=1)
            assert isna(result)

            # All-NA
            s = Series([np.nan])
            # NA by default
            result = getattr(s, method)()
            assert result == unit

            # Explicit
            result = getattr(s, method)(min_count=0)
            assert result == unit

            result = getattr(s, method)(min_count=1)
            assert isna(result)

            # Skipna, default
            result = getattr(s, method)(skipna=True)
            result == unit

            # skipna, explicit
            result = getattr(s, method)(skipna=True, min_count=0)
            assert result == unit

            result = getattr(s, method)(skipna=True, min_count=1)
            assert isna(result)

            # Mix of valid, empty
            s = Series([np.nan, 1])
            # Default
            result = getattr(s, method)()
            assert result == 1.0

            # Explicit
            result = getattr(s, method)(min_count=0)
            assert result == 1.0

            result = getattr(s, method)(min_count=1)
            assert result == 1.0

            # Skipna
            result = getattr(s, method)(skipna=True)
            assert result == 1.0

            result = getattr(s, method)(skipna=True, min_count=0)
            assert result == 1.0

            result = getattr(s, method)(skipna=True, min_count=1)
            assert result == 1.0

            # GH #844 (changed in 9422)
            df = DataFrame(np.empty((10, 0)))
            assert (getattr(df, method)(1) == unit).all()

            s = pd.Series([1])
            result = getattr(s, method)(min_count=2)
            assert isna(result)

            s = pd.Series([np.nan])
            result = getattr(s, method)(min_count=2)
            assert isna(result)

            s = pd.Series([np.nan, 1])
            result = getattr(s, method)(min_count=2)
            assert isna(result)

    @pytest.mark.parametrize('method, unit', [
        ('sum', 0.0),
        ('prod', 1.0),
    ])
    def test_empty_multi(self, method, unit):
        s = pd.Series([1, np.nan, np.nan, np.nan],
                      index=pd.MultiIndex.from_product([('a', 'b'), (0, 1)]))
        # 1 / 0 by default
        result = getattr(s, method)(level=0)
        expected = pd.Series([1, unit], index=['a', 'b'])
        tm.assert_series_equal(result, expected)

        # min_count=0
        result = getattr(s, method)(level=0, min_count=0)
        expected = pd.Series([1, unit], index=['a', 'b'])
        tm.assert_series_equal(result, expected)

        # min_count=1
        result = getattr(s, method)(level=0, min_count=1)
        expected = pd.Series([1, np.nan], index=['a', 'b'])
        tm.assert_series_equal(result, expected)

    @pytest.mark.parametrize(
        "method", ['mean', 'median', 'std', 'var'])
    def test_ops_consistency_on_empty(self, method):

        # GH 7869
        # consistency on empty

        # float
        result = getattr(Series(dtype=float), method)()
        assert isna(result)

        # timedelta64[ns]
        result = getattr(Series(dtype='m8[ns]'), method)()
        assert result is pd.NaT

    def test_nansum_buglet(self):
        s = Series([1.0, np.nan], index=[0, 1])
        result = np.nansum(s)
        assert_almost_equal(result, 1)

    @pytest.mark.parametrize("use_bottleneck", [True, False])
    def test_sum_overflow(self, use_bottleneck):

        with pd.option_context('use_bottleneck', use_bottleneck):
            # GH 6915
            # overflowing on the smaller int dtypes
            for dtype in ['int32', 'int64']:
                v = np.arange(5000000, dtype=dtype)
                s = Series(v)

                result = s.sum(skipna=False)
                assert int(result) == v.sum(dtype='int64')
                result = s.min(skipna=False)
                assert int(result) == 0
                result = s.max(skipna=False)
                assert int(result) == v[-1]

            for dtype in ['float32', 'float64']:
                v = np.arange(5000000, dtype=dtype)
                s = Series(v)

                result = s.sum(skipna=False)
                assert result == v.sum(dtype=dtype)
                result = s.min(skipna=False)
                assert np.allclose(float(result), 0.0)
                result = s.max(skipna=False)
                assert np.allclose(float(result), v[-1])

    def test_sum(self, string_series):
        self._check_stat_op('sum', np.sum, string_series, check_allna=False)

    def test_sum_inf(self):
        s = Series(np.random.randn(10))
        s2 = s.copy()

        s[5:8] = np.inf
        s2[5:8] = np.nan

        assert np.isinf(s.sum())

        arr = np.random.randn(100, 100).astype('f4')
        arr[:, 2] = np.inf

        with pd.option_context("mode.use_inf_as_na", True):
            assert_almost_equal(s.sum(), s2.sum())

        res = nanops.nansum(arr, axis=1)
        assert np.isinf(res).all()

    def test_mean(self, string_series):
        self._check_stat_op('mean', np.mean, string_series)

    def test_median(self, string_series):
        self._check_stat_op('median', np.median, string_series)

        # test with integers, test failure
        int_ts = Series(np.ones(10, dtype=int), index=lrange(10))
        tm.assert_almost_equal(np.median(int_ts), int_ts.median())

    def test_prod(self, string_series):
        self._check_stat_op('prod', np.prod, string_series)

    def test_min(self, string_series):
        self._check_stat_op('min', np.min, string_series, check_objects=True)

    def test_max(self, string_series):
        self._check_stat_op('max', np.max, string_series, check_objects=True)

    def test_var_std(self, datetime_series, string_series):
        alt = lambda x: np.std(x, ddof=1)
        self._check_stat_op('std', alt, string_series)

        alt = lambda x: np.var(x, ddof=1)
        self._check_stat_op('var', alt, string_series)

        result = datetime_series.std(ddof=4)
        expected = np.std(datetime_series.values, ddof=4)
        assert_almost_equal(result, expected)

        result = datetime_series.var(ddof=4)
        expected = np.var(datetime_series.values, ddof=4)
        assert_almost_equal(result, expected)

        # 1 - element series with ddof=1
        s = datetime_series.iloc[[0]]
        result = s.var(ddof=1)
        assert isna(result)

        result = s.std(ddof=1)
        assert isna(result)

    def test_sem(self, datetime_series, string_series):
        alt = lambda x: np.std(x, ddof=1) / np.sqrt(len(x))
        self._check_stat_op('sem', alt, string_series)

        result = datetime_series.sem(ddof=4)
        expected = np.std(datetime_series.values,
                          ddof=4) / np.sqrt(len(datetime_series.values))
        assert_almost_equal(result, expected)

        # 1 - element series with ddof=1
        s = datetime_series.iloc[[0]]
        result = s.sem(ddof=1)
        assert isna(result)

    @td.skip_if_no_scipy
    def test_skew(self, string_series):
        from scipy.stats import skew
        alt = lambda x: skew(x, bias=False)
        self._check_stat_op('skew', alt, string_series)

        # test corner cases, skew() returns NaN unless there's at least 3
        # values
        min_N = 3
        for i in range(1, min_N + 1):
            s = Series(np.ones(i))
            df = DataFrame(np.ones((i, i)))
            if i < min_N:
                assert np.isnan(s.skew())
                assert np.isnan(df.skew()).all()
            else:
                assert 0 == s.skew()
                assert (df.skew() == 0).all()

    @td.skip_if_no_scipy
    def test_kurt(self, string_series):
        from scipy.stats import kurtosis
        alt = lambda x: kurtosis(x, bias=False)
        self._check_stat_op('kurt', alt, string_series)

        index = MultiIndex(levels=[['bar'], ['one', 'two', 'three'], [0, 1]],
                           codes=[[0, 0, 0, 0, 0, 0], [0, 1, 2, 0, 1, 2],
                                  [0, 1, 0, 1, 0, 1]])
        s = Series(np.random.randn(6), index=index)
        tm.assert_almost_equal(s.kurt(), s.kurt(level=0)['bar'])

        # test corner cases, kurt() returns NaN unless there's at least 4
        # values
        min_N = 4
        for i in range(1, min_N + 1):
            s = Series(np.ones(i))
            df = DataFrame(np.ones((i, i)))
            if i < min_N:
                assert np.isnan(s.kurt())
                assert np.isnan(df.kurt()).all()
            else:
                assert 0 == s.kurt()
                assert (df.kurt() == 0).all()

    def test_describe(self):
        s = Series([0, 1, 2, 3, 4], name='int_data')
        result = s.describe()
        expected = Series([5, 2, s.std(), 0, 1, 2, 3, 4],
                          name='int_data',
                          index=['count', 'mean', 'std', 'min', '25%',
                                 '50%', '75%', 'max'])
        tm.assert_series_equal(result, expected)

        s = Series([True, True, False, False, False], name='bool_data')
        result = s.describe()
        expected = Series([5, 2, False, 3], name='bool_data',
                          index=['count', 'unique', 'top', 'freq'])
        tm.assert_series_equal(result, expected)

        s = Series(['a', 'a', 'b', 'c', 'd'], name='str_data')
        result = s.describe()
        expected = Series([5, 4, 'a', 2], name='str_data',
                          index=['count', 'unique', 'top', 'freq'])
        tm.assert_series_equal(result, expected)

    def test_describe_with_tz(self, tz_naive_fixture):
        # GH 21332
        tz = tz_naive_fixture
        name = str(tz_naive_fixture)
        start = Timestamp(2018, 1, 1)
        end = Timestamp(2018, 1, 5)
        s = Series(date_range(start, end, tz=tz), name=name)
        result = s.describe()
        expected = Series(
            [5, 5, s.value_counts().index[0], 1, start.tz_localize(tz),
             end.tz_localize(tz)
             ],
            name=name,
            index=['count', 'unique', 'top', 'freq', 'first', 'last']
        )
        tm.assert_series_equal(result, expected)

    def test_argsort(self, datetime_series):
        self._check_accum_op('argsort', datetime_series, check_dtype=False)
        argsorted = datetime_series.argsort()
        assert issubclass(argsorted.dtype.type, np.integer)

        # GH 2967 (introduced bug in 0.11-dev I think)
        s = Series([Timestamp('201301%02d' % (i + 1)) for i in range(5)])
        assert s.dtype == 'datetime64[ns]'
        shifted = s.shift(-1)
        assert shifted.dtype == 'datetime64[ns]'
        assert isna(shifted[4])

        result = s.argsort()
        expected = Series(lrange(5), dtype='int64')
        assert_series_equal(result, expected)

        result = shifted.argsort()
        expected = Series(lrange(4) + [-1], dtype='int64')
        assert_series_equal(result, expected)

    def test_argsort_stable(self):
        s = Series(np.random.randint(0, 100, size=10000))
        mindexer = s.argsort(kind='mergesort')
        qindexer = s.argsort()

        mexpected = np.argsort(s.values, kind='mergesort')
        qexpected = np.argsort(s.values, kind='quicksort')

        tm.assert_series_equal(mindexer, Series(mexpected),
                               check_dtype=False)
        tm.assert_series_equal(qindexer, Series(qexpected),
                               check_dtype=False)
        pytest.raises(AssertionError, tm.assert_numpy_array_equal,
                      qindexer, mindexer)

    def test_cumsum(self, datetime_series):
        self._check_accum_op('cumsum', datetime_series)

    def test_cumprod(self, datetime_series):
        self._check_accum_op('cumprod', datetime_series)

    def test_cummin(self, datetime_series):
        tm.assert_numpy_array_equal(datetime_series.cummin().values,
                                    np.minimum
                                    .accumulate(np.array(datetime_series)))
        ts = datetime_series.copy()
        ts[::2] = np.NaN
        result = ts.cummin()[1::2]
        expected = np.minimum.accumulate(ts.dropna())

        tm.assert_series_equal(result, expected)

    def test_cummax(self, datetime_series):
        tm.assert_numpy_array_equal(datetime_series.cummax().values,
                                    np.maximum
                                    .accumulate(np.array(datetime_series)))
        ts = datetime_series.copy()
        ts[::2] = np.NaN
        result = ts.cummax()[1::2]
        expected = np.maximum.accumulate(ts.dropna())

        tm.assert_series_equal(result, expected)

    def test_cummin_datetime64(self):
        s = pd.Series(pd.to_datetime(['NaT', '2000-1-2', 'NaT', '2000-1-1',
                                      'NaT', '2000-1-3']))

        expected = pd.Series(pd.to_datetime(['NaT', '2000-1-2', 'NaT',
                                             '2000-1-1', 'NaT', '2000-1-1']))
        result = s.cummin(skipna=True)
        tm.assert_series_equal(expected, result)

        expected = pd.Series(pd.to_datetime(
            ['NaT', '2000-1-2', '2000-1-2', '2000-1-1', '2000-1-1', '2000-1-1'
             ]))
        result = s.cummin(skipna=False)
        tm.assert_series_equal(expected, result)

    def test_cummax_datetime64(self):
        s = pd.Series(pd.to_datetime(['NaT', '2000-1-2', 'NaT', '2000-1-1',
                                      'NaT', '2000-1-3']))

        expected = pd.Series(pd.to_datetime(['NaT', '2000-1-2', 'NaT',
                                             '2000-1-2', 'NaT', '2000-1-3']))
        result = s.cummax(skipna=True)
        tm.assert_series_equal(expected, result)

        expected = pd.Series(pd.to_datetime(
            ['NaT', '2000-1-2', '2000-1-2', '2000-1-2', '2000-1-2', '2000-1-3'
             ]))
        result = s.cummax(skipna=False)
        tm.assert_series_equal(expected, result)

    def test_cummin_timedelta64(self):
        s = pd.Series(pd.to_timedelta(['NaT',
                                       '2 min',
                                       'NaT',
                                       '1 min',
                                       'NaT',
                                       '3 min', ]))

        expected = pd.Series(pd.to_timedelta(['NaT',
                                              '2 min',
                                              'NaT',
                                              '1 min',
                                              'NaT',
                                              '1 min', ]))
        result = s.cummin(skipna=True)
        tm.assert_series_equal(expected, result)

        expected = pd.Series(pd.to_timedelta(['NaT',
                                              '2 min',
                                              '2 min',
                                              '1 min',
                                              '1 min',
                                              '1 min', ]))
        result = s.cummin(skipna=False)
        tm.assert_series_equal(expected, result)

    def test_cummax_timedelta64(self):
        s = pd.Series(pd.to_timedelta(['NaT',
                                       '2 min',
                                       'NaT',
                                       '1 min',
                                       'NaT',
                                       '3 min', ]))

        expected = pd.Series(pd.to_timedelta(['NaT',
                                              '2 min',
                                              'NaT',
                                              '2 min',
                                              'NaT',
                                              '3 min', ]))
        result = s.cummax(skipna=True)
        tm.assert_series_equal(expected, result)

        expected = pd.Series(pd.to_timedelta(['NaT',
                                              '2 min',
                                              '2 min',
                                              '2 min',
                                              '2 min',
                                              '3 min', ]))
        result = s.cummax(skipna=False)
        tm.assert_series_equal(expected, result)

    def test_npdiff(self):
        pytest.skip("skipping due to Series no longer being an "
                    "ndarray")

        # no longer works as the return type of np.diff is now nd.array
        s = Series(np.arange(5))

        r = np.diff(s)
        assert_series_equal(Series([nan, 0, 0, 0, nan]), r)

    def _check_stat_op(self, name, alternate, string_series_,
                       check_objects=False, check_allna=False):

        with pd.option_context('use_bottleneck', False):
            f = getattr(Series, name)

            # add some NaNs
            string_series_[5:15] = np.NaN

            # idxmax, idxmin, min, and max are valid for dates
            if name not in ['max', 'min']:
                ds = Series(date_range('1/1/2001', periods=10))
                pytest.raises(TypeError, f, ds)

            # skipna or no
            assert notna(f(string_series_))
            assert isna(f(string_series_, skipna=False))

            # check the result is correct
            nona = string_series_.dropna()
            assert_almost_equal(f(nona), alternate(nona.values))
            assert_almost_equal(f(string_series_), alternate(nona.values))

            allna = string_series_ * nan

            if check_allna:
                assert np.isnan(f(allna))

            # dtype=object with None, it works!
            s = Series([1, 2, 3, None, 5])
            f(s)

            # 2888
            items = [0]
            items.extend(lrange(2 ** 40, 2 ** 40 + 1000))
            s = Series(items, dtype='int64')
            assert_almost_equal(float(f(s)), float(alternate(s.values)))

            # check date range
            if check_objects:
                s = Series(bdate_range('1/1/2000', periods=10))
                res = f(s)
                exp = alternate(s)
                assert res == exp

            # check on string data
            if name not in ['sum', 'min', 'max']:
                pytest.raises(TypeError, f, Series(list('abc')))

            # Invalid axis.
            pytest.raises(ValueError, f, string_series_, axis=1)

            # Unimplemented numeric_only parameter.
            if 'numeric_only' in compat.signature(f).args:
                with pytest.raises(NotImplementedError, match=name):
                    f(string_series_, numeric_only=True)

    def _check_accum_op(self, name, datetime_series_, check_dtype=True):
        func = getattr(np, name)
        tm.assert_numpy_array_equal(func(datetime_series_).values,
                                    func(np.array(datetime_series_)),
                                    check_dtype=check_dtype)

        # with missing values
        ts = datetime_series_.copy()
        ts[::2] = np.NaN

        result = func(ts)[1::2]
        expected = func(np.array(ts.dropna()))

        tm.assert_numpy_array_equal(result.values, expected,
                                    check_dtype=False)

    def test_compress(self):
        cond = [True, False, True, False, False]
        s = Series([1, -1, 5, 8, 7],
                   index=list('abcde'), name='foo')
        expected = Series(s.values.compress(cond),
                          index=list('ac'), name='foo')
        with tm.assert_produces_warning(FutureWarning):
            result = s.compress(cond)
        tm.assert_series_equal(result, expected)

    def test_numpy_compress(self):
        cond = [True, False, True, False, False]
        s = Series([1, -1, 5, 8, 7],
                   index=list('abcde'), name='foo')
        expected = Series(s.values.compress(cond),
                          index=list('ac'), name='foo')
        with tm.assert_produces_warning(FutureWarning, check_stacklevel=False):
            tm.assert_series_equal(np.compress(cond, s), expected)

        with tm.assert_produces_warning(FutureWarning, check_stacklevel=False):
            msg = "the 'axis' parameter is not supported"
            with pytest.raises(ValueError, match=msg):
                np.compress(cond, s, axis=1)

            msg = "the 'out' parameter is not supported"
            with pytest.raises(ValueError, match=msg):
                np.compress(cond, s, out=s)

    def test_round(self, datetime_series):
        datetime_series.index.name = "index_name"
        result = datetime_series.round(2)
        expected = Series(np.round(datetime_series.values, 2),
                          index=datetime_series.index, name='ts')
        assert_series_equal(result, expected)
        assert result.name == datetime_series.name

    def test_numpy_round(self):
        # See gh-12600
        s = Series([1.53, 1.36, 0.06])
        out = np.round(s, decimals=0)
        expected = Series([2., 1., 0.])
        assert_series_equal(out, expected)

        msg = "the 'out' parameter is not supported"
        with pytest.raises(ValueError, match=msg):
            np.round(s, decimals=0, out=s)

    def test_built_in_round(self):
        if not compat.PY3:
            pytest.skip(
                'build in round cannot be overridden prior to Python 3')

        s = Series([1.123, 2.123, 3.123], index=lrange(3))
        result = round(s)
        expected_rounded0 = Series([1., 2., 3.], index=lrange(3))
        tm.assert_series_equal(result, expected_rounded0)

        decimals = 2
        expected_rounded = Series([1.12, 2.12, 3.12], index=lrange(3))
        result = round(s, decimals)
        tm.assert_series_equal(result, expected_rounded)

    def test_prod_numpy16_bug(self):
        s = Series([1., 1., 1.], index=lrange(3))
        result = s.prod()

        assert not isinstance(result, Series)

    def test_all_any(self):
        ts = tm.makeTimeSeries()
        bool_series = ts > 0
        assert not bool_series.all()
        assert bool_series.any()

        # Alternative types, with implicit 'object' dtype.
        s = Series(['abc', True])
        assert 'abc' == s.any()  # 'abc' || True => 'abc'

    def test_all_any_params(self):
        # Check skipna, with implicit 'object' dtype.
        s1 = Series([np.nan, True])
        s2 = Series([np.nan, False])
        assert s1.all(skipna=False)  # nan && True => True
        assert s1.all(skipna=True)
        assert np.isnan(s2.any(skipna=False))  # nan || False => nan
        assert not s2.any(skipna=True)

        # Check level.
        s = pd.Series([False, False, True, True, False, True],
                      index=[0, 0, 1, 1, 2, 2])
        assert_series_equal(s.all(level=0), Series([False, True, False]))
        assert_series_equal(s.any(level=0), Series([False, True, True]))

        # bool_only is not implemented with level option.
        pytest.raises(NotImplementedError, s.any, bool_only=True, level=0)
        pytest.raises(NotImplementedError, s.all, bool_only=True, level=0)

        # bool_only is not implemented alone.
        pytest.raises(NotImplementedError, s.any, bool_only=True)
        pytest.raises(NotImplementedError, s.all, bool_only=True)

    @td.skip_if_no_scipy
    def test_corr(self, datetime_series):
        import scipy.stats as stats

        # full overlap
        tm.assert_almost_equal(datetime_series.corr(datetime_series), 1)

        # partial overlap
        tm.assert_almost_equal(datetime_series[:15].corr(datetime_series[5:]),
                               1)

        assert isna(datetime_series[:15].corr(datetime_series[5:],
                    min_periods=12))

        ts1 = datetime_series[:15].reindex(datetime_series.index)
        ts2 = datetime_series[5:].reindex(datetime_series.index)
        assert isna(ts1.corr(ts2, min_periods=12))

        # No overlap
        assert np.isnan(datetime_series[::2].corr(datetime_series[1::2]))

        # all NA
        cp = datetime_series[:10].copy()
        cp[:] = np.nan
        assert isna(cp.corr(cp))

        A = tm.makeTimeSeries()
        B = tm.makeTimeSeries()
        result = A.corr(B)
        expected, _ = stats.pearsonr(A, B)
        tm.assert_almost_equal(result, expected)

    @td.skip_if_no_scipy
    def test_corr_rank(self):
        import scipy
        import scipy.stats as stats

        # kendall and spearman
        A = tm.makeTimeSeries()
        B = tm.makeTimeSeries()
        A[-5:] = A[:5]
        result = A.corr(B, method='kendall')
        expected = stats.kendalltau(A, B)[0]
        tm.assert_almost_equal(result, expected)

        result = A.corr(B, method='spearman')
        expected = stats.spearmanr(A, B)[0]
        tm.assert_almost_equal(result, expected)

        # these methods got rewritten in 0.8
        if LooseVersion(scipy.__version__) < LooseVersion('0.9'):
            pytest.skip("skipping corr rank because of scipy version "
                        "{0}".format(scipy.__version__))

        # results from R
        A = Series(
            [-0.89926396, 0.94209606, -1.03289164, -0.95445587, 0.76910310, -
             0.06430576, -2.09704447, 0.40660407, -0.89926396, 0.94209606])
        B = Series(
            [-1.01270225, -0.62210117, -1.56895827, 0.59592943, -0.01680292,
             1.17258718, -1.06009347, -0.10222060, -0.89076239, 0.89372375])
        kexp = 0.4319297
        sexp = 0.5853767
        tm.assert_almost_equal(A.corr(B, method='kendall'), kexp)
        tm.assert_almost_equal(A.corr(B, method='spearman'), sexp)

    def test_corr_invalid_method(self):
        # GH PR #22298
        s1 = pd.Series(np.random.randn(10))
        s2 = pd.Series(np.random.randn(10))
        msg = ("method must be either 'pearson', 'spearman', "
               "or 'kendall'")
        with pytest.raises(ValueError, match=msg):
            s1.corr(s2, method="____")

    def test_corr_callable_method(self, datetime_series):
        # simple correlation example
        # returns 1 if exact equality, 0 otherwise
        my_corr = lambda a, b: 1. if (a == b).all() else 0.

        # simple example
        s1 = Series([1, 2, 3, 4, 5])
        s2 = Series([5, 4, 3, 2, 1])
        expected = 0
        tm.assert_almost_equal(
            s1.corr(s2, method=my_corr),
            expected)

        # full overlap
        tm.assert_almost_equal(datetime_series.corr(
            datetime_series, method=my_corr), 1.)

        # partial overlap
        tm.assert_almost_equal(datetime_series[:15].corr(
            datetime_series[5:], method=my_corr), 1.)

        # No overlap
        assert np.isnan(datetime_series[::2].corr(
            datetime_series[1::2], method=my_corr))

        # dataframe example
        df = pd.DataFrame([s1, s2])
        expected = pd.DataFrame([
            {0: 1., 1: 0}, {0: 0, 1: 1.}])
        tm.assert_almost_equal(
            df.transpose().corr(method=my_corr), expected)

    def test_cov(self, datetime_series):
        # full overlap
        tm.assert_almost_equal(datetime_series.cov(datetime_series),
                               datetime_series.std() ** 2)

        # partial overlap
        tm.assert_almost_equal(datetime_series[:15].cov(datetime_series[5:]),
                               datetime_series[5:15].std() ** 2)

        # No overlap
        assert np.isnan(datetime_series[::2].cov(datetime_series[1::2]))

        # all NA
        cp = datetime_series[:10].copy()
        cp[:] = np.nan
        assert isna(cp.cov(cp))

        # min_periods
        assert isna(datetime_series[:15].cov(datetime_series[5:],
                    min_periods=12))

        ts1 = datetime_series[:15].reindex(datetime_series.index)
        ts2 = datetime_series[5:].reindex(datetime_series.index)
        assert isna(ts1.cov(ts2, min_periods=12))

    def test_count(self, datetime_series):
        assert datetime_series.count() == len(datetime_series)

        datetime_series[::2] = np.NaN

        assert datetime_series.count() == np.isfinite(datetime_series).sum()

        mi = MultiIndex.from_arrays([list('aabbcc'), [1, 2, 2, nan, 1, 2]])
        ts = Series(np.arange(len(mi)), index=mi)

        left = ts.count(level=1)
        right = Series([2, 3, 1], index=[1, 2, nan])
        assert_series_equal(left, right)

        ts.iloc[[0, 3, 5]] = nan
        assert_series_equal(ts.count(level=1), right - 1)

    def test_dot(self):
        a = Series(np.random.randn(4), index=['p', 'q', 'r', 's'])
        b = DataFrame(np.random.randn(3, 4), index=['1', '2', '3'],
                      columns=['p', 'q', 'r', 's']).T

        result = a.dot(b)
        expected = Series(np.dot(a.values, b.values), index=['1', '2', '3'])
        assert_series_equal(result, expected)

        # Check index alignment
        b2 = b.reindex(index=reversed(b.index))
        result = a.dot(b)
        assert_series_equal(result, expected)

        # Check ndarray argument
        result = a.dot(b.values)
        assert np.all(result == expected.values)
        assert_almost_equal(a.dot(b['2'].values), expected['2'])

        # Check series argument
        assert_almost_equal(a.dot(b['1']), expected['1'])
        assert_almost_equal(a.dot(b2['1']), expected['1'])

        pytest.raises(Exception, a.dot, a.values[:3])
        pytest.raises(ValueError, a.dot, b.T)

    @pytest.mark.skipif(not PY35,
                        reason='matmul supported for Python>=3.5')
    def test_matmul(self):
        # matmul test is for GH #10259
        a = Series(np.random.randn(4), index=['p', 'q', 'r', 's'])
        b = DataFrame(np.random.randn(3, 4), index=['1', '2', '3'],
                      columns=['p', 'q', 'r', 's']).T

        # Series @ DataFrame
        result = operator.matmul(a, b)
        expected = Series(np.dot(a.values, b.values), index=['1', '2', '3'])
        assert_series_equal(result, expected)

        # DataFrame @ Series
        result = operator.matmul(b.T, a)
        expected = Series(np.dot(b.T.values, a.T.values),
                          index=['1', '2', '3'])
        assert_series_equal(result, expected)

        # Series @ Series
        result = operator.matmul(a, a)
        expected = np.dot(a.values, a.values)
        assert_almost_equal(result, expected)

        # GH 21530
        # vector (1D np.array) @ Series (__rmatmul__)
        result = operator.matmul(a.values, a)
        expected = np.dot(a.values, a.values)
        assert_almost_equal(result, expected)

        # GH 21530
        # vector (1D list) @ Series (__rmatmul__)
        result = operator.matmul(a.values.tolist(), a)
        expected = np.dot(a.values, a.values)
        assert_almost_equal(result, expected)

        # GH 21530
        # matrix (2D np.array) @ Series (__rmatmul__)
        result = operator.matmul(b.T.values, a)
        expected = np.dot(b.T.values, a.values)
        assert_almost_equal(result, expected)

        # GH 21530
        # matrix (2D nested lists) @ Series (__rmatmul__)
        result = operator.matmul(b.T.values.tolist(), a)
        expected = np.dot(b.T.values, a.values)
        assert_almost_equal(result, expected)

        # mixed dtype DataFrame @ Series
        a['p'] = int(a.p)
        result = operator.matmul(b.T, a)
        expected = Series(np.dot(b.T.values, a.T.values),
                          index=['1', '2', '3'])
        assert_series_equal(result, expected)

        # different dtypes DataFrame @ Series
        a = a.astype(int)
        result = operator.matmul(b.T, a)
        expected = Series(np.dot(b.T.values, a.T.values),
                          index=['1', '2', '3'])
        assert_series_equal(result, expected)

        pytest.raises(Exception, a.dot, a.values[:3])
        pytest.raises(ValueError, a.dot, b.T)

    def test_clip(self, datetime_series):
        val = datetime_series.median()

        with tm.assert_produces_warning(FutureWarning):
            assert datetime_series.clip_lower(val).min() == val
        with tm.assert_produces_warning(FutureWarning):
            assert datetime_series.clip_upper(val).max() == val

        assert datetime_series.clip(lower=val).min() == val
        assert datetime_series.clip(upper=val).max() == val

        result = datetime_series.clip(-0.5, 0.5)
        expected = np.clip(datetime_series, -0.5, 0.5)
        assert_series_equal(result, expected)
        assert isinstance(expected, Series)

    def test_clip_types_and_nulls(self):

        sers = [Series([np.nan, 1.0, 2.0, 3.0]), Series([None, 'a', 'b', 'c']),
                Series(pd.to_datetime(
                    [np.nan, 1, 2, 3], unit='D'))]

        for s in sers:
            thresh = s[2]
            with tm.assert_produces_warning(FutureWarning):
                lower = s.clip_lower(thresh)
            with tm.assert_produces_warning(FutureWarning):
                upper = s.clip_upper(thresh)
            assert lower[notna(lower)].min() == thresh
            assert upper[notna(upper)].max() == thresh
            assert list(isna(s)) == list(isna(lower))
            assert list(isna(s)) == list(isna(upper))

    def test_clip_with_na_args(self):
        """Should process np.nan argument as None """
        # GH # 17276
        s = Series([1, 2, 3])

        assert_series_equal(s.clip(np.nan), Series([1, 2, 3]))
        assert_series_equal(s.clip(upper=np.nan, lower=np.nan),
                            Series([1, 2, 3]))

        # GH #19992
        assert_series_equal(s.clip(lower=[0, 4, np.nan]),
                            Series([1, 4, np.nan]))
        assert_series_equal(s.clip(upper=[1, np.nan, 1]),
                            Series([1, np.nan, 1]))

    def test_clip_against_series(self):
        # GH #6966

        s = Series([1.0, 1.0, 4.0])
        threshold = Series([1.0, 2.0, 3.0])

        with tm.assert_produces_warning(FutureWarning):
            assert_series_equal(s.clip_lower(threshold),
                                Series([1.0, 2.0, 4.0]))
        with tm.assert_produces_warning(FutureWarning):
            assert_series_equal(s.clip_upper(threshold),
                                Series([1.0, 1.0, 3.0]))

        lower = Series([1.0, 2.0, 3.0])
        upper = Series([1.5, 2.5, 3.5])

        assert_series_equal(s.clip(lower, upper), Series([1.0, 2.0, 3.5]))
        assert_series_equal(s.clip(1.5, upper), Series([1.5, 1.5, 3.5]))

    @pytest.mark.parametrize("inplace", [True, False])
    @pytest.mark.parametrize("upper", [[1, 2, 3], np.asarray([1, 2, 3])])
    def test_clip_against_list_like(self, inplace, upper):
        # GH #15390
        original = pd.Series([5, 6, 7])
        result = original.clip(upper=upper, inplace=inplace)
        expected = pd.Series([1, 2, 3])

        if inplace:
            result = original
        tm.assert_series_equal(result, expected, check_exact=True)

    def test_clip_with_datetimes(self):

        # GH 11838
        # naive and tz-aware datetimes

        t = Timestamp('2015-12-01 09:30:30')
        s = Series([Timestamp('2015-12-01 09:30:00'),
                    Timestamp('2015-12-01 09:31:00')])
        result = s.clip(upper=t)
        expected = Series([Timestamp('2015-12-01 09:30:00'),
                           Timestamp('2015-12-01 09:30:30')])
        assert_series_equal(result, expected)

        t = Timestamp('2015-12-01 09:30:30', tz='US/Eastern')
        s = Series([Timestamp('2015-12-01 09:30:00', tz='US/Eastern'),
                    Timestamp('2015-12-01 09:31:00', tz='US/Eastern')])
        result = s.clip(upper=t)
        expected = Series([Timestamp('2015-12-01 09:30:00', tz='US/Eastern'),
                           Timestamp('2015-12-01 09:30:30', tz='US/Eastern')])
        assert_series_equal(result, expected)

    def test_cummethods_bool(self):
        # GH 6270

        a = pd.Series([False, False, False, True, True, False, False])
        b = ~a
        c = pd.Series([False] * len(b))
        d = ~c
        methods = {'cumsum': np.cumsum,
                   'cumprod': np.cumprod,
                   'cummin': np.minimum.accumulate,
                   'cummax': np.maximum.accumulate}
        args = product((a, b, c, d), methods)
        for s, method in args:
            expected = Series(methods[method](s.values))
            result = getattr(s, method)()
            assert_series_equal(result, expected)

        e = pd.Series([False, True, nan, False])
        cse = pd.Series([0, 1, nan, 1], dtype=object)
        cpe = pd.Series([False, 0, nan, 0])
        cmin = pd.Series([False, False, nan, False])
        cmax = pd.Series([False, True, nan, True])
        expecteds = {'cumsum': cse,
                     'cumprod': cpe,
                     'cummin': cmin,
                     'cummax': cmax}

        for method in methods:
            res = getattr(e, method)()
            assert_series_equal(res, expecteds[method])

    def test_isin(self):
        s = Series(['A', 'B', 'C', 'a', 'B', 'B', 'A', 'C'])

        result = s.isin(['A', 'C'])
        expected = Series([True, False, True, False, False, False, True, True])
        assert_series_equal(result, expected)

        # GH: 16012
        # This specific issue has to have a series over 1e6 in len, but the
        # comparison array (in_list) must be large enough so that numpy doesn't
        # do a manual masking trick that will avoid this issue altogether
        s = Series(list('abcdefghijk' * 10 ** 5))
        # If numpy doesn't do the manual comparison/mask, these
        # unorderable mixed types are what cause the exception in numpy
        in_list = [-1, 'a', 'b', 'G', 'Y', 'Z', 'E',
                   'K', 'E', 'S', 'I', 'R', 'R'] * 6

        assert s.isin(in_list).sum() == 200000

    def test_isin_with_string_scalar(self):
        # GH4763
        s = Series(['A', 'B', 'C', 'a', 'B', 'B', 'A', 'C'])
        with pytest.raises(TypeError):
            s.isin('a')

        with pytest.raises(TypeError):
            s = Series(['aaa', 'b', 'c'])
            s.isin('aaa')

    def test_isin_with_i8(self):
        # GH 5021

        expected = Series([True, True, False, False, False])
        expected2 = Series([False, True, False, False, False])

        # datetime64[ns]
        s = Series(date_range('jan-01-2013', 'jan-05-2013'))

        result = s.isin(s[0:2])
        assert_series_equal(result, expected)

        result = s.isin(s[0:2].values)
        assert_series_equal(result, expected)

        # fails on dtype conversion in the first place
        result = s.isin(s[0:2].values.astype('datetime64[D]'))
        assert_series_equal(result, expected)

        result = s.isin([s[1]])
        assert_series_equal(result, expected2)

        result = s.isin([np.datetime64(s[1])])
        assert_series_equal(result, expected2)

        result = s.isin(set(s[0:2]))
        assert_series_equal(result, expected)

        # timedelta64[ns]
        s = Series(pd.to_timedelta(lrange(5), unit='d'))
        result = s.isin(s[0:2])
        assert_series_equal(result, expected)

    @pytest.mark.parametrize("empty", [[], Series(), np.array([])])
    def test_isin_empty(self, empty):
        # see gh-16991
        s = Series(["a", "b"])
        expected = Series([False, False])

        result = s.isin(empty)
        tm.assert_series_equal(expected, result)

    def test_timedelta64_analytics(self):
        from pandas import date_range

        # index min/max
        td = Series(date_range('2012-1-1', periods=3, freq='D')) - \
            Timestamp('20120101')

        result = td.idxmin()
        assert result == 0

        result = td.idxmax()
        assert result == 2

        # GH 2982
        # with NaT
        td[0] = np.nan

        result = td.idxmin()
        assert result == 1

        result = td.idxmax()
        assert result == 2

        # abs
        s1 = Series(date_range('20120101', periods=3))
        s2 = Series(date_range('20120102', periods=3))
        expected = Series(s2 - s1)

        # this fails as numpy returns timedelta64[us]
        # result = np.abs(s1-s2)
        # assert_frame_equal(result,expected)

        result = (s1 - s2).abs()
        assert_series_equal(result, expected)

        # max/min
        result = td.max()
        expected = Timedelta('2 days')
        assert result == expected

        result = td.min()
        expected = Timedelta('1 days')
        assert result == expected

    def test_idxmin(self, string_series):
        # test idxmin
        # _check_stat_op approach can not be used here because of isna check.

        # add some NaNs
        string_series[5:15] = np.NaN

        # skipna or no
        assert string_series[string_series.idxmin()] == string_series.min()
        assert isna(string_series.idxmin(skipna=False))

        # no NaNs
        nona = string_series.dropna()
        assert nona[nona.idxmin()] == nona.min()
        assert (nona.index.values.tolist().index(nona.idxmin()) ==
                nona.values.argmin())

        # all NaNs
        allna = string_series * nan
        assert isna(allna.idxmin())

        # datetime64[ns]
        from pandas import date_range
        s = Series(date_range('20130102', periods=6))
        result = s.idxmin()
        assert result == 0

        s[0] = np.nan
        result = s.idxmin()
        assert result == 1

    def test_numpy_argmin_deprecated(self):
        # See gh-16830
        data = np.arange(1, 11)

        s = Series(data, index=data)
        with tm.assert_produces_warning(FutureWarning, check_stacklevel=False):
            # The deprecation of Series.argmin also causes a deprecation
            # warning when calling np.argmin. This behavior is temporary
            # until the implementation of Series.argmin is corrected.
            result = np.argmin(s)

        assert result == 1

        with tm.assert_produces_warning(FutureWarning):
            # argmin is aliased to idxmin
            result = s.argmin()

        assert result == 1

        with tm.assert_produces_warning(FutureWarning,
                                        check_stacklevel=False):
            msg = "the 'out' parameter is not supported"
            with pytest.raises(ValueError, match=msg):
                np.argmin(s, out=data)

    def test_idxmax(self, string_series):
        # test idxmax
        # _check_stat_op approach can not be used here because of isna check.

        # add some NaNs
        string_series[5:15] = np.NaN

        # skipna or no
        assert string_series[string_series.idxmax()] == string_series.max()
        assert isna(string_series.idxmax(skipna=False))

        # no NaNs
        nona = string_series.dropna()
        assert nona[nona.idxmax()] == nona.max()
        assert (nona.index.values.tolist().index(nona.idxmax()) ==
                nona.values.argmax())

        # all NaNs
        allna = string_series * nan
        assert isna(allna.idxmax())

        from pandas import date_range
        s = Series(date_range('20130102', periods=6))
        result = s.idxmax()
        assert result == 5

        s[5] = np.nan
        result = s.idxmax()
        assert result == 4

        # Float64Index
        # GH 5914
        s = pd.Series([1, 2, 3], [1.1, 2.1, 3.1])
        result = s.idxmax()
        assert result == 3.1
        result = s.idxmin()
        assert result == 1.1

        s = pd.Series(s.index, s.index)
        result = s.idxmax()
        assert result == 3.1
        result = s.idxmin()
        assert result == 1.1

    def test_numpy_argmax_deprecated(self):
        # See gh-16830
        data = np.arange(1, 11)

        s = Series(data, index=data)
        with tm.assert_produces_warning(FutureWarning, check_stacklevel=False):
            # The deprecation of Series.argmax also causes a deprecation
            # warning when calling np.argmax. This behavior is temporary
            # until the implementation of Series.argmax is corrected.
            result = np.argmax(s)
        assert result == 10

        with tm.assert_produces_warning(FutureWarning):
            # argmax is aliased to idxmax
            result = s.argmax()

        assert result == 10

        with tm.assert_produces_warning(FutureWarning,
                                        check_stacklevel=False):
            msg = "the 'out' parameter is not supported"
            with pytest.raises(ValueError, match=msg):
                np.argmax(s, out=data)

    def test_ptp(self):
        # GH21614
        N = 1000
        arr = np.random.randn(N)
        ser = Series(arr)
        with tm.assert_produces_warning(FutureWarning, check_stacklevel=False):
            assert np.ptp(ser) == np.ptp(arr)

        # GH11163
        s = Series([3, 5, np.nan, -3, 10])
        with tm.assert_produces_warning(FutureWarning, check_stacklevel=False):
            assert s.ptp() == 13
            assert pd.isna(s.ptp(skipna=False))

        mi = pd.MultiIndex.from_product([['a', 'b'], [1, 2, 3]])
        s = pd.Series([1, np.nan, 7, 3, 5, np.nan], index=mi)

        expected = pd.Series([6, 2], index=['a', 'b'], dtype=np.float64)
        with tm.assert_produces_warning(FutureWarning, check_stacklevel=False):
            tm.assert_series_equal(s.ptp(level=0), expected)

        expected = pd.Series([np.nan, np.nan], index=['a', 'b'])
        with tm.assert_produces_warning(FutureWarning, check_stacklevel=False):
            tm.assert_series_equal(s.ptp(level=0, skipna=False), expected)

        with pytest.raises(ValueError):
            with tm.assert_produces_warning(FutureWarning,
                                            check_stacklevel=False):
                s.ptp(axis=1)

        s = pd.Series(['a', 'b', 'c', 'd', 'e'])
        with pytest.raises(TypeError):
            with tm.assert_produces_warning(FutureWarning,
                                            check_stacklevel=False):
                s.ptp()

        with pytest.raises(NotImplementedError):
            with tm.assert_produces_warning(FutureWarning,
                                            check_stacklevel=False):
                s.ptp(numeric_only=True)

    def test_empty_timeseries_redections_return_nat(self):
        # covers #11245
        for dtype in ('m8[ns]', 'm8[ns]', 'M8[ns]', 'M8[ns, UTC]'):
            assert Series([], dtype=dtype).min() is pd.NaT
            assert Series([], dtype=dtype).max() is pd.NaT

    def test_repeat(self):
        s = Series(np.random.randn(3), index=['a', 'b', 'c'])

        reps = s.repeat(5)
        exp = Series(s.values.repeat(5), index=s.index.values.repeat(5))
        assert_series_equal(reps, exp)

        to_rep = [2, 3, 4]
        reps = s.repeat(to_rep)
        exp = Series(s.values.repeat(to_rep),
                     index=s.index.values.repeat(to_rep))
        assert_series_equal(reps, exp)

    def test_numpy_repeat(self):
        s = Series(np.arange(3), name='x')
        expected = Series(s.values.repeat(2), name='x',
                          index=s.index.values.repeat(2))
        assert_series_equal(np.repeat(s, 2), expected)

        msg = "the 'axis' parameter is not supported"
        with pytest.raises(ValueError, match=msg):
            np.repeat(s, 2, axis=0)

    def test_searchsorted(self):
        s = Series([1, 2, 3])

        result = s.searchsorted(1, side='left')
        assert tm.is_scalar(result)
        assert result == 0

        result = s.searchsorted(1, side='right')
        assert tm.is_scalar(result)
        assert result == 1

    def test_searchsorted_numeric_dtypes_scalar(self):
        s = Series([1, 2, 90, 1000, 3e9])
        r = s.searchsorted(30)
        assert tm.is_scalar(r)
        assert r == 2

        r = s.searchsorted([30])
        e = np.array([2], dtype=np.intp)
        tm.assert_numpy_array_equal(r, e)

    def test_searchsorted_numeric_dtypes_vector(self):
        s = Series([1, 2, 90, 1000, 3e9])
        r = s.searchsorted([91, 2e6])
        e = np.array([3, 4], dtype=np.intp)
        tm.assert_numpy_array_equal(r, e)

    def test_search_sorted_datetime64_scalar(self):
        s = Series(pd.date_range('20120101', periods=10, freq='2D'))
        v = pd.Timestamp('20120102')
        r = s.searchsorted(v)
        assert tm.is_scalar(r)
        assert r == 1

    def test_search_sorted_datetime64_list(self):
        s = Series(pd.date_range('20120101', periods=10, freq='2D'))
        v = [pd.Timestamp('20120102'), pd.Timestamp('20120104')]
        r = s.searchsorted(v)
        e = np.array([1, 2], dtype=np.intp)
        tm.assert_numpy_array_equal(r, e)

    def test_searchsorted_sorter(self):
        # GH8490
        s = Series([3, 1, 2])
        r = s.searchsorted([0, 3], sorter=np.argsort(s))
        e = np.array([0, 2], dtype=np.intp)
        tm.assert_numpy_array_equal(r, e)

    def test_is_monotonic(self):

        s = Series(np.random.randint(0, 10, size=1000))
        assert not s.is_monotonic
        s = Series(np.arange(1000))
        assert s.is_monotonic is True
        assert s.is_monotonic_increasing is True
        s = Series(np.arange(1000, 0, -1))
        assert s.is_monotonic_decreasing is True

        s = Series(pd.date_range('20130101', periods=10))
        assert s.is_monotonic is True
        assert s.is_monotonic_increasing is True
        s = Series(list(reversed(s.tolist())))
        assert s.is_monotonic is False
        assert s.is_monotonic_decreasing is True

    def test_sort_index_level(self):
        mi = MultiIndex.from_tuples([[1, 1, 3], [1, 1, 1]], names=list('ABC'))
        s = Series([1, 2], mi)
        backwards = s.iloc[[1, 0]]

        res = s.sort_index(level='A')
        assert_series_equal(backwards, res)

        res = s.sort_index(level=['A', 'B'])
        assert_series_equal(backwards, res)

        res = s.sort_index(level='A', sort_remaining=False)
        assert_series_equal(s, res)

        res = s.sort_index(level=['A', 'B'], sort_remaining=False)
        assert_series_equal(s, res)

    def test_apply_categorical(self):
        values = pd.Categorical(list('ABBABCD'), categories=list('DCBA'),
                                ordered=True)
        s = pd.Series(values, name='XX', index=list('abcdefg'))
        result = s.apply(lambda x: x.lower())

        # should be categorical dtype when the number of categories are
        # the same
        values = pd.Categorical(list('abbabcd'), categories=list('dcba'),
                                ordered=True)
        exp = pd.Series(values, name='XX', index=list('abcdefg'))
        tm.assert_series_equal(result, exp)
        tm.assert_categorical_equal(result.values, exp.values)

        result = s.apply(lambda x: 'A')
        exp = pd.Series(['A'] * 7, name='XX', index=list('abcdefg'))
        tm.assert_series_equal(result, exp)
        assert result.dtype == np.object

    def test_shift_int(self, datetime_series):
        ts = datetime_series.astype(int)
        shifted = ts.shift(1)
        expected = ts.astype(float).shift(1)
        assert_series_equal(shifted, expected)

    def test_shift_categorical(self):
        # GH 9416
        s = pd.Series(['a', 'b', 'c', 'd'], dtype='category')

        assert_series_equal(s.iloc[:-1], s.shift(1).shift(-1).dropna())

        sp1 = s.shift(1)
        assert_index_equal(s.index, sp1.index)
        assert np.all(sp1.values.codes[:1] == -1)
        assert np.all(s.values.codes[:-1] == sp1.values.codes[1:])

        sn2 = s.shift(-2)
        assert_index_equal(s.index, sn2.index)
        assert np.all(sn2.values.codes[-2:] == -1)
        assert np.all(s.values.codes[2:] == sn2.values.codes[:-2])

        assert_index_equal(s.values.categories, sp1.values.categories)
        assert_index_equal(s.values.categories, sn2.values.categories)

    def test_unstack(self):
        from numpy import nan

        index = MultiIndex(levels=[['bar', 'foo'], ['one', 'three', 'two']],
                           codes=[[1, 1, 0, 0], [0, 1, 0, 2]])

        s = Series(np.arange(4.), index=index)
        unstacked = s.unstack()

        expected = DataFrame([[2., nan, 3.], [0., 1., nan]],
                             index=['bar', 'foo'],
                             columns=['one', 'three', 'two'])

        assert_frame_equal(unstacked, expected)

        unstacked = s.unstack(level=0)
        assert_frame_equal(unstacked, expected.T)

        index = MultiIndex(levels=[['bar'], ['one', 'two', 'three'], [0, 1]],
                           codes=[[0, 0, 0, 0, 0, 0], [0, 1, 2, 0, 1, 2],
                                  [0, 1, 0, 1, 0, 1]])
        s = Series(np.random.randn(6), index=index)
        exp_index = MultiIndex(levels=[['one', 'two', 'three'], [0, 1]],
                               codes=[[0, 1, 2, 0, 1, 2], [0, 1, 0, 1, 0, 1]])
        expected = DataFrame({'bar': s.values},
                             index=exp_index).sort_index(level=0)
        unstacked = s.unstack(0).sort_index()
        assert_frame_equal(unstacked, expected)

        # GH5873
        idx = pd.MultiIndex.from_arrays([[101, 102], [3.5, np.nan]])
        ts = pd.Series([1, 2], index=idx)
        left = ts.unstack()
        right = DataFrame([[nan, 1], [2, nan]], index=[101, 102],
                          columns=[nan, 3.5])
        assert_frame_equal(left, right)

        idx = pd.MultiIndex.from_arrays([['cat', 'cat', 'cat', 'dog', 'dog'
                                          ], ['a', 'a', 'b', 'a', 'b'],
                                         [1, 2, 1, 1, np.nan]])
        ts = pd.Series([1.0, 1.1, 1.2, 1.3, 1.4], index=idx)
        right = DataFrame([[1.0, 1.3], [1.1, nan], [nan, 1.4], [1.2, nan]],
                          columns=['cat', 'dog'])
        tpls = [('a', 1), ('a', 2), ('b', nan), ('b', 1)]
        right.index = pd.MultiIndex.from_tuples(tpls)
        assert_frame_equal(ts.unstack(level=0), right)

    def test_value_counts_datetime(self):
        # most dtypes are tested in test_base.py
        values = [pd.Timestamp('2011-01-01 09:00'),
                  pd.Timestamp('2011-01-01 10:00'),
                  pd.Timestamp('2011-01-01 11:00'),
                  pd.Timestamp('2011-01-01 09:00'),
                  pd.Timestamp('2011-01-01 09:00'),
                  pd.Timestamp('2011-01-01 11:00')]

        exp_idx = pd.DatetimeIndex(['2011-01-01 09:00', '2011-01-01 11:00',
                                    '2011-01-01 10:00'])
        exp = pd.Series([3, 2, 1], index=exp_idx, name='xxx')

        s = pd.Series(values, name='xxx')
        tm.assert_series_equal(s.value_counts(), exp)
        # check DatetimeIndex outputs the same result
        idx = pd.DatetimeIndex(values, name='xxx')
        tm.assert_series_equal(idx.value_counts(), exp)

        # normalize
        exp = pd.Series(np.array([3., 2., 1]) / 6.,
                        index=exp_idx, name='xxx')
        tm.assert_series_equal(s.value_counts(normalize=True), exp)
        tm.assert_series_equal(idx.value_counts(normalize=True), exp)

    def test_value_counts_datetime_tz(self):
        values = [pd.Timestamp('2011-01-01 09:00', tz='US/Eastern'),
                  pd.Timestamp('2011-01-01 10:00', tz='US/Eastern'),
                  pd.Timestamp('2011-01-01 11:00', tz='US/Eastern'),
                  pd.Timestamp('2011-01-01 09:00', tz='US/Eastern'),
                  pd.Timestamp('2011-01-01 09:00', tz='US/Eastern'),
                  pd.Timestamp('2011-01-01 11:00', tz='US/Eastern')]

        exp_idx = pd.DatetimeIndex(['2011-01-01 09:00', '2011-01-01 11:00',
                                    '2011-01-01 10:00'], tz='US/Eastern')
        exp = pd.Series([3, 2, 1], index=exp_idx, name='xxx')

        s = pd.Series(values, name='xxx')
        tm.assert_series_equal(s.value_counts(), exp)
        idx = pd.DatetimeIndex(values, name='xxx')
        tm.assert_series_equal(idx.value_counts(), exp)

        exp = pd.Series(np.array([3., 2., 1]) / 6.,
                        index=exp_idx, name='xxx')
        tm.assert_series_equal(s.value_counts(normalize=True), exp)
        tm.assert_series_equal(idx.value_counts(normalize=True), exp)

    def test_value_counts_period(self):
        values = [pd.Period('2011-01', freq='M'),
                  pd.Period('2011-02', freq='M'),
                  pd.Period('2011-03', freq='M'),
                  pd.Period('2011-01', freq='M'),
                  pd.Period('2011-01', freq='M'),
                  pd.Period('2011-03', freq='M')]

        exp_idx = pd.PeriodIndex(['2011-01', '2011-03', '2011-02'], freq='M')
        exp = pd.Series([3, 2, 1], index=exp_idx, name='xxx')

        s = pd.Series(values, name='xxx')
        tm.assert_series_equal(s.value_counts(), exp)
        # check DatetimeIndex outputs the same result
        idx = pd.PeriodIndex(values, name='xxx')
        tm.assert_series_equal(idx.value_counts(), exp)

        # normalize
        exp = pd.Series(np.array([3., 2., 1]) / 6.,
                        index=exp_idx, name='xxx')
        tm.assert_series_equal(s.value_counts(normalize=True), exp)
        tm.assert_series_equal(idx.value_counts(normalize=True), exp)

    def test_value_counts_categorical_ordered(self):
        # most dtypes are tested in test_base.py
        values = pd.Categorical([1, 2, 3, 1, 1, 3], ordered=True)

        exp_idx = pd.CategoricalIndex([1, 3, 2], categories=[1, 2, 3],
                                      ordered=True)
        exp = pd.Series([3, 2, 1], index=exp_idx, name='xxx')

        s = pd.Series(values, name='xxx')
        tm.assert_series_equal(s.value_counts(), exp)
        # check CategoricalIndex outputs the same result
        idx = pd.CategoricalIndex(values, name='xxx')
        tm.assert_series_equal(idx.value_counts(), exp)

        # normalize
        exp = pd.Series(np.array([3., 2., 1]) / 6.,
                        index=exp_idx, name='xxx')
        tm.assert_series_equal(s.value_counts(normalize=True), exp)
        tm.assert_series_equal(idx.value_counts(normalize=True), exp)

    def test_value_counts_categorical_not_ordered(self):
        values = pd.Categorical([1, 2, 3, 1, 1, 3], ordered=False)

        exp_idx = pd.CategoricalIndex([1, 3, 2], categories=[1, 2, 3],
                                      ordered=False)
        exp = pd.Series([3, 2, 1], index=exp_idx, name='xxx')

        s = pd.Series(values, name='xxx')
        tm.assert_series_equal(s.value_counts(), exp)
        # check CategoricalIndex outputs the same result
        idx = pd.CategoricalIndex(values, name='xxx')
        tm.assert_series_equal(idx.value_counts(), exp)

        # normalize
        exp = pd.Series(np.array([3., 2., 1]) / 6.,
                        index=exp_idx, name='xxx')
        tm.assert_series_equal(s.value_counts(normalize=True), exp)
        tm.assert_series_equal(idx.value_counts(normalize=True), exp)


main_dtypes = [
    'datetime',
    'datetimetz',
    'timedelta',
    'int8',
    'int16',
    'int32',
    'int64',
    'float32',
    'float64',
    'uint8',
    'uint16',
    'uint32',
    'uint64'
]


@pytest.fixture
def s_main_dtypes():
    """A DataFrame with many dtypes

    * datetime
    * datetimetz
    * timedelta
    * [u]int{8,16,32,64}
    * float{32,64}

    The columns are the name of the dtype.
    """
    df = pd.DataFrame(
        {'datetime': pd.to_datetime(['2003', '2002',
                                     '2001', '2002',
                                     '2005']),
         'datetimetz': pd.to_datetime(
             ['2003', '2002',
              '2001', '2002',
              '2005']).tz_localize('US/Eastern'),
         'timedelta': pd.to_timedelta(['3d', '2d', '1d',
                                       '2d', '5d'])})

    for dtype in ['int8', 'int16', 'int32', 'int64',
                  'float32', 'float64',
                  'uint8', 'uint16', 'uint32', 'uint64']:
        df[dtype] = Series([3, 2, 1, 2, 5], dtype=dtype)

    return df


@pytest.fixture(params=main_dtypes)
def s_main_dtypes_split(request, s_main_dtypes):
    """Each series in s_main_dtypes."""
    return s_main_dtypes[request.param]


class TestMode(object):

    @pytest.mark.parametrize('dropna, expected', [
        (True, Series([], dtype=np.float64)),
        (False, Series([], dtype=np.float64))
    ])
    def test_mode_empty(self, dropna, expected):
        s = Series([], dtype=np.float64)
        result = s.mode(dropna)
        tm.assert_series_equal(result, expected)

    @pytest.mark.parametrize('dropna, data, expected', [
        (True, [1, 1, 1, 2], [1]),
        (True, [1, 1, 1, 2, 3, 3, 3], [1, 3]),
        (False, [1, 1, 1, 2], [1]),
        (False, [1, 1, 1, 2, 3, 3, 3], [1, 3]),
    ])
    @pytest.mark.parametrize(
        'dt',
        list(np.typecodes['AllInteger'] + np.typecodes['Float'])
    )
    def test_mode_numerical(self, dropna, data, expected, dt):
        s = Series(data, dtype=dt)
        result = s.mode(dropna)
        expected = Series(expected, dtype=dt)
        tm.assert_series_equal(result, expected)

    @pytest.mark.parametrize('dropna, expected', [
        (True, [1.0]),
        (False, [1, np.nan]),
    ])
    def test_mode_numerical_nan(self, dropna, expected):
        s = Series([1, 1, 2, np.nan, np.nan])
        result = s.mode(dropna)
        expected = Series(expected)
        tm.assert_series_equal(result, expected)

    @pytest.mark.parametrize('dropna, expected1, expected2, expected3', [
        (True, ['b'], ['bar'], ['nan']),
        (False, ['b'], [np.nan], ['nan'])
    ])
    def test_mode_str_obj(self, dropna, expected1, expected2, expected3):
        # Test string and object types.
        data = ['a'] * 2 + ['b'] * 3

        s = Series(data, dtype='c')
        result = s.mode(dropna)
        expected1 = Series(expected1, dtype='c')
        tm.assert_series_equal(result, expected1)

        data = ['foo', 'bar', 'bar', np.nan, np.nan, np.nan]

        s = Series(data, dtype=object)
        result = s.mode(dropna)
        expected2 = Series(expected2, dtype=object)
        tm.assert_series_equal(result, expected2)

        data = ['foo', 'bar', 'bar', np.nan, np.nan, np.nan]

        s = Series(data, dtype=object).astype(str)
        result = s.mode(dropna)
        expected3 = Series(expected3, dtype=str)
        tm.assert_series_equal(result, expected3)

    @pytest.mark.parametrize('dropna, expected1, expected2', [
        (True, ['foo'], ['foo']),
        (False, ['foo'], [np.nan])
    ])
    def test_mode_mixeddtype(self, dropna, expected1, expected2):
        s = Series([1, 'foo', 'foo'])
        result = s.mode(dropna)
        expected = Series(expected1)
        tm.assert_series_equal(result, expected)

        s = Series([1, 'foo', 'foo', np.nan, np.nan, np.nan])
        result = s.mode(dropna)
        expected = Series(expected2, dtype=object)
        tm.assert_series_equal(result, expected)

    @pytest.mark.parametrize('dropna, expected1, expected2', [
        (True, ['1900-05-03', '2011-01-03', '2013-01-02'],
               ['2011-01-03', '2013-01-02']),
        (False, [np.nan], [np.nan, '2011-01-03', '2013-01-02']),
    ])
    def test_mode_datetime(self, dropna, expected1, expected2):
        s = Series(['2011-01-03', '2013-01-02',
                    '1900-05-03', 'nan', 'nan'], dtype='M8[ns]')
        result = s.mode(dropna)
        expected1 = Series(expected1, dtype='M8[ns]')
        tm.assert_series_equal(result, expected1)

        s = Series(['2011-01-03', '2013-01-02', '1900-05-03',
                    '2011-01-03', '2013-01-02', 'nan', 'nan'],
                   dtype='M8[ns]')
        result = s.mode(dropna)
        expected2 = Series(expected2, dtype='M8[ns]')
        tm.assert_series_equal(result, expected2)

    @pytest.mark.parametrize('dropna, expected1, expected2', [
        (True, ['-1 days', '0 days', '1 days'], ['2 min', '1 day']),
        (False, [np.nan], [np.nan, '2 min', '1 day']),
    ])
    def test_mode_timedelta(self, dropna, expected1, expected2):
        # gh-5986: Test timedelta types.

        s = Series(['1 days', '-1 days', '0 days', 'nan', 'nan'],
                   dtype='timedelta64[ns]')
        result = s.mode(dropna)
        expected1 = Series(expected1, dtype='timedelta64[ns]')
        tm.assert_series_equal(result, expected1)

        s = Series(['1 day', '1 day', '-1 day', '-1 day 2 min',
                    '2 min', '2 min', 'nan', 'nan'],
                   dtype='timedelta64[ns]')
        result = s.mode(dropna)
        expected2 = Series(expected2, dtype='timedelta64[ns]')
        tm.assert_series_equal(result, expected2)

    @pytest.mark.parametrize('dropna, expected1, expected2, expected3', [
        (True, Categorical([1, 2], categories=[1, 2]),
         Categorical(['a'], categories=[1, 'a']),
         Categorical([3, 1], categories=[3, 2, 1], ordered=True)),
        (False, Categorical([np.nan], categories=[1, 2]),
         Categorical([np.nan, 'a'], categories=[1, 'a']),
         Categorical([np.nan, 3, 1], categories=[3, 2, 1], ordered=True)),
    ])
    def test_mode_category(self, dropna, expected1, expected2, expected3):
        s = Series(Categorical([1, 2, np.nan, np.nan]))
        result = s.mode(dropna)
        expected1 = Series(expected1, dtype='category')
        tm.assert_series_equal(result, expected1)

        s = Series(Categorical([1, 'a', 'a', np.nan, np.nan]))
        result = s.mode(dropna)
        expected2 = Series(expected2, dtype='category')
        tm.assert_series_equal(result, expected2)

        s = Series(Categorical([1, 1, 2, 3, 3, np.nan, np.nan],
                               categories=[3, 2, 1], ordered=True))
        result = s.mode(dropna)
        expected3 = Series(expected3, dtype='category')
        tm.assert_series_equal(result, expected3)

    @pytest.mark.parametrize('dropna, expected1, expected2', [
        (True, [2**63], [1, 2**63]),
        (False, [2**63], [1, 2**63])
    ])
    def test_mode_intoverflow(self, dropna, expected1, expected2):
        # Test for uint64 overflow.
        s = Series([1, 2**63, 2**63], dtype=np.uint64)
        result = s.mode(dropna)
        expected1 = Series(expected1, dtype=np.uint64)
        tm.assert_series_equal(result, expected1)

        s = Series([1, 2**63], dtype=np.uint64)
        result = s.mode(dropna)
        expected2 = Series(expected2, dtype=np.uint64)
        tm.assert_series_equal(result, expected2)

    @pytest.mark.skipif(not compat.PY3, reason="only PY3")
    def test_mode_sortwarning(self):
        # Check for the warning that is raised when the mode
        # results cannot be sorted

        expected = Series(['foo', np.nan])
        s = Series([1, 'foo', 'foo', np.nan, np.nan])

        with tm.assert_produces_warning(UserWarning, check_stacklevel=False):
            result = s.mode(dropna=False)
            result = result.sort_values().reset_index(drop=True)

        tm.assert_series_equal(result, expected)


def assert_check_nselect_boundary(vals, dtype, method):
    # helper function for 'test_boundary_{dtype}' tests
    s = Series(vals, dtype=dtype)
    result = getattr(s, method)(3)
    expected_idxr = [0, 1, 2] if method == 'nsmallest' else [3, 2, 1]
    expected = s.loc[expected_idxr]
    tm.assert_series_equal(result, expected)


class TestNLargestNSmallest(object):

    @pytest.mark.parametrize(
        "r", [Series([3., 2, 1, 2, '5'], dtype='object'),
              Series([3., 2, 1, 2, 5], dtype='object'),
              # not supported on some archs
              # Series([3., 2, 1, 2, 5], dtype='complex256'),
              Series([3., 2, 1, 2, 5], dtype='complex128'),
              Series(list('abcde')),
              Series(list('abcde'), dtype='category')])
    def test_error(self, r):
        dt = r.dtype
        msg = ("Cannot use method 'n(larg|small)est' with "
               "dtype {dt}".format(dt=dt))
        args = 2, len(r), 0, -1
        methods = r.nlargest, r.nsmallest
        for method, arg in product(methods, args):
            with pytest.raises(TypeError, match=msg):
                method(arg)

    def test_nsmallest_nlargest(self, s_main_dtypes_split):
        # float, int, datetime64 (use i8), timedelts64 (same),
        # object that are numbers, object that are strings
        s = s_main_dtypes_split

        assert_series_equal(s.nsmallest(2), s.iloc[[2, 1]])
        assert_series_equal(s.nsmallest(2, keep='last'), s.iloc[[2, 3]])

        empty = s.iloc[0:0]
        assert_series_equal(s.nsmallest(0), empty)
        assert_series_equal(s.nsmallest(-1), empty)
        assert_series_equal(s.nlargest(0), empty)
        assert_series_equal(s.nlargest(-1), empty)

        assert_series_equal(s.nsmallest(len(s)), s.sort_values())
        assert_series_equal(s.nsmallest(len(s) + 1), s.sort_values())
        assert_series_equal(s.nlargest(len(s)), s.iloc[[4, 0, 1, 3, 2]])
        assert_series_equal(s.nlargest(len(s) + 1),
                            s.iloc[[4, 0, 1, 3, 2]])

    def test_misc(self):

        s = Series([3., np.nan, 1, 2, 5])
        assert_series_equal(s.nlargest(), s.iloc[[4, 0, 3, 2]])
        assert_series_equal(s.nsmallest(), s.iloc[[2, 3, 0, 4]])

        msg = 'keep must be either "first", "last"'
        with pytest.raises(ValueError, match=msg):
            s.nsmallest(keep='invalid')
        with pytest.raises(ValueError, match=msg):
            s.nlargest(keep='invalid')

        # GH 15297
        s = Series([1] * 5, index=[1, 2, 3, 4, 5])
        expected_first = Series([1] * 3, index=[1, 2, 3])
        expected_last = Series([1] * 3, index=[5, 4, 3])

        result = s.nsmallest(3)
        assert_series_equal(result, expected_first)

        result = s.nsmallest(3, keep='last')
        assert_series_equal(result, expected_last)

        result = s.nlargest(3)
        assert_series_equal(result, expected_first)

        result = s.nlargest(3, keep='last')
        assert_series_equal(result, expected_last)

    @pytest.mark.parametrize('n', range(1, 5))
    def test_n(self, n):

        # GH 13412
        s = Series([1, 4, 3, 2], index=[0, 0, 1, 1])
        result = s.nlargest(n)
        expected = s.sort_values(ascending=False).head(n)
        assert_series_equal(result, expected)

        result = s.nsmallest(n)
        expected = s.sort_values().head(n)
        assert_series_equal(result, expected)

    def test_boundary_integer(self, nselect_method, any_int_dtype):
        # GH 21426
        dtype_info = np.iinfo(any_int_dtype)
        min_val, max_val = dtype_info.min, dtype_info.max
        vals = [min_val, min_val + 1, max_val - 1, max_val]
        assert_check_nselect_boundary(vals, any_int_dtype, nselect_method)

    def test_boundary_float(self, nselect_method, float_dtype):
        # GH 21426
        dtype_info = np.finfo(float_dtype)
        min_val, max_val = dtype_info.min, dtype_info.max
        min_2nd, max_2nd = np.nextafter(
            [min_val, max_val], 0, dtype=float_dtype)
        vals = [min_val, min_2nd, max_2nd, max_val]
        assert_check_nselect_boundary(vals, float_dtype, nselect_method)

    @pytest.mark.parametrize('dtype', ['datetime64[ns]', 'timedelta64[ns]'])
    def test_boundary_datetimelike(self, nselect_method, dtype):
        # GH 21426
        # use int64 bounds and +1 to min_val since true minimum is NaT
        # (include min_val/NaT at end to maintain same expected_idxr)
        dtype_info = np.iinfo('int64')
        min_val, max_val = dtype_info.min, dtype_info.max
        vals = [min_val + 1, min_val + 2, max_val - 1, max_val, min_val]
        assert_check_nselect_boundary(vals, dtype, nselect_method)

    def test_duplicate_keep_all_ties(self):
        # see gh-16818
        s = Series([10, 9, 8, 7, 7, 7, 7, 6])
        result = s.nlargest(4, keep='all')
        expected = Series([10, 9, 8, 7, 7, 7, 7])
        assert_series_equal(result, expected)

        result = s.nsmallest(2, keep='all')
        expected = Series([6, 7, 7, 7, 7], index=[7, 3, 4, 5, 6])
        assert_series_equal(result, expected)


class TestCategoricalSeriesAnalytics(object):

    def test_count(self):

        s = Series(Categorical([np.nan, 1, 2, np.nan],
                               categories=[5, 4, 3, 2, 1], ordered=True))
        result = s.count()
        assert result == 2

    def test_min_max(self):
        # unordered cats have no min/max
        cat = Series(Categorical(["a", "b", "c", "d"], ordered=False))
        pytest.raises(TypeError, lambda: cat.min())
        pytest.raises(TypeError, lambda: cat.max())

        cat = Series(Categorical(["a", "b", "c", "d"], ordered=True))
        _min = cat.min()
        _max = cat.max()
        assert _min == "a"
        assert _max == "d"

        cat = Series(Categorical(["a", "b", "c", "d"], categories=[
                     'd', 'c', 'b', 'a'], ordered=True))
        _min = cat.min()
        _max = cat.max()
        assert _min == "d"
        assert _max == "a"

        cat = Series(Categorical(
            [np.nan, "b", "c", np.nan], categories=['d', 'c', 'b', 'a'
                                                    ], ordered=True))
        _min = cat.min()
        _max = cat.max()
        assert np.isnan(_min)
        assert _max == "b"

        cat = Series(Categorical(
            [np.nan, 1, 2, np.nan], categories=[5, 4, 3, 2, 1], ordered=True))
        _min = cat.min()
        _max = cat.max()
        assert np.isnan(_min)
        assert _max == 1

    def test_value_counts(self):
        # GH 12835
        cats = Categorical(list('abcccb'), categories=list('cabd'))
        s = Series(cats, name='xxx')
        res = s.value_counts(sort=False)

        exp_index = CategoricalIndex(list('cabd'), categories=cats.categories)
        exp = Series([3, 1, 2, 0], name='xxx', index=exp_index)
        tm.assert_series_equal(res, exp)

        res = s.value_counts(sort=True)

        exp_index = CategoricalIndex(list('cbad'), categories=cats.categories)
        exp = Series([3, 2, 1, 0], name='xxx', index=exp_index)
        tm.assert_series_equal(res, exp)

        # check object dtype handles the Series.name as the same
        # (tested in test_base.py)
        s = Series(["a", "b", "c", "c", "c", "b"], name='xxx')
        res = s.value_counts()
        exp = Series([3, 2, 1], name='xxx', index=["c", "b", "a"])
        tm.assert_series_equal(res, exp)

    def test_value_counts_with_nan(self):
        # see gh-9443

        # sanity check
        s = Series(["a", "b", "a"], dtype="category")
        exp = Series([2, 1], index=CategoricalIndex(["a", "b"]))

        res = s.value_counts(dropna=True)
        tm.assert_series_equal(res, exp)

        res = s.value_counts(dropna=True)
        tm.assert_series_equal(res, exp)

        # same Series via two different constructions --> same behaviour
        series = [
            Series(["a", "b", None, "a", None, None], dtype="category"),
            Series(Categorical(["a", "b", None, "a", None, None],
                               categories=["a", "b"]))
        ]

        for s in series:
            # None is a NaN value, so we exclude its count here
            exp = Series([2, 1], index=CategoricalIndex(["a", "b"]))
            res = s.value_counts(dropna=True)
            tm.assert_series_equal(res, exp)

            # we don't exclude the count of None and sort by counts
            exp = Series([3, 2, 1], index=CategoricalIndex([np.nan, "a", "b"]))
            res = s.value_counts(dropna=False)
            tm.assert_series_equal(res, exp)

            # When we aren't sorting by counts, and np.nan isn't a
            # category, it should be last.
            exp = Series([2, 1, 3], index=CategoricalIndex(["a", "b", np.nan]))
            res = s.value_counts(dropna=False, sort=False)
            tm.assert_series_equal(res, exp)

    @pytest.mark.parametrize(
        "dtype",
        ["int_", "uint", "float_", "unicode_", "timedelta64[h]",
         pytest.param("datetime64[D]",
                      marks=pytest.mark.xfail(reason="GH#7996"))]
    )
    @pytest.mark.parametrize("is_ordered", [True, False])
    def test_drop_duplicates_categorical_non_bool(self, dtype, is_ordered):
        cat_array = np.array([1, 2, 3, 4, 5], dtype=np.dtype(dtype))

        # Test case 1
        input1 = np.array([1, 2, 3, 3], dtype=np.dtype(dtype))
        tc1 = Series(Categorical(input1, categories=cat_array,
                                 ordered=is_ordered))

        expected = Series([False, False, False, True])
        tm.assert_series_equal(tc1.duplicated(), expected)
        tm.assert_series_equal(tc1.drop_duplicates(), tc1[~expected])
        sc = tc1.copy()
        sc.drop_duplicates(inplace=True)
        tm.assert_series_equal(sc, tc1[~expected])

        expected = Series([False, False, True, False])
        tm.assert_series_equal(tc1.duplicated(keep='last'), expected)
        tm.assert_series_equal(tc1.drop_duplicates(keep='last'),
                               tc1[~expected])
        sc = tc1.copy()
        sc.drop_duplicates(keep='last', inplace=True)
        tm.assert_series_equal(sc, tc1[~expected])

        expected = Series([False, False, True, True])
        tm.assert_series_equal(tc1.duplicated(keep=False), expected)
        tm.assert_series_equal(tc1.drop_duplicates(keep=False), tc1[~expected])
        sc = tc1.copy()
        sc.drop_duplicates(keep=False, inplace=True)
        tm.assert_series_equal(sc, tc1[~expected])

        # Test case 2
        input2 = np.array([1, 2, 3, 5, 3, 2, 4], dtype=np.dtype(dtype))
        tc2 = Series(Categorical(
            input2, categories=cat_array, ordered=is_ordered)
        )

        expected = Series([False, False, False, False, True, True, False])
        tm.assert_series_equal(tc2.duplicated(), expected)
        tm.assert_series_equal(tc2.drop_duplicates(), tc2[~expected])
        sc = tc2.copy()
        sc.drop_duplicates(inplace=True)
        tm.assert_series_equal(sc, tc2[~expected])

        expected = Series([False, True, True, False, False, False, False])
        tm.assert_series_equal(tc2.duplicated(keep='last'), expected)
        tm.assert_series_equal(tc2.drop_duplicates(keep='last'),
                               tc2[~expected])
        sc = tc2.copy()
        sc.drop_duplicates(keep='last', inplace=True)
        tm.assert_series_equal(sc, tc2[~expected])

        expected = Series([False, True, True, False, True, True, False])
        tm.assert_series_equal(tc2.duplicated(keep=False), expected)
        tm.assert_series_equal(tc2.drop_duplicates(keep=False), tc2[~expected])
        sc = tc2.copy()
        sc.drop_duplicates(keep=False, inplace=True)
        tm.assert_series_equal(sc, tc2[~expected])

    @pytest.mark.parametrize("is_ordered", [True, False])
    def test_drop_duplicates_categorical_bool(self, is_ordered):
        tc = Series(Categorical([True, False, True, False],
                                categories=[True, False], ordered=is_ordered))

        expected = Series([False, False, True, True])
        tm.assert_series_equal(tc.duplicated(), expected)
        tm.assert_series_equal(tc.drop_duplicates(), tc[~expected])
        sc = tc.copy()
        sc.drop_duplicates(inplace=True)
        tm.assert_series_equal(sc, tc[~expected])

        expected = Series([True, True, False, False])
        tm.assert_series_equal(tc.duplicated(keep='last'), expected)
        tm.assert_series_equal(tc.drop_duplicates(keep='last'), tc[~expected])
        sc = tc.copy()
        sc.drop_duplicates(keep='last', inplace=True)
        tm.assert_series_equal(sc, tc[~expected])

        expected = Series([True, True, True, True])
        tm.assert_series_equal(tc.duplicated(keep=False), expected)
        tm.assert_series_equal(tc.drop_duplicates(keep=False), tc[~expected])
        sc = tc.copy()
        sc.drop_duplicates(keep=False, inplace=True)
        tm.assert_series_equal(sc, tc[~expected])
