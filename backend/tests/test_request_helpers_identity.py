from tests.request_helpers import admin_request, registered_compat_admin
from services.resource_access import require_principal, is_admin


def test_direct_request_uses_real_registry_and_observes_role_revocation(registered_compat_admin):
    request = admin_request()
    assert is_admin(require_principal(request))
    user = registered_compat_admin.get_user('compat-admin')
    user.roles = ['viewer']
    registered_compat_admin._save_user(user)
    assert not is_admin(require_principal(request))
