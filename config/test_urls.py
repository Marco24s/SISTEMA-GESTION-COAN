from django.http import HttpResponse
from django.urls import include, path


urlpatterns = [
    path('portal/', lambda request: HttpResponse("portal"), name='portal'),
    path('verify-pin/', lambda request: HttpResponse("verify-pin"), name='verify_pin'),
    path('create-pin/', lambda request: HttpResponse("create-pin"), name='create_pin'),
    path('', include(('budget.urls', 'budget'), namespace='budget')),
]
