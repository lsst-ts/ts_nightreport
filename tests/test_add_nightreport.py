import unittest

import httpx
from lsst.ts.nightreport.testutils import (
    ReportDictT,
    assert_good_response,
    cast_special,
    create_test_client,
)


def assert_good_add_response(response: httpx.Response, add_args: dict) -> ReportDictT:
    """Check the response from a successful add_reports request.

    Parameters
    ----------
    response
        Response to HTTP request.
    add_args:
        Arguments to add_report.

    Returns
    -------
    report
        The report added.
    """
    report = assert_good_response(response)
    assert report["is_valid"]
    assert report["parent_id"] is None
    assert report["date_invalidated"] is None
    for key, value in add_args.items():
        assert cast_special(report[key]) == cast_special(add_args[key])
    return report


class AddreportTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_add_report(self) -> None:
        async with create_test_client(num_reports=0) as (
            client,
            reports,
        ):
            # Add a report with only the required fields specified.
            add_args = dict(
                telescope="AuxTel",
                day_obs=20240101,
                summary="A sample report",
                telescope_status="OK",
                confluence_url="https://example.com",
                user_id="test_add_report",
                user_agent="pytest",
            )
            for suffix in ("", "/"):
                response = await client.post(
                    "/nightreport/reports" + suffix, json=add_args
                )
                assert_good_add_response(response=response, add_args=add_args)
