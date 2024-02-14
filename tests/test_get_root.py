import http
import unittest

from lsst.ts.nightreport.testutils import create_test_client


class GetRootTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_get_root(self) -> None:
        async with create_test_client(num_reports=0) as (client, reports):
            response = await client.get("/nightreport/")
            assert response.status_code == http.HTTPStatus.OK
            assert "Night Report service" in response.text
            assert "/nightreport/docs" in response.text
            assert "OpenAPI" in response.text
