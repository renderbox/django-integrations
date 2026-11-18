from dataclasses import dataclass

# The one capability this package actually implements. plans/000-v2.md names
# "webhooks" and "oauth" as potential future capabilities - deliberately
# not built, per its own "do not build speculative capability
# implementations until required."
TEST_CONNECTION = "test_connection"


@dataclass(frozen=True)
class ConnectionTestResult:
    success: bool
    message: str = ""
