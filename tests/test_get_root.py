import http

import pytest
from lsst.ts.nightreport.testutils import create_test_client


@pytest.mark.asyncio
async def test_get_root(postgresql) -> None:
    async with create_test_client(postgresql, num_reports=0) as (client, reports):
        response = await client.get("/nightreport/")
        assert response.status_code == http.HTTPStatus.OK
        assert "Night Report service" in response.text
        assert "/nightreport/docs" in response.text
        assert "OpenAPI" in response.text
