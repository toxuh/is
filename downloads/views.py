import tempfile

from django import forms
from django.shortcuts import render
from pytube import YouTube
from moviepy.editor import VideoFileClip, AudioFileClip

from .forms import VideoDownloadForm

def get_video_resolutions(url):
    youtube = YouTube(url)
    video_streams = youtube.streams.filter(only_video=True, file_extension='mp4').order_by('resolution').desc()

    resolutions = set()
    for stream in video_streams:
        if stream.resolution:
            resolutions.add(int(stream.resolution.replace('p', '')))

    return sorted(list(resolutions), reverse=True)

def download_video(request):
    title, thumbnail_url, resolutions = None, None, None
    form = VideoDownloadForm(request.POST or None)

    if form.is_valid():
        url = form.cleaned_data['url']
        yt = YouTube(url)
        title = yt.title
        thumbnail_url = yt.thumbnail_url
        resolutions = get_video_resolutions(url)
        resolution_field = forms.ChoiceField(choices=[(f'{r}p', f'{r}p') for r in resolutions])
        form.fields['resolution'] = resolution_field

        if 'resolution' in request.POST:
            chosen_resolution = form['resolution'].value()
            video_stream = yt.streams.filter(only_video=True, resolution=chosen_resolution,
                                             file_extension='mp4').first()
            audio_stream = yt.streams.filter(only_audio=True).first()

            with tempfile.TemporaryDirectory() as tmpdirname:
                video_filename = video_stream.download(output_path=tmpdirname)
                audio_filename = audio_stream.download(output_path=tmpdirname)

                video_clip = VideoFileClip(video_filename)
                audio_clip = AudioFileClip(audio_filename)
                final_clip = video_clip.set_audio(audio_clip)
                final_clip.write_videofile('final_output.mp4', codec='libx264', threads=4)

    return render(request, 'download_video.html', {'form': form, 'title': title, 'thumbnail_url': thumbnail_url, 'resolutions': resolutions})
