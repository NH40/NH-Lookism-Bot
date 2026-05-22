from app.services.admin.base import AdminBaseService
from app.services.admin.resources import AdminResourcesMixin
from app.services.admin.prestige import AdminPrestigeMixin
from app.services.admin.characters import AdminCharactersMixin
from app.services.admin.cities import AdminCitiesMixin
from app.services.admin.backup import AdminBackupMixin


class AdminService(
    AdminBaseService,
    AdminResourcesMixin,
    AdminPrestigeMixin,
    AdminCharactersMixin,
    AdminCitiesMixin,
    AdminBackupMixin,
):
    pass


admin_service = AdminService()

__all__ = ["AdminService", "admin_service"]
