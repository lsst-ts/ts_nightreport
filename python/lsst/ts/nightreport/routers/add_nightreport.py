__all__ = ["add_nightreport"]

import http

import astropy.time
import fastapi
import sqlalchemy as sa

from ..nightreport import NightReport, Telescope
from ..shared_state import SharedState, get_shared_state

router = fastapi.APIRouter()


# The pair of decorators avoids a redirect from uvicorn if the trailing "/"
# is not as expected. include_in_schema=False hides one from the API docs.
# https://github.com/tiangolo/fastapi/issues/2060
@router.post("/reports", response_model=NightReport)
@router.post("/reports/", response_model=NightReport, include_in_schema=False)
async def add_nightreport(
    telescope: Telescope = fastapi.Body(
        default=Telescope.maintel, description="Telescope name"
    ),
    day_obs: int = fastapi.Body(..., description="Day of observation"),
    summary: str = fastapi.Body(..., description="NightReport text"),
    telescope_status: str = fastapi.Body(..., description="Telescope status"),
    confluence_url: str = fastapi.Body(
        ..., description="URL of the Confluence page containing the report"
    ),
    user_id: str = fastapi.Body(..., description="User ID"),
    user_agent: str = fastapi.Body(
        default=...,
        description="User agent (name of application creating the report)",
    ),
    state: SharedState = fastapi.Depends(get_shared_state),
) -> NightReport:
    """Add a report to the database and return the added report.

    Notes
    -----
    This is a FastAPI endpoint.
    For more information on FastAPI use of APIRouter,
    see https://fastapi.tiangolo.com/tutorial/.

    Most of the parameters are FastAPI.Body parameters.
    The state parameter is a FastAPI.Depends parameter
    with the database shared state.

    See also:
    - https://fastapi.tiangolo.com/tutorial/\
        body-multiple-params/#singular-values-in-body
    - https://fastapi.tiangolo.com/tutorial/dependencies/\
        #declare-the-dependency-in-the-dependant
    """
    curr_tai = astropy.time.Time.now()

    nightreport_table = state.nightreport_db.nightreport_table
    async with state.nightreport_db.engine.begin() as connection:
        # Add the report.
        result_report = await connection.execute(
            nightreport_table.insert()
            .values(
                site_id=state.site_id,
                telescope=telescope,
                day_obs=day_obs,
                summary=summary,
                telescope_status=telescope_status,
                confluence_url=confluence_url,
                user_id=user_id,
                user_agent=user_agent,
                date_added=curr_tai.tai.datetime,
            )
            .returning(sa.literal_column("*"))
        )
        row_report = result_report.fetchone()
        if row_report is None:
            raise fastapi.HTTPException(
                status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR,
                detail="Couldn't create report entry",
            )

        # Find the report
        result_report_joined = await connection.execute(
            nightreport_table.select().where(nightreport_table.c.id == row_report.id)
        )
        row = result_report_joined.fetchone()

        return NightReport.from_orm(row)
