import pytest

from src.calculator import square


@pytest.mark.parametrize("number", range(-30, 30))
def test_square(number):
    assert square(number) >= 0
    assert square(number) == number ** 2
