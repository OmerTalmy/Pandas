from cpython.datetime cimport (
    datetime,
    tzinfo,
)
from numpy cimport (
    int32_t,
    int64_t,
    ndarray,
)

from pandas._libs.tslibs.np_datetime cimport npy_datetimestruct


cdef class _TSObject:
    cdef readonly:
        npy_datetimestruct dts      # npy_datetimestruct
        int64_t value               # numpy dt64
        tzinfo tzinfo
        bint fold


cdef convert_to_tsobject(object ts, tzinfo tz, str unit,
                         bint dayfirst, bint yearfirst,
                         int32_t nanos=*)

cdef _TSObject convert_datetime_to_tsobject(datetime ts, tzinfo tz,
                                            int32_t nanos=*)

cdef int64_t get_datetime64_nanos(object val) except? -1

cpdef datetime localize_pydatetime(datetime dt, tzinfo tz)
cdef int64_t cast_from_unit(object ts, str unit) except? -1
cpdef (int64_t, int) precision_from_unit(str unit)
