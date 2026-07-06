from .models import Notification

def unread_notifications(request):
    if request.user.is_authenticated:
        # Get unread notifications
        notifications = Notification.objects.filter(user=request.user, is_read=False).order_by('-created_at')
        count = notifications.count()
        return {
            'unread_notifications_count': count,
            'recent_notifications': notifications[:5]  # Limit to 5 for dropdown
        }
    return {
        'unread_notifications_count': 0,
        'recent_notifications': []
    }
