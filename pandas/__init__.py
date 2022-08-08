from __future__ import annotations

import inspect

__docformat__ = "restructuredtext"

# Let users know if they're missing any of our hard dependencies
_hard_dependencies = ("numpy", "pytz", "dateutil")
_missing_dependencies = []

for _dependency in _hard_dependencies:
    try:
        __import__(_dependency)
    except ImportError as _e:
        _missing_dependencies.append(f"{_dependency}: {_e}")

if _missing_dependencies:
    raise ImportError(
        "Unable to import required dependencies:\n" + "\n".join(_missing_dependencies)
    )
del _hard_dependencies, _dependency, _missing_dependencies

# numpy compat
from pandas.compat import is_numpy_dev as _is_numpy_dev  # pyright: ignore # noqa:F401

try:
    from pandas._libs import (
        hashtable as _hashtable,
        lib as _lib,
        tslib as _tslib,
    )
except ImportError as _err:  # pragma: no cover
    _module = _err.name
    raise ImportError(
        f"C extension: {_module} not built. If you want to import "
        "pandas from the source directory, you may need to run "
        "'python setup.py build_ext --force' to build the C extensions first."
    ) from _err
else:
    del _tslib, _lib, _hashtable

from pandas._config import (
    describe_option,
    get_option,
    option_context,
    options,
    reset_option,
    set_option,
)

from pandas.util._print_versions import show_versions
from pandas.util._tester import test

from pandas import (
    api,
    arrays,
    errors,
    io,
    plotting,
    tseries,
)
from pandas import testing  # noqa:PDF015

# use the closest tagged version if possible
from pandas._version import get_versions
from pandas.core.api import (  # dtype; missing; indexes; tseries; conversion; misc
    NA,
    BooleanDtype,
    Categorical,
    CategoricalDtype,
    CategoricalIndex,
    DataFrame,
    DateOffset,
    DatetimeIndex,
    DatetimeTZDtype,
    Flags,
    Float32Dtype,
    Float64Dtype,
    Grouper,
    Index,
    IndexSlice,
    Int8Dtype,
    Int16Dtype,
    Int32Dtype,
    Int64Dtype,
    Interval,
    IntervalDtype,
    IntervalIndex,
    MultiIndex,
    NamedAgg,
    NaT,
    Period,
    PeriodDtype,
    PeriodIndex,
    RangeIndex,
    Series,
    StringDtype,
    Timedelta,
    TimedeltaIndex,
    Timestamp,
    UInt8Dtype,
    UInt16Dtype,
    UInt32Dtype,
    UInt64Dtype,
    array,
    bdate_range,
    date_range,
    factorize,
    interval_range,
    isna,
    isnull,
    notna,
    notnull,
    period_range,
    set_eng_float_format,
    timedelta_range,
    to_datetime,
    to_numeric,
    to_timedelta,
    unique,
    value_counts,
)
from pandas.core.arrays.sparse import SparseDtype
from pandas.core.computation.api import eval

# let init-time option registration happen
import pandas.core.config_init  # pyright: ignore # noqa:F401
from pandas.core.reshape.api import (
    concat,
    crosstab,
    cut,
    from_dummies,
    get_dummies,
    lreshape,
    melt,
    merge,
    merge_asof,
    merge_ordered,
    pivot,
    pivot_table,
    qcut,
    wide_to_long,
)

from pandas.io.api import (  # excel; parsers; pickle; pytables; sql; misc
    ExcelFile,
    ExcelWriter,
    HDFStore,
    read_clipboard,
    read_csv,
    read_excel,
    read_feather,
    read_fwf,
    read_gbq,
    read_hdf,
    read_html,
    read_json,
    read_orc,
    read_parquet,
    read_pickle,
    read_sas,
    read_spss,
    read_sql,
    read_sql_query,
    read_sql_table,
    read_stata,
    read_table,
    read_xml,
    to_pickle,
)
from pandas.io.json import _json_normalize as json_normalize
from pandas.tseries import offsets
from pandas.tseries.api import infer_freq

v = get_versions()
__version__ = v.get("closest-tag", v["version"])
__git_version__ = v.get("full-revisionid")
del get_versions, v

# GH 27101
__deprecated_num_index_names = ["Float64Index", "Int64Index", "UInt64Index"]


def __dir__() -> list[str]:
    # GH43028
    # Int64Index etc. are deprecated, but we still want them to be available in the dir.
    # Remove in Pandas 2.0, when we remove Int64Index etc. from the code base.
    return list(globals().keys()) + __deprecated_num_index_names


def __getattr__(name):
    import warnings
    from pandas.util._exceptions import find_stack_level

    if name in __deprecated_num_index_names:
        warnings.warn(
            f"pandas.{name} is deprecated "
            "and will be removed from pandas in a future version. "
            "Use pandas.Index with the appropriate dtype instead.",
            FutureWarning,
            stacklevel=find_stack_level(inspect.currentframe()),
        )
        from pandas.core.api import (
            Float64Index,
            Int64Index,
            UInt64Index,
        )

        return {
            "Float64Index": Float64Index,
            "Int64Index": Int64Index,
            "UInt64Index": UInt64Index,
        }[name]
    elif name == "datetime":
        warnings.warn(
            "The pandas.datetime class is deprecated "
            "and will be removed from pandas in a future version. "
            "Import from datetime module instead.",
            FutureWarning,
            stacklevel=find_stack_level(inspect.currentframe()),
        )

        from datetime import datetime as dt

        return dt

    elif name == "np":

        warnings.warn(
            "The pandas.np module is deprecated "
            "and will be removed from pandas in a future version. "
            "Import numpy directly instead.",
            FutureWarning,
            stacklevel=find_stack_level(inspect.currentframe()),
        )
        import numpy as np

        return np

    elif name in {"SparseSeries", "SparseDataFrame"}:
        warnings.warn(
            f"The {name} class is removed from pandas. Accessing it from "
            "the top-level namespace will also be removed in the next version.",
            FutureWarning,
            stacklevel=find_stack_level(inspect.currentframe()),
        )

        return type(name, (), {})

    elif name == "SparseArray":

        warnings.warn(
            "The pandas.SparseArray class is deprecated "
            "and will be removed from pandas in a future version. "
            "Use pandas.arrays.SparseArray instead.",
            FutureWarning,
            stacklevel=find_stack_level(inspect.currentframe()),
        )
        from pandas.core.arrays.sparse import SparseArray as _SparseArray

        return _SparseArray

    raise AttributeError(f"module 'pandas' has no attribute '{name}'")


# module level doc-string
__doc__ = """
pandas - a powerful data analysis and manipulation library for Python
=====================================================================

**pandas** is a Python package providing fast, flexible, and expressive data
structures designed to make working with "relational" or "labeled" data both
easy and intuitive. It aims to be the fundamental high-level building block for
doing practical, **real world** data analysis in Python. Additionally, it has
the broader goal of becoming **the most powerful and flexible open source data
analysis / manipulation tool available in any language**. It is already well on
its way toward this goal.

Main Features
-------------
Here are just a few of the things that pandas does well:

  - Easy handling of missing data in floating point as well as non-floating
    point data.
  - Size mutability: columns can be inserted and deleted from DataFrame and
    higher dimensional objects
  - Automatic and explicit data alignment: objects can be explicitly aligned
    to a set of labels, or the user can simply ignore the labels and let
    `Series`, `DataFrame`, etc. automatically align the data for you in
    computations.
  - Powerful, flexible group by functionality to perform split-apply-combine
    operations on data sets, for both aggregating and transforming data.
  - Make it easy to convert ragged, differently-indexed data in other Python
    and NumPy data structures into DataFrame objects.
  - Intelligent label-based slicing, fancy indexing, and subsetting of large
    data sets.
  - Intuitive merging and joining data sets.
  - Flexible reshaping and pivoting of data sets.
  - Hierarchical labeling of axes (possible to have multiple labels per tick).
  - Robust IO tools for loading data from flat files (CSV and delimited),
    Excel files, databases, and saving/loading data from the ultrafast HDF5
    format.
  - Time series-specific functionality: date range generation and frequency
    conversion, moving window statistics, date shifting and lagging.
"""

# Use __all__ to let type checkers know what is part of the public API.
# Pandas is not (yet) a py.typed library: the public API is determined
# based on the documentation.
__all__ = [
    "BooleanDtype",
    "Categorical",
    "CategoricalDtype",
    "CategoricalIndex",
    "DataFrame",
    "DateOffset",
    "DatetimeIndex",
    "DatetimeTZDtype",
    "ExcelFile",
    "ExcelWriter",
    "Flags",
    "Float32Dtype",
    "Float64Dtype",
    "Grouper",
    "HDFStore",
    "Index",
    "IndexSlice",
    "Int16Dtype",
    "Int32Dtype",
    "Int64Dtype",
    "Int8Dtype",
    "Interval",
    "IntervalDtype",
    "IntervalIndex",
    "MultiIndex",
    "NA",
    "NaT",
    "NamedAgg",
    "Period",
    "PeriodDtype",
    "PeriodIndex",
    "RangeIndex",
    "Series",
    "SparseDtype",
    "StringDtype",
    "Timedelta",
    "TimedeltaIndex",
    "Timestamp",
    "UInt16Dtype",
    "UInt32Dtype",
    "UInt64Dtype",
    "UInt8Dtype",
    "api",
    "array",
    "arrays",
    "bdate_range",
    "concat",
    "crosstab",
    "cut",
    "date_range",
    "describe_option",
    "errors",
    "eval",
    "factorize",
    "get_dummies",
    "from_dummies",
    "get_option",
    "infer_freq",
    "interval_range",
    "io",
    "isna",
    "isnull",
    "json_normalize",
    "lreshape",
    "melt",
    "merge",
    "merge_asof",
    "merge_ordered",
    "notna",
    "notnull",
    "offsets",
    "option_context",
    "options",
    "period_range",
    "pivot",
    "pivot_table",
    "plotting",
    "qcut",
    "read_clipboard",
    "read_csv",
    "read_excel",
    "read_feather",
    "read_fwf",
    "read_gbq",
    "read_hdf",
    "read_html",
    "read_json",
    "read_orc",
    "read_parquet",
    "read_pickle",
    "read_sas",
    "read_spss",
    "read_sql",
    "read_sql_query",
    "read_sql_table",
    "read_stata",
    "read_table",
    "read_xml",
    "reset_option",
    "set_eng_float_format",
    "set_option",
    "show_versions",
    "test",
    "testing",
    "timedelta_range",
    "to_datetime",
    "to_numeric",
    "to_pickle",
    "to_timedelta",
    "tseries",
    "unique",
    "value_counts",
    "wide_to_long",
]
