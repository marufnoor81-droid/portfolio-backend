from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Category, Comment, ContactMessage, Post, Profile


class PublicPortfolioApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = get_user_model().objects.create_superuser(
            username="owner", email="owner@example.test", password="test-password-123"
        )
        self.category = Category.objects.create(name="Engineering")
        self.published = Post.objects.create(
            title="A published story",
            category=self.category,
            author=self.owner,
            status=Post.Status.PUBLISHED,
            content="A" * 120,
        )
        self.draft = Post.objects.create(
            title="A private draft",
            category=self.category,
            author=self.owner,
            content="A" * 120,
        )

    def test_public_posts_never_include_drafts(self):
        response = self.client.get("/api/posts/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["slug"] for row in response.data["results"]], [self.published.slug])
        self.assertEqual(self.client.get(f"/api/posts/{self.draft.slug}/").status_code, 404)

    def test_registration_endpoint_does_not_exist(self):
        self.assertEqual(self.client.post("/api/auth/register/", {}, format="json").status_code, 404)

    def test_invalid_owner_credentials_do_not_disclose_username(self):
        response = self.client.post(
            "/api/auth/login/", {"username": "missing-user", "password": "wrong"}, format="json"
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["detail"], "Invalid username or password.")

    def test_anonymous_cannot_create_owner_content(self):
        self.assertEqual(self.client.post("/api/skills/", {"name": "Django"}, format="json").status_code, 401)

    def test_post_view_count_is_once_per_visitor_per_cooldown(self):
        headers = {"HTTP_X_VISITOR_ID": "visitor-a"}
        for _ in range(2):
            self.assertEqual(
                self.client.get(f"/api/posts/{self.published.slug}/", **headers).status_code, 200
            )
        self.published.refresh_from_db()
        self.assertEqual(self.published.views_count, 1)

    def test_like_requires_visitor_id_and_toggles(self):
        url = f"/api/posts/{self.published.slug}/like/"
        self.assertEqual(self.client.post(url).status_code, 400)
        headers = {"HTTP_X_VISITOR_ID": "visitor-like"}
        first = self.client.post(url, **headers)
        second = self.client.post(url, **headers)
        self.assertEqual(first.data, {"liked": True, "likes_count": 1})
        self.assertEqual(second.data, {"liked": False, "likes_count": 0})

    def test_unapproved_comments_are_not_public_and_email_is_never_returned(self):
        comment = Comment.objects.create(
            post=self.published, name="Reader", email="reader@example.test", content="An unpublished note"
        )
        response = self.client.get(f"/api/posts/{self.published.slug}/comments/")
        self.assertEqual(response.data["results"], [])
        comment.is_approved = True
        comment.save()
        response = self.client.get(f"/api/posts/{self.published.slug}/comments/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("email", response.data["results"][0])

    def test_owner_can_approve_comments_but_visitors_cannot(self):
        comment = Comment.objects.create(
            post=self.published, name="Reader", email="reader@example.test", content="A thoughtful note"
        )
        self.client.force_authenticate(self.owner)
        response = self.client.patch(
            f"/api/comments/{comment.pk}/", {"is_approved": True}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_approved"])

    def test_public_contact_form_and_owner_inbox(self):
        response = self.client.post(
            "/api/contact/",
            {
                "name": "Reader",
                "email": "reader@example.test",
                "subject": "A note",
                "message": "A sufficiently long contact message.",
                "is_read": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(ContactMessage.objects.get().is_read)
        self.client.force_authenticate(self.owner)
        message_id = response.data["id"]
        response = self.client.patch(
            f"/api/contact/{message_id}/", {"is_read": True}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_read"])

    def test_profile_is_a_single_object_and_can_be_updated(self):
        self.client.force_authenticate(self.owner)
        response = self.client.patch("/api/profile/", {"headline": "Portfolio owner"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["headline"], "Portfolio owner")
        self.assertEqual(Profile.objects.count(), 1)


class PermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = get_user_model().objects.create_superuser(
            username="owner", email="owner@example.test", password="test-password-123"
        )
        self.regular = get_user_model().objects.create_user(
            username="reader", email="reader@example.test", password="test-password-123"
        )

    def test_authenticated_non_superuser_cannot_write(self):
        self.client.force_authenticate(self.regular)
        response = self.client.post("/api/skills/", {"name": "Django"}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_superuser_can_write(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            "/api/skills/", {"name": "Django", "category": "BACKEND", "proficiency": 85}, format="json"
        )
        self.assertEqual(response.status_code, 201)

    def test_superuser_can_load_dashboard_stats(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get("/api/dashboard/stats/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_posts"], 0)
        self.assertEqual(response.data["top_posts"], [])
