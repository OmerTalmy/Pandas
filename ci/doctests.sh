#!/bin/bash

echo "inside $0"


source activate pandas
cd "$TRAVIS_BUILD_DIR"

RET=0

if [ "$DOCTEST" ]; then

    echo "Running doctests"

    # running all doctests is not yet working
    # pytest --doctest-modules --ignore=pandas/tests -v  pandas

    # if [ $? -ne "0" ]; then
    #     RET=1
    # fi

    # DataFrame / Series docstrings
    pytest --doctest-modules -v ../pandas/core/frame.py \
        -k"-axes -combine -itertuples -join -nlargest -nsmallest -nunique -pivot_table -quantile -query -reindex -reindex_axis -replace -round -set_index -stack -to_dict -to_stata -to_excel -to_parquet"

    if [ $? -ne "0" ]; then
        RET=1
    fi

    pytest --doctest-modules -v ../pandas/core/series.py \
        -k"-nonzero -reindex -searchsorted -to_dict -to_excel"

    if [ $? -ne "0" ]; then
        RET=1
    fi

    pytest --doctest-modules -v ../pandas/core/generic.py \
        -k"-_set_axis_name -_xs -describe -droplevel -groupby -interpolate -pct_change -pipe -reindex -reindex_axis -resample -sample -to_json -transpose -values -xs -to_hdf -to_xarray"

    if [ $? -ne "0" ]; then
        RET=1
    fi

    pytest --doctest-modules -v ../pandas/core/ops.py \
        -k"-_gen_eval_kwargs"

    if [ $? -ne "0" ]; then
        RET=1
    fi

    # top-level reshaping functions
    pytest --doctest-modules -v \
        ../pandas/core/reshape/concat.py \
        ../pandas/core/reshape/pivot.py \
        ../pandas/core/reshape/reshape.py \
        ../pandas/core/reshape/tile.py \
        -k"-crosstab -pivot_table -cut"

    if [ $? -ne "0" ]; then
        RET=1
    fi

else
    echo "NOT running doctests"
fi

exit $RET
