import http
import unittest
import uuid

from lsst.ts.nightreport.testutils import (
    assert_good_response,
    assert_reports_equal,
    create_test_client,
)


class GetReportTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_get_report(self) -> None:
        async with create_test_client(num_reports=5) as (
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
