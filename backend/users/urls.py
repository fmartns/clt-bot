from django.urls import path
from users.views import HabboVerificationView, RefreshVerificationWordView

urlpatterns = [
    path('verify/', HabboVerificationView.as_view(), name='verify'),
    path('verify/refresh-word/', RefreshVerificationWordView.as_view(), name='verify-refresh-word'),
]