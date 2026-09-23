from django.urls import path

from . import views

urlpatterns = [
    path("chat/", views.ChatView.as_view(), name="chat"),
    path("upload/", views.UploadView.as_view(), name="upload"),
    path("conversations/", views.ConversationListView.as_view(), name="conversation-list"),
    path("conversations/<uuid:pk>/", views.ConversationDetailView.as_view(), name="conversation-detail"),
]
