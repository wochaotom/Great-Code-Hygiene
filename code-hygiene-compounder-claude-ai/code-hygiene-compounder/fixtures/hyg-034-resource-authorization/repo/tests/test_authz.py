import unittest

from app.authz import can_update


class ResourceAuthorizationTests(unittest.TestCase):
    def test_same_tenant_owner_allowed(self):
        actor = {"id": "user-1", "tenant_id": "tenant-a", "role": "member"}
        resource = {"id": "doc-1", "tenant_id": "tenant-a", "owner_id": "user-1"}

        self.assertTrue(can_update(actor, resource))

    def test_same_tenant_admin_allowed(self):
        actor = {"id": "admin-1", "tenant_id": "tenant-a", "role": "admin"}
        resource = {"id": "doc-1", "tenant_id": "tenant-a", "owner_id": "user-1"}

        self.assertTrue(can_update(actor, resource))

    def test_cross_tenant_owner_rejected(self):
        actor = {"id": "user-1", "tenant_id": "tenant-b", "role": "member"}
        resource = {"id": "doc-1", "tenant_id": "tenant-a", "owner_id": "user-1"}

        self.assertFalse(can_update(actor, resource))

    def test_cross_tenant_admin_rejected(self):
        actor = {"id": "admin-1", "tenant_id": "tenant-b", "role": "admin"}
        resource = {"id": "doc-1", "tenant_id": "tenant-a", "owner_id": "user-1"}

        self.assertFalse(can_update(actor, resource))

    def test_missing_tenant_context_fails_closed(self):
        complete_resource = {"id": "doc-1", "tenant_id": "tenant-a", "owner_id": "user-1"}
        complete_actor = {"id": "user-1", "tenant_id": "tenant-a", "role": "member"}

        cases = [
            ({"id": "admin-1", "role": "admin"}, complete_resource),
            (complete_actor, {"id": "doc-1", "owner_id": "user-1"}),
        ]

        for actor, resource in cases:
            with self.subTest(actor=actor, resource=resource):
                self.assertFalse(can_update(actor, resource))


if __name__ == "__main__":
    unittest.main()
