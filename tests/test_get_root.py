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

import psycopg
import pytest
from lsst.ts.nightreport.testutils import create_test_client


@pytest.mark.asyncio
async def test_get_root(postgresql: psycopg.Connection) -> None:
    async with create_test_client(postgresql, num_reports=0) as (client, reports):
        response = await client.get("/nightreport/")
        assert response.status_code == http.HTTPStatus.OK
        assert "Night Report service" in response.text
        assert "/nightreport/docs" in response.text
        assert "OpenAPI" in response.text
