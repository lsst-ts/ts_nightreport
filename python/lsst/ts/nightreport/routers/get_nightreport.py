__all__ = ["get_nightreport"]

import http

import fastapi

from ..nightreport import NightReport
from ..shared_state import SharedState, get_shared_state

router = fastapi.APIRouter()


@router.get("/reports/{id}", response_model=NightReport)
async def get_nightreport(
    id: str,
    state: SharedState = fastapi.Depends(get_shared_state),
) -> NightReport:
    """Find a specific night report by its id and return it.

    Notes
    -----
    This is a FastAPI endpoint.
    For more information on FastAPI use of APIRouter,
    see https://fastapi.tiangolo.com/tutorial/.

    The id parameter is a FastAPI.Path parameter.
    The state parameter is a FastAPI.Depends parameter
    with the database shared state.

    See also:
    - https://fastapi.tiangolo.com/tutorial/path-params/
    - https://fastapi.tiangolo.com/tutorial/dependencies/\
        #declare-the-dependency-in-the-dependant
    """
    nightreport_table = state.nightreport_db.nightreport_table

    async with state.nightreport_db.engine.connect() as connection:
        # Find the report
        result_report = await connection.execute(
            nightreport_table.select().where(nightreport_table.c.id == id)
        )
        row = result_report.fetchone()

        if row is None:
            raise fastapi.HTTPException(
                status_code=http.HTTPStatus.NOT_FOUND,
                detail=f"No report found with id={id}",
            )

        return NightReport.from_orm(row)
