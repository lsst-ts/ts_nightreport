__all__ = ["find_nightreports"]

import datetime
import enum
import http

import fastapi
import sqlalchemy as sa

from ..nightreport import NIGHTREPORT_ORDER_BY_VALUES, NightReport
from ..shared_state import SharedState, get_shared_state

router = fastapi.APIRouter()


class TriState(str, enum.Enum):
    either = "either"
    true = "true"
    false = "false"


NIGHTREPORT_ORDER_BY_SET = set(NIGHTREPORT_ORDER_BY_VALUES)


@router.get("/reports", response_model=list[NightReport])
@router.get("/reports/", response_model=list[NightReport], include_in_schema=False)
async def find_nightreports(
    site_ids: None | list[str] = fastapi.Query(
        default=None,
        description="Site IDs.",
    ),
    summary: None | str = fastapi.Query(
        default=None,
        description="Night report summary contains...",
    ),
    weather: None | str = fastapi.Query(
        default=None,
        description="Weather conditions during the night contains...",
    ),
    maintel_summary: None | str = fastapi.Query(
        default=None,
        description="Simonyi telescope summary contains...",
    ),
    auxtel_summary: None | str = fastapi.Query(
        default=None,
        description="AuxTel telescope summary contains...",
    ),
    user_ids: None | list[str] = fastapi.Query(
        default=None,
        description="User IDs. Repeat the parameter for each value.",
    ),
    user_agents: None | list[str] = fastapi.Query(
        default=None,
        description="User agents (which app created the report). "
        "Repeat the parameter for each value.",
    ),
    min_day_obs: None | int = fastapi.Query(
        default=None,
        description="Minimum day of observation, inclusive; "
        "an integer of the form YYYYMMDD",
    ),
    max_day_obs: None | int = fastapi.Query(
        default=None,
        description="Maximum day of observation, exclusive; "
        "an integer of the form YYYYMMDD",
    ),
    min_date_added: None | datetime.datetime = fastapi.Query(
        default=None,
        description="Minimum date the report was added, inclusive; "
        "TAI as an ISO string with no timezone information",
    ),
    max_date_added: None | datetime.datetime = fastapi.Query(
        default=None,
        description="Maximum date the report was added, exclusive; "
        "TAI as an ISO string with no timezone information",
    ),
    min_date_sent: None | datetime.datetime = fastapi.Query(
        default=None,
        description="Minimum date the report was confirmed and sent, inclusive; "
        "TAI as an ISO string with no timezone information",
    ),
    max_date_sent: None | datetime.datetime = fastapi.Query(
        default=None,
        description="Maximum date the report was confirmed and sent, exclusive; "
        "TAI as an ISO string with no timezone information",
    ),
    is_valid: TriState = fastapi.Query(
        default=TriState.true,
        description="Is the report valid? (False if deleted or superseded)",
    ),
    has_parent_id: None | bool = fastapi.Query(
        default=None,
        description="Does this report have a non-null parent ID?",
    ),
    order_by: None | list[str] = fastapi.Query(
        default=None,
        description="Fields to sort by. "
        "Prefix a name with - for descending order, e.g. -id. "
        "Repeat the parameter for each value.",
    ),
    offset: int = fastapi.Query(
        default=0,
        description="The number of reports to skip.",
        ge=0,
    ),
    limit: int = fastapi.Query(
        default=50,
        description="The maximum number of number of reports to return.",
        gt=1,
    ),
    state: SharedState = fastapi.Depends(get_shared_state),
) -> list[NightReport]:
    """Find night reports stored in the database and return a list of them.

    Notes
    -----
    This is a FastAPI endpoint.
    For more information on FastAPI use of APIRouter,
    see https://fastapi.tiangolo.com/tutorial/.

    Most of the parameters are FastAPI.Query parameters.
    The state parameter is a FastAPI.Depends parameter
    with the database shared state.

    See also:
    - https://fastapi.tiangolo.com/tutorial/\
        query-params-str-validations/
    - https://fastapi.tiangolo.com/tutorial/\
        dependencies/#declare-the-dependency-in-the-dependant
    """
    nightreport_table = state.nightreport_db.nightreport_table

    # Names of selection arguments
    select_arg_names = (
        "site_ids",
        "summary",
        "weather",
        "maintel_summary",
        "auxtel_summary",
        "user_ids",
        "user_agents",
        "min_day_obs",
        "max_day_obs",
        "min_date_added",
        "max_date_added",
        "min_date_sent",
        "max_date_sent",
        "is_valid",
        "has_parent_id",
    )

    # Compute the columns to order by.
    # If order_by does not include "id" then append it, to make the order
    # repeatable. Otherwise different calls can return data in different
    # orders, which is a disaster when using limit and offset.
    order_by_columns = []
    if order_by is None:
        order_by = ["id"]
    else:
        order_by_set = set(order_by)
        bad_fields = order_by_set - NIGHTREPORT_ORDER_BY_SET
        if bad_fields:
            raise fastapi.HTTPException(
                status_code=http.HTTPStatus.BAD_REQUEST,
                detail=f"Invalid order_by fields: {sorted(bad_fields)}; "
                + f"allowed values are {NIGHTREPORT_ORDER_BY_VALUES}",
            )
        if not order_by_set & {"id", "-id"}:
            order_by.append("id")
    for item in order_by:
        if item.startswith("-"):
            column_name = item[1:]
            column = nightreport_table.columns[column_name]
            order_by_columns.append(sa.sql.desc(column))
        else:
            column_name = item
            column = nightreport_table.columns[column_name]
            order_by_columns.append(sa.sql.asc(column))

    async with state.nightreport_db.engine.connect() as connection:
        conditions = []
        # Handle minimums and maximums
        for key in select_arg_names:
            value = locals()[key]
            if value is None:
                continue
            if key.startswith("min_"):
                column = nightreport_table.columns[key[4:]]
                conditions.append(column >= value)
            elif key.startswith("max_"):
                column = nightreport_table.columns[key[4:]]
                conditions.append(column < value)
            elif key.startswith("has_"):
                column = nightreport_table.columns[key[4:]]
                if value:
                    conditions.append(column != None)  # noqa
                else:
                    conditions.append(column == None)  # noqa
            elif key in {
                "site_ids",
                "user_ids",
                "user_agents",
            }:
                # Value is a list; field name is key without the final "s".
                # Note: the list cannot be empty, because the array is passed
                # by listing the parameter once per value.
                column = nightreport_table.columns[key[:-1]]
                conditions.append(column.in_(value))
            elif key in ("summary", "weather", "maintel_summary", "auxtel_summary"):
                column = nightreport_table.columns[key]
                conditions.append(column.contains(value))
            elif key in {"is_valid"}:
                if value != TriState.either:
                    logical_value = value == TriState.true
                    column = nightreport_table.columns[key]
                    conditions.append(column == logical_value)
            else:
                raise RuntimeError(f"Bug: unrecognized key: {key}")

        if conditions:
            full_conditions = sa.sql.and_(*conditions)
        else:
            full_conditions = sa.sql.and_(True)
        result = await connection.execute(
            nightreport_table.select()
            .where(full_conditions)
            .order_by(*order_by_columns)
            .limit(limit)
            .offset(offset)
        )
        rows = result.fetchall()

        return [NightReport.from_orm(row) for row in rows]
