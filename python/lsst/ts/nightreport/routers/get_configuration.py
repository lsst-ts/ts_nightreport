__all__ = ["get_config"]

import fastapi
import pydantic

from ..shared_state import SharedState, get_shared_state

router = fastapi.APIRouter()


class Config(pydantic.BaseModel):
    """A Config model.

    This is a Pydantic model for storing configurations
    for the night reports API.
    Please visit https://docs.pydantic.dev/latest/ for more information
    on Pydantic models.
    """

    site_id: str = pydantic.Field(title="Site ID.")

    class Config:
        orm_mode = True
        from_attributes = True


@router.get("/configuration", response_model=Config)
@router.get("/configuration/", response_model=Config, include_in_schema=False)
async def get_config(
    state: SharedState = fastapi.Depends(get_shared_state),
) -> Config:
    """Get the configuration parameters of the REST API.

    Notes
    -----
    This is a FastAPI endpoint.
    For more information on FastAPI use of APIRouter,
    see https://fastapi.tiangolo.com/tutorial/.

    The state parameter is a FastAPI.Depends parameter
    with the database shared state.
    """

    return Config.from_orm(state)
