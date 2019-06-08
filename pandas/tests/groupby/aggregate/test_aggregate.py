"""
test .agg behavior / note that .apply is tested generally in test_groupby.py
"""
from collections import OrderedDict
import functools

import numpy as np
import pytest

import pandas as pd
from pandas import DataFrame, Index, MultiIndex, Series, compat, concat
from pandas.core.base import SpecificationError
from pandas.core.groupby.grouper import Grouping
import pandas.util.testing as tm


def test_agg_regression1(tsframe):
    grouped = tsframe.groupby([lambda x: x.year, lambda x: x.month])
    result = grouped.agg(np.mean)
    expected = grouped.mean()
    tm.assert_frame_equal(result, expected)


@pytest.mark.filterwarnings("ignore:NDFrame:FutureWarning")
def test_agg_must_agg(df):
    grouped = df.groupby('A')['C']

    msg = "Must produce aggregated value"
    with pytest.raises(Exception, match=msg):
        grouped.agg(lambda x: x.describe())
    with pytest.raises(Exception, match=msg):
        grouped.agg(lambda x: x.index[:2])


@pytest.mark.filterwarnings("ignore:NDFrame:FutureWarning")
def test_agg_ser_multi_key(df):
    # TODO(wesm): unused
    ser = df.C  # noqa

    f = lambda x: x.sum()
    results = df.C.groupby([df.A, df.B]).aggregate(f)
    expected = df.groupby(['A', 'B']).sum()['C']
    tm.assert_series_equal(results, expected)


def test_groupby_aggregation_mixed_dtype():

    # GH 6212
    expected = DataFrame({
        'v1': [5, 5, 7, np.nan, 3, 3, 4, 1],
        'v2': [55, 55, 77, np.nan, 33, 33, 44, 11]},
        index=MultiIndex.from_tuples([(1, 95), (1, 99), (2, 95), (2, 99),
                                      ('big', 'damp'),
                                      ('blue', 'dry'),
                                      ('red', 'red'), ('red', 'wet')],
                                     names=['by1', 'by2']))

    df = DataFrame({
        'v1': [1, 3, 5, 7, 8, 3, 5, np.nan, 4, 5, 7, 9],
        'v2': [11, 33, 55, 77, 88, 33, 55, np.nan, 44, 55, 77, 99],
        'by1': ["red", "blue", 1, 2, np.nan, "big", 1, 2, "red", 1, np.nan,
                12],
        'by2': ["wet", "dry", 99, 95, np.nan, "damp", 95, 99, "red", 99,
                np.nan, np.nan]
    })

    g = df.groupby(['by1', 'by2'])
    result = g[['v1', 'v2']].mean()
    tm.assert_frame_equal(result, expected)


def test_agg_apply_corner(ts, tsframe):
    # nothing to group, all NA
    grouped = ts.groupby(ts * np.nan)
    assert ts.dtype == np.float64

    # groupby float64 values results in Float64Index
    exp = Series([], dtype=np.float64,
                 index=pd.Index([], dtype=np.float64))
    tm.assert_series_equal(grouped.sum(), exp)
    tm.assert_series_equal(grouped.agg(np.sum), exp)
    tm.assert_series_equal(grouped.apply(np.sum), exp,
                           check_index_type=False)

    # DataFrame
    grouped = tsframe.groupby(tsframe['A'] * np.nan)
    exp_df = DataFrame(columns=tsframe.columns, dtype=float,
                       index=pd.Index([], dtype=np.float64))
    tm.assert_frame_equal(grouped.sum(), exp_df, check_names=False)
    tm.assert_frame_equal(grouped.agg(np.sum), exp_df, check_names=False)
    tm.assert_frame_equal(grouped.apply(np.sum), exp_df.iloc[:, :0],
                          check_names=False)


def test_agg_grouping_is_list_tuple(ts):
    df = tm.makeTimeDataFrame()

    grouped = df.groupby(lambda x: x.year)
    grouper = grouped.grouper.groupings[0].grouper
    grouped.grouper.groupings[0] = Grouping(ts.index, list(grouper))

    result = grouped.agg(np.mean)
    expected = grouped.mean()
    tm.assert_frame_equal(result, expected)

    grouped.grouper.groupings[0] = Grouping(ts.index, tuple(grouper))

    result = grouped.agg(np.mean)
    expected = grouped.mean()
    tm.assert_frame_equal(result, expected)


def test_agg_python_multiindex(mframe):
    grouped = mframe.groupby(['A', 'B'])

    result = grouped.agg(np.mean)
    expected = grouped.mean()
    tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize('groupbyfunc', [
    lambda x: x.weekday(),
    [lambda x: x.month, lambda x: x.weekday()],
])
def test_aggregate_str_func(tsframe, groupbyfunc):
    grouped = tsframe.groupby(groupbyfunc)

    # single series
    result = grouped['A'].agg('std')
    expected = grouped['A'].std()
    tm.assert_series_equal(result, expected)

    # group frame by function name
    result = grouped.aggregate('var')
    expected = grouped.var()
    tm.assert_frame_equal(result, expected)

    # group frame by function dict
    result = grouped.agg(OrderedDict([['A', 'var'],
                                      ['B', 'std'],
                                      ['C', 'mean'],
                                      ['D', 'sem']]))
    expected = DataFrame(OrderedDict([['A', grouped['A'].var()],
                                      ['B', grouped['B'].std()],
                                      ['C', grouped['C'].mean()],
                                      ['D', grouped['D'].sem()]]))
    tm.assert_frame_equal(result, expected)


@pytest.mark.filterwarnings("ignore:NDFrame:FutureWarning")
def test_aggregate_item_by_item(df):
    grouped = df.groupby('A')

    aggfun = lambda ser: ser.size
    result = grouped.agg(aggfun)
    foo = (df.A == 'foo').sum()
    bar = (df.A == 'bar').sum()
    K = len(result.columns)

    # GH5782
    # odd comparisons can result here, so cast to make easy
    exp = pd.Series(np.array([foo] * K), index=list('BCD'),
                    dtype=np.float64, name='foo')
    tm.assert_series_equal(result.xs('foo'), exp)

    exp = pd.Series(np.array([bar] * K), index=list('BCD'),
                    dtype=np.float64, name='bar')
    tm.assert_almost_equal(result.xs('bar'), exp)

    def aggfun(ser):
        return ser.size

    result = DataFrame().groupby(df.A).agg(aggfun)
    assert isinstance(result, DataFrame)
    assert len(result) == 0


@pytest.mark.filterwarnings("ignore:NDFrame:FutureWarning")
def test_wrap_agg_out(three_group):
    grouped = three_group.groupby(['A', 'B'])

    def func(ser):
        if ser.dtype == np.object:
            raise TypeError
        else:
            return ser.sum()

    result = grouped.aggregate(func)
    exp_grouped = three_group.loc[:, three_group.columns != 'C']
    expected = exp_grouped.groupby(['A', 'B']).aggregate(func)
    tm.assert_frame_equal(result, expected)


def test_agg_multiple_functions_maintain_order(df):
    # GH #610
    funcs = [('mean', np.mean), ('max', np.max), ('min', np.min)]
    result = df.groupby('A')['C'].agg(funcs)
    exp_cols = Index(['mean', 'max', 'min'])

    tm.assert_index_equal(result.columns, exp_cols)


def test_multiple_functions_tuples_and_non_tuples(df):
    # #1359
    funcs = [('foo', 'mean'), 'std']
    ex_funcs = [('foo', 'mean'), ('std', 'std')]

    result = df.groupby('A')['C'].agg(funcs)
    expected = df.groupby('A')['C'].agg(ex_funcs)
    tm.assert_frame_equal(result, expected)

    result = df.groupby('A').agg(funcs)
    expected = df.groupby('A').agg(ex_funcs)
    tm.assert_frame_equal(result, expected)


@pytest.mark.filterwarnings("ignore:NDFrame:FutureWarning")
def test_agg_multiple_functions_too_many_lambdas(df):
    grouped = df.groupby('A')
    funcs = ['mean', lambda x: x.mean(), lambda x: x.std()]

    msg = 'Function names must be unique, found multiple named <lambda>'
    with pytest.raises(SpecificationError, match=msg):
        grouped.agg(funcs)


@pytest.mark.filterwarnings("ignore:NDFrame:FutureWarning")
def test_more_flexible_frame_multi_function(df):
    grouped = df.groupby('A')

    exmean = grouped.agg(OrderedDict([['C', np.mean], ['D', np.mean]]))
    exstd = grouped.agg(OrderedDict([['C', np.std], ['D', np.std]]))

    expected = concat([exmean, exstd], keys=['mean', 'std'], axis=1)
    expected = expected.swaplevel(0, 1, axis=1).sort_index(level=0, axis=1)

    d = OrderedDict([['C', [np.mean, np.std]], ['D', [np.mean, np.std]]])
    result = grouped.aggregate(d)

    tm.assert_frame_equal(result, expected)

    # be careful
    result = grouped.aggregate(OrderedDict([['C', np.mean],
                                            ['D', [np.mean, np.std]]]))
    expected = grouped.aggregate(OrderedDict([['C', np.mean],
                                              ['D', [np.mean, np.std]]]))
    tm.assert_frame_equal(result, expected)

    def foo(x):
        return np.mean(x)

    def bar(x):
        return np.std(x, ddof=1)

    # this uses column selection & renaming
    with tm.assert_produces_warning(FutureWarning, check_stacklevel=False):
        d = OrderedDict([['C', np.mean],
                         ['D', OrderedDict([['foo', np.mean],
                                            ['bar', np.std]])]])
        result = grouped.aggregate(d)

    d = OrderedDict([['C', [np.mean]], ['D', [foo, bar]]])
    expected = grouped.aggregate(d)

    tm.assert_frame_equal(result, expected)


def test_multi_function_flexible_mix(df):
    # GH #1268
    grouped = df.groupby('A')

    # Expected
    d = OrderedDict([['C', OrderedDict([['foo', 'mean'], ['bar', 'std']])],
                     ['D', {'sum': 'sum'}]])
    # this uses column selection & renaming
    with tm.assert_produces_warning(FutureWarning, check_stacklevel=False):
        expected = grouped.aggregate(d)

    # Test 1
    d = OrderedDict([['C', OrderedDict([['foo', 'mean'], ['bar', 'std']])],
                     ['D', 'sum']])
    # this uses column selection & renaming
    with tm.assert_produces_warning(FutureWarning, check_stacklevel=False):
        result = grouped.aggregate(d)
    tm.assert_frame_equal(result, expected)

    # Test 2
    d = OrderedDict([['C', OrderedDict([['foo', 'mean'], ['bar', 'std']])],
                     ['D', ['sum']]])
    # this uses column selection & renaming
    with tm.assert_produces_warning(FutureWarning, check_stacklevel=False):
        result = grouped.aggregate(d)
    tm.assert_frame_equal(result, expected)


@pytest.mark.filterwarnings("ignore:NDFrame:FutureWarning")
def test_groupby_agg_coercing_bools():
    # issue 14873
    dat = pd.DataFrame(
        {'a': [1, 1, 2, 2], 'b': [0, 1, 2, 3], 'c': [None, None, 1, 1]})
    gp = dat.groupby('a')

    index = Index([1, 2], name='a')

    result = gp['b'].aggregate(lambda x: (x != 0).all())
    expected = Series([False, True], index=index, name='b')
    tm.assert_series_equal(result, expected)

    result = gp['c'].aggregate(lambda x: x.isnull().all())
    expected = Series([True, False], index=index, name='c')
    tm.assert_series_equal(result, expected)


def test_order_aggregate_multiple_funcs():
    # GH 25692
    df = pd.DataFrame({'A': [1, 1, 2, 2], 'B': [1, 2, 3, 4]})

    res = df.groupby('A').agg(['sum', 'max', 'mean', 'ohlc', 'min'])
    result = res.columns.levels[1]

    expected = pd.Index(['sum', 'max', 'mean', 'ohlc', 'min'])

    tm.assert_index_equal(result, expected)


@pytest.mark.filterwarnings("ignore:NDFrame:FutureWarning")
@pytest.mark.parametrize('dtype', [np.int64, np.uint64])
@pytest.mark.parametrize('how', ['first', 'last', 'min',
                                 'max', 'mean', 'median'])
def test_uint64_type_handling(dtype, how):
    # GH 26310
    df = pd.DataFrame({'x': 6903052872240755750, 'y': [1, 2]})
    expected = df.groupby('y').agg({'x': how})
    df.x = df.x.astype(dtype)
    result = df.groupby('y').agg({'x': how})
    result.x = result.x.astype(np.int64)
    tm.assert_frame_equal(result, expected, check_exact=True)


@pytest.mark.filterwarnings("ignore:NDFrame:FutureWarning")
class TestNamedAggregation:

    def test_agg_relabel(self):
        df = pd.DataFrame({"group": ['a', 'a', 'b', 'b'],
                           "A": [0, 1, 2, 3],
                           "B": [5, 6, 7, 8]})
        result = df.groupby("group").agg(
            a_max=("A", "max"),
            b_max=("B", "max"),
        )
        expected = pd.DataFrame({"a_max": [1, 3], "b_max": [6, 8]},
                                index=pd.Index(['a', 'b'], name='group'),
                                columns=['a_max', 'b_max'])
        tm.assert_frame_equal(result, expected)

        # order invariance
        p98 = functools.partial(np.percentile, q=98)
        result = df.groupby('group').agg(
            b_min=("B", "min"),
            a_min=("A", min),
            a_mean=("A", np.mean),
            a_max=("A", "max"),
            b_max=("B", "max"),
            a_98=("A", p98)
        )
        expected = pd.DataFrame({"b_min": [5, 7],
                                 "a_min": [0, 2],
                                 "a_mean": [0.5, 2.5],
                                 "a_max": [1, 3],
                                 "b_max": [6, 8],
                                 "a_98": [0.98, 2.98]},
                                index=pd.Index(['a', 'b'], name='group'),
                                columns=['b_min', 'a_min', 'a_mean',
                                         'a_max', 'b_max', 'a_98'])
        if not compat.PY36:
            expected = expected[['a_98', 'a_max', 'a_mean',
                                 'a_min', 'b_max', 'b_min']]
        tm.assert_frame_equal(result, expected)

    def test_agg_relabel_non_identifier(self):
        df = pd.DataFrame({"group": ['a', 'a', 'b', 'b'],
                           "A": [0, 1, 2, 3],
                           "B": [5, 6, 7, 8]})

        result = df.groupby("group").agg(**{'my col': ('A', 'max')})
        expected = pd.DataFrame({'my col': [1, 3]},
                                index=pd.Index(['a', 'b'], name='group'))
        tm.assert_frame_equal(result, expected)

    def test_duplicate_raises(self):
        # TODO: we currently raise on multiple lambdas. We could *maybe*
        # update com.get_callable_name to append `_i` to each lambda.
        df = pd.DataFrame({"A": [0, 0, 1, 1], "B": [1, 2, 3, 4]})
        with pytest.raises(SpecificationError, match="Function names"):
            df.groupby("A").agg(a=("A", "min"), b=("A", "min"))

    def test_agg_relabel_with_level(self):
        df = pd.DataFrame({"A": [0, 0, 1, 1], "B": [1, 2, 3, 4]},
                          index=pd.MultiIndex.from_product([['A', 'B'],
                                                            ['a', 'b']]))
        result = df.groupby(level=0).agg(aa=('A', 'max'), bb=('A', 'min'),
                                         cc=('B', 'mean'))
        expected = pd.DataFrame({
            'aa': [0, 1],
            'bb': [0, 1],
            'cc': [1.5, 3.5]
        }, index=['A', 'B'])
        tm.assert_frame_equal(result, expected)

    def test_agg_relabel_other_raises(self):
        df = pd.DataFrame({"A": [0, 0, 1], "B": [1, 2, 3]})
        grouped = df.groupby("A")
        match = 'Must provide'
        with pytest.raises(TypeError, match=match):
            grouped.agg(foo=1)

        with pytest.raises(TypeError, match=match):
            grouped.agg()

        with pytest.raises(TypeError, match=match):
            grouped.agg(a=('B', 'max'), b=(1, 2, 3))

    def test_missing_raises(self):
        df = pd.DataFrame({"A": [0, 1], "B": [1, 2]})
        with pytest.raises(KeyError, match="Column 'C' does not exist"):
            df.groupby("A").agg(c=('C', 'sum'))

    def test_agg_namedtuple(self):
        df = pd.DataFrame({"A": [0, 1], "B": [1, 2]})
        result = df.groupby("A").agg(
            b=pd.NamedAgg("B", "sum"),
            c=pd.NamedAgg(column="B", aggfunc="count")
        )
        expected = df.groupby("A").agg(b=("B", "sum"),
                                       c=("B", "count"))
        tm.assert_frame_equal(result, expected)
