import logging

from django.core.mail import mail_admins
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Comment

logger = logging.getLogger("portfolio.comments")


@receiver(post_save, sender=Comment)
def notify_pending_comment(sender, instance, created, **kwargs):
    if created:
        logger.info("New comment awaiting approval for post '%s'.", instance.post.title)
        mail_admins(
            "New comment awaiting approval",
            f"A new comment on '{instance.post.title}' is awaiting approval.",
            fail_silently=False,
        )
