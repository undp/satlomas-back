from rest_framework import permissions

class UserProfilePermission(permissions.BasePermission):
    """
    Custom permission for user profiles
    * Allows staff
    * Allow only if from same user
    """
    def has_object_permission(self, request, view, obj):
        return request.user.is_staff or obj.user == request.user
