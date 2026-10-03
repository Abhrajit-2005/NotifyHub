import enum

class NotificationType(str, enum.Enum):
    ORDER_CONFIRMED = "ORDER_CONFIRMED"
    PASSWORD_RESET = "PASSWORD_RESET"
    WELCOME = "WELCOME"
    SECURITY_ALERT = "SECURITY_ALERT"
    GENERAL = "GENERAL"

class NotificationChannel(str, enum.Enum):
    EMAIL = "EMAIL"
    IN_APP = "IN_APP"

class NotificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    FAILED = "FAILED"
