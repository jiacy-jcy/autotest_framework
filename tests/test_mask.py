import unittest

from atf.mask import mask_data, mask_keys, mask_text
from atf.runner import Runner


class TestMask(unittest.TestCase):
    def test_mask_keys_parsing(self):
        self.assertEqual(mask_keys({}), [])
        self.assertEqual(mask_keys({"mask": ["a", "b"]}), ["a", "b"])
        self.assertEqual(mask_keys({"mask": "a, b"}), ["a", "b"])

    def test_mask_data_nested(self):
        data = {"password": "x", "data": {"token": "t", "name": "n"}, "list": [{"token": "y"}]}
        masked = mask_data(data, ["password", "token"])
        self.assertEqual(masked["password"], "******")
        self.assertEqual(masked["data"]["token"], "******")
        self.assertEqual(masked["data"]["name"], "n")
        self.assertEqual(masked["list"][0]["token"], "******")

    def test_mask_text_non_json_passthrough(self):
        self.assertEqual(mask_text("纯文本内容", ["a"]), "纯文本内容")

    def test_mask_text_json(self):
        masked = mask_text('{"token": "abc", "code": 0}', ["token"])
        self.assertIn("******", masked)
        self.assertNotIn("abc", masked)

    def test_runner_masks_response_body(self):
        case = {
            "config": {"name": "脱敏", "mask": ["secret"]},
            "teststeps": [{
                "name": "查询",
                "db": {"url": "sqlite:///:memory:",
                       "query": "SELECT 'topsecret' AS secret, 1 AS code"},
                "validate": [{"eq": ["$[0].code", 1]}],
            }],
        }
        suite = Runner().run_case(case)
        self.assertTrue(suite.passed, suite.steps[0].error)
        body = suite.steps[0].detail.response_body
        self.assertIn("******", body)
        self.assertNotIn("topsecret", body)


if __name__ == "__main__":
    unittest.main()
