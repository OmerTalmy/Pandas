from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Sequence,
    TypeVar,
)

import numpy as np

from pandas._libs import (
    lib,
    missing as libmissing,
)
from pandas._typing import (
    ArrayLike,
    Dtype,
    NpDtype,
    PositionalIndexer,
    Scalar,
    type_t,
)
from pandas.errors import AbstractMethodError
from pandas.util._decorators import (
    cache_readonly,
    doc,
)
from pandas.util._validators import validate_fillna_kwargs

from pandas.core.dtypes.base import ExtensionDtype
from pandas.core.dtypes.common import (
    is_dtype_equal,
    is_integer,
    is_object_dtype,
    is_scalar,
    is_string_dtype,
    pandas_dtype,
)
from pandas.core.dtypes.inference import is_array_like
from pandas.core.dtypes.missing import (
    isna,
    notna,
)

from pandas.core import (
    missing,
    nanops,
)
from pandas.core.algorithms import (
    factorize_array,
    isin,
    take,
)
from pandas.core.array_algos import masked_reductions
from pandas.core.arraylike import OpsMixin
from pandas.core.arrays import ExtensionArray
from pandas.core.indexers import check_array_indexer

if TYPE_CHECKING:
    from pandas import Series
    from pandas.core.arrays import BooleanArray


BaseMaskedArrayT = TypeVar("BaseMaskedArrayT", bound="BaseMaskedArray")


class BaseMaskedDtype(ExtensionDtype):
    """
    Base class for dtypes for BasedMaskedArray subclasses.
    """

    name: str
    base = None
    type: type

    na_value = libmissing.NA

    @cache_readonly
    def numpy_dtype(self) -> np.dtype:
        """Return an instance of our numpy dtype"""
        return np.dtype(self.type)

    @cache_readonly
    def kind(self) -> str:
        return self.numpy_dtype.kind

    @cache_readonly
    def itemsize(self) -> int:
        """Return the number of bytes in this dtype"""
        return self.numpy_dtype.itemsize

    @classmethod
    def construct_array_type(cls) -> type_t[BaseMaskedArray]:
        """
        Return the array type associated with this dtype.

        Returns
        -------
        type
        """
        raise NotImplementedError


class BaseMaskedArray(OpsMixin, ExtensionArray):
    """
    Base class for masked arrays (which use _data and _mask to store the data).

    numpy based
    """

    # The value used to fill '_data' to avoid upcasting
    _internal_fill_value: Scalar

    def __init__(
        self, values: np.ndarray, mask: np.ndarray | None = None, copy: bool = False
    ):
        # values is supposed to already be validated in the subclass
        if mask is not None:
            if not (isinstance(mask, np.ndarray) and mask.dtype == np.bool_):
                raise TypeError(
                    "mask should be boolean numpy array. Use "
                    "the 'pd.array' function instead"
                )
            if mask.ndim != 1:
                raise ValueError("mask must be a 1D array")

            if not mask.any():
                mask = None

        if values.ndim != 1:
            raise ValueError("values must be a 1D array")

        if copy:
            values = values.copy()
            if mask is not None:
                mask = mask.copy()

        self._data = values
        self._mask = mask

    @property
    def dtype(self) -> BaseMaskedDtype:
        raise AbstractMethodError(self)

    def __getitem__(self, item: PositionalIndexer) -> BaseMaskedArray | Any:
        if is_integer(item):
            if self._hasna and self._mask[item]:
                return self.dtype.na_value
            return self._data[item]

        item = check_array_indexer(self, item)
        if self._hasna:
            return type(self)(self._data[item], self._mask[item])
        else:
            return type(self)(self._data[item])

    @doc(ExtensionArray.fillna)
    def fillna(
        self: BaseMaskedArrayT, value=None, method=None, limit=None
    ) -> BaseMaskedArrayT:
        value, method = validate_fillna_kwargs(value, method)

        mask = self._mask

        if is_array_like(value):
            if len(value) != len(self):
                raise ValueError(
                    f"Length of 'value' does not match. Got ({len(value)}) "
                    f" expected {len(self)}"
                )
            if mask is not None:
                value = value[mask]

        if self._hasna:
            if method is not None:
                func = missing.get_fill_func(method)
                new_values, new_mask = func(
                    self._data.copy(),
                    limit=limit,
                    mask=mask.copy(),
                )
                return type(self)(new_values, new_mask.view(np.bool_))
            else:
                # fill with value
                new_values = self.copy()
                new_values[mask] = value
        else:
            new_values = self.copy()
        return new_values

    def _coerce_to_array(self, values) -> tuple[np.ndarray, np.ndarray]:
        raise AbstractMethodError(self)

    # TODO
    def __setitem__(self, key, value) -> None:
        _is_scalar = is_scalar(value)
        if _is_scalar:
            value = [value]
        value, mask = self._coerce_to_array(value)

        if _is_scalar:
            value = value[0]
            mask = mask[0]

        key = check_array_indexer(self, key)
        self._data[key] = value
        self._mask[key] = mask

    def __iter__(self):
        for i in range(len(self)):
            if self._hasna and self._mask[i]:
                yield self.dtype.na_value
            else:
                yield self._data[i]

    def __len__(self) -> int:
        return len(self._data)

    def __invert__(self: BaseMaskedArrayT) -> BaseMaskedArrayT:
        if self._hasna:
            return type(self)(~self._data, self._mask.copy())
        else:
            return type(self)(~self._data)

    # error: Argument 1 of "to_numpy" is incompatible with supertype "ExtensionArray";
    # supertype defines the argument type as "Union[ExtensionDtype, str, dtype[Any],
    # Type[str], Type[float], Type[int], Type[complex], Type[bool], Type[object], None]"
    def to_numpy(  # type: ignore[override]
        self,
        dtype: NpDtype | None = None,
        copy: bool = False,
        na_value: Scalar = lib.no_default,
    ) -> np.ndarray:
        """
        Convert to a NumPy Array.

        By default converts to an object-dtype NumPy array. Specify the `dtype` and
        `na_value` keywords to customize the conversion.

        Parameters
        ----------
        dtype : dtype, default object
            The numpy dtype to convert to.
        copy : bool, default False
            Whether to ensure that the returned value is a not a view on
            the array. Note that ``copy=False`` does not *ensure* that
            ``to_numpy()`` is no-copy. Rather, ``copy=True`` ensure that
            a copy is made, even if not strictly necessary. This is typically
            only possible when no missing values are present and `dtype`
            is the equivalent numpy dtype.
        na_value : scalar, optional
             Scalar missing value indicator to use in numpy array. Defaults
             to the native missing value indicator of this array (pd.NA).

        Returns
        -------
        numpy.ndarray

        Examples
        --------
        An object-dtype is the default result

        >>> a = pd.array([True, False, pd.NA], dtype="boolean")
        >>> a.to_numpy()
        array([True, False, <NA>], dtype=object)

        When no missing values are present, an equivalent dtype can be used.

        >>> pd.array([True, False], dtype="boolean").to_numpy(dtype="bool")
        array([ True, False])
        >>> pd.array([1, 2], dtype="Int64").to_numpy("int64")
        array([1, 2])

        However, requesting such dtype will raise a ValueError if
        missing values are present and the default missing value :attr:`NA`
        is used.

        >>> a = pd.array([True, False, pd.NA], dtype="boolean")
        >>> a
        <BooleanArray>
        [True, False, <NA>]
        Length: 3, dtype: boolean

        >>> a.to_numpy(dtype="bool")
        Traceback (most recent call last):
        ...
        ValueError: cannot convert to bool numpy array in presence of missing values

        Specify a valid `na_value` instead

        >>> a.to_numpy(dtype="bool", na_value=False)
        array([ True, False, False])
        """
        if na_value is lib.no_default:
            na_value = libmissing.NA
        if dtype is None:
            # error: Incompatible types in assignment (expression has type
            # "Type[object]", variable has type "Union[str, dtype[Any], None]")
            dtype = object  # type: ignore[assignment]
        if self._hasna:
            if (
                not is_object_dtype(dtype)
                and not is_string_dtype(dtype)
                and na_value is libmissing.NA
            ):
                raise ValueError(
                    f"cannot convert to '{dtype}'-dtype NumPy array "
                    "with missing values. Specify an appropriate 'na_value' "
                    "for this dtype."
                )
            # don't pass copy to astype -> always need a copy since we are mutating
            data = self._data.astype(dtype)
            data[self._mask] = na_value
        else:
            data = self._data.astype(dtype, copy=copy)
        return data

    def astype(self, dtype: Dtype, copy: bool = True) -> ArrayLike:
        dtype = pandas_dtype(dtype)

        if is_dtype_equal(dtype, self.dtype):
            if copy:
                return self.copy()
            return self

        # if we are astyping to another nullable masked dtype, we can fastpath
        if isinstance(dtype, BaseMaskedDtype):
            # TODO deal with NaNs for FloatingArray case
            data = self._data.astype(dtype.numpy_dtype, copy=copy)
            # mask is copied depending on whether the data was copied, and
            # not directly depending on the `copy` keyword
            mask = self._mask if data is self._data else self._copy_mask()
            cls = dtype.construct_array_type()
            return cls(data, mask, copy=False)

        if isinstance(dtype, ExtensionDtype):
            eacls = dtype.construct_array_type()
            return eacls._from_sequence(self, dtype=dtype, copy=copy)

        raise NotImplementedError("subclass must implement astype to np.dtype")

    __array_priority__ = 1000  # higher than ndarray so ops dispatch to us

    def __array__(self, dtype: NpDtype | None = None) -> np.ndarray:
        """
        the array interface, return my values
        We return an object array here to preserve our scalar values
        """
        return self.to_numpy(dtype=dtype)

    def __arrow_array__(self, type=None):
        """
        Convert myself into a pyarrow Array.
        """
        import pyarrow as pa

        return pa.array(self._data, mask=self._mask, type=type)

    @property
    def _hasna(self) -> bool:
        # Note: this is expensive right now! The hope is that we can
        # make this faster by having an optional mask, but not have to change
        # source code using it..

        # error: Incompatible return value type (got "bool_", expected "bool")
        return self._mask is not None  # type: ignore[return-value]

    def isna(self) -> np.ndarray:
        if self._hasna:
            return self._mask.copy()
        else:
            return np.zeros_like(self._data, dtype=np.bool_)

    @property
    def _na_value(self):
        return self.dtype.na_value

    def _mask_as_ndarray(self):
        return self._mask if self._hasna else np.zeros_like(self._data, dtype=np.bool_)

    def _copy_mask(self):
        return self._mask.copy() if self._hasna else None

    @property
    def nbytes(self) -> int:
        mask_size = self._mask.nbytes if self._hasna else None.__sizeof__()
        return self._data.nbytes + mask_size

    @classmethod
    def _concat_same_type(
        cls: type[BaseMaskedArrayT], to_concat: Sequence[BaseMaskedArrayT]
    ) -> BaseMaskedArrayT:
        data = np.concatenate([x._data for x in to_concat])
        mask = np.concatenate([x._mask_as_ndarray() for x in to_concat])
        return cls(data, mask)

    def take(
        self: BaseMaskedArrayT,
        indexer,
        *,
        allow_fill: bool = False,
        fill_value: Scalar | None = None,
    ) -> BaseMaskedArrayT:
        # we always fill with 1 internally
        # to avoid upcasting
        data_fill_value = self._internal_fill_value if isna(fill_value) else fill_value
        result = take(
            self._data, indexer, fill_value=data_fill_value, allow_fill=allow_fill
        )

        mask = take(
            self._mask_as_ndarray(), indexer, fill_value=True, allow_fill=allow_fill
        )

        # if we are filling
        # we only fill where the indexer is null
        # not existing missing values
        # TODO(jreback) what if we have a non-na float as a fill value?
        if allow_fill and notna(fill_value):
            fill_mask = np.asarray(indexer) == -1
            result[fill_mask] = fill_value
            mask = mask ^ fill_mask

        return type(self)(result, mask, copy=False)

    # error: Return type "BooleanArray" of "isin" incompatible with return type
    # "ndarray" in supertype "ExtensionArray"
    def isin(self, values) -> BooleanArray:  # type: ignore[override]

        from pandas.core.arrays import BooleanArray

        result = isin(self._data, values)
        if self._hasna:
            if libmissing.NA in values:
                result += self._mask
            else:
                result *= np.invert(self._mask)

        return BooleanArray(result, copy=False)

    def copy(self: BaseMaskedArrayT) -> BaseMaskedArrayT:
        data, mask = self._data, self._mask
        data = data.copy()
        mask = self._copy_mask()
        return type(self)(data, mask, copy=False)

    @doc(ExtensionArray.factorize)
    def factorize(self, na_sentinel: int = -1) -> tuple[np.ndarray, ExtensionArray]:
        arr = self._data
        mask = self._mask

        codes, uniques = factorize_array(arr, na_sentinel=na_sentinel, mask=mask)

        # the hashtables don't handle all different types of bits
        uniques = uniques.astype(self.dtype.numpy_dtype, copy=False)
        # error: Incompatible types in assignment (expression has type
        # "BaseMaskedArray", variable has type "ndarray")
        uniques = type(self)(uniques)  # type: ignore[assignment]

        # error: Incompatible return value type (got "Tuple[ndarray, ndarray]",
        # expected "Tuple[ndarray, ExtensionArray]")
        return codes, uniques  # type: ignore[return-value]

    def value_counts(self, dropna: bool = True) -> Series:
        """
        Returns a Series containing counts of each unique value.

        Parameters
        ----------
        dropna : bool, default True
            Don't include counts of missing values.

        Returns
        -------
        counts : Series

        See Also
        --------
        Series.value_counts
        """
        from pandas import (
            Index,
            Series,
        )
        from pandas.arrays import IntegerArray

        # compute counts on the data with no nans
        data = self._data[~self._mask] if self._hasna else self._data
        value_counts = Index(data).value_counts()

        # TODO(extension)
        # if we have allow Index to hold an ExtensionArray
        # this is easier
        index = value_counts.index._values.astype(object)

        # if we want nans, count the mask
        if dropna:
            counts = value_counts._values
        else:
            counts = np.empty(len(value_counts) + 1, dtype="int64")
            counts[:-1] = value_counts
            counts[-1] = self._mask.sum() if self._hasna else 0

            index = Index(
                np.concatenate([index, np.array([self.dtype.na_value], dtype=object)]),
                dtype=object,
            )

        counts = IntegerArray(counts)

        return Series(counts, index=index)

    def _reduce(self, name: str, *, skipna: bool = True, **kwargs):
        data = self._data
        mask = self._mask_as_ndarray()

        if name in {"sum", "prod", "min", "max", "mean"}:
            op = getattr(masked_reductions, name)
            return op(data, mask, skipna=skipna, **kwargs)

        # coerce to a nan-aware float if needed
        # (we explicitly use NaN within reductions)
        if self._hasna:
            data = self.to_numpy("float64", na_value=np.nan)

        op = getattr(nanops, "nan" + name)
        result = op(data, axis=0, skipna=skipna, mask=mask, **kwargs)

        if np.isnan(result):
            return libmissing.NA

        return result
