import re

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Profile(TimestampedModel):
    full_name = models.CharField(max_length=160, blank=True)
    headline = models.CharField(max_length=200, blank=True)
    bio = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    location = models.CharField(max_length=160, blank=True)
    avatar = models.ImageField(upload_to="profile/", blank=True)
    resume = models.FileField(upload_to="profile/resume/", blank=True)
    github_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    x_url = models.URLField(blank=True)
    website_url = models.URLField(blank=True)
    years_of_experience = models.PositiveSmallIntegerField(default=0)
    is_available_for_hire = models.BooleanField(default=False)

    class Meta:
        verbose_name = "profile"
        verbose_name_plural = "profile"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name or "Portfolio profile"


class Skill(TimestampedModel):
    class Category(models.TextChoices):
        FRONTEND = "FRONTEND", "Frontend"
        BACKEND = "BACKEND", "Backend"
        DATABASE = "DATABASE", "Database"
        DEVOPS = "DEVOPS", "DevOps"
        TOOLS = "TOOLS", "Tools"
        SOFT_SKILL = "SOFT_SKILL", "Soft skill"

    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    proficiency = models.PositiveSmallIntegerField(
        default=50, validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    icon = models.CharField(max_length=100, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_featured = models.BooleanField(default=False)

    class Meta:
        ordering = ("display_order", "name")

    def __str__(self):
        return self.name


class Experience(TimestampedModel):
    class EmploymentType(models.TextChoices):
        FULL_TIME = "FULL_TIME", "Full time"
        PART_TIME = "PART_TIME", "Part time"
        INTERNSHIP = "INTERNSHIP", "Internship"
        FREELANCE = "FREELANCE", "Freelance"
        CONTRACT = "CONTRACT", "Contract"

    company = models.CharField(max_length=160)
    role = models.CharField(max_length=160)
    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices)
    location = models.CharField(max_length=160, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    company_url = models.URLField(blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("-start_date", "display_order")

    def __str__(self):
        return f"{self.role} at {self.company}"


class Education(TimestampedModel):
    institution = models.CharField(max_length=180)
    degree = models.CharField(max_length=160)
    field_of_study = models.CharField(max_length=160, blank=True)
    start_year = models.PositiveSmallIntegerField()
    end_year = models.PositiveSmallIntegerField(null=True, blank=True)
    grade = models.CharField(max_length=60, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ("-start_year", "institution")

    def __str__(self):
        return f"{self.degree} — {self.institution}"


class Project(TimestampedModel):
    class Category(models.TextChoices):
        WEB = "WEB", "Web"
        MOBILE = "MOBILE", "Mobile"
        API = "API", "API"
        ML = "ML", "Machine learning"
        OTHER = "OTHER", "Other"

    title = models.CharField(max_length=180, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    summary = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to="projects/", blank=True)
    tech_stack = models.ManyToManyField(Skill, blank=True, related_name="projects")
    category = models.CharField(max_length=12, choices=Category.choices, default=Category.OTHER)
    live_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    is_featured = models.BooleanField(default=False)
    completed_date = models.DateField(null=True, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("display_order", "-completed_date", "title")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(type(self), self.title, self.pk)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Category(TimestampedModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(type(self), self.name, self.pk)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Tag(TimestampedModel):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(type(self), self.name, self.pk)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Post(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"

    title = models.CharField(max_length=220)
    slug = models.SlugField(max_length=240, unique=True, blank=True)
    excerpt = models.CharField(max_length=300, blank=True)
    content = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to="posts/", blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="posts", null=True, blank=True
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="portfolio_posts"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    views_count = models.PositiveIntegerField(default=0)
    reading_time = models.PositiveSmallIntegerField(default=1)
    is_featured = models.BooleanField(default=False)

    class Meta:
        ordering = ("-published_at", "-created_at")

    def save(self, *args, **kwargs):
        previous_status = None
        if self.pk:
            previous_status = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
        if not self.slug:
            self.slug = unique_slug(type(self), self.title, self.pk)
        if previous_status != self.Status.PUBLISHED and self.status == self.Status.PUBLISHED:
            from django.utils import timezone

            self.published_at = self.published_at or timezone.now()
        self.reading_time = max(1, (len(re.findall(r"\w+", self.content)) + 199) // 200)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class PostLike(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    visitor_id = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("post", "visitor_id"), name="unique_post_visitor_like")
        ]


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    name = models.CharField(max_length=120)
    email = models.EmailField()
    website = models.URLField(blank=True)
    content = models.TextField()
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Comment by {self.name} on {self.post}"


class ContactMessage(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    subject = models.CharField(max_length=180)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.subject} — {self.name}"


def unique_slug(model, value, instance_pk=None):
    base = slugify(value)[:220] or "item"
    slug = base
    suffix = 2
    query = model.objects.all()
    if instance_pk:
        query = query.exclude(pk=instance_pk)
    while query.filter(slug=slug).exists():
        slug = f"{base[:210]}-{suffix}"
        suffix += 1
    return slug
