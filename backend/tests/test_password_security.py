from hashlib import sha256
import unittest

import bcrypt

from app.core.security import (
    BCRYPT_PREFIX,
    BCRYPT_ROUNDS,
    hash_password,
    password_hash_needs_rehash,
    verify_password,
)


class PasswordSecurityTests(unittest.TestCase):
    def test_hash_password_uses_bcrypt_sha256_prefix_and_verifies(self):
        hashed = hash_password("AgentHive123!")

        self.assertTrue(hashed.startswith(BCRYPT_PREFIX))
        self.assertTrue(verify_password("AgentHive123!", hashed))
        self.assertFalse(verify_password("wrong-password", hashed))

    def test_verify_password_fails_closed_for_unsupported_or_corrupt_hashes(self):
        self.assertFalse(verify_password("AgentHive123!", "sha256$plain-digest"))
        self.assertFalse(verify_password("AgentHive123!", f"{BCRYPT_PREFIX}not-a-bcrypt-hash"))

    def test_new_hash_does_not_need_rehash(self):
        hashed = hash_password("AgentHive123!")

        self.assertFalse(password_hash_needs_rehash(hashed))

    def test_legacy_low_cost_bcrypt_hash_needs_rehash_but_still_verifies(self):
        digest = sha256("AgentHive123!".encode("utf-8")).digest()
        legacy = f"{BCRYPT_PREFIX}{bcrypt.hashpw(digest, bcrypt.gensalt(rounds=BCRYPT_ROUNDS - 2)).decode()}"

        self.assertTrue(verify_password("AgentHive123!", legacy))
        self.assertTrue(password_hash_needs_rehash(legacy))

    def test_unknown_hash_format_needs_rehash(self):
        self.assertTrue(password_hash_needs_rehash("sha256$legacy"))
        self.assertTrue(password_hash_needs_rehash(f"{BCRYPT_PREFIX}broken"))


if __name__ == "__main__":
    unittest.main()
