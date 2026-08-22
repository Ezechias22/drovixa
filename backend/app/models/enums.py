from enum import StrEnum


class UserStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BANNED = "banned"
    DELETED = "deleted"


class ContentType(StrEnum):
    SERIES = "series"
    MOVIE = "movie"


class ContentStatus(StrEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ContentVisibility(StrEnum):
    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"
    SCHEDULED = "scheduled"


class SeriesStatus(StrEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    PAUSED = "paused"
    ARCHIVED = "archived"


class Orientation(StrEnum):
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"
    MIXED = "mixed"


class EpisodeAccessType(StrEnum):
    FREE = "free"
    PREMIUM_SUBSCRIPTION = "premium_subscription"
    COIN_UNLOCK = "coin_unlock"
    PREMIUM_OR_COIN = "premium_or_coin"
    AD_UNLOCK = "ad_unlock"
    SCHEDULED_FREE = "scheduled_free"


class VideoStatus(StrEnum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class UploadProtocol(StrEnum):
    BASIC = "basic"
    TUS = "tus"
    RESUMABLE = "resumable"


class WebhookProcessingStatus(StrEnum):
    RECEIVED = "received"
    PROCESSED = "processed"
    IGNORED = "ignored"
    FAILED = "failed"


class SubtitleFormat(StrEnum):
    VTT = "vtt"
    SRT = "srt"


class AgeRating(StrEnum):
    ALL = "all"
    SEVEN_PLUS = "7+"
    THIRTEEN_PLUS = "13+"
    SIXTEEN_PLUS = "16+"
    EIGHTEEN_PLUS = "18+"


class WalletTransactionType(StrEnum):
    PURCHASE = "purchase"
    BONUS = "bonus"
    EPISODE_UNLOCK = "episode_unlock"
    REFUND = "refund"
    PROMOTION = "promotion"
    DAILY_REWARD = "daily_reward"
    REFERRAL = "referral"
    ADMIN_ADJUSTMENT = "admin_adjustment"
    EXPIRATION = "expiration"


class LedgerStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    REVERSED = "reversed"
    FAILED = "failed"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class PaymentProductType(StrEnum):
    COINS = "coins"
    SUBSCRIPTION = "subscription"


class PaymentPlatform(StrEnum):
    WEB = "web"
    ANDROID = "android"
    IOS = "ios"


class SubscriptionInterval(StrEnum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class SubscriptionStatus(StrEnum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REFUNDED = "refunded"


class RefundStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class LikeTargetType(StrEnum):
    CONTENT = "content"
    EPISODE = "episode"
    SHORT = "short"


class CommentTargetType(StrEnum):
    CONTENT = "content"
    EPISODE = "episode"
    SHORT = "short"


class CommentStatus(StrEnum):
    VISIBLE = "visible"
    HIDDEN = "hidden"
    DELETED = "deleted"
    UNDER_REVIEW = "under_review"
    SPAM = "spam"


class ReportTargetType(StrEnum):
    COMMENT = "comment"
    USER = "user"
    CONTENT = "content"
    EPISODE = "episode"
    VIDEO = "video"
    SUBTITLE = "subtitle"
    TECHNICAL = "technical"


class ReportStatus(StrEnum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
