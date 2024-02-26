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
import uuid

import pytest
from lsst.ts.nightreport.testutils import (
    assert_good_response,
    assert_reports_equal,
    create_test_client,
)


@pytest.mark.asyncio
async def test_get_report(postgresql) -> None:
    async with create_test_client(postgresql, num_reports=5) as (
        client,
        reports,
    ):
        chosen_report = reports[2]
        id = chosen_report["id"]
        response = await client.get(f"/nightreport/reports/{id}")
        report = assert_good_response(response)
        assert_reports_equal(report, chosen_report)

        # Test that a non-existent report returns NOT_FOUND
        bad_id = uuid.uuid4()
        response = await client.get(f"/nightreport/reports/{bad_id}")
        assert response.status_code == http.HTTPStatus.NOT_FOUND
