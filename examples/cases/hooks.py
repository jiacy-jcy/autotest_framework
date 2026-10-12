"""示例钩子（与 hooks_demo.yaml 同目录，便于框架自动导入）"""


def before_case(context):
    """用例开始前：准备一个运行标识，供用例以 ${run_id} 引用"""
    context.set("run_id", "RUN-DEMO")


def before_step(context):
    """每个步骤前：为请求统一追加一个追踪请求头"""
    request = context.step.get("request")
    if isinstance(request, dict):
        request.setdefault("headers", {})["X-Run-Id"] = context.get("run_id")


def after_step(context):
    """每个步骤后：记录失败步骤，便于排查"""
    if context.result and not context.result.passed:
        print(f"[钩子] 步骤失败：{context.step['name']}")
