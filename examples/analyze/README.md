# AI 失败分析演示

`examples/analyze/fail_demo.yaml` 是一条**故意写错期望值**的用例，用于演示失败分析能力。

```bash
python examples/mock_server.py                                  # 终端①：启动演示服务
atf run examples/analyze/fail_demo.yaml -e examples/config.yaml --ai-analyze
```

- 无密钥时：规则引擎给出分类（本例为"用例问题：断言期望与实际返回不一致"）
- 配置 `ATF_AI_API_KEY` 后：大模型给出更准确的原因与建议

再追加 `--ai-fix`，大模型会给出修改后的步骤 YAML（diff 形式）：

```bash
atf run examples/analyze/fail_demo.yaml -e examples/config.yaml --ai-analyze --ai-fix
```

该用例不在特性巡检套件（`feature_suite.yaml`）内——巡检必须保持绿色。
