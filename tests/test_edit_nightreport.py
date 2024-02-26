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

import http
import random
import uuid

import httpx
import pytest
from lsst.ts.nightreport.testutils import (
    ArgDictT,
    ReportDictT,
    assert_good_response,
    create_test_client,
)

random.seed(10)


def assert_good_edit_response(
    response: httpx.Response,
    *,
    old_report: ReportDictT,
    edit_args: ArgDictT,
) -> ReportDictT:
    """Assert that edit reports succeeded and return the new report."""
    new_report = assert_good_response(response)
    assert str(new_report["parent_id"]) == str(old_report["id"])
    assert new_report["is_valid"]
    assert not old_report["is_valid"]
    assert new_report["date_invalidated"] is None
    assert old_report["date_invalidated"] is not None
    for key in old_report:
        if key in set(
            (
                "id",
                "site_id",
                "parent_id",
                "is_valid",
                "date_added",
                "date_invalidated",
            )
        ):
            # These are handled above, except date_added,
            # which should not match.
            continue
        elif key in edit_args:
            assert new_report[key] == edit_args[key]
        else:
            assert new_report[key] == old_report[key]
    return new_report


@pytest.mark.asyncio
async def test_edit_report(postgresql) -> None:
    async with create_test_client(postgresql, num_reports=1) as (
        client,
        reports,
    ):
        old_id = reports[0]["id"]
        get_old_response = await client.get(
            f"/nightreport/reports/{old_id}",
        )
        assert_good_response(get_old_response)

        full_edit_args = dict(
            site_id="NewSite",
            telescope="AuxTel",
            day_obs=20240101,
            summary="New report text",
            telescope_status="OK",
            confluence_url="https://new.example.com",
            user_id="new user_id",
            user_agent="new user_agent",
        )
        # Repeatedly edit the old report. Each time
        # add a new version of the report with one field omitted,
        # to check that the one field is not changed from the original.
        # After each edit, find the old report and check that
        # the date_invalidated has been suitably updated.
        for del_key in full_edit_args:
            print("######")
            print(del_key)
            print("######")
            edit_args = full_edit_args.copy()
            del edit_args[del_key]
            edit_response = await client.patch(
                f"/nightreport/reports/{old_id}", json=edit_args
            )
            assert_good_response(edit_response)
            get_old_response = await client.get(
                f"/nightreport/reports/{old_id}",
            )
            old_report = assert_good_response(get_old_response)
            assert_good_edit_response(
                edit_response,
                old_report=old_report,
                edit_args=edit_args,
            )

        # Error: edit a report that does not exist.
        edit_args = full_edit_args.copy()
        bad_id = uuid.uuid4()
        response = await client.patch(f"/nightreport/reports/{bad_id}", json=edit_args)
        assert response.status_code == http.HTTPStatus.NOT_FOUND
