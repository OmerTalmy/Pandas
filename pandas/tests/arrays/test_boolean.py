import operator

import numpy as np
import pytest

import pandas as pd
from pandas.arrays import BooleanArray
from pandas.tests.extension.base import BaseOpsUtil
import pandas.util.testing as tm


def make_data():
    return [True, False] * 4 + [np.nan] + [True, False] * 44 + [np.nan] + [True, False]


@pytest.fixture
def dtype():
    return pd.BooleanDtype()


@pytest.fixture
def data(dtype):
    return pd.array(make_data(), dtype=dtype)


def test_boolean_array_constructor():
    values = np.array([True, False, True, False], dtype="bool")
    mask = np.array([False, False, False, True], dtype="bool")

    result = BooleanArray(values, mask)
    expected = pd.array([True, False, True, None], dtype="boolean")
    tm.assert_extension_array_equal(result, expected)

    with pytest.raises(TypeError):
        BooleanArray(values.tolist(), mask)

    with pytest.raises(TypeError):
        BooleanArray(values, mask.tolist())

    with pytest.raises(TypeError):
        BooleanArray(values.astype(int), mask)

    with pytest.raises(TypeError):
        BooleanArray(values, None)


def test_boolean_array_constructor_copy():
    values = np.array([True, False, True, False], dtype="bool")
    mask = np.array([False, False, False, True], dtype="bool")

    result = BooleanArray(values, mask)
    assert result._data is values
    assert result._mask is mask

    result = BooleanArray(values, mask, copy=True)
    assert result._data is not values
    assert result._mask is not mask


@pytest.mark.parametrize(
    "a, b",
    [
        ([True, None], [True, np.nan]),
        ([None], [np.nan]),
        ([None, np.nan], [np.nan, np.nan]),
        ([np.nan, np.nan], [np.nan, np.nan]),
    ],
)
def test_to_boolean_array_none_is_nan(a, b):
    result = pd.array(a, dtype="boolean")
    expected = pd.array(b, dtype="boolean")
    tm.assert_extension_array_equal(result, expected)


# @pytest.mark.parametrize(
#     "values",
#     [
#         ["foo", "bar"],
#         ["1", "2"],
#         "foo",
#         [1],
#         [1.0],
#         pd.date_range("20130101", periods=2),
#         np.array(["foo"]),
#         [[1, 2], [3, 4]],
#         [np.nan, {"a": 1}],
#     ],
# )
# def test_to_boolean_array_error(values):
#     # error in converting existing arrays to BooleanArray
#     with pytest.raises(TypeError):
#         pd.array(values, dtype="boolean")


def test_to_boolean_array_integer():
    result = pd.array([1, 0, 1, 0], dtype="boolean")
    expected = pd.array([True, False, True, False], dtype="boolean")
    tm.assert_extension_array_equal(result, expected)

    # with pytest.raises(TypeError, match="cannot safely cast non-equivalent"):
    #     pd.array([1, 2, 3], dtype="boolean")


def test_coerce_to_numpy_array():
    # with missing values -> object dtype
    arr = pd.array([True, False, None], dtype="boolean")
    result = np.array(arr)
    expected = np.array([True, False, None], dtype="object")
    tm.assert_numpy_array_equal(result, expected)

    # with no missing values -> bool dtype
    # TODO consistently return object dtype instead?
    arr = pd.array([True, False, True], dtype="boolean")
    result = np.array(arr)
    expected = np.array([True, False, True], dtype="bool")
    tm.assert_numpy_array_equal(result, expected)


def test_astype():
    # with missing values
    arr = pd.array([True, False, None], dtype="boolean")
    msg = "cannot convert float NaN to"

    with pytest.raises(ValueError, match=msg):
        arr.astype("int64")

    with pytest.raises(ValueError, match=msg):
        arr.astype("bool")

    # no missing values
    arr = pd.array([True, False, True], dtype="boolean")
    # result = arr.astype("int64")
    # expected = np.array([1, 0, 1], dtype="int64")
    # tm.assert_numpy_array_equal(result, expected)

    result = arr.astype("bool")
    expected = np.array([True, False, True], dtype="bool")
    tm.assert_numpy_array_equal(result, expected)


# @pytest.mark.parametrize("ufunc", [np.add])
# def test_ufuncs_binary(ufunc):
#     # two BooleanArrays
#     a = pd.array([True, False, None], dtype="boolean")
#     result = ufunc(a, a)
#     expected = ufunc(a.astype(float)
#     tm.assert_numpy_array_equal(result, expected)

#     # # IntegerArray with numpy array
#     # arr = np.array([1, 2, 3, 4])
#     # result = ufunc(a, arr)
#     # expected = integer_array(ufunc(a.astype(float), arr))
#     # tm.assert_extension_array_equal(result, expected)

#     # result = ufunc(arr, a)
#     # expected = integer_array(ufunc(arr, a.astype(float)))
#     # tm.assert_extension_array_equal(result, expected)

#     # # IntegerArray with scalar
#     # result = ufunc(a, 1)
#     # expected = integer_array(ufunc(a.astype(float), 1))
#     # tm.assert_extension_array_equal(result, expected)

#     # result = ufunc(1, a)
#     # expected = integer_array(ufunc(1, a.astype(float)))
#     # tm.assert_extension_array_equal(result, expected)


@pytest.mark.parametrize("values", [[True, False], [True, None]])
def test_ufunc_reduce_raises(values):
    a = pd.array(values, dtype="boolean")
    with pytest.raises(NotImplementedError):
        np.add.reduce(a)


class TestLogicalOps(BaseOpsUtil):
    def get_op_from_name(self, op_name):
        short_opname = op_name.strip("_")
        short_opname = short_opname if "xor" in short_opname else short_opname + "_"
        try:
            op = getattr(operator, short_opname)
        except AttributeError:
            # Assume it is the reverse operator
            rop = getattr(operator, short_opname[1:])
            op = lambda x, y: rop(y, x)

        return op

    def _compare_other(self, data, op_name, other):
        op = self.get_op_from_name(op_name)

        # array
        result = pd.Series(op(data, other))
        expected = pd.Series(op(data._data, other), dtype="boolean")

        # fill the nan locations
        expected[data._mask] = np.nan

        tm.assert_series_equal(result, expected)

        # series
        s = pd.Series(data)
        result = op(s, other)

        expected = pd.Series(data._data)
        expected = op(expected, other)
        expected = pd.Series(expected, dtype="boolean")

        # fill the nan locations
        expected[data._mask] = np.nan

        tm.assert_series_equal(result, expected)

    def test_scalar(self, data, all_logical_operators):
        op_name = all_logical_operators
        self._compare_other(data, op_name, True)

    def test_array(self, data, all_logical_operators):
        op_name = all_logical_operators
        other = pd.array([True] * len(data), dtype="boolean")
        self._compare_other(data, op_name, other)
        other = np.array([True] * len(data))
        self._compare_other(data, op_name, other)
        other = pd.Series([True] * len(data), dtype="boolean")
        self._compare_other(data, op_name, other)


class TestComparisonOps(BaseOpsUtil):
    def _compare_other(self, data, op_name, other):
        op = self.get_op_from_name(op_name)

        # array
        result = pd.Series(op(data, other))
        expected = pd.Series(op(data._data, other))

        # fill the nan locations
        expected[data._mask] = op_name == "__ne__"

        tm.assert_series_equal(result, expected)

        # series
        s = pd.Series(data)
        result = op(s, other)

        expected = pd.Series(data._data)
        expected = op(expected, other)

        # fill the nan locations
        expected[data._mask] = op_name == "__ne__"

        tm.assert_series_equal(result, expected)

    def test_compare_scalar(self, data, all_compare_operators):
        op_name = all_compare_operators
        self._compare_other(data, op_name, True)

    def test_compare_array(self, data, all_compare_operators):
        op_name = all_compare_operators
        other = pd.array([True] * len(data), dtype="boolean")
        self._compare_other(data, op_name, other)
        other = np.array([True] * len(data))
        self._compare_other(data, op_name, other)
        other = pd.Series([True] * len(data))
        self._compare_other(data, op_name, other)


def test_indexing_boolean_mask():
    arr = pd.array([1, 2, 3, 4], dtype="Int64")
    mask = pd.array([True, False, True, False], dtype="boolean")
    result = arr[mask]
    expected = pd.array([1, 3], dtype="Int64")
    tm.assert_extension_array_equal(result, expected)

    # missing values -> error
    mask = pd.array([True, False, True, None], dtype="boolean")
    with pytest.raises(IndexError):
        result = arr[mask]
