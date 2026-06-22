from django.urls import include, path


urlpatterns = [
    path('', include(('budget.urls', 'budget'), namespace='budget')),
]
