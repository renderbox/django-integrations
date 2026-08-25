import base64
import os

import pytest
from cryptography.fernet import Fernet, MultiFernet
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from integrations import conf


def _fresh_key():
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


class TestGetMultiFernet:
    @override_settings(ENCRYPTED_FIELD_KEYS=[])
    def test_empty_keys_raises_improperly_configured(self):
        with pytest.raises(ImproperlyConfigured):
            conf.get_multi_fernet()

    @override_settings(ENCRYPTED_FIELD_KEYS=None)
    def test_unset_keys_raises_improperly_configured(self):
        with pytest.raises(ImproperlyConfigured):
            conf.get_multi_fernet()

    @override_settings(ENCRYPTED_FIELD_KEYS=["not-a-valid-fernet-key"])
    def test_malformed_key_raises_improperly_configured(self):
        with pytest.raises(ImproperlyConfigured):
            conf.get_multi_fernet()

    def test_valid_keys_return_working_multi_fernet(self):
        key = _fresh_key()
        with override_settings(ENCRYPTED_FIELD_KEYS=[key]):
            multi_fernet = conf.get_multi_fernet()
        assert isinstance(multi_fernet, MultiFernet)
        token = Fernet(key).encrypt(b"hello")
        assert multi_fernet.decrypt(token) == b"hello"

    def test_resolves_settings_fresh_each_call(self):
        key_a = _fresh_key()
        key_b = _fresh_key()
        with override_settings(ENCRYPTED_FIELD_KEYS=[key_a]):
            token_a = conf.get_multi_fernet().encrypt(b"data")
        with override_settings(ENCRYPTED_FIELD_KEYS=[key_b, key_a]):
            # New primary key encrypts new values...
            token_b = conf.get_multi_fernet().encrypt(b"data")
            assert token_a != token_b
            # ...but old ciphertext still decrypts via the retained key.
            assert conf.get_multi_fernet().decrypt(token_a) == b"data"
