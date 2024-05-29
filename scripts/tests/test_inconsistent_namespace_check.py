import pytest

from scripts.check_for_inconsistent_pandas_namespace import (
    check_for_inconsistent_pandas_namespace,
)

BAD_FILE_0 = (
    "from pandas import Categorical\n"
    "cat_0 = Categorical()\n"
    "cat_1 = pd.Categorical()"
)
BAD_FILE_1 = (
    "from pandas import Categorical\n"
    "cat_0 = pd.Categorical()\n"
    "cat_1 = Categorical()"
)
BAD_FILE_2 = (
    "from pandas import Categorical\n"
    "cat_0 = pandas.Categorical()\n"
    "cat_1 = Categorical()"
)
GOOD_FILE_0 = (
    "from pandas import Categorical\ncat_0 = Categorical()\ncat_1 = Categorical()"
)
GOOD_FILE_1 = "cat_0 = pd.Categorical()\ncat_1 = pd.Categorical()"
GOOD_FILE_2 = "from array import array\nimport pandas as pd\narr = pd.array([])"
EMPTY_FILE = ""  # Edge case: empty file
COMMENT_ONLY_FILE = "# This is a comment\n# Another comment"  # Edge case: file with only comments
NON_PANDAS_FILE = "from numpy import array\narr = array([])"  # Edge case: file with no pandas references
MIXED_GOOD_FILE = (
    "from pandas import Categorical\n"
    "from pandas import DataFrame\n"
    "cat = Categorical()\n"
    "df = DataFrame()\n"
)  # Mixed good case: multiple correct imports from pandas
PATH = "t.py"


@pytest.mark.parametrize(
    "content, expected",
    [
        (BAD_FILE_0, "t.py:3:8: Found both 'pd.Categorical' and 'Categorical' in t.py"),
        (BAD_FILE_1, "t.py:2:8: Found both 'pd.Categorical' and 'Categorical' in t.py"),
        (
            BAD_FILE_2,
            "t.py:2:8: Found both 'pandas.Categorical' and 'Categorical' in t.py",
        ),
    ],
)
def test_inconsistent_usage(content, expected, capsys):
    with pytest.raises(SystemExit):
        check_for_inconsistent_pandas_namespace(content, PATH, replace=False)
    result, _ = capsys.readouterr()
    assert result == expected


@pytest.mark.parametrize("content", [GOOD_FILE_0, GOOD_FILE_1, GOOD_FILE_2])
@pytest.mark.parametrize("replace", [True, False])
def test_consistent_usage(content, replace):
    # should not raise
    check_for_inconsistent_pandas_namespace(content, PATH, replace=replace)


@pytest.mark.parametrize("content", [BAD_FILE_0, BAD_FILE_1, BAD_FILE_2])
def test_inconsistent_usage_with_replace(content):
    result = check_for_inconsistent_pandas_namespace(content, PATH, replace=True)
    expected = (
        "from pandas import Categorical\ncat_0 = Categorical()\ncat_1 = Categorical()"
    )
    assert result == expected

@pytest.mark.parametrize("content", [EMPTY_FILE, COMMENT_ONLY_FILE, NON_PANDAS_FILE])
@pytest.mark.parametrize("replace", [True, False])
def test_edge_cases(content, replace):
    # should not raise or modify content
    result = check_for_inconsistent_pandas_namespace(content, PATH, replace=replace)
    assert result is None or result == content
