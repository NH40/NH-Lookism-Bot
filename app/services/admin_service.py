# backward compat shim — logic lives in app/services/admin/
from app.services.admin import admin_service, AdminService  # noqa: F401
