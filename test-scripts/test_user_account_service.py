import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.db.database import UsersDatabase, apply_users_schema
from src.services.user_account_service import UserAccountService


class UserAccountServiceTests(unittest.TestCase):
    def test_account_and_multi_member_lifecycle(self):
        with tempfile.TemporaryDirectory() as temporary:
            db_path = Path(temporary) / "users.sqlite3"
            db = UsersDatabase(db_path)
            service = UserAccountService(db)
            service.profiles_dir = Path(temporary) / "profiles_pic"
            service.profiles_dir.mkdir(parents=True, exist_ok=True)

            # 1. Default account creation
            default_data = service.get_or_create_default_account()
            self.assertIsNotNone(default_data["account"])
            self.assertEqual("Default Trainer", default_data["account"]["display_name"])
            self.assertEqual(1, len(default_data["members"]))
            self.assertEqual("Trainer", default_data["active_member"]["name"])
            user_id = default_data["account"]["id"]

            # 2. Add multiple members to the account
            m1 = service.add_member(user_id, "Ash Ketchum")
            m2 = service.add_member(user_id, "Misty Waterflower")
            self.assertEqual("Ash Ketchum", m1["name"])
            self.assertEqual("Misty Waterflower", m2["name"])

            account_data = service.get_account_by_id(user_id)
            self.assertEqual(3, len(account_data["members"]))

            # 3. Switch active member
            switched = service.set_active_member(user_id, m2["id"])
            self.assertEqual("Misty Waterflower", switched["active_member"]["name"])

            # 4. Update account info
            updated = service.update_account(user_id, display_name="Pallet Town Heroes", email="pallet@pokemon.org")
            self.assertEqual("Pallet Town Heroes", updated["account"]["display_name"])
            self.assertEqual("pallet@pokemon.org", updated["account"]["email"])

            # 5. Remove member
            deleted = service.delete_member(m1["id"])
            self.assertTrue(deleted)
            account_after = service.get_account_by_id(user_id)
            self.assertEqual(2, len(account_after["members"]))

            # 6. Create second account with password
            acc2 = service.create_account("Team Rocket", email="rocket@giovanni.biz", password="secret_rocket_pwd", initial_member_name="Jessie")
            self.assertEqual("Team Rocket", acc2["account"]["display_name"])
            self.assertEqual("Jessie", acc2["active_member"]["name"])
            self.assertTrue(acc2["account"]["has_password"])
            acc2_id = acc2["account"]["id"]

            # 7. Password verification
            self.assertTrue(service.verify_password(acc2_id, "secret_rocket_pwd"))
            self.assertFalse(service.verify_password(acc2_id, "wrong_password"))

            # 8. Password update
            service.update_account(acc2_id, password="new_rocket_pwd")
            self.assertTrue(service.verify_password(acc2_id, "new_rocket_pwd"))
            self.assertFalse(service.verify_password(acc2_id, "secret_rocket_pwd"))

            all_accounts = service.list_all_accounts()
            self.assertEqual(2, len(all_accounts))
            rocket_listed = next(a for a in all_accounts if a["id"] == acc2_id)
            self.assertTrue(rocket_listed["has_password"])
            self.assertNotIn("password_hash", rocket_listed)

            # 9. Delete account
            deleted_acc = service.delete_account(acc2_id)
            self.assertTrue(deleted_acc)
            self.assertIsNone(service.get_account_by_id(acc2_id))
            self.assertEqual(1, len(service.list_all_accounts()))


if __name__ == "__main__":
    unittest.main()
