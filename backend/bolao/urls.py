from django.urls import path
from bolao.views import (
    BolaoBetView,
    BolaoCloseView,
    BolaoCurrentView,
    BolaoMessageView,
    BolaoStartView,
)

urlpatterns = [
    path('current/', BolaoCurrentView.as_view(), name='bolao-current'),
    path('start/', BolaoStartView.as_view(), name='bolao-start'),
    path('<int:pk>/message/', BolaoMessageView.as_view(), name='bolao-message'),
    path('<int:pk>/bets/', BolaoBetView.as_view(), name='bolao-bets'),
    path('<int:pk>/close/', BolaoCloseView.as_view(), name='bolao-close'),
]
