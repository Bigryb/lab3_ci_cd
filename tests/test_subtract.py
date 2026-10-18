import pytest

from src.calculator import subtract


@pytest.mark.parametrize("number", range(-30, 30))
def test_subtract(number):
    assert subtract(number, 7) == number - 7
