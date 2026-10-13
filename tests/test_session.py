import unittest

from atf.runner import Runner


def _extract_case(name, shared=True):
    config = {"name": name}
    if shared:
        config["session"] = "shared"
    return {"config": config, "teststeps": [{
        "name": "取数",
        "db": {"url": "sqlite:///:memory:", "query": "SELECT 42 AS n"},
        "extract": {"n": "$[0].n"},
    }]}


def _use_case(name, shared=True):
    config = {"name": name}
    if shared:
        config["session"] = "shared"
    return {"config": config, "teststeps": [{
        "name": "用共享变量",
        "db": {"url": "sqlite:///:memory:", "query": "SELECT 1 AS x"},
        "validate": [{"eq": ["${n}", 42]}],
    }]}


class TestSession(unittest.TestCase):
    def test_shared_session_propagates_variables(self):
        suites = Runner().run_cases([_extract_case("A"), _use_case("B")])
        self.assertEqual(len(suites), 2)
        self.assertTrue(all(suite.passed for suite in suites),
                        [suite.steps[0].error for suite in suites])

    def test_without_shared_variable_not_propagated(self):
        suites = Runner().run_cases([_extract_case("A", shared=False),
                                     _use_case("B", shared=False)])
        self.assertTrue(suites[0].passed)
        self.assertFalse(suites[1].passed)  # 非共享，拿不到 n

    def test_config_variables_not_leaked_into_session(self):
        # A 通过 hooks/extract 产生的变量会共享；但 B 自己的 config.variables 不被 A 污染
        a = _extract_case("A")
        b = _use_case("B")
        b["config"]["variables"] = {"local_only": "B"}
        suites = Runner().run_cases([a, b])
        self.assertTrue(all(suite.passed for suite in suites))


if __name__ == "__main__":
    unittest.main()
