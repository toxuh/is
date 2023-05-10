import tempfile
import os
import hashlib
import random
import ffmpeg

from django import forms
from django.shortcuts import render
from django.http import FileResponse
from pytube import YouTube

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

                video_input = ffmpeg.input(video_filename)
                audio_input = ffmpeg.input(audio_filename)

                short_hash = hashlib.sha1(str(random.random()).encode('utf-8')).hexdigest()[:5]

                output_filename = f'ISAVER.CLICK_{title[:10]}_{short_hash}.mp4'

                output_path = os.path.join('/videos', output_filename)

                ffmpeg.output(video_input, audio_input, output_path, vcodec='copy', acodec='copy').run()

                return FileResponse(open(output_path, 'rb'), as_attachment=True, filename=output_filename)

    return render(request, 'download_video.html',
                  {'form': form, 'title': title, 'thumbnail_url': thumbnail_url, 'resolutions': resolutions})
