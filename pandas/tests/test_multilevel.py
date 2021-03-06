import datetime
from io import StringIO
import itertools
from itertools import product

import numpy as np
from numpy.random import randn
import pytest

from pandas.core.dtypes.common import is_float_dtype, is_integer_dtype

import pandas as pd
from pandas import DataFrame, Index, MultiIndex, Series, Timestamp
import pandas._testing as tm

AGG_FUNCTIONS = [
    "sum",
    "prod",
    "min",
    "max",
    "median",
    "mean",
    "skew",
    "mad",
    "std",
    "var",
    "sem",
]


class Base:
    def setup_method(self, method):

        # create test series object
        arrays = [
            ["bar", "bar", "baz", "baz", "qux", "qux", "foo", "foo"],
            ["one", "two", "one", "two", "one", "two", "one", "two"],
        ]
        tuples = zip(*arrays)
        index = MultiIndex.from_tuples(tuples)
        s = Series(randn(8), index=index)
        s[3] = np.NaN
        self.series = s


class TestMultiLevel(Base):
    def test_append(self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data

        a, b = frame[:5], frame[5:]

        result = a.append(b)
        tm.assert_frame_equal(result, frame)

        result = a["A"].append(b["A"])
        tm.assert_series_equal(result, frame["A"])

    def test_dataframe_constructor(self):
        multi = DataFrame(
            np.random.randn(4, 4),
            index=[np.array(["a", "a", "b", "b"]), np.array(["x", "y", "x", "y"])],
        )
        assert isinstance(multi.index, MultiIndex)
        assert not isinstance(multi.columns, MultiIndex)

        multi = DataFrame(
            np.random.randn(4, 4), columns=[["a", "a", "b", "b"], ["x", "y", "x", "y"]]
        )
        assert isinstance(multi.columns, MultiIndex)

    def test_series_constructor(self):
        multi = Series(
            1.0, index=[np.array(["a", "a", "b", "b"]), np.array(["x", "y", "x", "y"])]
        )
        assert isinstance(multi.index, MultiIndex)

        multi = Series(1.0, index=[["a", "a", "b", "b"], ["x", "y", "x", "y"]])
        assert isinstance(multi.index, MultiIndex)

        multi = Series(range(4), index=[["a", "a", "b", "b"], ["x", "y", "x", "y"]])
        assert isinstance(multi.index, MultiIndex)

    def test_reindex_level(self, multiindex_year_month_day_dataframe_random_data):
        # axis=0
        ymd = multiindex_year_month_day_dataframe_random_data

        month_sums = ymd.sum(level="month")
        result = month_sums.reindex(ymd.index, level=1)
        expected = ymd.groupby(level="month").transform(np.sum)

        tm.assert_frame_equal(result, expected)

        # Series
        result = month_sums["A"].reindex(ymd.index, level=1)
        expected = ymd["A"].groupby(level="month").transform(np.sum)
        tm.assert_series_equal(result, expected, check_names=False)

        # axis=1
        month_sums = ymd.T.sum(axis=1, level="month")
        result = month_sums.reindex(columns=ymd.index, level=1)
        expected = ymd.groupby(level="month").transform(np.sum).T
        tm.assert_frame_equal(result, expected)

    def test_binops_level(self, multiindex_year_month_day_dataframe_random_data):
        ymd = multiindex_year_month_day_dataframe_random_data

        def _check_op(opname):
            op = getattr(DataFrame, opname)
            month_sums = ymd.sum(level="month")
            result = op(ymd, month_sums, level="month")

            broadcasted = ymd.groupby(level="month").transform(np.sum)
            expected = op(ymd, broadcasted)
            tm.assert_frame_equal(result, expected)

            # Series
            op = getattr(Series, opname)
            result = op(ymd["A"], month_sums["A"], level="month")
            broadcasted = ymd["A"].groupby(level="month").transform(np.sum)
            expected = op(ymd["A"], broadcasted)
            expected.name = "A"
            tm.assert_series_equal(result, expected)

        _check_op("sub")
        _check_op("add")
        _check_op("mul")
        _check_op("div")

    def test_pickle(
        self,
        multiindex_year_month_day_dataframe_random_data,
        multiindex_dataframe_random_data,
    ):
        ymd = multiindex_year_month_day_dataframe_random_data
        frame = multiindex_dataframe_random_data

        def _test_roundtrip(frame):
            unpickled = tm.round_trip_pickle(frame)
            tm.assert_frame_equal(frame, unpickled)

        _test_roundtrip(frame)
        _test_roundtrip(frame.T)
        _test_roundtrip(ymd)
        _test_roundtrip(ymd.T)

    def test_reindex(self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data

        expected = frame.iloc[[0, 3]]
        reindexed = frame.loc[[("foo", "one"), ("bar", "one")]]
        tm.assert_frame_equal(reindexed, expected)

    def test_reindex_preserve_levels(
        self, multiindex_year_month_day_dataframe_random_data
    ):
        ymd = multiindex_year_month_day_dataframe_random_data

        new_index = ymd.index[::10]
        chunk = ymd.reindex(new_index)
        assert chunk.index is new_index

        chunk = ymd.loc[new_index]
        assert chunk.index is new_index

        ymdT = ymd.T
        chunk = ymdT.reindex(columns=new_index)
        assert chunk.columns is new_index

        chunk = ymdT.loc[:, new_index]
        assert chunk.columns is new_index

    def test_repr_to_string(
        self,
        multiindex_year_month_day_dataframe_random_data,
        multiindex_dataframe_random_data,
    ):
        ymd = multiindex_year_month_day_dataframe_random_data
        frame = multiindex_dataframe_random_data

        repr(frame)
        repr(ymd)
        repr(frame.T)
        repr(ymd.T)

        buf = StringIO()
        frame.to_string(buf=buf)
        ymd.to_string(buf=buf)
        frame.T.to_string(buf=buf)
        ymd.T.to_string(buf=buf)

    def test_repr_name_coincide(self):
        index = MultiIndex.from_tuples(
            [("a", 0, "foo"), ("b", 1, "bar")], names=["a", "b", "c"]
        )

        df = DataFrame({"value": [0, 1]}, index=index)

        lines = repr(df).split("\n")
        assert lines[2].startswith("a 0 foo")

    def test_delevel_infer_dtype(self):
        tuples = list(product(["foo", "bar"], [10, 20], [1.0, 1.1]))
        index = MultiIndex.from_tuples(tuples, names=["prm0", "prm1", "prm2"])
        df = DataFrame(np.random.randn(8, 3), columns=["A", "B", "C"], index=index)
        deleveled = df.reset_index()
        assert is_integer_dtype(deleveled["prm1"])
        assert is_float_dtype(deleveled["prm2"])

    def test_reset_index_with_drop(
        self, multiindex_year_month_day_dataframe_random_data
    ):
        ymd = multiindex_year_month_day_dataframe_random_data

        deleveled = ymd.reset_index(drop=True)
        assert len(deleveled.columns) == len(ymd.columns)
        assert deleveled.index.name == ymd.index.name

        deleveled = self.series.reset_index()
        assert isinstance(deleveled, DataFrame)
        assert len(deleveled.columns) == len(self.series.index.levels) + 1
        assert deleveled.index.name == self.series.index.name

        deleveled = self.series.reset_index(drop=True)
        assert isinstance(deleveled, Series)
        assert deleveled.index.name == self.series.index.name

    def test_count_level_series(self):
        index = MultiIndex(
            levels=[["foo", "bar", "baz"], ["one", "two", "three", "four"]],
            codes=[[0, 0, 0, 2, 2], [2, 0, 1, 1, 2]],
        )

        s = Series(np.random.randn(len(index)), index=index)

        result = s.count(level=0)
        expected = s.groupby(level=0).count()
        tm.assert_series_equal(
            result.astype("f8"), expected.reindex(result.index).fillna(0)
        )

        result = s.count(level=1)
        expected = s.groupby(level=1).count()
        tm.assert_series_equal(
            result.astype("f8"), expected.reindex(result.index).fillna(0)
        )

    def test_get_level_number_out_of_bounds(self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data

        with pytest.raises(IndexError, match="Too many levels"):
            frame.index._get_level_number(2)
        with pytest.raises(IndexError, match="not a valid level number"):
            frame.index._get_level_number(-3)

    def test_unstack(self, multiindex_year_month_day_dataframe_random_data):
        # just check that it works for now
        ymd = multiindex_year_month_day_dataframe_random_data

        unstacked = ymd.unstack()
        unstacked.unstack()

        # test that ints work
        ymd.astype(int).unstack()

        # test that int32 work
        ymd.astype(np.int32).unstack()

    @pytest.mark.parametrize(
        "result_rows,result_columns,index_product,expected_row",
        [
            (
                [[1, 1, None, None, 30.0, None], [2, 2, None, None, 30.0, None]],
                ["ix1", "ix2", "col1", "col2", "col3", "col4"],
                2,
                [None, None, 30.0, None],
            ),
            (
                [[1, 1, None, None, 30.0], [2, 2, None, None, 30.0]],
                ["ix1", "ix2", "col1", "col2", "col3"],
                2,
                [None, None, 30.0],
            ),
            (
                [[1, 1, None, None, 30.0], [2, None, None, None, 30.0]],
                ["ix1", "ix2", "col1", "col2", "col3"],
                None,
                [None, None, 30.0],
            ),
        ],
    )
    def test_unstack_partial(
        self, result_rows, result_columns, index_product, expected_row
    ):
        # check for regressions on this issue:
        # https://github.com/pandas-dev/pandas/issues/19351
        # make sure DataFrame.unstack() works when its run on a subset of the DataFrame
        # and the Index levels contain values that are not present in the subset
        result = pd.DataFrame(result_rows, columns=result_columns).set_index(
            ["ix1", "ix2"]
        )
        result = result.iloc[1:2].unstack("ix2")
        expected = pd.DataFrame(
            [expected_row],
            columns=pd.MultiIndex.from_product(
                [result_columns[2:], [index_product]], names=[None, "ix2"]
            ),
            index=pd.Index([2], name="ix1"),
        )
        tm.assert_frame_equal(result, expected)

    def test_unstack_multiple_no_empty_columns(self):
        index = MultiIndex.from_tuples(
            [(0, "foo", 0), (0, "bar", 0), (1, "baz", 1), (1, "qux", 1)]
        )

        s = Series(np.random.randn(4), index=index)

        unstacked = s.unstack([1, 2])
        expected = unstacked.dropna(axis=1, how="all")
        tm.assert_frame_equal(unstacked, expected)

    def test_stack(self, multiindex_year_month_day_dataframe_random_data):
        ymd = multiindex_year_month_day_dataframe_random_data

        # regular roundtrip
        unstacked = ymd.unstack()
        restacked = unstacked.stack()
        tm.assert_frame_equal(restacked, ymd)

        unlexsorted = ymd.sort_index(level=2)

        unstacked = unlexsorted.unstack(2)
        restacked = unstacked.stack()
        tm.assert_frame_equal(restacked.sort_index(level=0), ymd)

        unlexsorted = unlexsorted[::-1]
        unstacked = unlexsorted.unstack(1)
        restacked = unstacked.stack().swaplevel(1, 2)
        tm.assert_frame_equal(restacked.sort_index(level=0), ymd)

        unlexsorted = unlexsorted.swaplevel(0, 1)
        unstacked = unlexsorted.unstack(0).swaplevel(0, 1, axis=1)
        restacked = unstacked.stack(0).swaplevel(1, 2)
        tm.assert_frame_equal(restacked.sort_index(level=0), ymd)

        # columns unsorted
        unstacked = ymd.unstack()
        unstacked = unstacked.sort_index(axis=1, ascending=False)
        restacked = unstacked.stack()
        tm.assert_frame_equal(restacked, ymd)

        # more than 2 levels in the columns
        unstacked = ymd.unstack(1).unstack(1)

        result = unstacked.stack(1)
        expected = ymd.unstack()
        tm.assert_frame_equal(result, expected)

        result = unstacked.stack(2)
        expected = ymd.unstack(1)
        tm.assert_frame_equal(result, expected)

        result = unstacked.stack(0)
        expected = ymd.stack().unstack(1).unstack(1)
        tm.assert_frame_equal(result, expected)

        # not all levels present in each echelon
        unstacked = ymd.unstack(2).loc[:, ::3]
        stacked = unstacked.stack().stack()
        ymd_stacked = ymd.stack()
        tm.assert_series_equal(stacked, ymd_stacked.reindex(stacked.index))

        # stack with negative number
        result = ymd.unstack(0).stack(-2)
        expected = ymd.unstack(0).stack(0)

        # GH10417
        def check(left, right):
            tm.assert_series_equal(left, right)
            assert left.index.is_unique is False
            li, ri = left.index, right.index
            tm.assert_index_equal(li, ri)

        df = DataFrame(
            np.arange(12).reshape(4, 3),
            index=list("abab"),
            columns=["1st", "2nd", "3rd"],
        )

        mi = MultiIndex(
            levels=[["a", "b"], ["1st", "2nd", "3rd"]],
            codes=[np.tile(np.arange(2).repeat(3), 2), np.tile(np.arange(3), 4)],
        )

        left, right = df.stack(), Series(np.arange(12), index=mi)
        check(left, right)

        df.columns = ["1st", "2nd", "1st"]
        mi = MultiIndex(
            levels=[["a", "b"], ["1st", "2nd"]],
            codes=[np.tile(np.arange(2).repeat(3), 2), np.tile([0, 1, 0], 4)],
        )

        left, right = df.stack(), Series(np.arange(12), index=mi)
        check(left, right)

        tpls = ("a", 2), ("b", 1), ("a", 1), ("b", 2)
        df.index = MultiIndex.from_tuples(tpls)
        mi = MultiIndex(
            levels=[["a", "b"], [1, 2], ["1st", "2nd"]],
            codes=[
                np.tile(np.arange(2).repeat(3), 2),
                np.repeat([1, 0, 1], [3, 6, 3]),
                np.tile([0, 1, 0], 4),
            ],
        )

        left, right = df.stack(), Series(np.arange(12), index=mi)
        check(left, right)

    def test_unstack_odd_failure(self):
        data = """day,time,smoker,sum,len
Fri,Dinner,No,8.25,3.
Fri,Dinner,Yes,27.03,9
Fri,Lunch,No,3.0,1
Fri,Lunch,Yes,13.68,6
Sat,Dinner,No,139.63,45
Sat,Dinner,Yes,120.77,42
Sun,Dinner,No,180.57,57
Sun,Dinner,Yes,66.82,19
Thur,Dinner,No,3.0,1
Thur,Lunch,No,117.32,44
Thur,Lunch,Yes,51.51,17"""

        df = pd.read_csv(StringIO(data)).set_index(["day", "time", "smoker"])

        # it works, #2100
        result = df.unstack(2)

        recons = result.stack()
        tm.assert_frame_equal(recons, df)

    def test_stack_mixed_dtype(self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data

        df = frame.T
        df["foo", "four"] = "foo"
        df = df.sort_index(level=1, axis=1)

        stacked = df.stack()
        result = df["foo"].stack().sort_index()
        tm.assert_series_equal(stacked["foo"], result, check_names=False)
        assert result.name is None
        assert stacked["bar"].dtype == np.float_

    def test_unstack_bug(self):
        df = DataFrame(
            {
                "state": ["naive", "naive", "naive", "activ", "activ", "activ"],
                "exp": ["a", "b", "b", "b", "a", "a"],
                "barcode": [1, 2, 3, 4, 1, 3],
                "v": ["hi", "hi", "bye", "bye", "bye", "peace"],
                "extra": np.arange(6.0),
            }
        )

        result = df.groupby(["state", "exp", "barcode", "v"]).apply(len)

        unstacked = result.unstack()
        restacked = unstacked.stack()
        tm.assert_series_equal(restacked, result.reindex(restacked.index).astype(float))

    def test_stack_unstack_preserve_names(self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data

        unstacked = frame.unstack()
        assert unstacked.index.name == "first"
        assert unstacked.columns.names == ["exp", "second"]

        restacked = unstacked.stack()
        assert restacked.index.names == frame.index.names

    @pytest.mark.parametrize("method", ["stack", "unstack"])
    def test_stack_unstack_wrong_level_name(
        self, method, multiindex_dataframe_random_data
    ):
        # GH 18303 - wrong level name should raise
        frame = multiindex_dataframe_random_data

        # A DataFrame with flat axes:
        df = frame.loc["foo"]

        with pytest.raises(KeyError, match="does not match index name"):
            getattr(df, method)("mistake")

        if method == "unstack":
            # Same on a Series:
            s = df.iloc[:, 0]
            with pytest.raises(KeyError, match="does not match index name"):
                getattr(s, method)("mistake")

    def test_unused_level_raises(self):
        # GH 20410
        mi = MultiIndex(
            levels=[["a_lot", "onlyone", "notevenone"], [1970, ""]],
            codes=[[1, 0], [1, 0]],
        )
        df = DataFrame(-1, index=range(3), columns=mi)

        with pytest.raises(KeyError, match="notevenone"):
            df["notevenone"]

    def test_unstack_level_name(self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data

        result = frame.unstack("second")
        expected = frame.unstack(level=1)
        tm.assert_frame_equal(result, expected)

    def test_stack_level_name(self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data

        unstacked = frame.unstack("second")
        result = unstacked.stack("exp")
        expected = frame.unstack().stack(0)
        tm.assert_frame_equal(result, expected)

        result = frame.stack("exp")
        expected = frame.stack()
        tm.assert_series_equal(result, expected)

    def test_stack_unstack_multiple(
        self, multiindex_year_month_day_dataframe_random_data
    ):
        ymd = multiindex_year_month_day_dataframe_random_data

        unstacked = ymd.unstack(["year", "month"])
        expected = ymd.unstack("year").unstack("month")
        tm.assert_frame_equal(unstacked, expected)
        assert unstacked.columns.names == expected.columns.names

        # series
        s = ymd["A"]
        s_unstacked = s.unstack(["year", "month"])
        tm.assert_frame_equal(s_unstacked, expected["A"])

        restacked = unstacked.stack(["year", "month"])
        restacked = restacked.swaplevel(0, 1).swaplevel(1, 2)
        restacked = restacked.sort_index(level=0)

        tm.assert_frame_equal(restacked, ymd)
        assert restacked.index.names == ymd.index.names

        # GH #451
        unstacked = ymd.unstack([1, 2])
        expected = ymd.unstack(1).unstack(1).dropna(axis=1, how="all")
        tm.assert_frame_equal(unstacked, expected)

        unstacked = ymd.unstack([2, 1])
        expected = ymd.unstack(2).unstack(1).dropna(axis=1, how="all")
        tm.assert_frame_equal(unstacked, expected.loc[:, unstacked.columns])

    def test_stack_names_and_numbers(
        self, multiindex_year_month_day_dataframe_random_data
    ):
        ymd = multiindex_year_month_day_dataframe_random_data

        unstacked = ymd.unstack(["year", "month"])

        # Can't use mixture of names and numbers to stack
        with pytest.raises(ValueError, match="level should contain"):
            unstacked.stack([0, "month"])

    def test_stack_multiple_out_of_bounds(
        self, multiindex_year_month_day_dataframe_random_data
    ):
        # nlevels == 3
        ymd = multiindex_year_month_day_dataframe_random_data

        unstacked = ymd.unstack(["year", "month"])

        with pytest.raises(IndexError, match="Too many levels"):
            unstacked.stack([2, 3])
        with pytest.raises(IndexError, match="not a valid level number"):
            unstacked.stack([-4, -3])

    def test_unstack_period_series(self):
        # GH 4342
        idx1 = pd.PeriodIndex(
            ["2013-01", "2013-01", "2013-02", "2013-02", "2013-03", "2013-03"],
            freq="M",
            name="period",
        )
        idx2 = Index(["A", "B"] * 3, name="str")
        value = [1, 2, 3, 4, 5, 6]

        idx = MultiIndex.from_arrays([idx1, idx2])
        s = Series(value, index=idx)

        result1 = s.unstack()
        result2 = s.unstack(level=1)
        result3 = s.unstack(level=0)

        e_idx = pd.PeriodIndex(
            ["2013-01", "2013-02", "2013-03"], freq="M", name="period"
        )
        expected = DataFrame(
            {"A": [1, 3, 5], "B": [2, 4, 6]}, index=e_idx, columns=["A", "B"]
        )
        expected.columns.name = "str"

        tm.assert_frame_equal(result1, expected)
        tm.assert_frame_equal(result2, expected)
        tm.assert_frame_equal(result3, expected.T)

        idx1 = pd.PeriodIndex(
            ["2013-01", "2013-01", "2013-02", "2013-02", "2013-03", "2013-03"],
            freq="M",
            name="period1",
        )

        idx2 = pd.PeriodIndex(
            ["2013-12", "2013-11", "2013-10", "2013-09", "2013-08", "2013-07"],
            freq="M",
            name="period2",
        )
        idx = MultiIndex.from_arrays([idx1, idx2])
        s = Series(value, index=idx)

        result1 = s.unstack()
        result2 = s.unstack(level=1)
        result3 = s.unstack(level=0)

        e_idx = pd.PeriodIndex(
            ["2013-01", "2013-02", "2013-03"], freq="M", name="period1"
        )
        e_cols = pd.PeriodIndex(
            ["2013-07", "2013-08", "2013-09", "2013-10", "2013-11", "2013-12"],
            freq="M",
            name="period2",
        )
        expected = DataFrame(
            [
                [np.nan, np.nan, np.nan, np.nan, 2, 1],
                [np.nan, np.nan, 4, 3, np.nan, np.nan],
                [6, 5, np.nan, np.nan, np.nan, np.nan],
            ],
            index=e_idx,
            columns=e_cols,
        )

        tm.assert_frame_equal(result1, expected)
        tm.assert_frame_equal(result2, expected)
        tm.assert_frame_equal(result3, expected.T)

    def test_unstack_period_frame(self):
        # GH 4342
        idx1 = pd.PeriodIndex(
            ["2014-01", "2014-02", "2014-02", "2014-02", "2014-01", "2014-01"],
            freq="M",
            name="period1",
        )
        idx2 = pd.PeriodIndex(
            ["2013-12", "2013-12", "2014-02", "2013-10", "2013-10", "2014-02"],
            freq="M",
            name="period2",
        )
        value = {"A": [1, 2, 3, 4, 5, 6], "B": [6, 5, 4, 3, 2, 1]}
        idx = MultiIndex.from_arrays([idx1, idx2])
        df = DataFrame(value, index=idx)

        result1 = df.unstack()
        result2 = df.unstack(level=1)
        result3 = df.unstack(level=0)

        e_1 = pd.PeriodIndex(["2014-01", "2014-02"], freq="M", name="period1")
        e_2 = pd.PeriodIndex(
            ["2013-10", "2013-12", "2014-02", "2013-10", "2013-12", "2014-02"],
            freq="M",
            name="period2",
        )
        e_cols = MultiIndex.from_arrays(["A A A B B B".split(), e_2])
        expected = DataFrame(
            [[5, 1, 6, 2, 6, 1], [4, 2, 3, 3, 5, 4]], index=e_1, columns=e_cols
        )

        tm.assert_frame_equal(result1, expected)
        tm.assert_frame_equal(result2, expected)

        e_1 = pd.PeriodIndex(
            ["2014-01", "2014-02", "2014-01", "2014-02"], freq="M", name="period1"
        )
        e_2 = pd.PeriodIndex(
            ["2013-10", "2013-12", "2014-02"], freq="M", name="period2"
        )
        e_cols = MultiIndex.from_arrays(["A A B B".split(), e_1])
        expected = DataFrame(
            [[5, 4, 2, 3], [1, 2, 6, 5], [6, 3, 1, 4]], index=e_2, columns=e_cols
        )

        tm.assert_frame_equal(result3, expected)

    def test_stack_multiple_bug(self):
        """ bug when some uniques are not present in the data #3170"""
        id_col = ([1] * 3) + ([2] * 3)
        name = (["a"] * 3) + (["b"] * 3)
        date = pd.to_datetime(["2013-01-03", "2013-01-04", "2013-01-05"] * 2)
        var1 = np.random.randint(0, 100, 6)
        df = DataFrame(dict(ID=id_col, NAME=name, DATE=date, VAR1=var1))

        multi = df.set_index(["DATE", "ID"])
        multi.columns.name = "Params"
        unst = multi.unstack("ID")
        down = unst.resample("W-THU").mean()

        rs = down.stack("ID")
        xp = unst.loc[:, ["VAR1"]].resample("W-THU").mean().stack("ID")
        xp.columns.name = "Params"
        tm.assert_frame_equal(rs, xp)

    def test_stack_dropna(self):
        # GH #3997
        df = DataFrame({"A": ["a1", "a2"], "B": ["b1", "b2"], "C": [1, 1]})
        df = df.set_index(["A", "B"])

        stacked = df.unstack().stack(dropna=False)
        assert len(stacked) > len(stacked.dropna())

        stacked = df.unstack().stack(dropna=True)
        tm.assert_frame_equal(stacked, stacked.dropna())

    def test_unstack_multiple_hierarchical(self):
        df = DataFrame(
            index=[
                [0, 0, 0, 0, 1, 1, 1, 1],
                [0, 0, 1, 1, 0, 0, 1, 1],
                [0, 1, 0, 1, 0, 1, 0, 1],
            ],
            columns=[[0, 0, 1, 1], [0, 1, 0, 1]],
        )

        df.index.names = ["a", "b", "c"]
        df.columns.names = ["d", "e"]

        # it works!
        df.unstack(["b", "c"])

    def test_groupby_transform(self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data

        s = frame["A"]
        grouper = s.index.get_level_values(0)

        grouped = s.groupby(grouper)

        applied = grouped.apply(lambda x: x * 2)
        expected = grouped.transform(lambda x: x * 2)
        result = applied.reindex(expected.index)
        tm.assert_series_equal(result, expected, check_names=False)

    def test_unstack_sparse_keyspace(self):
        # memory problems with naive impl #2278
        # Generate Long File & Test Pivot
        NUM_ROWS = 1000

        df = DataFrame(
            {
                "A": np.random.randint(100, size=NUM_ROWS),
                "B": np.random.randint(300, size=NUM_ROWS),
                "C": np.random.randint(-7, 7, size=NUM_ROWS),
                "D": np.random.randint(-19, 19, size=NUM_ROWS),
                "E": np.random.randint(3000, size=NUM_ROWS),
                "F": np.random.randn(NUM_ROWS),
            }
        )

        idf = df.set_index(["A", "B", "C", "D", "E"])

        # it works! is sufficient
        idf.unstack("E")

    def test_unstack_unobserved_keys(self):
        # related to #2278 refactoring
        levels = [[0, 1], [0, 1, 2, 3]]
        codes = [[0, 0, 1, 1], [0, 2, 0, 2]]

        index = MultiIndex(levels, codes)

        df = DataFrame(np.random.randn(4, 2), index=index)

        result = df.unstack()
        assert len(result.columns) == 4

        recons = result.stack()
        tm.assert_frame_equal(recons, df)

    @pytest.mark.slow
    def test_unstack_number_of_levels_larger_than_int32(self):
        # GH 20601
        df = DataFrame(
            np.random.randn(2 ** 16, 2), index=[np.arange(2 ** 16), np.arange(2 ** 16)]
        )
        with pytest.raises(ValueError, match="int32 overflow"):
            df.unstack()

    def test_stack_order_with_unsorted_levels(self):
        # GH 16323

        def manual_compare_stacked(df, df_stacked, lev0, lev1):
            assert all(
                df.loc[row, col] == df_stacked.loc[(row, col[lev0]), col[lev1]]
                for row in df.index
                for col in df.columns
            )

        # deep check for 1-row case
        for width in [2, 3]:
            levels_poss = itertools.product(
                itertools.permutations([0, 1, 2], width), repeat=2
            )

            for levels in levels_poss:
                columns = MultiIndex(levels=levels, codes=[[0, 0, 1, 1], [0, 1, 0, 1]])
                df = DataFrame(columns=columns, data=[range(4)])
                for stack_lev in range(2):
                    df_stacked = df.stack(stack_lev)
                    manual_compare_stacked(df, df_stacked, stack_lev, 1 - stack_lev)

        # check multi-row case
        mi = MultiIndex(
            levels=[["A", "C", "B"], ["B", "A", "C"]],
            codes=[np.repeat(range(3), 3), np.tile(range(3), 3)],
        )
        df = DataFrame(
            columns=mi, index=range(5), data=np.arange(5 * len(mi)).reshape(5, -1)
        )
        manual_compare_stacked(df, df.stack(0), 0, 1)

    def test_stack_unstack_unordered_multiindex(self):
        # GH 18265
        values = np.arange(5)
        data = np.vstack(
            [
                [f"b{x}" for x in values],  # b0, b1, ..
                [f"a{x}" for x in values],  # a0, a1, ..
            ]
        )
        df = pd.DataFrame(data.T, columns=["b", "a"])
        df.columns.name = "first"
        second_level_dict = {"x": df}
        multi_level_df = pd.concat(second_level_dict, axis=1)
        multi_level_df.columns.names = ["second", "first"]
        df = multi_level_df.reindex(sorted(multi_level_df.columns), axis=1)
        result = df.stack(["first", "second"]).unstack(["first", "second"])
        expected = DataFrame(
            [["a0", "b0"], ["a1", "b1"], ["a2", "b2"], ["a3", "b3"], ["a4", "b4"]],
            index=[0, 1, 2, 3, 4],
            columns=MultiIndex.from_tuples(
                [("a", "x"), ("b", "x")], names=["first", "second"]
            ),
        )
        tm.assert_frame_equal(result, expected)

    def test_groupby_corner(self):
        midx = MultiIndex(
            levels=[["foo"], ["bar"], ["baz"]],
            codes=[[0], [0], [0]],
            names=["one", "two", "three"],
        )
        df = DataFrame([np.random.rand(4)], columns=["a", "b", "c", "d"], index=midx)
        # should work
        df.groupby(level="three")

    def test_groupby_level_no_obs(self):
        # #1697
        midx = MultiIndex.from_tuples(
            [
                ("f1", "s1"),
                ("f1", "s2"),
                ("f2", "s1"),
                ("f2", "s2"),
                ("f3", "s1"),
                ("f3", "s2"),
            ]
        )
        df = DataFrame([[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]], columns=midx)
        df1 = df.loc(axis=1)[df.columns.map(lambda u: u[0] in ["f2", "f3"])]

        grouped = df1.groupby(axis=1, level=0)
        result = grouped.sum()
        assert (result.columns == ["f2", "f3"]).all()

    def test_join(self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data

        a = frame.loc[frame.index[:5], ["A"]]
        b = frame.loc[frame.index[2:], ["B", "C"]]

        joined = a.join(b, how="outer").reindex(frame.index)
        expected = frame.copy()
        expected.values[np.isnan(joined.values)] = np.nan

        assert not np.isnan(joined.values).all()

        # TODO what should join do with names ?
        tm.assert_frame_equal(joined, expected, check_names=False)

    def test_swaplevel(self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data

        swapped = frame["A"].swaplevel()
        swapped2 = frame["A"].swaplevel(0)
        swapped3 = frame["A"].swaplevel(0, 1)
        swapped4 = frame["A"].swaplevel("first", "second")
        assert not swapped.index.equals(frame.index)
        tm.assert_series_equal(swapped, swapped2)
        tm.assert_series_equal(swapped, swapped3)
        tm.assert_series_equal(swapped, swapped4)

        back = swapped.swaplevel()
        back2 = swapped.swaplevel(0)
        back3 = swapped.swaplevel(0, 1)
        back4 = swapped.swaplevel("second", "first")
        assert back.index.equals(frame.index)
        tm.assert_series_equal(back, back2)
        tm.assert_series_equal(back, back3)
        tm.assert_series_equal(back, back4)

        ft = frame.T
        swapped = ft.swaplevel("first", "second", axis=1)
        exp = frame.swaplevel("first", "second").T
        tm.assert_frame_equal(swapped, exp)

        msg = "Can only swap levels on a hierarchical axis."
        with pytest.raises(TypeError, match=msg):
            DataFrame(range(3)).swaplevel()

    def test_insert_index(self, multiindex_year_month_day_dataframe_random_data):
        ymd = multiindex_year_month_day_dataframe_random_data

        df = ymd[:5].T
        df[2000, 1, 10] = df[2000, 1, 7]
        assert isinstance(df.columns, MultiIndex)
        assert (df[2000, 1, 10] == df[2000, 1, 7]).all()

    def test_alignment(self):
        x = Series(
            data=[1, 2, 3], index=MultiIndex.from_tuples([("A", 1), ("A", 2), ("B", 3)])
        )

        y = Series(
            data=[4, 5, 6], index=MultiIndex.from_tuples([("Z", 1), ("Z", 2), ("B", 3)])
        )

        res = x - y
        exp_index = x.index.union(y.index)
        exp = x.reindex(exp_index) - y.reindex(exp_index)
        tm.assert_series_equal(res, exp)

        # hit non-monotonic code path
        res = x[::-1] - y[::-1]
        exp_index = x.index.union(y.index)
        exp = x.reindex(exp_index) - y.reindex(exp_index)
        tm.assert_series_equal(res, exp)

    def test_count(self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data

        frame = frame.copy()
        frame.index.names = ["a", "b"]

        result = frame.count(level="b")
        expect = frame.count(level=1)
        tm.assert_frame_equal(result, expect, check_names=False)

        result = frame.count(level="a")
        expect = frame.count(level=0)
        tm.assert_frame_equal(result, expect, check_names=False)

        series = self.series.copy()
        series.index.names = ["a", "b"]

        result = series.count(level="b")
        expect = self.series.count(level=1).rename_axis("b")
        tm.assert_series_equal(result, expect)

        result = series.count(level="a")
        expect = self.series.count(level=0).rename_axis("a")
        tm.assert_series_equal(result, expect)

        msg = "Level x not found"
        with pytest.raises(KeyError, match=msg):
            series.count("x")
        with pytest.raises(KeyError, match=msg):
            frame.count(level="x")

    @pytest.mark.parametrize("op", AGG_FUNCTIONS)
    @pytest.mark.parametrize("level", [0, 1])
    @pytest.mark.parametrize("skipna", [True, False])
    @pytest.mark.parametrize("sort", [True, False])
    def test_series_group_min_max(self, op, level, skipna, sort):
        # GH 17537
        grouped = self.series.groupby(level=level, sort=sort)
        # skipna=True
        leftside = grouped.agg(lambda x: getattr(x, op)(skipna=skipna))
        rightside = getattr(self.series, op)(level=level, skipna=skipna)
        if sort:
            rightside = rightside.sort_index(level=level)
        tm.assert_series_equal(leftside, rightside)

    @pytest.mark.parametrize("op", AGG_FUNCTIONS)
    @pytest.mark.parametrize("level", [0, 1])
    @pytest.mark.parametrize("axis", [0, 1])
    @pytest.mark.parametrize("skipna", [True, False])
    @pytest.mark.parametrize("sort", [True, False])
    def test_frame_group_ops(
        self, op, level, axis, skipna, sort, multiindex_dataframe_random_data
    ):
        # GH 17537
        frame = multiindex_dataframe_random_data

        frame.iloc[1, [1, 2]] = np.nan
        frame.iloc[7, [0, 1]] = np.nan

        level_name = frame.index.names[level]

        if axis == 0:
            frame = frame
        else:
            frame = frame.T

        grouped = frame.groupby(level=level, axis=axis, sort=sort)

        pieces = []

        def aggf(x):
            pieces.append(x)
            return getattr(x, op)(skipna=skipna, axis=axis)

        leftside = grouped.agg(aggf)
        rightside = getattr(frame, op)(level=level, axis=axis, skipna=skipna)
        if sort:
            rightside = rightside.sort_index(level=level, axis=axis)
            frame = frame.sort_index(level=level, axis=axis)

        # for good measure, groupby detail
        level_index = frame._get_axis(axis).levels[level].rename(level_name)

        tm.assert_index_equal(leftside._get_axis(axis), level_index)
        tm.assert_index_equal(rightside._get_axis(axis), level_index)

        tm.assert_frame_equal(leftside, rightside)

    def test_stat_op_corner(self):
        obj = Series([10.0], index=MultiIndex.from_tuples([(2, 3)]))

        result = obj.sum(level=0)
        expected = Series([10.0], index=[2])
        tm.assert_series_equal(result, expected)

    def test_std_var_pass_ddof(self):
        index = MultiIndex.from_arrays(
            [np.arange(5).repeat(10), np.tile(np.arange(10), 5)]
        )
        df = DataFrame(np.random.randn(len(index), 5), index=index)

        for meth in ["var", "std"]:
            ddof = 4
            alt = lambda x: getattr(x, meth)(ddof=ddof)

            result = getattr(df[0], meth)(level=0, ddof=ddof)
            expected = df[0].groupby(level=0).agg(alt)
            tm.assert_series_equal(result, expected)

            result = getattr(df, meth)(level=0, ddof=ddof)
            expected = df.groupby(level=0).agg(alt)
            tm.assert_frame_equal(result, expected)

    def test_frame_series_agg_multiple_levels(
        self, multiindex_year_month_day_dataframe_random_data
    ):
        ymd = multiindex_year_month_day_dataframe_random_data

        result = ymd.sum(level=["year", "month"])
        expected = ymd.groupby(level=["year", "month"]).sum()
        tm.assert_frame_equal(result, expected)

        result = ymd["A"].sum(level=["year", "month"])
        expected = ymd["A"].groupby(level=["year", "month"]).sum()
        tm.assert_series_equal(result, expected)

    def test_groupby_multilevel(self, multiindex_year_month_day_dataframe_random_data):
        ymd = multiindex_year_month_day_dataframe_random_data

        result = ymd.groupby(level=[0, 1]).mean()

        k1 = ymd.index.get_level_values(0)
        k2 = ymd.index.get_level_values(1)

        expected = ymd.groupby([k1, k2]).mean()

        # TODO groupby with level_values drops names
        tm.assert_frame_equal(result, expected, check_names=False)
        assert result.index.names == ymd.index.names[:2]

        result2 = ymd.groupby(level=ymd.index.names[:2]).mean()
        tm.assert_frame_equal(result, result2)

    def test_groupby_multilevel_with_transform(self):
        pass

    def test_multilevel_consolidate(self):
        index = MultiIndex.from_tuples(
            [("foo", "one"), ("foo", "two"), ("bar", "one"), ("bar", "two")]
        )
        df = DataFrame(np.random.randn(4, 4), index=index, columns=index)
        df["Totals", ""] = df.sum(1)
        df = df._consolidate()

    def test_loc_preserve_names(self, multiindex_year_month_day_dataframe_random_data):
        ymd = multiindex_year_month_day_dataframe_random_data

        result = ymd.loc[2000]
        result2 = ymd["A"].loc[2000]
        assert result.index.names == ymd.index.names[1:]
        assert result2.index.names == ymd.index.names[1:]

        result = ymd.loc[2000, 2]
        result2 = ymd["A"].loc[2000, 2]
        assert result.index.name == ymd.index.names[2]
        assert result2.index.name == ymd.index.names[2]

    def test_unstack_preserve_types(
        self, multiindex_year_month_day_dataframe_random_data
    ):
        # GH #403
        ymd = multiindex_year_month_day_dataframe_random_data
        ymd["E"] = "foo"
        ymd["F"] = 2

        unstacked = ymd.unstack("month")
        assert unstacked["A", 1].dtype == np.float64
        assert unstacked["E", 1].dtype == np.object_
        assert unstacked["F", 1].dtype == np.float64

    def test_unstack_group_index_overflow(self):
        codes = np.tile(np.arange(500), 2)
        level = np.arange(500)

        index = MultiIndex(
            levels=[level] * 8 + [[0, 1]],
            codes=[codes] * 8 + [np.arange(2).repeat(500)],
        )

        s = Series(np.arange(1000), index=index)
        result = s.unstack()
        assert result.shape == (500, 2)

        # test roundtrip
        stacked = result.stack()
        tm.assert_series_equal(s, stacked.reindex(s.index))

        # put it at beginning
        index = MultiIndex(
            levels=[[0, 1]] + [level] * 8,
            codes=[np.arange(2).repeat(500)] + [codes] * 8,
        )

        s = Series(np.arange(1000), index=index)
        result = s.unstack(0)
        assert result.shape == (500, 2)

        # put it in middle
        index = MultiIndex(
            levels=[level] * 4 + [[0, 1]] + [level] * 4,
            codes=([codes] * 4 + [np.arange(2).repeat(500)] + [codes] * 4),
        )

        s = Series(np.arange(1000), index=index)
        result = s.unstack(4)
        assert result.shape == (500, 2)

    def test_to_html(self, multiindex_year_month_day_dataframe_random_data):
        ymd = multiindex_year_month_day_dataframe_random_data

        ymd.columns.name = "foo"
        ymd.to_html()
        ymd.T.to_html()

    def test_level_with_tuples(self):
        index = MultiIndex(
            levels=[[("foo", "bar", 0), ("foo", "baz", 0), ("foo", "qux", 0)], [0, 1]],
            codes=[[0, 0, 1, 1, 2, 2], [0, 1, 0, 1, 0, 1]],
        )

        series = Series(np.random.randn(6), index=index)
        frame = DataFrame(np.random.randn(6, 4), index=index)

        result = series[("foo", "bar", 0)]
        result2 = series.loc[("foo", "bar", 0)]
        expected = series[:2]
        expected.index = expected.index.droplevel(0)
        tm.assert_series_equal(result, expected)
        tm.assert_series_equal(result2, expected)

        with pytest.raises(KeyError, match=r"^\(\('foo', 'bar', 0\), 2\)$"):
            series[("foo", "bar", 0), 2]

        result = frame.loc[("foo", "bar", 0)]
        result2 = frame.xs(("foo", "bar", 0))
        expected = frame[:2]
        expected.index = expected.index.droplevel(0)
        tm.assert_frame_equal(result, expected)
        tm.assert_frame_equal(result2, expected)

        index = MultiIndex(
            levels=[[("foo", "bar"), ("foo", "baz"), ("foo", "qux")], [0, 1]],
            codes=[[0, 0, 1, 1, 2, 2], [0, 1, 0, 1, 0, 1]],
        )

        series = Series(np.random.randn(6), index=index)
        frame = DataFrame(np.random.randn(6, 4), index=index)

        result = series[("foo", "bar")]
        result2 = series.loc[("foo", "bar")]
        expected = series[:2]
        expected.index = expected.index.droplevel(0)
        tm.assert_series_equal(result, expected)
        tm.assert_series_equal(result2, expected)

        result = frame.loc[("foo", "bar")]
        result2 = frame.xs(("foo", "bar"))
        expected = frame[:2]
        expected.index = expected.index.droplevel(0)
        tm.assert_frame_equal(result, expected)
        tm.assert_frame_equal(result2, expected)

    def test_reindex_level_partial_selection(self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data

        result = frame.reindex(["foo", "qux"], level=0)
        expected = frame.iloc[[0, 1, 2, 7, 8, 9]]
        tm.assert_frame_equal(result, expected)

        result = frame.T.reindex(["foo", "qux"], axis=1, level=0)
        tm.assert_frame_equal(result, expected.T)

        result = frame.loc[["foo", "qux"]]
        tm.assert_frame_equal(result, expected)

        result = frame["A"].loc[["foo", "qux"]]
        tm.assert_series_equal(result, expected["A"])

        result = frame.T.loc[:, ["foo", "qux"]]
        tm.assert_frame_equal(result, expected.T)

    def test_unicode_repr_level_names(self):
        index = MultiIndex.from_tuples([(0, 0), (1, 1)], names=["\u0394", "i1"])

        s = Series(range(2), index=index)
        df = DataFrame(np.random.randn(2, 4), index=index)
        repr(s)
        repr(df)

    def test_join_segfault(self):
        # 1532
        df1 = DataFrame({"a": [1, 1], "b": [1, 2], "x": [1, 2]})
        df2 = DataFrame({"a": [2, 2], "b": [1, 2], "y": [1, 2]})
        df1 = df1.set_index(["a", "b"])
        df2 = df2.set_index(["a", "b"])
        # it works!
        for how in ["left", "right", "outer"]:
            df1.join(df2, how=how)

    def test_frame_dict_constructor_empty_series(self):
        s1 = Series(
            [1, 2, 3, 4], index=MultiIndex.from_tuples([(1, 2), (1, 3), (2, 2), (2, 4)])
        )
        s2 = Series(
            [1, 2, 3, 4], index=MultiIndex.from_tuples([(1, 2), (1, 3), (3, 2), (3, 4)])
        )
        s3 = Series(dtype=object)

        # it works!
        DataFrame({"foo": s1, "bar": s2, "baz": s3})
        DataFrame.from_dict({"foo": s1, "baz": s3, "bar": s2})

    @pytest.mark.parametrize("d", [4, "d"])
    def test_empty_frame_groupby_dtypes_consistency(self, d):
        # GH 20888
        group_keys = ["a", "b", "c"]
        df = DataFrame({"a": [1], "b": [2], "c": [3], "d": [d]})

        g = df[df.a == 2].groupby(group_keys)
        result = g.first().index
        expected = MultiIndex(
            levels=[[1], [2], [3]], codes=[[], [], []], names=["a", "b", "c"]
        )

        tm.assert_index_equal(result, expected)

    def test_multiindex_na_repr(self):
        # only an issue with long columns
        df3 = DataFrame(
            {
                "A" * 30: {("A", "A0006000", "nuit"): "A0006000"},
                "B" * 30: {("A", "A0006000", "nuit"): np.nan},
                "C" * 30: {("A", "A0006000", "nuit"): np.nan},
                "D" * 30: {("A", "A0006000", "nuit"): np.nan},
                "E" * 30: {("A", "A0006000", "nuit"): "A"},
                "F" * 30: {("A", "A0006000", "nuit"): np.nan},
            }
        )

        idf = df3.set_index(["A" * 30, "C" * 30])
        repr(idf)

    def test_assign_index_sequences(self):
        # #2200
        df = DataFrame({"a": [1, 2, 3], "b": [4, 5, 6], "c": [7, 8, 9]}).set_index(
            ["a", "b"]
        )
        index = list(df.index)
        index[0] = ("faz", "boo")
        df.index = index
        repr(df)

        # this travels an improper code path
        index[0] = ["faz", "boo"]
        df.index = index
        repr(df)

    def test_duplicate_groupby_issues(self):
        idx_tp = [
            ("600809", "20061231"),
            ("600809", "20070331"),
            ("600809", "20070630"),
            ("600809", "20070331"),
        ]
        dt = ["demo", "demo", "demo", "demo"]

        idx = MultiIndex.from_tuples(idx_tp, names=["STK_ID", "RPT_Date"])
        s = Series(dt, index=idx)

        result = s.groupby(s.index).first()
        assert len(result) == 3

    def test_duplicate_mi(self):
        # GH 4516
        df = DataFrame(
            [
                ["foo", "bar", 1.0, 1],
                ["foo", "bar", 2.0, 2],
                ["bah", "bam", 3.0, 3],
                ["bah", "bam", 4.0, 4],
                ["foo", "bar", 5.0, 5],
                ["bah", "bam", 6.0, 6],
            ],
            columns=list("ABCD"),
        )
        df = df.set_index(["A", "B"])
        df = df.sort_index(level=0)
        expected = DataFrame(
            [["foo", "bar", 1.0, 1], ["foo", "bar", 2.0, 2], ["foo", "bar", 5.0, 5]],
            columns=list("ABCD"),
        ).set_index(["A", "B"])
        result = df.loc[("foo", "bar")]
        tm.assert_frame_equal(result, expected)

    def test_multiindex_set_index(self):
        # segfault in #3308
        d = {"t1": [2, 2.5, 3], "t2": [4, 5, 6]}
        df = DataFrame(d)
        tuples = [(0, 1), (0, 2), (1, 2)]
        df["tuples"] = tuples

        index = MultiIndex.from_tuples(df["tuples"])
        # it works!
        df.set_index(index)

    def test_reset_index_datetime(self, tz_naive_fixture):
        # GH 3950
        tz = tz_naive_fixture
        idx1 = pd.date_range("1/1/2011", periods=5, freq="D", tz=tz, name="idx1")
        idx2 = Index(range(5), name="idx2", dtype="int64")
        idx = MultiIndex.from_arrays([idx1, idx2])
        df = DataFrame(
            {"a": np.arange(5, dtype="int64"), "b": ["A", "B", "C", "D", "E"]},
            index=idx,
        )

        expected = DataFrame(
            {
                "idx1": [
                    datetime.datetime(2011, 1, 1),
                    datetime.datetime(2011, 1, 2),
                    datetime.datetime(2011, 1, 3),
                    datetime.datetime(2011, 1, 4),
                    datetime.datetime(2011, 1, 5),
                ],
                "idx2": np.arange(5, dtype="int64"),
                "a": np.arange(5, dtype="int64"),
                "b": ["A", "B", "C", "D", "E"],
            },
            columns=["idx1", "idx2", "a", "b"],
        )
        expected["idx1"] = expected["idx1"].apply(lambda d: Timestamp(d, tz=tz))

        tm.assert_frame_equal(df.reset_index(), expected)

        idx3 = pd.date_range(
            "1/1/2012", periods=5, freq="MS", tz="Europe/Paris", name="idx3"
        )
        idx = MultiIndex.from_arrays([idx1, idx2, idx3])
        df = DataFrame(
            {"a": np.arange(5, dtype="int64"), "b": ["A", "B", "C", "D", "E"]},
            index=idx,
        )

        expected = DataFrame(
            {
                "idx1": [
                    datetime.datetime(2011, 1, 1),
                    datetime.datetime(2011, 1, 2),
                    datetime.datetime(2011, 1, 3),
                    datetime.datetime(2011, 1, 4),
                    datetime.datetime(2011, 1, 5),
                ],
                "idx2": np.arange(5, dtype="int64"),
                "idx3": [
                    datetime.datetime(2012, 1, 1),
                    datetime.datetime(2012, 2, 1),
                    datetime.datetime(2012, 3, 1),
                    datetime.datetime(2012, 4, 1),
                    datetime.datetime(2012, 5, 1),
                ],
                "a": np.arange(5, dtype="int64"),
                "b": ["A", "B", "C", "D", "E"],
            },
            columns=["idx1", "idx2", "idx3", "a", "b"],
        )
        expected["idx1"] = expected["idx1"].apply(lambda d: Timestamp(d, tz=tz))
        expected["idx3"] = expected["idx3"].apply(
            lambda d: Timestamp(d, tz="Europe/Paris")
        )
        tm.assert_frame_equal(df.reset_index(), expected)

        # GH 7793
        idx = MultiIndex.from_product(
            [["a", "b"], pd.date_range("20130101", periods=3, tz=tz)]
        )
        df = DataFrame(
            np.arange(6, dtype="int64").reshape(6, 1), columns=["a"], index=idx
        )

        expected = DataFrame(
            {
                "level_0": "a a a b b b".split(),
                "level_1": [
                    datetime.datetime(2013, 1, 1),
                    datetime.datetime(2013, 1, 2),
                    datetime.datetime(2013, 1, 3),
                ]
                * 2,
                "a": np.arange(6, dtype="int64"),
            },
            columns=["level_0", "level_1", "a"],
        )
        expected["level_1"] = expected["level_1"].apply(
            lambda d: Timestamp(d, freq="D", tz=tz)
        )
        tm.assert_frame_equal(df.reset_index(), expected)

    def test_reset_index_period(self):
        # GH 7746
        idx = MultiIndex.from_product(
            [pd.period_range("20130101", periods=3, freq="M"), list("abc")],
            names=["month", "feature"],
        )

        df = DataFrame(
            np.arange(9, dtype="int64").reshape(-1, 1), index=idx, columns=["a"]
        )
        expected = DataFrame(
            {
                "month": (
                    [pd.Period("2013-01", freq="M")] * 3
                    + [pd.Period("2013-02", freq="M")] * 3
                    + [pd.Period("2013-03", freq="M")] * 3
                ),
                "feature": ["a", "b", "c"] * 3,
                "a": np.arange(9, dtype="int64"),
            },
            columns=["month", "feature", "a"],
        )
        tm.assert_frame_equal(df.reset_index(), expected)

    def test_reset_index_multiindex_columns(self):
        levels = [["A", ""], ["B", "b"]]
        df = DataFrame([[0, 2], [1, 3]], columns=MultiIndex.from_tuples(levels))
        result = df[["B"]].rename_axis("A").reset_index()
        tm.assert_frame_equal(result, df)

        # gh-16120: already existing column
        msg = r"cannot insert \('A', ''\), already exists"
        with pytest.raises(ValueError, match=msg):
            df.rename_axis("A").reset_index()

        # gh-16164: multiindex (tuple) full key
        result = df.set_index([("A", "")]).reset_index()
        tm.assert_frame_equal(result, df)

        # with additional (unnamed) index level
        idx_col = DataFrame(
            [[0], [1]], columns=MultiIndex.from_tuples([("level_0", "")])
        )
        expected = pd.concat([idx_col, df[[("B", "b"), ("A", "")]]], axis=1)
        result = df.set_index([("B", "b")], append=True).reset_index()
        tm.assert_frame_equal(result, expected)

        # with index name which is a too long tuple...
        msg = "Item must have length equal to number of levels."
        with pytest.raises(ValueError, match=msg):
            df.rename_axis([("C", "c", "i")]).reset_index()

        # or too short...
        levels = [["A", "a", ""], ["B", "b", "i"]]
        df2 = DataFrame([[0, 2], [1, 3]], columns=MultiIndex.from_tuples(levels))
        idx_col = DataFrame(
            [[0], [1]], columns=MultiIndex.from_tuples([("C", "c", "ii")])
        )
        expected = pd.concat([idx_col, df2], axis=1)
        result = df2.rename_axis([("C", "c")]).reset_index(col_fill="ii")
        tm.assert_frame_equal(result, expected)

        # ... which is incompatible with col_fill=None
        with pytest.raises(
            ValueError,
            match=(
                "col_fill=None is incompatible with "
                r"incomplete column name \('C', 'c'\)"
            ),
        ):
            df2.rename_axis([("C", "c")]).reset_index(col_fill=None)

        # with col_level != 0
        result = df2.rename_axis([("c", "ii")]).reset_index(col_level=1, col_fill="C")
        tm.assert_frame_equal(result, expected)

    def test_subsets_multiindex_dtype(self):
        # GH 20757
        data = [["x", 1]]
        columns = [("a", "b", np.nan), ("a", "c", 0.0)]
        df = DataFrame(data, columns=pd.MultiIndex.from_tuples(columns))
        expected = df.dtypes.a.b
        result = df.a.b.dtypes
        tm.assert_series_equal(result, expected)


class TestSorted(Base):
    """ everything you wanted to test about sorting """

    @pytest.mark.parametrize(
        "gen,extra",
        [
            ([1.0, 3.0, 2.0, 5.0], 4.0),
            ([1, 3, 2, 5], 4),
            (
                [
                    Timestamp("20130101"),
                    Timestamp("20130103"),
                    Timestamp("20130102"),
                    Timestamp("20130105"),
                ],
                Timestamp("20130104"),
            ),
            (["1one", "3one", "2one", "5one"], "4one"),
        ],
    )
    def test_sorting_repr_8017(self, gen, extra):

        np.random.seed(0)
        data = np.random.randn(3, 4)

        columns = MultiIndex.from_tuples([("red", i) for i in gen])
        df = DataFrame(data, index=list("def"), columns=columns)
        df2 = pd.concat(
            [
                df,
                DataFrame(
                    "world",
                    index=list("def"),
                    columns=MultiIndex.from_tuples([("red", extra)]),
                ),
            ],
            axis=1,
        )

        # check that the repr is good
        # make sure that we have a correct sparsified repr
        # e.g. only 1 header of read
        assert str(df2).splitlines()[0].split() == ["red"]

        # GH 8017
        # sorting fails after columns added

        # construct single-dtype then sort
        result = df.copy().sort_index(axis=1)
        expected = df.iloc[:, [0, 2, 1, 3]]
        tm.assert_frame_equal(result, expected)

        result = df2.sort_index(axis=1)
        expected = df2.iloc[:, [0, 2, 1, 4, 3]]
        tm.assert_frame_equal(result, expected)

        # setitem then sort
        result = df.copy()
        result[("red", extra)] = "world"

        result = result.sort_index(axis=1)
        tm.assert_frame_equal(result, expected)

    def test_sort_non_lexsorted(self):
        # degenerate case where we sort but don't
        # have a satisfying result :<
        # GH 15797
        idx = MultiIndex(
            [["A", "B", "C"], ["c", "b", "a"]], [[0, 1, 2, 0, 1, 2], [0, 2, 1, 1, 0, 2]]
        )

        df = DataFrame({"col": range(len(idx))}, index=idx, dtype="int64")
        assert df.index.is_lexsorted() is False
        assert df.index.is_monotonic is False

        sorted = df.sort_index()
        assert sorted.index.is_lexsorted() is True
        assert sorted.index.is_monotonic is True

        expected = DataFrame(
            {"col": [1, 4, 5, 2]},
            index=MultiIndex.from_tuples(
                [("B", "a"), ("B", "c"), ("C", "a"), ("C", "b")]
            ),
            dtype="int64",
        )
        result = sorted.loc[pd.IndexSlice["B":"C", "a":"c"], :]
        tm.assert_frame_equal(result, expected)

    @pytest.mark.parametrize(
        "keys, expected",
        [
            (["b", "a"], [["b", "b", "a", "a"], [1, 2, 1, 2]]),
            (["a", "b"], [["a", "a", "b", "b"], [1, 2, 1, 2]]),
            ((["a", "b"], [1, 2]), [["a", "a", "b", "b"], [1, 2, 1, 2]]),
            ((["a", "b"], [2, 1]), [["a", "a", "b", "b"], [2, 1, 2, 1]]),
            ((["b", "a"], [2, 1]), [["b", "b", "a", "a"], [2, 1, 2, 1]]),
            ((["b", "a"], [1, 2]), [["b", "b", "a", "a"], [1, 2, 1, 2]]),
            ((["c", "a"], [2, 1]), [["c", "a", "a"], [1, 2, 1]]),
        ],
    )
    @pytest.mark.parametrize("dim", ["index", "columns"])
    def test_multilevel_index_loc_order(self, dim, keys, expected):
        # GH 22797
        # Try to respect order of keys given for MultiIndex.loc
        kwargs = {dim: [["c", "a", "a", "b", "b"], [1, 1, 2, 1, 2]]}
        df = pd.DataFrame(np.arange(25).reshape(5, 5), **kwargs)
        exp_index = MultiIndex.from_arrays(expected)
        if dim == "index":
            res = df.loc[keys, :]
            tm.assert_index_equal(res.index, exp_index)
        elif dim == "columns":
            res = df.loc[:, keys]
            tm.assert_index_equal(res.columns, exp_index)
