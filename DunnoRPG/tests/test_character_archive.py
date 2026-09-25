from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from DunnoRPG import models


class CharacterArchiveTest(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="owner", password="test")
        self.other_user = get_user_model().objects.create_user(username="other", password="test")
        self.admin = get_user_model().objects.create_superuser(
            username="admin",
            password="test",
            email="admin@example.com",
        )
        self.character = models.Character.objects.create(
            owner=self.owner.username,
            name="Active character",
            type="Player",
            race="Human",
            size="M",
            HP=10,
            fullHP=10,
            INT=1,
            SIŁ=1,
            ZRE=1,
            CHAR=1,
            CEL=1,
        )

    def test_owner_can_archive_character(self):
        self.client.force_login(self.owner)

        response = self.client.post(reverse("archive_character", args=[self.character.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Zarchiwizowano Active character")
        self.character.refresh_from_db()
        self.assertTrue(self.character.hidden)

    def test_other_user_cannot_archive_character(self):
        self.client.force_login(self.other_user)

        response = self.client.post(reverse("archive_character", args=[self.character.id]))

        self.assertEqual(response.status_code, 404)
        self.character.refresh_from_db()
        self.assertFalse(self.character.hidden)

    def test_archived_character_is_hidden_from_admin_home(self):
        self.character.hidden = True
        self.character.save(update_fields=["hidden"])
        self.client.force_login(self.admin)

        response = self.client.get(reverse("home"))

        self.assertNotContains(response, self.character.name)
