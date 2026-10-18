import pytest

from src.calculator import multiply


@pytest.mark.parametrize("number", range(-30, 30))
def test_multiply(number):
    assert multiply(number, 7) == number * 7
