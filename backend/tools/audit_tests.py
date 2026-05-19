from __future__ import annotations
from typing import Any
import pandas as pd
from tools.base import BaseTool, ExecutionContext, ToolError
from tools.preparation import _evaluate_condition


class TestTool(BaseTool):
    tool_type = "test"
    display_name = "Test"
    category = "Audit Tests / Controls"
    description = "Validate assumptions and produce pass/fail results."
    input_ports = ["in"]
    output_ports = ["passed", "failed"]
    config_schema = {
        "test_name": {"type": "text", "label": "Test name", "default": "Validation test"},
        "test_type": {
            "type": "select",
            "label": "Test type",
            "options": [
                "record_count_equals",
                "record_count_gte",
                "record_count_lte",
                "required_fields_exist",
                "field_has_no_nulls",
                "expression_true_for_all",
                "expression_true_for_any",
            ],
            "default": "record_count_gte",
        },
        "expected_value": {"type": "text", "label": "Expected value"},
        "fields": {"type": "multi_field_selector", "label": "Fields (for field-based tests)"},
        "condition": {"type": "condition_builder", "label": "Condition (for expression tests)"},
        "severity": {"type": "select", "label": "Severity", "options": ["info", "warning", "error"], "default": "error"},
        "stop_on_failure": {"type": "checkbox", "label": "Stop workflow on failure", "default": False},
    }

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        df = inputs.get("in", pd.DataFrame())
        test_type = config.get("test_type", "record_count_gte")
        test_name = config.get("test_name", "Test")
        severity = config.get("severity", "error")
        stop = config.get("stop_on_failure", False)

        passed = True
        message = ""

        if test_type == "record_count_equals":
            expected = int(config.get("expected_value", 0))
            passed = len(df) == expected
            message = f"Expected {expected} rows, got {len(df)}"
        elif test_type == "record_count_gte":
            expected = int(config.get("expected_value", 1))
            passed = len(df) >= expected
            message = f"Expected >= {expected} rows, got {len(df)}"
        elif test_type == "record_count_lte":
            expected = int(config.get("expected_value", 0))
            passed = len(df) <= expected
            message = f"Expected <= {expected} rows, got {len(df)}"
        elif test_type == "required_fields_exist":
            fields = config.get("fields", [])
            missing = [f for f in fields if f not in df.columns]
            passed = len(missing) == 0
            message = f"Missing fields: {missing}" if missing else "All required fields present"
        elif test_type == "field_has_no_nulls":
            fields = config.get("fields") or list(df.columns)
            null_fields = [f for f in fields if f in df.columns and df[f].isna().any()]
            passed = len(null_fields) == 0
            message = f"Fields with nulls: {null_fields}" if null_fields else "No null values found"
        elif test_type == "expression_true_for_all":
            cond = config.get("condition")
            if cond:
                mask = _evaluate_condition(df, cond)
                passed = bool(mask.all())
                fail_count = int((~mask).sum())
                message = f"{fail_count} rows failed the condition" if not passed else "All rows passed"
            else:
                passed = True
                message = "No condition configured"
        elif test_type == "expression_true_for_any":
            cond = config.get("condition")
            if cond:
                mask = _evaluate_condition(df, cond)
                passed = bool(mask.any())
                message = "No rows matched the condition" if not passed else "At least one row passed"
            else:
                passed = True
                message = "No condition configured"

        log_fn = context.logger
        status = "PASS" if passed else "FAIL"
        log_fn(f"[{severity.upper()}] Test '{test_name}': {status} — {message}")

        if not passed and stop:
            raise ToolError(f"Test '{test_name}' failed: {message}")

        fail_df = pd.DataFrame([{
            "test_name": test_name,
            "test_type": test_type,
            "passed": passed,
            "severity": severity,
            "message": message,
        }])

        return {
            "passed": df.copy() if passed else pd.DataFrame(columns=df.columns),
            "failed": fail_df if not passed else pd.DataFrame(columns=fail_df.columns),
        }

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        in_var = input_vars.get("in", "df")
        test_name = config.get("test_name", "Test")
        test_type = config.get("test_type", "record_count_gte")
        expected = config.get("expected_value", 1)
        return (
            f"# Test: {test_name}\n"
            f"_test_passed = len({in_var}) >= {expected}  # {test_type}\n"
            f"assert _test_passed, \"Test '{test_name}' failed\""
        )


class MessageTool(BaseTool):
    tool_type = "message"
    display_name = "Message"
    category = "Audit Tests / Controls"
    description = "Emit user-defined messages, warnings, or errors during execution."
    input_ports = ["in"]
    output_ports = ["out"]
    config_schema = {
        "trigger": {
            "type": "select",
            "label": "Trigger",
            "options": ["always", "if_empty", "if_not_empty"],
            "default": "always",
        },
        "severity": {"type": "select", "label": "Severity", "options": ["info", "warning", "error"], "default": "info"},
        "message_text": {"type": "textarea", "label": "Message"},
        "stop_on_error": {"type": "checkbox", "label": "Stop on error", "default": False},
    }

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        df = inputs.get("in", pd.DataFrame())
        trigger = config.get("trigger", "always")
        text = config.get("message_text", "")
        severity = config.get("severity", "info")

        should_emit = (
            trigger == "always"
            or (trigger == "if_empty" and len(df) == 0)
            or (trigger == "if_not_empty" and len(df) > 0)
        )

        if should_emit:
            context.logger(f"[{severity.upper()}] {text}")
            if severity == "error" and config.get("stop_on_error"):
                raise ToolError(text)

        return {"out": df.copy()}

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        in_var = input_vars.get("in", "df")
        out_var = output_vars.get("out", "df")
        msg = config.get("message_text", "")
        severity = config.get("severity", "info")
        return f'print("[{severity.upper()}] {msg}")\n{out_var} = {in_var}.copy()'


class FieldInfoTool(BaseTool):
    tool_type = "field_info"
    display_name = "Field Info"
    category = "Audit Tests / Controls"
    description = "Output metadata about fields in the input dataset."
    input_ports = ["in"]
    output_ports = ["out"]
    config_schema = {}

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        df = inputs.get("in", pd.DataFrame())
        rows = [
            {"field_name": col, "dtype": str(df[col].dtype), "position": i, "nullable": bool(df[col].isna().any())}
            for i, col in enumerate(df.columns)
        ]
        return {"out": pd.DataFrame(rows)}

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        in_var = input_vars.get("in", "df")
        out_var = output_vars.get("out", "field_info")
        return (
            f"{out_var} = pd.DataFrame([\n"
            f"    {{\"field_name\": col, \"dtype\": str({in_var}[col].dtype), \"position\": i}}\n"
            f"    for i, col in enumerate({in_var}.columns)\n"
            f"])"
        )


class ExpectEqualTool(BaseTool):
    tool_type = "expect_equal"
    display_name = "Expect Equal"
    category = "Audit Tests / Controls"
    description = "Compare two data streams and detect differences."
    input_ports = ["actual", "expected"]
    output_ports = ["result", "differences"]
    config_schema = {
        "key_fields": {"type": "multi_field_selector", "label": "Key fields"},
        "compare_fields": {"type": "multi_field_selector", "label": "Fields to compare (empty = all)"},
        "ignore_row_order": {"type": "checkbox", "label": "Ignore row order", "default": True},
        "numeric_tolerance": {"type": "number", "label": "Numeric tolerance", "default": 0.0},
    }

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        actual = inputs.get("actual", pd.DataFrame())
        expected = inputs.get("expected", pd.DataFrame())
        key_fields = config.get("key_fields", [])
        compare_fields = config.get("compare_fields") or list(set(actual.columns) & set(expected.columns))
        ignore_order = config.get("ignore_row_order", True)
        tolerance = float(config.get("numeric_tolerance", 0.0))

        differences = []
        passed = True

        if set(actual.columns) != set(expected.columns):
            passed = False
            differences.append({
                "type": "schema_mismatch",
                "actual_columns": list(actual.columns),
                "expected_columns": list(expected.columns),
            })

        if ignore_order and key_fields:
            actual_s = actual.sort_values(key_fields).reset_index(drop=True)
            expected_s = expected.sort_values(key_fields).reset_index(drop=True)
        elif ignore_order:
            actual_s = actual.sort_values(list(actual.columns)).reset_index(drop=True)
            expected_s = expected.sort_values(list(expected.columns)).reset_index(drop=True)
        else:
            actual_s = actual.reset_index(drop=True)
            expected_s = expected.reset_index(drop=True)

        if len(actual_s) != len(expected_s):
            passed = False
            differences.append({
                "type": "row_count_mismatch",
                "actual_count": len(actual_s),
                "expected_count": len(expected_s),
            })

        result_df = pd.DataFrame([{
            "passed": passed,
            "actual_rows": len(actual),
            "expected_rows": len(expected),
            "difference_count": len(differences),
        }])
        diff_df = pd.DataFrame(differences) if differences else pd.DataFrame(columns=["type"])

        return {"result": result_df, "differences": diff_df}

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        actual_var = input_vars.get("actual", "actual_df")
        expected_var = input_vars.get("expected", "expected_df")
        result_var = output_vars.get("result", "comparison_result")
        return (
            f"_passed = {actual_var}.equals({expected_var})\n"
            f"{result_var} = pd.DataFrame([{{\"passed\": _passed, "
            f"\"actual_rows\": len({actual_var}), \"expected_rows\": len({expected_var})}}])"
        )
