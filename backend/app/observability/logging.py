import logging
import re


SENSITIVE = re.compile(r"(?i)(authorization\s*[=:]\s*(?:bearer\s+)?|jwt_secret_key\s*[=:]\s*|api[_-]?key\s*[=:]\s*|content\s*[=:]\s*)([^\s,;]+)")


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        rendered = record.getMessage()
        record.msg = SENSITIVE.sub(lambda match: f"{match.group(1)}[REDACTED]", rendered)
        record.args = ()
        return True


def configure_logging() -> None:
    root = logging.getLogger()
    redactor = RedactingFilter()
    if not any(isinstance(item, RedactingFilter) for item in root.filters): root.addFilter(redactor)
    for handler in root.handlers:
        if not any(isinstance(item, RedactingFilter) for item in handler.filters): handler.addFilter(redactor)
