# CI/CD 集成指南

ATF 是纯 CLI 工具，接入任何流水线只需要三步：装好、跑 `atf run`、按退出码判定结果。

| 退出码 | 含义 |
|--------|------|
| 0 | 全部通过 |
| 1 | 存在失败（或被跳过的步骤） |
| 2 | 用法错误（文件不存在、配置有误等） |

安装建议：PyPI 包发布前，先从 Git 安装（下方示例均如此，发布后替换为 `pip install atf` 即可）：

```bash
pip install git+https://github.com/jiacy-jcy/autotest_framework.git
```

## GitHub Actions

每次提交跑 smoke 标签用例，定时任务跑全量回归，报告作为 artifact 保留：

```yaml
name: 接口回归

on:
  push:
    branches: [main]
  schedule:
    - cron: "0 2 * * *"        # 每天 02:00 全量回归

jobs:
  api-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: 安装 ATF
        run: pip install git+https://github.com/jiacy-jcy/autotest_framework.git

      # --trend 的历史文件做缓存，跨次执行才能积累趋势
      - name: 缓存趋势历史
        uses: actions/cache@v4
        with:
          path: reports/history.jsonl
          key: atf-history

      - name: 冒烟回归（每次提交）
        run: atf run cases --tags smoke -e config.yaml --trend --html reports/smoke-report.html

      - name: 全量回归（仅定时任务）
        if: github.event_name == 'schedule'
        run: atf run cases -e config.yaml --trend --html reports/full-report.html

      - name: 上传报告
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: atf-report
          path: reports/
```

敏感信息（域名、密码）不要提交进配置文件，用 Secrets 在执行前生成临时配置：

```yaml
      - name: 生成临时环境配置
        run: printf 'base_url: %s\napi_secret: %s\n' "$BASE_URL" "$API_SECRET" > config.yaml
        env:
          BASE_URL: ${{ secrets.BASE_URL }}
          API_SECRET: ${{ secrets.API_SECRET }}
```

用例里用 `${sys.api_secret}` 引用，与命名空间设计一致：CI 注入的变量显式走 `sys`，不和用例变量混淆。

## Jenkins（Declarative Pipeline）

```groovy
pipeline {
    agent any
    parameters {
        string(name: 'ENV_NAME', defaultValue: 'test', description: '目标环境')
    }
    stages {
        stage('接口回归') {
            steps {
                sh 'pip install git+https://github.com/jiacy-jcy/autotest_framework.git'
                sh "atf run cases --tags smoke -e config.yaml --env-name ${params.ENV_NAME} " +
                   "--trend --html reports/atf-report.html"
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true
                }
            }
        }
    }
}
```

## GitLab CI

```yaml
api-test:
  image: python:3.12
  stage: test
  script:
    - pip install git+https://github.com/jiacy-jcy/autotest_framework.git
    - atf run cases --tags smoke -e config.yaml --trend --html reports/atf-report.html
  artifacts:
    when: always
    paths:
      - reports/
  cache:
    key: atf-history
    paths:
      - reports/history.jsonl
```

## 通用建议

- **分层回归**：`--tags smoke` 只跑冒烟集，每次提交执行；全量回归放定时任务，避免拖慢合并速度
- **趋势要持久化**：`--trend` 的历史写在 `reports/history.jsonl`，CI 里用 cache/artifact 保留它，否则每次都从零积累、趋势图没有意义
- **报告当产物**：HTML 报告是单文件，直接作为流水线产物归档，失败排查不用上服务器
- **配置分层**：多环境用 `environments` 分区 + `--env-name` 切换，CI 参数化目标环境（见 Jenkins 示例）
- **密钥管理**：账号密码放 CI Secrets，执行前生成临时配置文件；用例里通过 `${sys.变量名}` 显式引用
