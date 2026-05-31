
from django.urls import path
from .views import AnalyseByLocationView, AnalyseByCoordinatesView, ResultHistoryView, HomeView

urlpatterns = [
    path('',                      HomeView.as_view(),                       name='home'),
    path('api/analyse/location/', AnalyseByLocationView.as_view(),          name='analyse-location'),
    path('api/analyse/coordinates/', AnalyseByCoordinatesView.as_view(),    name='analyse-coordinates'),
    path('api/results/',          ResultHistoryView.as_view(),              name='results-history'),
]