import fastapi
import fastapi.responses
import starlette.requests

from . import shared_state
from .routers import (
    add_nightreport,
    delete_nightreport,
    edit_nightreport,
    find_nightreports,
    get_configuration,
    get_nightreport,
)

app = fastapi.FastAPI()

subapp = fastapi.FastAPI(
    title="Night report service",
    description="A REST web service to create and manage night reports for the Vera C. Rubin Observatory.",
)
app.mount("/nightreport", subapp)

subapp.include_router(add_nightreport.router)
subapp.include_router(delete_nightreport.router)
subapp.include_router(edit_nightreport.router)
subapp.include_router(find_nightreports.router)
subapp.include_router(get_configuration.router)
subapp.include_router(get_nightreport.router)


@subapp.get("/", response_class=fastapi.responses.HTMLResponse)
async def root(request: starlette.requests.Request) -> str:
    return f"""<html>
    <head>
        <title>
            Night Report service
        </title>
    </head>
    <body>
        <h1>Night Report service</h1>
        <p>Create and manage night reports.</p>
        <p><a href="{request.url}docs">Interactive OpenAPI documentation</a></p>
    </html>
    """


@app.on_event("startup")
async def startup_event() -> None:
    await shared_state.create_shared_state()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await shared_state.delete_shared_state()
