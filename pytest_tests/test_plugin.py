"""验证 ATF 的 pytest 插件：YAML 用例在 pytest 中被收集与执行"""
import textwrap


def _write_case(pytester, name, body):
    pytester.makefile(".yaml", **{name: textwrap.dedent(body)})


def test_runs_atf_case(pytester, mock_server):
    _write_case(pytester, "case", f"""
        config:
          name: 冒烟用例
          base_url: {mock_server}
        teststeps:
          - name: 查询用户
            request:
              method: GET
              url: /api/users/7
              headers:
                Authorization: "Bearer t-001"
            validate:
              - eq: [$.code, 0]
              - eq: [$.data.name, 张三]
    """)
    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)
    result.stdout.fnmatch_lines(["*冒烟用例*"])


def test_reports_failure_in_chinese(pytester, mock_server):
    _write_case(pytester, "case", f"""
        config:
          name: 会失败的用例
          base_url: {mock_server}
        teststeps:
          - name: 断言错误
            request:
              method: GET
              url: /api/users/7
              headers:
                Authorization: "Bearer t-001"
            validate:
              - eq: [$.code, 999]
    """)
    result = pytester.runpytest()
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*ATF 用例失败*", "*断言失败*"])


def test_ignores_non_atf_yaml(pytester):
    pytester.makefile(".yaml", other="foo: bar\n")
    result = pytester.runpytest()
    assert "collected 0 items" in result.stdout.str()
