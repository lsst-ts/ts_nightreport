__all__ = ["edit_nightreport"]

import http

import astropy.time
import fastapi
import sqlalchemy as sa

from ..nightreport import NightReport, Telescope
from ..shared_state import SharedState, get_shared_state

router = fastapi.APIRouter()


@router.patch("/reports/{id}", response_model=NightReport)
async def edit_nightreport(
    id: str,
    telescope: None | Telescope = fastapi.Body(
        default=None, description="Telescope name"
    ),
    day_obs: None | int = fastapi.Body(default=None, description="Day of observation"),
    summary: None | str = fastapi.Body(
        default=None, description="NightReport summary text"
    ),
    telescope_status: None | str = fastapi.Body(
        default=None, description="Telescope status text"
    ),
    confluence_url: None | str = fastapi.Body(
        default=None,
        description="URL of the Confluence page containing the report",
    ),
    site_id: None | str = fastapi.Body(default=None, description="Site ID"),
    user_id: None | str = fastapi.Body(default=None, description="User ID"),
    user_agent: None | str = fastapi.Body(
        default=None,
        description="User agent (which app created the report)",
    ),
    state: SharedState = fastapi.Depends(get_shared_state),
) -> NightReport:
    """Edit an existing report stored in the database
    and return the edited report.

    The process is:

    - Read the report to edit; call this the parent report.
    - Create a new report using the parent report data,
      overridden by the new user-supplied data.
      Set parent_id of the new report to the id of the parent report,
      in order to provide a link to the parent report.
    - Set timestamp_is_valid_changed=now on the parent report.

    Notes
    -----
    This is a FastAPI endpoint.
    For more information on FastAPI use of APIRouter,
    see https://fastapi.tiangolo.com/tutorial/.

    Most of the parameters are FastAPI.Body parameters.
    id is a FastAPI.Path parameter.
    The state parameter is a FastAPI.Depends parameter
    with the database shared state.

    See also:
    - https://fastapi.tiangolo.com/tutorial/\
        body-multiple-params/#singular-values-in-body
    - https://fastapi.tiangolo.com/tutorial/path-params/
    - https://fastapi.tiangolo.com/tutorial/dependencies/\
        #declare-the-dependency-in-the-dependant
    """
    nightreport_table = state.nightreport_db.nightreport_table

    parent_id = id
    old_site_id = site_id

    request_data = dict(id=id, site_id=site_id)
    for name in (
        "telescope",
        "day_obs",
        "summary",
        "telescope_status",
        "confluence_url",
        "site_id",
        "user_id",
        "user_agent",
    ):
        value = locals()[name]
        if value is not None:
            request_data[name] = value

    async with state.nightreport_db.engine.begin() as connection:
        # Find the parent report.
        get_parent_report_result = await connection.execute(
            nightreport_table.select()
            .where(nightreport_table.c.id == parent_id)
            .with_for_update()
        )
        parent_report_row = get_parent_report_result.fetchone()
        if parent_report_row is None:
            raise fastapi.HTTPException(
                status_code=http.HTTPStatus.NOT_FOUND,
                detail=f"NightReport with id={parent_id} not found",
            )

        # Add new report.
        nightreport_update_params = set(request_data.keys())
        new_nightreport_data = parent_report_row._asdict().copy()
        new_nightreport_data.update(
            {k: v for k, v in request_data.items() if k in nightreport_update_params}
        )
        for field in ("id", "is_valid", "date_invalidated"):
            del new_nightreport_data[field]
        current_tai = astropy.time.Time.now().tai.datetime
        new_nightreport_data["site_id"] = state.site_id
        new_nightreport_data["parent_id"] = parent_id
        add_row_result = await connection.execute(
            nightreport_table.insert()
            .values(**new_nightreport_data)
            .returning(sa.literal_column("*"))
        )
        row_report = add_row_result.fetchone()

        # Mark the parent report as invalid.
        await connection.execute(
            nightreport_table.update()
            .where(nightreport_table.c.id == parent_id)
            .values(date_invalidated=current_tai)
        )

        # Find the report and join with jira_fields
        result_report_joined = await connection.execute(
            nightreport_table.select().where(nightreport_table.c.id == row_report.id)
        )
        row = result_report_joined.fetchone()

    return NightReport.from_orm(row)
