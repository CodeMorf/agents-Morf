from app.services.remote_ssh import parse_ssh_hint_from_user_text


def test_parse_ssh_hint_spanish():
    text = "ssh root@86.48.20.221 Clave Gaia1234 puede entrar?"
    hint = parse_ssh_hint_from_user_text(text)
    assert hint is not None
    assert hint["host"] == "86.48.20.221"
    assert hint["username"] == "root"
    assert hint["password"] == "Gaia1234"


def test_parse_ssh_hint_password_after_host():
    text = "entra aqui ssh root@86.48.20.221 Gaia1234"
    hint = parse_ssh_hint_from_user_text(text)
    assert hint is not None
    assert hint["host"] == "86.48.20.221"
    assert hint["username"] == "root"
    assert hint["password"] == "Gaia1234"


def test_parse_ssh_hint_password_label():
    text = "conecta a 10.0.0.5 password: SecretPass99!"
    hint = parse_ssh_hint_from_user_text(text)
    assert hint is not None
    assert hint["host"] == "10.0.0.5"
    assert hint["password"] == "SecretPass99!"
