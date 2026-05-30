from app.chat_commands import is_clear_chat_command


def test_clear_chat_command_variants() -> None:
    assert is_clear_chat_command("/clear")
    assert is_clear_chat_command("  /clear  ")
    assert is_clear_chat_command("clear")
    assert is_clear_chat_command("/CLEAR.")
    assert is_clear_chat_command("\uff0fclear")


def test_non_clear_messages() -> None:
    assert not is_clear_chat_command("investigate brute force")
    assert not is_clear_chat_command("/clearing history")
