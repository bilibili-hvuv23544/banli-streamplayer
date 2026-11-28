# banli-streamplayer
板栗网页播放器。比滚木网页播放器更强，支持处理Range请求，可以流媒体，并且支持音频和视频处理。

只有Python，通过Python http.server运行

# Version2更新
1.通过同目录下的config.txt来确认音频或者视频的目录
2.将HTTPServer修改为ThreadingHTTPServer，这意味着你需要使用Python3.7以上的版本才可以正常运行，否则你需要改成HTTPServer
