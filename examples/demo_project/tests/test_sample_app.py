from src.sample_app import greeting


def test_greeting_trims_name() -> None:
    assert greeting(' Demo ') == 'Hello, Demo!'


def test_greeting_uses_default() -> None:
    assert greeting('   ') == 'Hello, there!'
