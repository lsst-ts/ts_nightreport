import http
import uuid

import pytest
from lsst.ts.nightreport.testutils import (
    assert_good_response,
    assert_reports_equal,
    create_test_client,
)


@pytest.mark.asyncio
async def test_delete_report(postgresql) -> None:
    async with create_test_client(postgresql, num_reports=5) as (
        client,
        reports,
    ):
        report_to_delete = reports[2]
        assert report_to_delete["date_invalidated"] is None
        id = report_to_delete["id"]

        # Delete the report
        response = await client.delete(f"/nightreport/reports/{id}")
        assert response.status_code == http.HTTPStatus.NO_CONTENT

        response = await client.get(f"/nightreport/reports/{id}")
        deleted_report1 = assert_good_response(response)
        assert not deleted_report1["is_valid"]
        assert deleted_report1["date_invalidated"] is not None

        # Delete the same reports again. This should have no effect.
        response = await client.delete(f"/nightreport/reports/{id}")
        assert response.status_code == http.HTTPStatus.NO_CONTENT

        response = await client.get(f"/nightreport/reports/{id}")
        deleted_report2 = assert_good_response(response)
        assert_reports_equal(deleted_report1, deleted_report2)

        # Test that a non-existent report returns NOT_FOUND
        bad_id = uuid.uuid4()
        response = await client.delete(f"/nightreport/reports/{bad_id}")
        assert response.status_code == http.HTTPStatus.NOT_FOUND
