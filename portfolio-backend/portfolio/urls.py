from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CategoryViewSet,
    ChangePasswordView,
    CommentModerationViewSet,
    ContactMessageViewSet,
    DashboardStatsView,
    EducationViewSet,
    ExperienceViewSet,
    LoginView,
    LogoutView,
    MeView,
    PostViewSet,
    ProfileView,
    ProjectViewSet,
    RefreshView,
    SkillViewSet,
    TagViewSet,
)

router = DefaultRouter()
router.register("skills", SkillViewSet)
router.register("experiences", ExperienceViewSet)
router.register("education", EducationViewSet)
router.register("projects", ProjectViewSet, basename="project")
router.register("posts", PostViewSet, basename="post")
router.register("categories", CategoryViewSet)
router.register("tags", TagViewSet)
router.register("comments", CommentModerationViewSet, basename="comment")
router.register("contact", ContactMessageViewSet, basename="contact")

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", RefreshView.as_view(), name="refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("dashboard/stats/", DashboardStatsView.as_view(), name="dashboard-stats"),
    path("", include(router.urls)),
]
