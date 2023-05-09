from django import forms

class VideoDownloadForm(forms.Form):
    url = forms.URLField()
