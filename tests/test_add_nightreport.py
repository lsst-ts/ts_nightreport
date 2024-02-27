# This file is part of ts_nightreport.
#
# Developed for the Vera C. Rubin Observatory Telescope and Site Systems.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import httpx
import psycopg
import pytest
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
    response : `httpx.Response`
        Response to HTTP request.
    add_args : `dict`
        Arguments to add_report.

    Returns
    -------
    report: `ReportDictT`
        The report added.
    """
    report = assert_good_response(response)
    assert report["is_valid"]
    assert report["parent_id"] is None
    assert report["date_invalidated"] is None
    for key, value in add_args.items():
        assert cast_special(report[key]) == cast_special(add_args[key])
    return report


@pytest.mark.asyncio
async def test_add_report(postgresql: psycopg.Connection) -> None:
    async with create_test_client(postgresql, num_reports=0) as (
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
            response = await client.post("/nightreport/reports" + suffix, json=add_args)
            assert_good_add_response(response=response, add_args=add_args)
