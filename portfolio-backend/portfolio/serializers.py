from pathlib import Path

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from .models import (
    Category,
    Comment,
    ContactMessage,
    Education,
    Experience,
    Post,
    Project,
    Profile,
    Skill,
    Tag,
)

MAX_IMAGE_SIZE = 2 * 1024 * 1024
MAX_RESUME_SIZE = 5 * 1024 * 1024
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def validate_upload(file, allowed_extensions, max_size, label):
    if file and hasattr(file, "size"):
        if file.size > max_size:
            raise serializers.ValidationError(f"{label} must be no larger than {max_size // (1024 * 1024)} MB.")
        if Path(file.name).suffix.lower() not in allowed_extensions:
            raise serializers.ValidationError(f"{label} must use one of: {', '.join(sorted(allowed_extensions))}.")
    return file


class AbsoluteFileMixin:
    def get_fields(self):
        fields = super().get_fields()
        for name in ("avatar", "resume", "cover_image"):
            field = fields.get(name)
            if field is not None:
                field.use_url = True
                field.validators.append(
                    lambda value, field_name=name: validate_upload(
                        value,
                        {".pdf"} if field_name == "resume" else IMAGE_EXTENSIONS,
                        MAX_RESUME_SIZE if field_name == "resume" else MAX_IMAGE_SIZE,
                        "Resume" if field_name == "resume" else "Image",
                    )
                )
        return fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if request:
            for name in ("avatar", "resume", "cover_image"):
                value = data.get(name)
                if value and not value.startswith(("http://", "https://")):
                    data[name] = request.build_absolute_uri(value)
        return data


class ProfileSerializer(AbsoluteFileMixin, serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class ExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experience
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        current = attrs.get("is_current", getattr(self.instance, "is_current", False))
        if start and start > timezone.localdate():
            raise serializers.ValidationError({"start_date": "Start date cannot be in the future."})
        if current and end:
            raise serializers.ValidationError({"end_date": "End date must be empty for a current role."})
        if not current and (not end or (start and end <= start)):
            raise serializers.ValidationError({"end_date": "End date must be after start date."})
        return attrs


class EducationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Education
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class ProjectSerializer(AbsoluteFileMixin, serializers.ModelSerializer):
    tech_stack = SkillSerializer(many=True, read_only=True)
    tech_stack_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Skill.objects.all(), source="tech_stack", write_only=True, required=False
    )

    class Meta:
        model = Project
        fields = "__all__"
        read_only_fields = ("id", "slug", "created_at", "updated_at")

    def validate(self, attrs):
        live_url = attrs.get("live_url", getattr(self.instance, "live_url", ""))
        github_url = attrs.get("github_url", getattr(self.instance, "github_url", ""))
        if not live_url and not github_url:
            raise serializers.ValidationError("Provide at least one of live_url or github_url.")
        return attrs


class CategorySerializer(serializers.ModelSerializer):
    posts_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "description", "posts_count", "created_at", "updated_at")
        read_only_fields = ("id", "slug", "created_at", "updated_at")


class TagSerializer(serializers.ModelSerializer):
    posts_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Tag
        fields = ("id", "name", "slug", "posts_count", "created_at", "updated_at")
        read_only_fields = ("id", "slug", "created_at", "updated_at")


class PublicUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ("id", "username", "email")


class PostSerializer(AbsoluteFileMixin, serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source="category", write_only=True, required=False
    )
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Tag.objects.all(), source="tags", write_only=True, required=False
    )
    author = PublicUserSerializer(read_only=True)
    likes_count = serializers.IntegerField(read_only=True, default=0)
    comments_count = serializers.IntegerField(read_only=True, default=0)
    is_liked = serializers.BooleanField(read_only=True, default=False)
    related_posts = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "id", "title", "slug", "excerpt", "content", "cover_image", "category", "category_id",
            "tags", "tag_ids", "author", "status", "published_at", "views_count", "reading_time",
            "is_featured", "likes_count", "comments_count", "is_liked", "related_posts",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "slug", "author", "published_at", "views_count", "reading_time",
            "created_at", "updated_at", "likes_count", "comments_count", "is_liked", "related_posts",
        )

    def validate_title(self, value):
        if len(value.strip()) < 5:
            raise serializers.ValidationError("Title must be at least 5 characters long.")
        return value

    def validate(self, attrs):
        status = attrs.get("status", getattr(self.instance, "status", Post.Status.DRAFT))
        content = attrs.get("content", getattr(self.instance, "content", ""))
        category = attrs.get("category", getattr(self.instance, "category", None))
        if status == Post.Status.PUBLISHED and len(content.strip()) < 100:
            raise serializers.ValidationError({"content": "Published posts must contain at least 100 characters."})
        if status == Post.Status.PUBLISHED and not category:
            raise serializers.ValidationError({"category_id": "Published posts require a category."})
        return attrs

    def get_related_posts(self, post):
        if not post.category_id or post.status != Post.Status.PUBLISHED:
            return []
        related = (
            Post.objects.filter(category_id=post.category_id, status=Post.Status.PUBLISHED)
            .exclude(pk=post.pk)
            .order_by("-published_at")[:3]
        )
        return [
            {"title": item.title, "slug": item.slug, "excerpt": item.excerpt, "reading_time": item.reading_time}
            for item in related
        ]


class CommentSerializer(serializers.ModelSerializer):
    replies = serializers.SerializerMethodField()
    email = serializers.EmailField(write_only=True)
    is_approved = serializers.BooleanField(required=False)

    class Meta:
        model = Comment
        fields = ("id", "post", "name", "email", "website", "content", "parent", "is_approved", "created_at", "replies")
        read_only_fields = ("id", "post", "created_at", "replies")

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        is_owner = bool(request and request.user.is_authenticated and request.user.is_superuser)
        fields["is_approved"].read_only = not is_owner
        return fields

    def validate_name(self, value):
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Name must be at least 2 characters long.")
        return value

    def validate_content(self, value):
        if not 5 <= len(value.strip()) <= 1000:
            raise serializers.ValidationError("Comment must be between 5 and 1000 characters.")
        return value

    def validate_parent(self, parent):
        if parent and parent.parent_id:
            raise serializers.ValidationError("Replies can only be one level deep.")
        post = self.context.get("post")
        if parent and post and parent.post_id != post.pk:
            raise serializers.ValidationError("Reply must belong to the same post.")
        if parent and not parent.is_approved:
            raise serializers.ValidationError("You can only reply to an approved comment.")
        return parent

    def get_replies(self, comment):
        replies = comment.replies.filter(is_approved=True).order_by("created_at")
        return [
            {
                "id": reply.id,
                "name": reply.name,
                "website": reply.website,
                "content": reply.content,
                "created_at": reply.created_at,
            }
            for reply in replies
        ]


class ContactMessageSerializer(serializers.ModelSerializer):
    is_read = serializers.BooleanField(required=False)

    class Meta:
        model = ContactMessage
        fields = ("id", "name", "email", "subject", "message", "is_read", "created_at")
        read_only_fields = ("id", "created_at")

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        is_owner = bool(request and request.user.is_authenticated and request.user.is_superuser)
        fields["is_read"].read_only = not is_owner
        return fields

    def validate_message(self, value):
        if not 10 <= len(value.strip()) <= 2000:
            raise serializers.ValidationError("Message must be between 10 and 2000 characters.")
        return value


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        from django.contrib.auth import authenticate
        from rest_framework.exceptions import AuthenticationFailed
        from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

        user = authenticate(
            request=self.context.get("request"),
            username=attrs["username"],
            password=attrs["password"],
        )
        if not user or not user.is_superuser:
            raise AuthenticationFailed("Invalid username or password.")
        token = TokenObtainPairSerializer.get_token(user)
        return {
            "refresh": str(token),
            "access": str(token.access_token),
            "user": PublicUserSerializer(user).data,
        }
