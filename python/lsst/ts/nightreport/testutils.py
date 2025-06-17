# This file is part of ts_nightreport.
#
# Developed for the Vera C. Rubin Observatory Telescope and Site Systems.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

__all__ = [
    "TEST_SITE_ID",
    "ArgDictT",
    "ReportDictT",
    "assert_good_response",
    "assert_reports_equal",
    "cast_special",
    "create_test_client",
    "db_config_from_dsn",
    "dsn_from_connection_info",
    "modify_environ",
]

import collections.abc
import contextlib
import datetime
import http
import os
import random
import typing
import unittest.mock
import uuid

import astropy.time
import httpx
import psycopg
import sqlalchemy.engine
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import create_async_engine

from . import main, shared_state
from .create_tables import create_nightreport_table
from .nightreport import NIGHTREPORT_FIELDS, Telescope

# Range of dates for random report.
MIN_DATE_RANDOM_REPORT = "2021-01-01"
MAX_DATE_RANDOM_REPORT = "2022-12-31"
MAX_TIME_DELTA_RANDOM_REPORT = datetime.timedelta(days=2)

# Other test data
TEST_SITE_ID = "test"
TEST_CREW_MEMBERS = "user1 user2 user3".split()

# Type annotation aliases
ReportDictT = dict[str, typing.Any]
ArgDictT = dict[str, typing.Any]

random.seed(47)


@contextlib.asynccontextmanager
async def create_test_client(
    postgresql: psycopg.Connection,
    num_reports: int = 0,
    num_edited: int = 0,
) -> collections.abc.AsyncGenerator[tuple[httpx.AsyncClient, list[ReportDictT]], None]:
    """Create the test database, test server, and httpx client.

    Parameters
    ----------
    postgresql : `psycopg.Connection`
        A connection to a PostgreSQL database.
    num_reports : `typing.Optional[int]`
        Number of reports to create in the test database.
        Default is 0.
    num_edited : `typing.Optional[int]`
        Number of these reports that should be edited versions.
        Default is 0.

    Yields
    ------
    tuple : `tuple[httpx.AsyncClient, list[ReportDictT]]`
        A tuple of the httpx client and the reports in the test database.
    """
    with postgresql as conn:
        postgresql_url = f"postgresql://{conn.info.user}@{conn.info.host}:{conn.info.port}/{conn.info.dbname}"
        reports = await create_test_database(
            postgres_url=postgresql_url,
            num_reports=num_reports,
            num_edited=num_edited,
        )

        dsn = dsn_from_connection_info(conn.info)
        db_config = db_config_from_dsn(dsn)
        with modify_environ(
            SITE_ID=TEST_SITE_ID,
            **db_config,
        ):
            # Note: httpx.AsyncClient does not trigger startup and shutdown
            # events. We could use asgi-lifespan's LifespanManager,
            # but it does not trigger the shutdown event if there is
            # an exception, so it does not seem worth the bother.
            assert not shared_state.has_shared_state()
            await main.startup_event()
            try:
                transport = httpx.ASGITransport(app=main.app)
                async with httpx.AsyncClient(
                    transport=transport, base_url="http://test"
                ) as client:
                    assert shared_state.has_shared_state()
                    yield client, reports
            finally:
                await main.shutdown_event()


@contextlib.contextmanager
def modify_environ(**kwargs: typing.Any) -> collections.abc.Iterator:
    """Context manager to temporarily patch os.environ.

    This calls `unittest.mock.patch` and is only intended for unit tests.

    Parameters
    ----------
    kwargs : `dict` [`str`, `str` or `None`]
        Environment variables to set or clear.
        Each key is the name of an environment variable (with correct case);
        it need not already exist. Each value must be one of:

        * A string value to set the env variable.
        * None to delete the env variable, if present.

    Raises
    ------
    RuntimeError
        If any value in kwargs is not of type `str` or `None`.

    Notes
    -----
    Example of use::

        ...
        def test_foo(self):
            set_value = "Value for $ENV_TO_SET"
            with modify_environ(
                HOME=None,  # Delete this env var
                ENV_TO_SET=set_value,  # Set this env var
            ):
                self.assertNotIn("HOME", os.environ)
                self.assert(os.environ["ENV_TO_SET"], set_value)
    """
    bad_value_strs = [
        f"{name}: {value!r}"
        for name, value in kwargs.items()
        if not isinstance(value, str) and value is not None
    ]
    if bad_value_strs:
        raise RuntimeError(
            "The following arguments are not of type str or None: "
            + ", ".join(bad_value_strs)
        )

    new_environ = os.environ.copy()
    for name, value in kwargs.items():
        if value is None:
            new_environ.pop(name, None)
        else:
            new_environ[name] = value
    with unittest.mock.patch("os.environ", new_environ):
        yield


def assert_good_response(response: httpx.Response) -> typing.Any:
    """Assert that a response is good and return the data.

    Parameters
    ----------
    response : `httpx.Response`
        The response to check.

    Returns
    -------
    data : `typing.Any`
        The data from the response.
    """
    assert (
        response.status_code == http.HTTPStatus.OK
    ), f"Bad response {response.status_code}: {response.text}"
    data = response.json()
    assert "errors" not in data, f"errors={data['errors']}"
    return data


def assert_reports_equal(report1: ReportDictT, report2: ReportDictT) -> None:
    """Assert that two reports are identical.

    Handle the "id" field specially because it may be a uuid.UUID or a str.
    Handle date fields specially because they may be datetime.datetime
    or ISOT strings.
    Handle timedelta fields specially they may be datetime.timedelta
    or float seconds.

    Parameters
    ----------
    report1 : `ReportDictT`
        The first report.
    report2 : `ReportDictT`
        The second report.
    """
    assert report1.keys() == report2.keys()
    for field in report1:
        values = [cast_special(value) for value in (report1[field], report2[field])]
        assert (
            values[0] == values[1]
        ), f"field {field} unequal: {values[0]!r} != {values[1]!r}"


def cast_special(value: typing.Any) -> typing.Any:
    """Cast special types to plain data types;
    return plain old data types unchanged.

    This allows comparison between values in the database
    and values returned by the web API.

    The special types are:

    * datetime.datetime: converted to an ISO string with "T" separator.
    * datetime.timedela: converted to float seconds.
    * uuid.UUID: convert to a string.

    Parameters
    ----------
    value : `typing.Any`
        The value to cast.

    Returns
    -------
    value : `typing.Any`
        The cast value.
    """
    if isinstance(value, datetime.datetime):
        return value.isoformat(sep="T")
    elif isinstance(value, datetime.timedelta):
        return value.total_seconds()
    elif isinstance(value, uuid.UUID):
        return str(value)
    return value


def dsn_from_connection_info(conn_info: psycopg.ConnectionInfo) -> dict[str, str]:
    """Get a database dsn from a psycopg.ConnectionInfo.

    Parameters
    ----------
    conn_info : `psycopg.ConnectionInfo`
        The connection info.

    Returns
    -------
    dsn : `dict[str, str]`
        The database dsn.
    """
    return {
        "user": conn_info.user,
        "host": conn_info.host,
        "port": conn_info.port,
        "database": conn_info.dbname,
    }


def db_config_from_dsn(dsn: dict[str, str]) -> dict[str, str]:
    """Get app database configuration arguments from a database dsn.

    The intended usage is to configure the application
    from an instance of testing.postgresql.Postgresql()::

        with testing.postgresql.Postgresql() as postgresql:
            create_test_database(postgresql.url(), num_reports=0)

            db_config = db_config_from_dsn(postgresql.dsn())
            with modify_environ(
                SITE_ID=TEST_SITE_ID,
                **db_config,
            ):
                import nightreport.app

                client = fastapi.testclient.TestClient(nightreport.main.app)

    Parameters
    ----------
    dsn : `dict[str, str]`
        The database dsn dict.

    Returns
    -------
    db_config : `dict[str, str]`
        The app database configuration arguments.

    """
    assert dsn.keys() <= {"port", "host", "user", "database"}
    return {f"nightreport_db_{key}".upper(): str(value) for key, value in dsn.items()}


def random_bool() -> bool:
    """Create a random bool.

    Returns
    -------
    value : `bool`
        The random bool. Half of the time it will be True.
    """
    return random.random() > 0.5


def random_date(precision: int = 0) -> datetime.datetime:
    """Create a random date between MIN_DATE_RANDOM_REPORT
    and MAX_DATE_RANDOM_REPORT.

    Parameters
    ----------
    precision : `int`
        The number of decimal digits of seconds.
        If 0 then the output has no decimal point after the seconds field.

    Returns
    -------
    date : `datetime.datetime`
        The random date.
    """
    min_date_unix = astropy.time.Time(MIN_DATE_RANDOM_REPORT).unix
    max_date_unix = astropy.time.Time(MAX_DATE_RANDOM_REPORT).unix
    dsec = max_date_unix - min_date_unix
    unix_time = min_date_unix + random.random() * dsec
    return astropy.time.Time(unix_time, format="unix", precision=precision).datetime


def random_duration(precision: int = 0) -> datetime.timedelta:
    """Create a random duration. Half of the time return duration=0.

    Parameters
    ----------
    precision : int
        Number of digits after the decimal point of seconds.

    Returns
    -------
    duration : `datetime.timedelta`
        The random duration.
    """
    if random.random() > 0.5:
        return datetime.timedelta()
    dsec = MAX_TIME_DELTA_RANDOM_REPORT.total_seconds()
    duration_sec = round(random.random() * dsec, precision)
    return datetime.timedelta(seconds=duration_sec)


def random_str(nchar: int) -> str:
    """Create a random string of nchar printable UTF-8 characters.

    The list of characters is limited, but attempts to
    cover a wide range of potentially problematic characters
    including ' " \t \n \\ and an assortment of non-ASCII characters.

    Parameters
    ----------
    nchar : `int`
        The number of characters in the string.

    Returns
    -------
    string : `str`
        The random string.
    """
    chars = list(
        "abcdefgABCDEFG012345 \t\n\r"
        "'\"“”`~!@#$%^&*()-_=+[]{}\\|,.<>/?"
        "¡™£¢∞§¶•ªº–≠“‘”’«»…ÚæÆ≤¯≥˘÷¿"
        "œŒ∑„®‰†ˇ¥ÁüîøØπ∏åÅßÍ∂ÎƒÏ©˝˙Ó∆Ô˚¬ÒΩ¸≈˛çÇ√◊∫ıñµÂ"
        "✅😀⭐️🌈🌎1️⃣🟢❖🍏🪐💫🥕🥑🌮🥗🚠🚞🚀⚓️🚁🚄🏝🧭🕰📡🗝📅🖋🔎❤️☮️"
    )
    return "".join(random.sample(chars, nchar))


def random_strings(words: list[str], max_num: int = 3) -> list[str]:
    """Create a list of 0 or more strings from a list of strings.

    Half of the time it will return 0 items.
    The rest of the time it will return 1 - max_num values
    in random order, with equal probability per number of returned strings.

    Parameters
    ----------
    strings : `list[str]`
        List of strings from which to select returned strings.
    max_num : `typing.Optional[int]`
        The maximum number of returned strings.
        Default is 3.

    Returns
    -------
    strings : `list[str]`
        The random list of strings.
    """
    if random.random() < 0.5:
        return []
    num_to_return = random.randint(1, max_num)
    return random.sample(words, num_to_return)


def random_day_obs() -> int:
    """Return a random day_obs, as an integer in the form YYYYMMDD.

    Returns
    -------
    day_obs : `int`
        The random day_obs.
    """
    return int(random_date().isoformat().split("T")[0].replace("-", ""))


def random_report() -> ReportDictT:
    """Make one random report, as a dict of field: value.

    All reports will have ``id=None``, ``site_id=TEST_SITE_ID``,
    ``is_valid=True``, ``date_invalidated=None``, ``date_sent=None``,
    and ``parent_id=None``.

    Fields are in the same order as `Report` and the database schema,
    to make it easier to visually compare these reports to reports in
    responses.

    String are random unicode characters. Tags and urls are generated from
    a random selection (of random length) of possible tags and URLs.

    To use:

    * Call multiple times to make a list of reports.
    * Sort that list by ``date_added``.
    * Add the ``id`` field, in order, starting at 1.
    * Optionally modify some reports to be edited versions
      of earlier reports, as follows:

      * Set edited_report["parent_id"] = parent_report["id"]
      * Set parent_report["is_valid"] = False
      * Set parent_report["date_invalidated"] =
        edited_report["date_added"]

    Returns
    -------
    report : `ReportDictT`
        The random report.
    """

    report = dict(
        id=None,
        site_id=TEST_SITE_ID,
        telescope=random.choice([t.value for t in Telescope]),
        day_obs=random_day_obs(),
        summary=random_str(nchar=20),
        telescope_status=random_str(nchar=20),
        confluence_url=random_str(nchar=30),
        user_id=random_str(nchar=14),
        user_agent=random_str(nchar=12),
        is_valid=True,
        date_added=random_date(),
        date_sent=None,
        observers_crew=random_strings(TEST_CREW_MEMBERS, max_num=3),
        date_invalidated=None,
        parent_id=None,
    )

    # Check that we have set all fields (not necessarily in order).
    assert set(report) == set(NIGHTREPORT_FIELDS)

    return report


def random_reports(num_reports: int, num_edited: int) -> list[ReportDictT]:
    """Make a list of random reports, each a dict of field: value.

    Parameters
    ----------
    num_reports : `int`
        Number of reports.
    num_edited : `int`
        Number of these reports that should be edited versions
        of earlier reports.

    Returns
    -------
    reports : `list[ReportDictT]`
        The random reports.

    Notes
    -----
    The list will be in order of increasing ``date_added``.
    Link about half of the reports to an older report.
    """
    report_list = [random_report() for i in range(num_reports)]
    report_list.sort(key=lambda report: report["date_added"])
    for i, report in enumerate(report_list):
        report["id"] = uuid.uuid4()

    # Create edited reports.
    parent_report_id_set: set[uuid.UUID] = set()
    edited_reports: list[ReportDictT] = list(
        # [1:] because there is no older report to be the parent.
        random.sample(report_list[1:], num_edited)
    )
    edited_reports.sort(key=lambda report: report["date_added"])
    for i, report in enumerate(edited_reports):
        while True:
            parent_report = random.choice(report_list[0 : i + 1])
            if parent_report["id"] not in parent_report_id_set:
                parent_report_id_set.add(parent_report["id"])
                break
        report["parent_id"] = parent_report["id"]
        parent_report["is_valid"] = False
        parent_report["date_invalidated"] = report["date_added"]
    return report_list


async def create_test_database(
    postgres_url: str,
    num_reports: int,
    num_edited: int = 0,
) -> list[ReportDictT]:
    """Create a test database, initialize it with random reports,
    and return the reports.

    Parameters
    ----------
    postgresql_url : `str`
        URL to PostgreSQL database. Typically a test database created using::

            with testing.postgresql.Postgresql() as postgresql:
                postgres_url = postgresql.url()
    num_reports : `int`
        Number of reports.
    num_edited : `typing.Optional[int]`
        Number of these reports that should be edited versions
        of earlier reports. Must be 0 or < ``num_reports``.

    Returns
    -------
    reports : `list[ReportDictT]`
        The randomly created reports. Each report is a dict of field: value
        and all fields are set.
    """
    if num_edited > 0 and num_edited >= num_reports:
        raise ValueError(
            f"num_edited={num_edited} must be zero or "
            f"less than num_reports={num_reports}"
        )
    sa_url = sqlalchemy.engine.make_url(postgres_url)
    sa_url = sa_url.set(drivername="postgresql+asyncpg")
    engine = create_async_engine(sa_url, future=True)

    sa_metadata = MetaData()
    table_report = create_nightreport_table(sa_metadata)
    async with engine.begin() as connection:
        # await connection.run_sync(table_report.metadata.create_all)
        await connection.run_sync(sa_metadata.create_all)

    reports = random_reports(num_reports=num_reports, num_edited=num_edited)
    async with engine.begin() as connection:
        for report in reports:
            # Do not insert the "is_valid" field
            # because it is computed.
            pruned_report = report.copy()
            del pruned_report["is_valid"]

            # Insert the report
            result_report = await connection.execute(
                table_report.insert()
                .values(**pruned_report)
                .returning(table_report.c.id, table_report.c.is_valid)
            )
            data_report = result_report.fetchone()
            assert report["id"] == data_report.id
            assert report["is_valid"] == data_report.is_valid

    return reports
