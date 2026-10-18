import pytest

from src.calculator import add


@pytest.mark.parametrize("number", range(-30, 30))
def test_add(number):
    assert add(number, 7) == number + 7
