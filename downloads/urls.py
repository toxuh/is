# In your app's urls.py file
from django.urls import path
from .views import download_video

urlpatterns = [
    path('', download_video, name='download_video'),
]
