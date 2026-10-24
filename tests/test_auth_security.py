def test_password_hash_is_not_plaintext():
    from app.services.auth_service import (
        hash_password,
        verify_password,
    )

    password = "A-Strong-Test-Password-123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_contains_user_subject():
    from uuid import uuid4

    from app.services.auth_service import (
        create_access_token,
        decode_access_token,
    )

    user_id = str(uuid4())
    token = create_access_token(user_id)

    assert decode_access_token(token)["sub"] == user_id