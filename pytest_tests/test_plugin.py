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


def test_tags_filter_collects_matching_only(pytester):
    pytester.makefile(".yaml", tagged=textwrap.dedent("""
        config:
          name: 带标签用例
          tags: [smoke]
        teststeps:
          - name: 步骤
            db:
              url: "sqlite:///:memory:"
              query: "SELECT 1 AS x"
            validate:
              - eq: ["$[0].x", 1]
    """))
    pytester.makefile(".yaml", other=textwrap.dedent("""
        config:
          name: 普通用例
        teststeps:
          - name: 步骤
            db:
              url: "sqlite:///:memory:"
              query: "SELECT 1 AS x"
            validate:
              - eq: ["$[0].x", 1]
    """))
    result = pytester.runpytest("--atf-tags", "smoke", "-v")
    result.assert_outcomes(passed=1)
    result.stdout.fnmatch_lines(["*带标签用例*"])


def test_data_driven_parametrization(pytester, mock_server):
    pytester.makefile(
        ".csv",
        login="case_name,username,password,expect_code\n"
              "正确登录,admin,123456,0\n"
              "密码错误,admin,000000,1001\n",
    )
    pytester.makefile(".yaml", case=textwrap.dedent(f"""
        config:
          name: 登录参数化
          base_url: {mock_server}
          datas: login.csv
        teststeps:
          - name: 登录
            request:
              method: POST
              url: /api/login
              json:
                username: ${{username}}
                password: ${{password}}
            validate:
              - eq: [$.code, "${{expect_code}}"]
    """))
    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=2)  # 两行数据参数化为两个用例
    result.stdout.fnmatch_lines(["*正确登录*", "*密码错误*"])
