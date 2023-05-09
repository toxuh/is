import ffmpeg

from django.db import models
from pytube import YouTube
from youtube_transcript_api import YouTubeTranscriptApi

class Video(models.Model):
    url = models.URLField()
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    thumbnail_url = models.URLField(blank=True)
    format = models.CharField(max_length=50)
    download_status = models.CharField(max_length=50, default='pending')
    file_path = models.CharField(max_length=500, blank=True)

    def download(self):
        yt = YouTube(self.url)

        video_stream = yt.streams.filter(progressive=True, file_extension='mp4').first()
        audio_stream = yt.streams.get_audio_only()

        video_path = video_stream.download('/path/to/download/video/directory')
        audio_path = audio_stream.download('/path/to/download/audio/directory')

        self.file_path = video_path
        self.save()

    def convert_to_avi(self):
        output_file_path = self.file_path.replace('.mp4', '.avi')
        stream = ffmpeg.input(self.file_path)
        stream = ffmpeg.output(stream, output_file_path)
        ffmpeg.run(stream)

        # Update the file_path field to the new file and save the model instance
        self.file_path = output_file_path
        self.save()

class Playlist(models.Model):
    url = models.URLField()
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    thumbnail_url = models.URLField(blank=True)
    download_status = models.CharField(max_length=50, default='pending')

class Batch(models.Model):
    videos = models.ManyToManyField(Video)
    download_status = models.CharField(max_length=50, default='pending')

class Subtitle(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    language = models.CharField(max_length=50)
    file_path = models.CharField(max_length=500)

    def download(self):
        video_id = self.video.url.split('=')[-1]
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[self.language])

        with open('/path/to/download/directory/subtitle.txt', 'w') as f:
            for line in transcript:
                f.write(line['text'] + '\n')

        self.file_path = '/path/to/download/directory/subtitle.txt'
        self.save()
