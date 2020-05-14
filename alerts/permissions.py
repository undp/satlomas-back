from rest_framework import permissions

class UserProfilePermission(permissions.BasePermission):
    """
    Custom permission for user profiles
    * Allow only if from same user
    """
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user

class UserPermission(permissions.BasePermission):
    """
    Custom permission for users

    * Allow only if same user

    """
    def has_object_permission(self, request, view, obj):
        return obj == request.user