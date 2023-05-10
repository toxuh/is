import os
import shutil
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

            tmpdirname = tempfile.mkdtemp()
            try:
                video_filename = 'video.mp4'
                video_stream.download(output_path=tmpdirname, filename=video_filename)
                video_file_path = os.path.join(tmpdirname, video_filename)
                print(f'Video downloaded to {video_file_path}')

                audio_filename = 'audio.mp4'
                audio_stream.download(output_path=tmpdirname, filename=audio_filename)
                audio_file_path = os.path.join(tmpdirname, audio_filename)
                print(f'Audio downloaded to {audio_file_path}')

                short_hash = hashlib.sha1(str(random.random()).encode('utf-8')).hexdigest()[:5]
                output_filename = f'ISAVER.CLICK_{short_hash}.mp4'
                output_filepath = os.path.join(tmpdirname, output_filename)

                command = f'ffmpeg -i "{video_file_path}" -i "{audio_file_path}" -f mp4 "{output_filepath}"'
                args = shlex.split(command)
                process = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if process.returncode != 0:
                    print(f'ffmpeg failed with error: {process.stderr.decode()}')
                else:
                    print(f'ffmpeg succeeded: {process.stdout.decode()}')

                file_size = os.path.getsize(output_filepath)
                response = StreamingHttpResponse(stream_video(output_filepath),
                                                 content_type='application/octet-stream')

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
            finally:
                shutil.rmtree(tmpdirname)

    return render(request, 'download_video.html',
                  {'form': form, 'title': title, 'thumbnail_url': thumbnail_url, 'resolutions': resolutions})
