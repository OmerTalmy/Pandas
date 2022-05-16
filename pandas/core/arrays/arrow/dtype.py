from __future__ import annotations

import numpy as np
import pyarrow as pa

from pandas._typing import DtypeObj
from pandas.util._decorators import cache_readonly

from pandas.core.dtypes.base import StorageExtensionDtype

from pandas.core.arrays.arrow import ArrowExtensionArray


class ArrowDtype(StorageExtensionDtype):
    """
    Base class for dtypes for ArrowExtensionArray.
    Modeled after BaseMaskedDtype
    """

    na_value = pa.NA

    def __init__(self, pa_dtype: pa.DataType) -> None:
        super().__init__("pyarrow")
        if not isinstance(pa_dtype, pa.DataType):
            raise ValueError("pa_dtype must be an instance of a pyarrow.DataType")
        self.pa_dtype = pa_dtype

    @property
    def type(self):
        """
        The scalar type for the array, e.g. ``int``
        """
        return self.pa_dtype

    @property
    def name(self) -> str:
        """
        A string identifying the data type.
        """
        return str(self.pa_dtype)

    @cache_readonly
    def numpy_dtype(self) -> np.dtype:
        """Return an instance of the related numpy dtype"""
        return self.type.to_pandas_dtype()

    @cache_readonly
    def kind(self) -> str:
        return self.numpy_dtype.kind

    @cache_readonly
    def itemsize(self) -> int:
        """Return the number of bytes in this dtype"""
        return self.numpy_dtype.itemsize

    @classmethod
    def construct_array_type(cls):
        """
        Return the array type associated with this dtype.

        Returns
        -------
        type
        """
        return ArrowExtensionArray

    @classmethod
    def construct_from_string(cls, string: str):
        """
        Construct this type from a string.

        Parameters
        ----------
        string : str
            string should follow the format f"{pyarrow_type}[pyarrow]"
            e.g. int64[pyarrow]
        """
        if not isinstance(string, str):
            raise TypeError(
                f"'construct_from_string' expects a string, got {type(string)}"
            )
        if not string.endswith("[pyarrow]"):
            raise TypeError(f"string {string} must end with '[pyarrow]'")
        base_type = string.split("[pyarrow]")[0]
        pa_dtype = getattr(pa, base_type, None)
        if pa_dtype is None:
            raise TypeError(f"'{base_type}' is not a valid pyarrow data type.")
        return cls(pa_dtype())

    @property
    def _is_numeric(self) -> bool:
        """
        Whether columns with this dtype should be considered numeric.
        """
        # TODO: pa.types.is_boolean?
        return (
            pa.types.is_integer(self.pa_dtype)
            or pa.types.is_floating(self.pa_dtype)
            or pa.types.is_decimal(self.pa_dtype)
        )

    @property
    def _is_boolean(self) -> bool:
        """
        Whether this dtype should be considered boolean.
        """
        return pa.types.is_boolean(self.pa_dtype)

    def _get_common_dtype(self, dtypes: list[DtypeObj]) -> DtypeObj | None:
        # We unwrap any masked dtypes, find the common dtype we would use
        #  for that, then re-mask the result.
        # Mirrors BaseMaskedDtype
        from pandas.core.dtypes.cast import find_common_type

        new_dtype = find_common_type(
            [
                dtype.numpy_dtype if isinstance(dtype, ArrowDtype) else dtype
                for dtype in dtypes
            ]
        )
        if not isinstance(new_dtype, np.dtype):
            return None
        pa_dtype = pa.from_numpy_dtype(new_dtype)
        return type(self)(pa_dtype)

    def __from_arrow__(self, array: pa.Array | pa.ChunkedArray):
        """
        Construct IntegerArray/FloatingArray from pyarrow Array/ChunkedArray.
        """
        array_class = self.construct_array_type()
        return array_class(array)
