import unittest
from uuid import uuid4

from pydantic import ValidationError

from app.core.secrets import encrypt_secret, mask_secret
from app.schemas.llm import LLMConnectionTestRequest, LLMCredentialUpsertRequest


class LLMCredentialSecurityTests(unittest.TestCase):
    def test_credential_base_url_is_normalized(self):
        payload = LLMCredentialUpsertRequest(
            display_name="Qwen Key",
            api_key="sk-test",
            base_url=" https://dashscope.aliyuncs.com/compatible-mode/v1/ ",
            owner_type="TENANT",
        )

        self.assertEqual("https://dashscope.aliyuncs.com/compatible-mode/v1", payload.base_url)
        self.assertEqual("tenant", payload.owner_type)

    def test_invalid_owner_type_is_rejected(self):
        with self.assertRaises(ValidationError):
            LLMCredentialUpsertRequest(
                display_name="Bad Key",
                api_key="sk-test",
                owner_type="workspace",
            )

    def test_owner_id_scope_rules_are_enforced(self):
        department_id = uuid4()
        payload = LLMCredentialUpsertRequest(
            display_name="Department Key",
            api_key="sk-test",
            owner_type="department",
            owner_id=department_id,
        )

        self.assertEqual("department", payload.owner_type)
        self.assertEqual(department_id, payload.owner_id)

        with self.assertRaises(ValidationError):
            LLMCredentialUpsertRequest(
                display_name="Missing Owner",
                api_key="sk-test",
                owner_type="department",
            )

        with self.assertRaises(ValidationError):
            LLMCredentialUpsertRequest(
                display_name="Tenant With Owner",
                api_key="sk-test",
                owner_type="tenant",
                owner_id=uuid4(),
            )

    def test_non_http_base_url_is_rejected_for_saved_and_temporary_credentials(self):
        with self.assertRaises(ValidationError):
            LLMCredentialUpsertRequest(
                display_name="Bad URL",
                api_key="sk-test",
                base_url="file:///tmp/model.sock",
            )

        with self.assertRaises(ValidationError):
            LLMConnectionTestRequest(
                provider_key="openai_compatible",
                api_key="sk-test",
                base_url="ftp://model.local/v1",
            )

    def test_encrypted_secret_can_exceed_legacy_varchar_length(self):
        secret = "sk-" + "x" * 256
        encrypted = encrypt_secret(secret)

        self.assertGreater(len(encrypted), 255)
        self.assertEqual("sk-x...xxxx", mask_secret(secret))


if __name__ == "__main__":
    unittest.main()
