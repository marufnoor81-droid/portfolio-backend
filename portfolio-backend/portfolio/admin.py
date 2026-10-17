from django.contrib import admin

from .models import Category, Comment, ContactMessage, Education, Experience, Post, PostLike, Profile, Project, Skill, Tag


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "headline", "email", "is_available_for_hire")
    search_fields = ("full_name", "headline", "email")
    list_filter = ("is_available_for_hire",)


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "proficiency", "is_featured", "display_order")
    search_fields = ("name",)
    list_filter = ("category", "is_featured")


@admin.register(Experience)
class ExperienceAdmin(admin.ModelAdmin):
    list_display = ("role", "company", "start_date", "end_date", "is_current")
    search_fields = ("role", "company")
    list_filter = ("employment_type", "is_current")


@admin.register(Education)
class EducationAdmin(admin.ModelAdmin):
    list_display = ("institution", "degree", "field_of_study", "start_year", "end_year")
    search_fields = ("institution", "degree", "field_of_study")
    list_filter = ("start_year", "end_year")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "is_featured", "completed_date", "display_order")
    search_fields = ("title", "summary", "description")
    list_filter = ("category", "is_featured")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "description")


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name",)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "category", "published_at", "views_count", "is_featured")
    search_fields = ("title", "excerpt", "content")
    list_filter = ("status", "category", "is_featured", "tags")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(PostLike)
class PostLikeAdmin(admin.ModelAdmin):
    list_display = ("post", "visitor_id", "created_at")
    search_fields = ("post__title", "visitor_id")
    list_filter = ("created_at",)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("post", "name", "is_approved", "created_at")
    search_fields = ("post__title", "name", "email", "content")
    list_filter = ("is_approved", "created_at")


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "name", "email", "is_read", "created_at")
    search_fields = ("subject", "name", "email", "message")
    list_filter = ("is_read", "created_at")
