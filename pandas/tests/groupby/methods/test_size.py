import numpy as np
import pytest

from pandas._config import using_string_dtype

from pandas import (
    DataFrame,
    Index,
    PeriodIndex,
    Series,
)
import pandas._testing as tm


@pytest.mark.parametrize("by", ["A", "B", ["A", "B"]])
def test_size(df, by):
    grouped = df.groupby(by=by)
    result = grouped.size()
    for key, group in grouped:
        assert result[key] == len(group)


@pytest.mark.parametrize("by", ["A", "B", ["A", "B"]])
def test_size_sort(sort, by):
    df = DataFrame(np.random.default_rng(2).choice(20, (1000, 3)), columns=list("ABC"))
    left = df.groupby(by=by, sort=sort).size()
    right = df.groupby(by=by, sort=sort)["C"].apply(lambda a: a.shape[0])
    tm.assert_series_equal(left, right, check_names=False)


def test_size_series_dataframe():
    # https://github.com/pandas-dev/pandas/issues/11699
    df = DataFrame(columns=["A", "B"])
    out = Series(dtype="int64", index=Index([], name="A"))
    tm.assert_series_equal(df.groupby("A").size(), out)


def test_size_groupby_all_null():
    # https://github.com/pandas-dev/pandas/issues/23050
    # Assert no 'Value Error : Length of passed values is 2, index implies 0'
    df = DataFrame({"A": [None, None]})  # all-null groups
    result = df.groupby("A").size()
    expected = Series(dtype="int64", index=Index([], name="A"))
    tm.assert_series_equal(result, expected)


def test_size_period_index():
    # https://github.com/pandas-dev/pandas/issues/34010
    ser = Series([1], index=PeriodIndex(["2000"], name="A", freq="D"))
    grp = ser.groupby(level="A")
    result = grp.size()
    tm.assert_series_equal(result, ser)


def test_size_on_categorical(as_index):
    df = DataFrame([[1, 1], [2, 2]], columns=["A", "B"])
    df["A"] = df["A"].astype("category")
    result = df.groupby(["A", "B"], as_index=as_index, observed=False).size()

    expected = DataFrame(
        [[1, 1, 1], [1, 2, 0], [2, 1, 0], [2, 2, 1]], columns=["A", "B", "size"]
    )
    expected["A"] = expected["A"].astype("category")
    if as_index:
        expected = expected.set_index(["A", "B"])["size"].rename(None)

    tm.assert_equal(result, expected)


@pytest.mark.parametrize("dtype", ["Int64", "Float64", "boolean"])
def test_size_series_masked_type_returns_Int64(dtype):
    # GH 54132
    ser = Series([1, 1, 1], index=["a", "a", "b"], dtype=dtype)
    result = ser.groupby(level=0).size()
    expected = Series([2, 1], dtype="Int64", index=["a", "b"])
    tm.assert_series_equal(result, expected)


@pytest.mark.xfail(using_string_dtype(), reason="TODO(infer_string)", strict=False)
def test_size_strings(any_string_dtype):
    # GH#55627
    dtype = any_string_dtype
    df = DataFrame({"a": ["a", "a", "b"], "b": "a"}, dtype=dtype)
    result = df.groupby("a")["b"].size()
    exp_dtype = "Int64" if dtype == "string[pyarrow]" else "int64"
    expected = Series(
        [2, 1],
        index=Index(["a", "b"], name="a", dtype=dtype),
        name="b",
        dtype=exp_dtype,
    )
    tm.assert_series_equal(result, expected)
