import collections.abc
import http
import itertools
import random
import typing

import httpx
import pytest
from lsst.ts.nightreport.nightreport import NIGHTREPORT_FIELDS
from lsst.ts.nightreport.testutils import (
    ReportDictT,
    assert_good_response,
    assert_reports_equal,
    cast_special,
    create_test_client,
)

random.seed(11)


class doc_str:
    """Decorator to add a doc string to a function.

    Unlike the standard technique, this works with f strings
    """

    def __init__(self, doc: str):
        self.doc = doc

    def __call__(self, func: collections.abc.Callable) -> collections.abc.Callable:
        func.__doc__ = self.doc
        return func


def assert_good_find_response(
    response: httpx.Response,
    reports: list[ReportDictT],
    predicate: collections.abc.Callable,
) -> list[ReportDictT]:
    """Assert that the correct reports were found.

    Parameters
    ----------
    response
        Response from find_reports command.
    reports
        All reports in the database (in any order).
    predicate
        Callable that takes one report and returns True if a report
        meets the find criteria, False if not.

    Returns
    found_reports
        The found reports.
    """
    found_reports = assert_good_response(response)
    for report in found_reports:
        assert predicate(report), f"report {report} does not match {predicate.__doc__}"
    missing_reports = get_missing_report(reports, found_reports)
    for report in missing_reports:
        assert not predicate(report), f"report {report} matches {predicate.__doc__}"

    return found_reports


def assert_reports_ordered(reports: list[ReportDictT], order_by: list[str]) -> None:
    """Assert that a list of report is ordered as specified.

    Parameters
    ----------
    reports
        Reports to test
    order_by
        Field names by which the data should be ordered.
        Each name can be prefixed by "-" to mean descending order.
    """
    full_order_by = list(order_by)
    if not ("id" in order_by or "-id" in order_by):
        full_order_by.append("id")
    report1: None | dict = None
    for report2 in reports:
        if report1 is not None:
            assert_two_reports_ordered(
                report1=report1,
                report2=report2,
                order_by=full_order_by,
            )
        report1 = report2


def assert_two_reports_ordered(
    report1: ReportDictT, report2: ReportDictT, order_by: list[str]
) -> None:
    """Assert that two reports are ordered as specified.

    Parameters
    ----------
    report1
        A report.
    report2
        The next report.
    order_by
        Field names by which the data should be ordered.
        Each name can be prefixed by "-" to mean descending order.
    """
    for key in order_by:
        if key.startswith("-"):
            field = key[1:]
            desired_cmp_result = 1
        else:
            field = key
            desired_cmp_result = -1
        val1 = report1[field]
        val2 = report2[field]
        cmp_result = cmp_report_field(field, val1, val2)
        if cmp_result == desired_cmp_result:
            # These two reports are fine
            return
        elif cmp_result != 0:
            raise AssertionError(
                f"reports mis-ordered in key {key}: "
                f"report1[{field!r}]={val1!r}, report2[{field!r}]={val2!r}"
            )


def cmp_report_field(field: str, val1: typing.Any, val2: typing.Any) -> int:
    """Return -1 if val1 < val2, 0 if val1 == val2, 1 if val1 > val2.

    Value None is equal to None and larger than every value.
    This mimics how PostgreSQL handles NULL.
    """
    if val1 == val2:
        return 0
    elif val1 is None:
        return 1
    elif val2 is None:
        return -1
    elif val1 > val2:
        return 1
    return -1


def get_missing_report(
    reports: list[ReportDictT],
    found_reports: list[ReportDictT],
) -> list[ReportDictT]:
    """Get reports that were not found."""
    found_ids = set(found_report["id"] for found_report in found_reports)
    return [report for report in reports if str(report["id"]) not in found_ids]


@pytest.mark.asyncio
async def test_find_reports(postgresql) -> None:
    num_reports = 12
    num_edited = 6  # Must be at least 4 in order to test ranges.
    async with create_test_client(
        postgresql, num_reports=num_reports, num_edited=num_edited
    ) as (
        client,
        reports,
    ):
        # Make a list of find arguments and associated predicates.
        # Each entry is a tuple of:
        # * dict of find arg name: value
        # * predicate: function that takes a report dict
        #   and returns True if the report matches the query
        find_args_predicates: list[
            tuple[dict[str, typing.Any], collections.abc.Callable]
        ] = list()

        # Range arguments: min_<field>, max_<field>.
        for field in (
            "day_obs",
            "date_added",
            # "date_sent",
        ):
            values = sorted(
                report[field] for report in reports if report[field] is not None
            )
            assert len(values) >= 4, f"not enough values for {field}"
            min_name = f"min_{field}"
            max_name = f"max_{field}"
            min_value = values[1]
            max_value = values[-1]
            assert max_value > min_value

            @doc_str(f"report[{field!r}] not None and >= {min_value}.")
            def test_min(
                report: ReportDictT,
                field: str = field,
                min_value: typing.Any = min_value,
            ) -> bool:
                min_value = cast_special(min_value)
                value = cast_special(report[field])
                return value is not None and value >= min_value

            @doc_str(f"report[{field!r}] not None and < {max_value}.")
            def test_max(
                report: ReportDictT,
                field: str = field,
                max_value: typing.Any = max_value,
            ) -> bool:
                max_value = cast_special(max_value)
                value = cast_special(report[field])
                return value is not None and value < max_value

            find_args_predicates += [
                ({min_name: min_value}, test_min),
                ({max_name: max_value}, test_max),
            ]

            # Test that an empty range (max <= min) returns no reports.
            # There is no point combining this with other tests,
            # so test it now instead of adding it to find_args_predicates.
            empty_range_args = {min_name: min_value, max_name: min_value}
            response = await client.get(
                "/nightreport/reports",
                params=empty_range_args,
            )
            found_reports = assert_good_response(response)
            assert len(found_reports) == 0

        # Collection arguments: <field>s, with a list of values.
        num_to_find = 2
        for field in (
            "user_id",
            "user_agent",
        ):
            reports_to_find = random.sample(reports, num_to_find)
            values = [report[field] for report in reports_to_find]
            arg_name = field + "s"

            @doc_str(f"report[{field!r}] in {values}")
            def test_collection(
                report: ReportDictT,
                field: str = field,
                values: list[typing.Any] = values,
            ) -> bool:
                return report[field] in values

            find_args_predicates.append(({arg_name: values}, test_collection))

        # "Contains" arguments: these specify a substring to match.
        # Search for two characters out of one report,
        # in hopes more than one (though one is fine)
        # and fewer than all reports (not a good test)
        # will match.
        for field in ("summary", "telescope_status"):
            value = reports[2][field][1:2]
            if value == "\\":
                # A backslash escapes the next character,
                # so include that character, as well.
                value = reports[2][field][1:3]

            @doc_str(f"{value!r} in report[{field!r}]")
            def test_contains(
                report: ReportDictT,
                field: str = field,
                value: str = value,
            ) -> bool:
                return value in report[field]

            find_args_predicates.append(({field: value}, test_contains))

        # has_<field> arguments (for fields that may be null).
        for field in ("parent_id",):
            arg_name = f"has_{field}"

            @doc_str(f"report[{field!r}] is not None")
            def test_has(report: ReportDictT, field: str = field) -> bool:
                return report[field] is not None

            @doc_str(f"report[{field!r}] is None")
            def test_has_not(report: ReportDictT, field: str = field) -> bool:
                return report[field] is None

            find_args_predicates += [
                ({arg_name: True}, test_has),
                ({arg_name: False}, test_has_not),
            ]

        # Tre-state boolean fields.
        for field in ("is_valid",):

            @doc_str(f"report[{field!r}] is True")
            def test_true(report: ReportDictT, field: str = field) -> bool:
                return report[field] is True

            @doc_str(f"report[{field!r}] is False")
            def test_false(report: ReportDictT, field: str = field) -> bool:
                return report[field] is False

            @doc_str(f"report[{field!r}] is either")
            def test_either(report: ReportDictT, field: str = field) -> bool:
                return True

            find_args_predicates += [
                ({field: "true"}, test_true),
                ({field: "false"}, test_false),
                ({field: "either"}, test_either),
            ]

        # Test single requests: one entry from find_args_predicates.
        for find_args, predicate in find_args_predicates:
            response = await client.get("/nightreport/reports", params=find_args)
            if "is_valid" not in find_args:
                # Handle the fact that is_valid defaults to True
                @doc_str(f'{predicate.__doc__} and report["is_valid"] is True')
                def predicate_and_is_valid(
                    report: ReportDictT,
                    predicate: collections.abc.Callable = predicate,
                ) -> bool:
                    return predicate(report) and report["is_valid"] is True

                predicate = predicate_and_is_valid
            assert_good_find_response(response, reports, predicate)

        # Test pairs of requests: two entries from find_args_predicates,
        # which are ``and``-ed together.
        for (
            (find_args1, predicate1),
            (find_args2, predicate2),
        ) in itertools.product(find_args_predicates, find_args_predicates):
            find_args = find_args1.copy()
            find_args.update(find_args2)
            if len(find_args) < len(find_args1) + len(find_args):
                # Overlapping arguments makes the predicates invalid.
                continue

            @doc_str(f"{predicate1.__doc__} and {predicate2.__doc__}")
            def and_predicates(
                report: ReportDictT,
                predicate1: collections.abc.Callable,
                predicate2: collections.abc.Callable,
            ) -> bool:
                return predicate1(report) and predicate2(report)

            response = await client.get("/nightreport/reports", params=find_args)
            assert_good_find_response(response, reports, and_predicates)

        # Test that find with no arguments finds all is_valid reports.
        def is_valid_predicate(report: ReportDictT) -> bool:
            """report["is_valid"] is True"""
            return report["is_valid"] is True

        response = await client.get("/nightreport/reports", params=dict())
        reports = assert_good_response(response)
        assert_good_find_response(response, reports, is_valid_predicate)

        # Check order_by one field
        # Note: SQL databases sort strings differently than Python.
        # Rather than try to mimic Postgresql's sorting in Python,
        # I issue the order_by command but do not test the resulting
        # order if ordering by a string field.
        fields = list(NIGHTREPORT_FIELDS)
        str_fields = set(
            (
                "day_obs",
                "summary",
                "telescope_status",
                "confluence_url",
                "user_id",
                "user_agent",
            )
        )
        for field, prefix in itertools.product(fields, ("", "-")):
            order_by = [prefix + field]
            find_args = dict()
            find_args["order_by"] = order_by
            response = await client.get("/nightreport/reports", params=find_args)
            reports = assert_good_response(response)
            if field not in str_fields:
                assert_reports_ordered(reports=reports, order_by=order_by)

            paged_reports: list[ReportDictT] = []
            limit = 2
            find_args["limit"] = limit
            while len(paged_reports) < len(reports):
                num_remaining = len(reports) - len(paged_reports)
                # Check limit and offset
                response = await client.get("/nightreport/reports", params=find_args)
                new_paged_reports = assert_good_response(response)
                paged_reports += new_paged_reports
                assert len(new_paged_reports) == min(limit, num_remaining)
                find_args["offset"] = find_args.get("offset", 0) + len(
                    new_paged_reports
                )

            # Run one more find that should return no reports
            response = await client.get("/nightreport/reports", params=find_args)
            no_more_paged_reports = assert_good_response(response)
            assert len(no_more_paged_reports) == 0

            assert len(reports) == len(paged_reports)

            # Compare paged to unpaged reports
            for report1, report2 in zip(reports, paged_reports):
                assert_reports_equal(report1, report2)

        # Check order_by two fields
        for field1, field2 in itertools.product(fields, fields):
            order_by = [field1, field2]
            find_args = {"order_by": order_by}
            response = await client.get("/nightreport/reports", params=find_args)
            reports = assert_good_response(response)
            if field1 not in str_fields and field2 not in str_fields:
                assert_reports_ordered(reports=reports, order_by=order_by)

        # Check invalid order_by fields
        for bad_order_by in ("not_a_field", "+id"):
            find_args = {"order_by": [bad_order_by]}
            response = await client.get("/nightreport/reports", params=find_args)
            assert response.status_code == http.HTTPStatus.BAD_REQUEST

        # Check that limit must be positive
        response = await client.get("/nightreport/reports", params={"limit": 0})
        assert response.status_code == 422

        # Check that offset must be >= 0
        response = await client.get("/nightreport/reports", params={"offset": -1})
        assert response.status_code == 422
