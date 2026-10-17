import hashlib
from datetime import date

from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, F, Q, Sum
from django.db.models.deletion import ProtectedError
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django_filters import rest_framework as django_filters
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Category, Comment, ContactMessage, Education, Experience, Post, PostLike, Project, Profile, Skill, Tag
from .pagination import StandardPagination
from .permissions import IsOwner, IsOwnerOrReadOnly
from .serializers import (
    CategorySerializer,
    CommentSerializer,
    ContactMessageSerializer,
    EducationSerializer,
    ExperienceSerializer,
    LoginSerializer,
    PostSerializer,
    ProjectSerializer,
    ProfileSerializer,
    PublicUserSerializer,
    SkillSerializer,
    TagSerializer,
)


class ProjectFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(field_name="category")
    is_featured = django_filters.BooleanFilter()
    tech = django_filters.CharFilter(method="filter_tech")

    class Meta:
        model = Project
        fields = ()

    def filter_tech(self, queryset, name, value):
        if value.isdecimal():
            return queryset.filter(tech_stack__id=int(value)).distinct()
        return queryset.filter(tech_stack__name__iexact=value).distinct()


class PostFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(field_name="category__slug")
    tag = django_filters.CharFilter(field_name="tags__slug")
    is_featured = django_filters.BooleanFilter()

    class Meta:
        model = Post
        fields = ()


class CommentFilter(django_filters.FilterSet):
    is_approved = django_filters.BooleanFilter()
    post = django_filters.CharFilter(field_name="post__slug")

    class Meta:
        model = Comment
        fields = ()


class LoginView(GenericAPIView):
    permission_classes = (AllowAny,)
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


class RefreshView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = TokenRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


class LogoutView(APIView):
    permission_classes = (IsOwner,)

    def post(self, request):
        token = request.data.get("refresh")
        if not token:
            raise ValidationError({"refresh": "This field is required."})
        try:
            RefreshToken(token).blacklist()
        except TokenError as exc:
            raise ValidationError({"refresh": "Refresh token is invalid."}) from exc
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = (IsOwner,)

    def get(self, request):
        return Response(PublicUserSerializer(request.user).data)


class ChangePasswordView(APIView):
    permission_classes = (IsOwner,)

    def post(self, request):
        old_password = request.data.get("old_password", "")
        new_password = request.data.get("new_password", "")
        if not request.user.check_password(old_password):
            raise ValidationError({"old_password": "Current password is incorrect."})
        if len(new_password) < 8:
            raise ValidationError({"new_password": "Password must be at least 8 characters long."})
        from django.contrib.auth.password_validation import validate_password

        try:
            validate_password(new_password, request.user)
        except DjangoValidationError as exc:
            raise ValidationError({"new_password": list(exc.messages)}) from exc
        request.user.set_password(new_password)
        request.user.save(update_fields=["password"])
        return Response({"detail": "Password updated successfully."})


class ProfileView(APIView):
    permission_classes = (IsOwnerOrReadOnly,)
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_object(self):
        profile, _ = Profile.objects.get_or_create(pk=1)
        return profile

    def get(self, request):
        return Response(ProfileSerializer(self.get_object(), context={"request": request}).data)

    def patch(self, request):
        serializer = ProfileSerializer(
            self.get_object(), data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class SkillViewSet(viewsets.ModelViewSet):
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
    filterset_fields = ("category", "is_featured")
    search_fields = ("name",)
    ordering_fields = ("display_order", "proficiency", "name")
    ordering = ("display_order", "-proficiency", "name")


class ExperienceViewSet(viewsets.ModelViewSet):
    queryset = Experience.objects.all()
    serializer_class = ExperienceSerializer
    filterset_fields = ("employment_type", "is_current")
    ordering_fields = ("start_date", "display_order")


class EducationViewSet(viewsets.ModelViewSet):
    queryset = Education.objects.all()
    serializer_class = EducationSerializer
    ordering_fields = ("start_year", "institution")


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.prefetch_related("tech_stack").all()
    serializer_class = ProjectSerializer
    lookup_field = "slug"
    pagination_class = type("ProjectPagination", (StandardPagination,), {"page_size": 9})
    filterset_class = ProjectFilter
    search_fields = ("title", "summary", "description")
    ordering_fields = ("completed_date", "display_order", "title")
    ordering = ("display_order", "-completed_date")

    def get_queryset(self):
        return super().get_queryset()


class PostViewSet(viewsets.ModelViewSet):
    serializer_class = PostSerializer
    lookup_field = "slug"
    pagination_class = type("PostPagination", (StandardPagination,), {"page_size": 6})
    filterset_class = PostFilter
    search_fields = ("title", "excerpt", "content")
    ordering_fields = ("published_at", "views_count", "likes_count", "title")
    ordering = ("-published_at",)

    def get_throttles(self):
        if self.action == "like":
            self.throttle_scope = "likes"
        elif self.action == "comments" and self.request.method == "POST":
            self.throttle_scope = "comment_create"
        return super().get_throttles()

    def get_queryset(self):
        queryset = (
            Post.objects.select_related("category", "author")
            .prefetch_related("tags")
            .annotate(
                likes_count=Count("likes", distinct=True),
                comments_count=Count("comments", filter=Q(comments__is_approved=True), distinct=True),
            )
        )
        if not (self.request.user.is_authenticated and self.request.user.is_superuser):
            queryset = queryset.filter(status=Post.Status.PUBLISHED)
        elif self.request.query_params.get("status") == "DRAFT":
            queryset = queryset.filter(status=Post.Status.DRAFT)
        elif self.request.query_params.get("status") == "PUBLISHED":
            queryset = queryset.filter(status=Post.Status.PUBLISHED)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        visitor_id = self.request.headers.get("X-Visitor-Id", "")
        if visitor_id:
            context["visitor_id"] = visitor_id
        return context

    def get_serializer(self, *args, **kwargs):
        serializer = super().get_serializer(*args, **kwargs)
        return serializer

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        visitor_id = request.headers.get("X-Visitor-Id", "")
        results = response.data.get("results", []) if isinstance(response.data, dict) else response.data
        if visitor_id:
            liked_slugs = set(
                PostLike.objects.filter(visitor_id=visitor_id, post__slug__in=[row["slug"] for row in results])
                .values_list("post__slug", flat=True)
            )
            for item in results:
                item["is_liked"] = item["slug"] in liked_slugs
        return response

    def retrieve(self, request, *args, **kwargs):
        post = self.get_object()
        visitor_id = request.headers.get("X-Visitor-Id", "")
        if visitor_id:
            visitor_hash = hashlib.sha256(visitor_id.encode("utf-8")).hexdigest()
            cache_key = f"post-view:{post.pk}:{visitor_hash}"
            if cache.add(cache_key, True, timeout=24 * 60 * 60):
                Post.objects.filter(pk=post.pk).update(views_count=F("views_count") + 1)
                post.refresh_from_db(fields=("views_count",))
        serializer = self.get_serializer(post)
        data = serializer.data
        data["is_liked"] = bool(visitor_id and PostLike.objects.filter(post=post, visitor_id=visitor_id).exists())
        return Response(data)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True, methods=("post",), permission_classes=(AllowAny,))
    def like(self, request, slug=None):
        visitor_id = request.headers.get("X-Visitor-Id", "").strip()
        if not visitor_id:
            return Response({"detail": "X-Visitor-Id header is required."}, status=status.HTTP_400_BAD_REQUEST)
        post = self.get_object()
        like, created = PostLike.objects.get_or_create(
            post=post,
            visitor_id=visitor_id,
            defaults={"ip_address": self.get_client_ip(request)},
        )
        if created:
            liked = True
        else:
            like.delete()
            liked = False
        return Response({"liked": liked, "likes_count": post.likes.count()})

    @action(detail=True, methods=("get", "post"), permission_classes=(AllowAny,), url_path="comments")
    def comments(self, request, slug=None):
        post = self.get_object()
        if request.method == "GET":
            comments = Comment.objects.filter(post=post, parent__isnull=True, is_approved=True).prefetch_related("replies")
            paginator = StandardPagination()
            page = paginator.paginate_queryset(comments, request, view=self)
            serializer = CommentSerializer(page, many=True, context={"post": post, "request": request})
            return paginator.get_paginated_response(serializer.data)
        serializer = CommentSerializer(data=request.data, context={"post": post, "request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(post=post)
        return Response(
            {"message": "Your comment is awaiting approval."},
            status=status.HTTP_201_CREATED,
        )

    @staticmethod
    def get_client_ip(request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")


class TaxonomyViewSet(viewsets.ModelViewSet):
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ("name",)
    ordering_fields = ("name", "created_at")

    def get_queryset(self):
        return self.queryset.annotate(
            posts_count=Count("posts", filter=Q(posts__status=Post.Status.PUBLISHED), distinct=True)
        )


class CategoryViewSet(TaxonomyViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError as exc:
            raise ValidationError({"detail": "This category is in use by a post and cannot be deleted."}) from exc


class TagViewSet(TaxonomyViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer


class CommentModerationViewSet(viewsets.ModelViewSet):
    permission_classes = (IsOwner,)
    serializer_class = CommentSerializer
    http_method_names = ("get", "patch", "delete", "head", "options")
    filterset_class = CommentFilter
    ordering_fields = ("created_at", "is_approved")
    ordering = ("is_approved", "-created_at")

    def get_queryset(self):
        return Comment.objects.select_related("post").prefetch_related("replies").all()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["post"] = getattr(self, "post", None)
        return context


class ContactMessageViewSet(viewsets.ModelViewSet):
    serializer_class = ContactMessageSerializer
    pagination_class = StandardPagination
    permission_classes = (AllowAny,)
    http_method_names = ("get", "post", "patch", "delete", "head", "options")
    filterset_fields = ("is_read",)
    ordering_fields = ("created_at", "is_read")
    ordering = ("-created_at",)

    def get_queryset(self):
        if not (self.request.user.is_authenticated and self.request.user.is_superuser):
            return ContactMessage.objects.none()
        return ContactMessage.objects.all()

    def get_permissions(self):
        if self.action == "create":
            return [AllowAny()]
        return [IsOwner()]

    def get_throttles(self):
        if self.action == "create":
            self.throttle_scope = "contact_create"
            return [AnonRateThrottle(), ScopedRateThrottle()]
        return super().get_throttles()


class DashboardStatsView(APIView):
    permission_classes = (IsOwner,)

    def get(self, request):
        posts = Post.objects.all()
        now = timezone.localdate()
        months = []
        current_month_index = now.year * 12 + now.month - 1
        for offset in range(5, -1, -1):
            year, month_index = divmod(current_month_index - offset, 12)
            months.append(date(year, month_index + 1, 1))
        first_month = months[0]
        monthly_data = {
            row["month"].strftime("%Y-%m"): row["count"]
            for row in posts.filter(status=Post.Status.PUBLISHED, published_at__date__gte=first_month)
            .annotate(month=TruncMonth("published_at"))
            .values("month")
            .annotate(count=Count("id"))
        }
        top_posts = posts.annotate(likes_count=Count("likes", distinct=True)).order_by("-views_count")[:5]
        recent_comments = Comment.objects.select_related("post").order_by("-created_at")[:5]
        return Response(
            {
                "total_posts": posts.count(),
                "published_posts": posts.filter(status=Post.Status.PUBLISHED).count(),
                "draft_posts": posts.filter(status=Post.Status.DRAFT).count(),
                "total_projects": Project.objects.count(),
                "total_skills": Skill.objects.count(),
                "total_comments": Comment.objects.count(),
                "pending_comments": Comment.objects.filter(is_approved=False).count(),
                "total_likes": PostLike.objects.count(),
                "total_views": posts.aggregate(total=Sum("views_count"))["total"] or 0,
                "unread_messages": ContactMessage.objects.filter(is_read=False).count(),
                "top_posts": [
                    {"title": post.title, "slug": post.slug, "views": post.views_count, "likes": post.likes_count}
                    for post in top_posts
                ],
                "recent_comments": [
                    {"id": comment.id, "name": comment.name, "post": comment.post.title,
                     "content": comment.content, "created_at": comment.created_at,
                     "is_approved": comment.is_approved}
                    for comment in recent_comments
                ],
                "posts_per_month": [
                    {"month": month.strftime("%Y-%m"), "count": monthly_data.get(month.strftime("%Y-%m"), 0)}
                    for month in months
                ],
            }
        )
