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

import typing

import asyncpg.exceptions
import psycopg
import pytest
from lsst.ts.nightreport.create_tables import SITE_ID_LEN
from lsst.ts.nightreport.shared_state import (
    create_shared_state,
    delete_shared_state,
    get_env,
    get_shared_state,
    has_shared_state,
)
from lsst.ts.nightreport.testutils import (
    TEST_SITE_ID,
    create_test_database,
    db_config_from_dsn,
    modify_environ,
)


@pytest.mark.asyncio
async def test_shared_state(postgresql: psycopg.Connection) -> None:
    try:
        with postgresql as conn:
            postgresql_url = (
                f"postgresql://"
                f"{conn.info.user}@{conn.info.host}"
                f":{conn.info.port}/{conn.info.dbname}"
            )
            await create_test_database(postgresql_url, num_reports=0)
            assert not has_shared_state()
            with pytest.raises(RuntimeError):
                get_shared_state()

            postgresql_dsn = {
                "user": conn.info.user,
                "host": conn.info.host,
                "port": conn.info.port,
                "database": conn.info.dbname,
            }
            required_kwargs: dict[str, typing.Any] = dict(SITE_ID=TEST_SITE_ID)
            db_config = db_config_from_dsn(postgresql_dsn)

            # Test missing required env variables.
            for key in required_kwargs:
                missing_required_kwargs = required_kwargs.copy()
                missing_required_kwargs[key] = None
                with modify_environ(
                    **missing_required_kwargs,
                    **db_config,
                ):
                    assert not has_shared_state()
                    with pytest.raises(ValueError):
                        await create_shared_state()

            # Test invalid SITE_ID
            bad_site_id = "A" * (SITE_ID_LEN + 1)
            with modify_environ(
                SITE_ID=bad_site_id,
                **db_config,
            ):
                assert not has_shared_state()
                with pytest.raises(ValueError):
                    await create_shared_state()

            # Dict of invalid database configuration and the expected error
            # that results if that one item is bad.
            db_bad_config_error = dict(
                NIGHTREPORT_DB_PORT=("54321", OSError),
                # An invalid NIGHTREPORT_DB_HOST
                # takes a long time to time out, so don't bother.
                NIGHTREPORT_DB_USER=(
                    "invalid_user",
                    asyncpg.exceptions.PostgresError,
                ),
                NIGHTREPORT_DB_DATABASE=(
                    "invalid_database",
                    asyncpg.exceptions.PostgresError,
                ),
            )

            # Test bad database configuration env variables.
            for key, (
                bad_value,
                expected_error,
            ) in db_bad_config_error.items():
                bad_db_config = db_config.copy()
                bad_db_config[key] = bad_value
                with modify_environ(
                    **required_kwargs,
                    **bad_db_config,
                ):
                    assert not has_shared_state()
                    with pytest.raises(expected_error):
                        await create_shared_state()

            # Test a valid shared state
            with modify_environ(
                **required_kwargs,
                **db_config,
            ):
                await create_shared_state()
                assert has_shared_state()

                state = get_shared_state()
                assert state.site_id == required_kwargs["SITE_ID"]

                # Cannot create shared state once it is created
                with pytest.raises(RuntimeError):
                    await create_shared_state()

            await delete_shared_state()
            assert not has_shared_state()
            with pytest.raises(RuntimeError):
                get_shared_state()

            # Closing the database again should be a no-op
            await state.nightreport_db.close()

            # Deleting shared state again should be a no-op
            await delete_shared_state()
            assert not has_shared_state()
    finally:
        await delete_shared_state()


def test_get_env() -> None:
    # If default=None then value must be present
    with modify_environ(SITE_ID=None):
        with pytest.raises(ValueError):
            get_env(name="SITE_ID", default=None)

    # the default must be a str or None
    for bad_default in (1.2, 34, True, False):
        with pytest.raises(ValueError):
            get_env(name="SITE_ID", default=bad_default)  # type: ignore
