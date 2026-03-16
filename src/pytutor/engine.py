from __future__ import annotations

import io
import traceback
import unittest
from contextlib import redirect_stdout, redirect_stderr

from .models import GradeResult


class _UserCodeTestCase(unittest.TestCase):
    pass


def _discover_testcase_classes(namespace: dict[str, object]) -> list[type[unittest.TestCase]]:
    classes: list[type[unittest.TestCase]] = []
    for obj in namespace.values():
        if not isinstance(obj, type):
            continue
        try:
            is_case = issubclass(obj, unittest.TestCase)
        except TypeError:
            continue
        if not is_case:
            continue
        if obj is unittest.TestCase:
            continue
        classes.append(obj)
    return classes


def grade_submission(user_code: str, tests_code: str) -> GradeResult:
    stdout = io.StringIO()
    stderr = io.StringIO()

    try:
        globals_ns: dict[str, object] = {
            "__name__": "__pytutor__",
            "unittest": unittest,
            "_UserCodeTestCase": _UserCodeTestCase,
        }
        locals_ns: dict[str, object] = {}

        with redirect_stdout(stdout), redirect_stderr(stderr):
            exec(compile(user_code, "<user_code>", "exec"), globals_ns, locals_ns)
            exec(compile(tests_code, "<tests>", "exec"), globals_ns, locals_ns)

            combined_ns = {**globals_ns, **locals_ns}
            case_classes = _discover_testcase_classes(combined_ns)
            suite = unittest.TestSuite()
            for case_cls in case_classes:
                suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(case_cls))

            if suite.countTestCases() == 0:
                raise RuntimeError(
                    "No tests were discovered. Ensure your tests define a unittest.TestCase subclass with methods named test_*()."
                )

            runner = unittest.TextTestRunner(stream=stdout, verbosity=2)
            result = runner.run(suite)

        output = stdout.getvalue() + stderr.getvalue()
        if result.wasSuccessful():
            return GradeResult(passed=True, output=output)

        failed = None
        if result.failures:
            failed = result.failures[0][0].id()
        elif result.errors:
            failed = result.errors[0][0].id()

        return GradeResult(passed=False, output=output, failed_test=failed)

    except Exception:
        output = stdout.getvalue() + stderr.getvalue() + traceback.format_exc()
        return GradeResult(passed=False, output=output, failed_test="<runtime>")
