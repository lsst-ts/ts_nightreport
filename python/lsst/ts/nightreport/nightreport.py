__all__ = [
    "Telescope",
    "NightReport",
    "NIGHTREPORT_FIELDS",
    "NIGHTREPORT_ORDER_BY_VALUES",
]

import datetime
import enum
import uuid

from pydantic import BaseModel, Field


class Telescope(str, enum.Enum):
    auxtel = "AuxTel"
    maintel = "Simonyi"


class NightReport(BaseModel):
    id: uuid.UUID = Field(title="Night report ID: a UUID that is the primary key.")
    site_id: str = Field(title="Site at which the report was created.")

    telescope: Telescope = Field(title="Telescope for which the report was created.")
    day_obs: int = Field(title="Observation day, as an integer in the form YYYYMMDD.")

    summary: str = Field(title="Night report summary.")
    telescope_status: str = Field(title="Telescope status.")
    confluence_url: str = Field(
        title="URL of the Confluence page with the night report."
    )

    user_id: str = Field(title="User ID.")
    user_agent: str = Field(
        title="User agent: the application that created the report."
    )

    date_added: datetime.datetime = Field(
        title="TAI date at which the night report was added."
    )
    date_sent: None | datetime.datetime = Field(
        title="TAI date at which the night report was confirmed and sent."
    )

    is_valid: bool = Field(
        description="Is this report still valid (false if deleted or edited)."
    )
    date_invalidated: None | datetime.datetime = Field(
        description="TAI date at which is_valid was last set true."
    )
    parent_id: None | uuid.UUID = Field(
        description="Report ID of night report this is an edited version of."
    )

    class Config:
        orm_mode = True
        from_attributes = True


NIGHTREPORT_FIELDS = tuple(set(NightReport.schema()["properties"].keys()))


def _make_report_order_by_values() -> tuple[str, ...]:
    """Make a tuple of valid order_by values for find_nightreports.

    Return a tuple of all field names,
    plus those same field names with a leading "-".
    """
    order_by_values = []
    for field in NightReport.schema()["properties"]:
        order_by_values += [field, "-" + field]
    return tuple(order_by_values)


# Tuple of valid order_by fields.
# Each of these exists in the NightReport class.
NIGHTREPORT_ORDER_BY_VALUES = _make_report_order_by_values()
