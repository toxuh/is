import os
import tempfile
import hashlib
import random
import subprocess
import shlex
import re

from django import forms
from django.shortcuts import render
from django.http import StreamingHttpResponse
from pytube import YouTube

from .forms import VideoDownloadForm

range_re = re.compile(r'bytes\s*=\s*(\d*)-(\d*)')


def stream_video(output_filepath):
    with open(output_filepath, 'rb') as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            yield chunk

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

                short_hash = hashlib.sha1(str(random.random()).encode('utf-8')).hexdigest()[:5]
                output_filename = f'ISAVER.CLICK_{title[:10]}_{short_hash}.mp4'
                output_filepath = os.path.join(tmpdirname, output_filename)

                command = f'ffmpeg -i {video_filename} -i {audio_filename} -f mp4 {output_filename}'
                args = shlex.split(command)
                subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                file_size = os.path.getsize(output_filepath)
                response = StreamingHttpResponse(stream_video(output_filepath), content_type='application/octet-stream')  # Stream the output file

                range_header = request.META.get('HTTP_RANGE', '').strip()
                range_match = range_re.match(range_header)
                if range_match:
                    range_type, ranges = range_match.groups()
                    if range_type == 'bytes':
                        start, end = ranges.split('-')
                        start = int(start.strip())
                        end = int(end.strip()) if end.strip() else file_size - 1
                        response.status_code = 206
                        response['Content-Range'] = f'bytes {start}-{end}/{file_size}'

                response['Content-Disposition'] = 'attachment;'
                response['Accept-Ranges'] = 'bytes'
                response['Content-Length'] = str(file_size)

                return response

    return render(request, 'download_video.html',
                  {'form': form, 'title': title, 'thumbnail_url': thumbnail_url, 'resolutions': resolutions})
