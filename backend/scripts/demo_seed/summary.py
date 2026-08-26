from dataclasses import dataclass


@dataclass(frozen=True)
class DemoSeedSummary:
    tenant_slug: str
    admin_email: str
    admin_password: str
    employee_email: str | None = None
    employee_password: str | None = None

    def to_message(self) -> str:
        message = (
            "AgentHive demo data seeded.\n"
            f"Tenant slug: {self.tenant_slug}\n"
            f"Admin email: {self.admin_email}\n"
            f"Admin password: {self.admin_password}"
        )
        if self.employee_email and self.employee_password:
            message += (
                "\n"
                f"Employee email: {self.employee_email}\n"
                f"Employee password: {self.employee_password}"
            )
        return message
