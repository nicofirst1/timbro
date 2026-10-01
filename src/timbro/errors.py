"""One public class for every expected user error (issue #191).

`UserError` marks errors the user can fix: a bad name, a missing file, a
failed install. The CLI's single handler in `timbro.cli.main()` prints them
as one `timbro: error: <msg>` line. The compat subclasses also inherit the
builtin they replace, so existing `except` clauses and API callers keep
working. Bugs never raise these: they keep their builtin types and traceback.
"""


class UserError(Exception):
    """An expected, user-fixable error, printed as one `timbro: error:` line."""


class UserValueError(UserError, ValueError):
    """User error raised where callers catch `ValueError`."""


class UserFileNotFoundError(UserError, FileNotFoundError):
    """User error raised where callers catch `FileNotFoundError`."""


class UserFileExistsError(UserError, FileExistsError):
    """User error raised where callers catch `FileExistsError`."""


class UserRuntimeError(UserError, RuntimeError):
    """User error raised where callers catch `RuntimeError`."""


__all__ = [
    "UserError",
    "UserFileExistsError",
    "UserFileNotFoundError",
    "UserRuntimeError",
    "UserValueError",
]
