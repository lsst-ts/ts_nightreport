__all__ = ["delete_nightreport"]

import http

import astropy.time
import fastapi
import sqlalchemy as sa

from ..shared_state import SharedState, get_shared_state

router = fastapi.APIRouter()


@router.delete("/reports/{id}", status_code=http.HTTPStatus.NO_CONTENT)
async def delete_nightreport(
    id: str,
    state: SharedState = fastapi.Depends(get_shared_state),
) -> fastapi.Response:
    """Delete a report stored in the database
    by marking it invalid.

    A no-op if already the report is already marked invalid.

    If the report is valid: set ``is_valid`` false and ``date_invalidated``
    to the current date.

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
    current_tai = astropy.time.Time.now().tai.datetime

    nightreport_table = state.nightreport_db.nightreport_table

    # Delete the report by setting date_invalidated to the current TAI time
    # (if not already set). Note: coalesce returns the first non-null
    # value from a list of values.
    async with state.nightreport_db.engine.begin() as connection:
        result = await connection.execute(
            nightreport_table.update()
            .where(nightreport_table.c.id == id)
            .values(
                date_invalidated=sa.func.coalesce(
                    nightreport_table.c.date_invalidated, current_tai
                )
            )
        )

    if result.rowcount == 0:
        raise fastapi.HTTPException(
            status_code=http.HTTPStatus.NOT_FOUND,
            detail=f"No report found with id={id}",
        )
    return fastapi.Response(status_code=http.HTTPStatus.NO_CONTENT)
