class ResumeError(Exception):
    """An expected, user-actionable failure."""

    code = "resume_error"

    def __init__(self, message: str, *, code: str | None = None):
        super().__init__(message)
        if code:
            self.code = code


class InvalidInput(ResumeError):
    code = "invalid_input"


class UnsupportedTemplate(ResumeError):
    code = "unsupported_template"


class InsufficientEvidence(ResumeError):
    code = "insufficient_evidence"


class ConversionFailure(ResumeError):
    code = "conversion_failure"


class LayoutFailure(ResumeError):
    code = "unresolvable_layout"


class JobCancelled(ResumeError):
    code = "cancelled"

