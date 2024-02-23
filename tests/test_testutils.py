import datetime
import os
import random

import pytest
from lsst.ts.nightreport.testutils import create_test_client, modify_environ

random.seed(12)


@pytest.mark.asyncio
async def test_create_client_errors(postgresql) -> None:
    # num_edited must be < num_reports (unless both are 0)
    with pytest.raises(ValueError):
        async with create_test_client(postgresql, num_reports=5, num_edited=5):
            pass


def test_modify_environ() -> None:
    original_environ = os.environ.copy()
    n_to_delete = 3
    assert len(original_environ) > n_to_delete
    curr_time = datetime.datetime.now().isoformat()
    new_key0 = "_a_long_key_name_" + curr_time
    new_key1 = "_another_long_key_name_" + curr_time
    assert new_key0 not in os.environ
    assert new_key1 not in os.environ
    some_keys = random.sample(list(original_environ.keys()), 3)
    kwargs = {
        some_keys[0]: None,
        some_keys[1]: None,
        some_keys[2]: "foo",
        new_key0: "bar",
        new_key1: None,
    }

    with modify_environ(**kwargs):
        for name, value in kwargs.items():
            if value is None:
                assert name not in os.environ
            else:
                assert os.environ[name] == value
        for name, value in os.environ.items():
            if name in kwargs:
                assert value == kwargs[name]
            else:
                assert value == original_environ[name]
    assert os.environ == original_environ

    # Values that are neither None nor a string should raise RuntimeError
    for bad_value in (3, 1.23, True, False):
        bad_kwargs = kwargs.copy()
        bad_kwargs[new_key1] = bad_value  # type: ignore
        with pytest.raises(RuntimeError):
            with modify_environ(**bad_kwargs):
                pass
        assert os.environ == original_environ
