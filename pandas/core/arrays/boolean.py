import numbers
from typing import TYPE_CHECKING, Type
import warnings

import numpy as np

from pandas._libs import lib
from pandas.compat import set_function_name

from pandas.core.dtypes.base import ExtensionDtype
from pandas.core.dtypes.cast import astype_nansafe
from pandas.core.dtypes.common import (
    is_bool_dtype,
    is_float,
    is_float_dtype,
    is_integer,
    is_list_like,
    is_scalar,
)
from pandas.core.dtypes.dtypes import register_extension_dtype
from pandas.core.dtypes.generic import ABCDataFrame, ABCIndexClass, ABCSeries
from pandas.core.dtypes.missing import isna, notna

from pandas.core import nanops, ops
from pandas.core.algorithms import take
from pandas.core.arrays import ExtensionArray, ExtensionOpsMixin

if TYPE_CHECKING:
    from pandas._typing import Scalar


@register_extension_dtype
class BooleanDtype(ExtensionDtype):
    """
    Extension dtype for boolean data.

    .. versionadded:: 1.0.0

    .. warning::

       BooleanDtype is considered experimental. The implementation and
       parts of the API may change without warning.

    Attributes
    ----------
    None

    Methods
    -------
    None

    Examples
    --------
    >>> pd.BooleanDtype()
    BooleanDtype
    """

    @property
    def na_value(self) -> "Scalar":
        """
        StringDtype uses :attr:`numpy.nan` as the missing NA value.

        .. warning::

           `na_value` may change in a future release.
        """
        return np.nan

    @property
    def type(self) -> Type:
        return np.bool_

    @property
    def kind(self) -> str:
        return "b"

    @property
    def name(self) -> str:
        """
        The alias for StringDtype is ``'string'``.
        """
        return "boolean"

    @classmethod
    def construct_from_string(cls, string: str) -> ExtensionDtype:
        if string == "boolean":
            return cls()
        return super().construct_from_string(string)

    @classmethod
    def construct_array_type(cls) -> "Type[BooleanArray]":
        return BooleanArray

    def __repr__(self) -> str:
        return "BooleanDtype"

    @property
    def _is_boolean(self) -> bool:
        return True


def coerce_to_array(values, mask=None, copy=False):
    """
    Coerce the input values array to numpy arrays with a mask

    Parameters
    ----------
    values : 1D list-like
    dtype : integer dtype
    mask : bool 1D array, optional
    copy : bool, default False
        if True, copy the input

    Returns
    -------
    tuple of (values, mask)
    """
    if isinstance(values, BooleanArray):
        if mask is not None:
            raise ValueError("cannot pass mask for BooleanArray input")
        values, mask = values._data, values._mask
        if copy:
            values = values.copy()
            mask = mask.copy()
        return values, mask

    mask_values = None
    if isinstance(values, np.ndarray) and values.dtype == np.bool_:
        if copy:
            values = values.copy()
    else:
        values_object = np.asarray(values, dtype=object)
        mask_values = isna(values)
        values = np.zeros(len(values), dtype=bool)
        values[~mask_values] = values_object[~mask_values].astype(bool)

    if isinstance(mask, np.ndarray) and mask.dtype == np.bool_:
        if copy:
            mask = mask.copy()
    else:
        if mask is None:
            if mask_values is None:
                # TODO optimize this case?
                mask = np.zeros(len(values), dtype=bool)
            else:
                mask = mask_values
        else:
            mask = np.asarray(mask, dtype=bool)
            if mask_values is not None:
                mask = mask | mask_values

    if not values.ndim == 1:
        raise TypeError("values must be a 1D list-like")
    if not mask.ndim == 1:
        raise TypeError("mask must be a 1D list-like")

    return values, mask


class BooleanArray(ExtensionArray, ExtensionOpsMixin):
    def __init__(self, values, mask, copy=False):
        if not (isinstance(values, np.ndarray) and values.dtype == np.bool_):
            raise TypeError(
                "values should be boolean numpy array. Use "
                "the 'array' function instead"
            )
        if not (isinstance(mask, np.ndarray) and mask.dtype == np.bool_):
            raise TypeError(
                "mask should be boolean numpy array. Use "
                "the 'array' function instead"
            )

        if copy:
            values = values.copy()
            mask = mask.copy()

        self._data = values
        self._mask = mask
        self._dtype = BooleanDtype()

    @property
    def dtype(self):
        return self._dtype

    @classmethod
    def _from_sequence(cls, scalars, dtype=None, copy=False):
        if dtype:
            assert dtype == "boolean"
        values, mask = coerce_to_array(scalars, copy=copy)
        return BooleanArray(values, mask)

    @classmethod
    def _from_factorized(cls, values, original):
        return cls._from_sequence(values, dtype=original.dtype)

    def _formatter(self, boxed=False):
        def fmt(x):
            if isna(x):
                return "NaN"
            return str(x)

        return fmt

    def __getitem__(self, item):
        if is_integer(item):
            if self._mask[item]:
                return self.dtype.na_value
            return self._data[item]
        return type(self)(self._data[item], self._mask[item])

    def _coerce_to_ndarray(self):
        """
        coerce to an ndarary of object dtype
        """
        if self.isna().any():
            data = self._data.astype(object)
            data[self._mask] = self._na_value
            return data
        else:
            return self._data

    __array_priority__ = 1000  # higher than ndarray so ops dispatch to us

    def __array__(self, dtype=None):
        """
        the array interface, return my values
        We return an object array here to preserve our scalar values
        """
        return self._coerce_to_ndarray()

    def __arrow_array__(self, type=None):
        """
        Convert myself into a pyarrow Array.
        """
        import pyarrow as pa

        return pa.array(self._data, mask=self._mask, type=type)

    _HANDLED_TYPES = (np.ndarray, numbers.Number, bool)

    def __array_ufunc__(self, ufunc, method, *inputs, **kwargs):
        # For BooleanArray inputs, we apply the ufunc to ._data
        # and mask the result.
        if method == "reduce":
            # Not clear how to handle missing values in reductions. Raise.
            raise NotImplementedError("The 'reduce' method is not supported.")
        out = kwargs.get("out", ())

        for x in inputs + out:
            if not isinstance(x, self._HANDLED_TYPES + (BooleanArray,)):
                return NotImplemented

        # for binary ops, use our custom dunder methods
        result = ops.maybe_dispatch_ufunc_to_dunder_op(
            self, ufunc, method, *inputs, **kwargs
        )
        if result is not NotImplemented:
            return result

        mask = np.zeros(len(self), dtype=bool)
        inputs2 = []
        for x in inputs:
            if isinstance(x, BooleanArray):
                mask |= x._mask
                inputs2.append(x._data)
            else:
                inputs2.append(x)

        def reconstruct(x):
            # we don't worry about scalar `x` here, since we
            # raise for reduce up above.

            if is_bool_dtype(x.dtype):
                m = mask.copy()
                return BooleanArray(x, m)
            else:
                x[mask] = np.nan
            return x

        result = getattr(ufunc, method)(*inputs2, **kwargs)
        if isinstance(result, tuple):
            tuple(reconstruct(x) for x in result)
        else:
            return reconstruct(result)

    def __iter__(self):
        for i in range(len(self)):
            if self._mask[i]:
                yield self.dtype.na_value
            else:
                yield self._data[i]

    def take(self, indexer, allow_fill=False, fill_value=None):
        # we always fill with False internally
        # to avoid upcasting
        data_fill_value = False if isna(fill_value) else fill_value
        result = take(
            self._data, indexer, fill_value=data_fill_value, allow_fill=allow_fill
        )

        mask = take(self._mask, indexer, fill_value=True, allow_fill=allow_fill)

        # if we are filling
        # we only fill where the indexer is null
        # not existing missing values
        # TODO(jreback) what if we have a non-na float as a fill value?
        if allow_fill and notna(fill_value):
            fill_mask = np.asarray(indexer) == -1
            result[fill_mask] = fill_value
            mask = mask ^ fill_mask

        return type(self)(result, mask, copy=False)

    def copy(self):
        data, mask = self._data, self._mask
        data = data.copy()
        mask = mask.copy()
        return type(self)(data, mask, copy=False)

    def __setitem__(self, key, value):
        _is_scalar = is_scalar(value)
        if _is_scalar:
            value = [value]
        value, mask = coerce_to_array(value)

        if _is_scalar:
            value = value[0]
            mask = mask[0]

        self._data[key] = value
        self._mask[key] = mask

    def __len__(self):
        return len(self._data)

    @property
    def nbytes(self):
        return self._data.nbytes + self._mask.nbytes

    def isna(self):
        return self._mask

    @property
    def _na_value(self):
        return np.nan

    @classmethod
    def _concat_same_type(cls, to_concat):
        data = np.concatenate([x._data for x in to_concat])
        mask = np.concatenate([x._mask for x in to_concat])
        return cls(data, mask)

    def astype(self, dtype, copy=True):
        """
        Cast to a NumPy array or BooleanArray with 'dtype'.

        Parameters
        ----------
        dtype : str or dtype
            Typecode or data-type to which the array is cast.
        copy : bool, default True
            Whether to copy the data, even if not necessary. If False,
            a copy is made only if the old dtype does not match the
            new dtype.

        Returns
        -------
        array : ndarray or BooleanArray
            NumPy ndarray or IntergerArray with 'dtype' for its dtype.

        Raises
        ------
        TypeError
            if incompatible type with an IntegerDtype, equivalent of same_kind
            casting
        """

        if isinstance(dtype, BooleanDtype):
            values, mask = coerce_to_array(self, copy=copy)
            return BooleanArray(values, mask, copy=False)

        if is_bool_dtype(dtype):
            # astype_nansafe converts np.nan to True
            if self.isna().any():
                raise ValueError("cannot convert float NaN to bool")
            else:
                return self._data.astype("bool", copy=copy)
        # coerce
        data = self._coerce_to_ndarray()
        return astype_nansafe(data, dtype, copy=None)

    @property
    def _ndarray_values(self) -> np.ndarray:
        """Internal pandas method for lossy conversion to a NumPy ndarray.

        This method is not part of the pandas interface.

        The expectation is that this is cheap to compute, and is primarily
        used for interacting with our indexers.
        """
        raise NotImplementedError
        # return self._data

    def value_counts(self, dropna=True):
        """
        Returns a Series containing counts of each category.

        Every category will have an entry, even those with a count of 0.

        Parameters
        ----------
        dropna : bool, default True
            Don't include counts of NaN.

        Returns
        -------
        counts : Series

        See Also
        --------
        Series.value_counts

        """

        from pandas import Index, Series

        # compute counts on the data with no nans
        data = self._data[~self._mask]
        value_counts = Index(data).value_counts()
        array = value_counts.values

        # TODO(extension)
        # if we have allow Index to hold an ExtensionArray
        # this is easier
        index = value_counts.index.values.astype(bool).astype(object)

        # if we want nans, count the mask
        if not dropna:

            # TODO(extension)
            # appending to an Index *always* infers
            # w/o passing the dtype
            array = np.append(array, [self._mask.sum()])
            index = Index(
                np.concatenate([index, np.array([np.nan], dtype=object)]), dtype=object
            )

        return Series(array, index=index)

    def _values_for_argsort(self) -> np.ndarray:
        """Return values for sorting.

        Returns
        -------
        ndarray
            The transformed values should maintain the ordering between values
            within the array.

        See Also
        --------
        ExtensionArray.argsort
        """
        data = self._data.copy()
        data[self._mask] = data.min() - 1
        return data

    @classmethod
    def _create_logical_method(cls, op):
        def logical_method(self, other):

            if isinstance(other, (ABCDataFrame, ABCSeries, ABCIndexClass)):
                # Rely on pandas to unbox and dispatch to us.
                return NotImplemented

            other = lib.item_from_zerodim(other)
            mask = None

            if isinstance(other, BooleanArray):
                other, mask = other._data, other._mask
            elif is_list_like(other):
                other = np.asarray(other, dtype="bool")
                if other.ndim > 1:
                    raise NotImplementedError(
                        "can only perform ops with 1-d structures"
                    )
                if len(self) != len(other):
                    raise ValueError("Lengths must match to compare")
                other, mask = coerce_to_array(other, copy=False)

            # numpy will show a DeprecationWarning on invalid elementwise
            # comparisons, this will raise in the future
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", "elementwise", FutureWarning)
                with np.errstate(all="ignore"):
                    result = op(self._data, other)

            # nans propagate
            if mask is None:
                mask = self._mask
            else:
                mask = self._mask | mask

            return BooleanArray(result, mask)

        name = "__{name}__".format(name=op.__name__)
        return set_function_name(logical_method, name, cls)

    @classmethod
    def _create_comparison_method(cls, op):
        op_name = op.__name__

        def cmp_method(self, other):

            if isinstance(other, (ABCDataFrame, ABCSeries, ABCIndexClass)):
                # Rely on pandas to unbox and dispatch to us.
                return NotImplemented

            other = lib.item_from_zerodim(other)
            mask = None

            if isinstance(other, BooleanArray):
                other, mask = other._data, other._mask

            elif is_list_like(other):
                other = np.asarray(other)
                if other.ndim > 1:
                    raise NotImplementedError(
                        "can only perform ops with 1-d structures"
                    )
                if len(self) != len(other):
                    raise ValueError("Lengths must match to compare")

            # numpy will show a DeprecationWarning on invalid elementwise
            # comparisons, this will raise in the future
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", "elementwise", FutureWarning)
                with np.errstate(all="ignore"):
                    result = op(self._data, other)

            # nans propagate
            if mask is None:
                mask = self._mask
            else:
                mask = self._mask | mask

            result[mask] = op_name == "ne"
            return result

        name = "__{name}__".format(name=op.__name__)
        return set_function_name(cmp_method, name, cls)

    def _reduce(self, name, skipna=True, **kwargs):
        data = self._data
        mask = self._mask

        # coerce to a nan-aware float if needed
        if mask.any():
            data = self._data.astype("float64")
            data[mask] = self._na_value

        op = getattr(nanops, "nan" + name)
        result = op(data, axis=0, skipna=skipna, mask=mask)

        # if we have a boolean op, don't coerce
        if name in ["any", "all"]:
            pass

        # if we have a preservable numeric op,
        # provide coercion back to an integer type if possible
        elif name in ["sum", "min", "max", "prod"] and notna(result):
            int_result = int(result)
            if int_result == result:
                result = int_result

        return result

    def _maybe_mask_result(self, result, mask, other, op_name):
        """
        Parameters
        ----------
        result : array-like
        mask : array-like bool
        other : scalar or array-like
        op_name : str
        """

        # may need to fill infs
        # and mask wraparound
        if is_float_dtype(result):
            mask |= (result == np.inf) | (result == -np.inf)

        # if we have a float operand we are by-definition
        # a float result
        # or our op is a divide
        if (is_float_dtype(other) or is_float(other)) or (
            op_name in ["rtruediv", "truediv"]
        ):
            result[mask] = np.nan
            return result

        return type(self)(result, mask, copy=False)


BooleanArray._add_logical_ops()
BooleanArray._add_comparison_ops()
