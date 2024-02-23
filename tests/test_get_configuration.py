import pytest
from lsst.ts.nightreport.shared_state import get_shared_state
from lsst.ts.nightreport.testutils import assert_good_response, create_test_client


@pytest.mark.asyncio
async def test_get_root(postgresql) -> None:
    async with create_test_client(postgresql, num_reports=0) as (
        client,
        reports,
    ):
        shared_state = get_shared_state()
        for suffix in ("", "/"):
            response = await client.get("/nightreport/configuration" + suffix)
            data = assert_good_response(response)
            assert data["site_id"] == shared_state.site_id
