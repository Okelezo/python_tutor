from __future__ import annotations

import io
import traceback
import unittest
from contextlib import redirect_stdout, redirect_stderr

from .models import GradeResult


class _UserCodeTestCase(unittest.TestCase):
    pass


def grade_submission(user_code: str, tests_code: str) -> GradeResult:
    stdout = io.StringIO()
    stderr = io.StringIO()

    try:
        globals_ns: dict[str, object] = {"__name__": "__pytutor__"}
        locals_ns: dict[str, object] = {}

        with redirect_stdout(stdout), redirect_stderr(stderr):
            exec(compile(user_code, "<user_code>", "exec"), globals_ns, locals_ns)
            exec(compile(tests_code, "<tests>", "exec"), globals_ns, locals_ns)

            suite = unittest.defaultTestLoader.loadTestsFromTestCase(_UserCodeTestCase)
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
