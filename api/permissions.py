from rest_framework import permissions

class IsOwner(permissions.BasePermission):
    message = "Vous n'avez pas la permission d'accéder à cet objet."
    
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user
    
    
