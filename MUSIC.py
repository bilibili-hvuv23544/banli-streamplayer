#!/usr/bin/env python3
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import re
import json
import urllib.parse

HTML_PAGE = '''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>板栗网页播放器(MUSIC)</title>
</head>
<body>

<audio id="player" controls style="width:100%;max-width:600px;"></audio>
<br>
<div id="cover"></div>
<div id="filename"></div>
<br>
<div id="filelist"></div>
<br>
<div id="debug" style="white-space:pre-wrap;font-family:monospace;background:#f4f4f4;padding:8px;"></div>

<script type="module">
import { parseBlob } from 'https://cdn.jsdelivr.net/npm/music-metadata@9/+esm';

const player = document.getElementById('player');
const coverBox = document.getElementById('cover');
const nameBox = document.getElementById('filename');
const fileListDiv = document.getElementById('filelist');
const debugDiv = document.getElementById('debug');

const audioExts = ['.mp3', '.flac', '.ogg', '.wav'];
let debugInfo = [];

function showDefault() {
  coverBox.innerHTML = '<img src="/default/No-Cover.webp" style="max-width:300px;">';
}

function playFile(path) {
  const fileName = decodeURIComponent(path.substring(path.lastIndexOf('/') + 1));
  nameBox.textContent = fileName;
  player.src = path;
  player.load();
  player.play().catch(err => console.warn('播放请求被服务器抛弃，变成滚木了:', err));

  fetch(path)
    .then(r => r.blob())
    .then(blob => parseBlob(blob))
    .then(meta => {
      const pic = meta.common.picture && meta.common.picture[0];
      if (pic) {
        const url = URL.createObjectURL(new Blob([pic.data], { type: pic.format }));
        coverBox.innerHTML = '<img src="' + url + '" style="max-width:300px;">';
      } else {
        showDefault();
      }
    })
    .catch(() => showDefault());
}

// 通过API获取文件列表
async function loadFileList() {
  try {
    const response = await fetch('/api/list');
    if (!response.ok) {
      debugInfo.push('[错误] 获取文件列表失败: HTTP ' + response.status);
      return [];
    }
    const data = await response.json();
    return data;
  } catch (err) {
    debugInfo.push('[错误] 获取文件列表失败: ' + err.message);
    return [];
  }
}

(async () => {
  debugInfo.push('正在通过API获取文件列表...');
  
  const files = await loadFileList();
  
  if (files.length === 0) {
    fileListDiv.textContent = '未找到音频文件';
    debugInfo.push('未找到任何音频文件');
  } else {
    fileListDiv.innerHTML = '';
    files.forEach(file => {
      const link = document.createElement('a');
      link.href = '#';
      link.textContent = file.name;
      link.style.display = 'inline-block';
      link.style.marginBottom = '4px';
      link.addEventListener('click', (e) => {
        e.preventDefault();
        playFile(file.path);
      });
      fileListDiv.appendChild(link);
      fileListDiv.appendChild(document.createElement('br'));
    });
    debugInfo.push('找到 ' + files.length + ' 个音频文件');
  }

  let debugOutput = '===== 调试输出 =====\\n';
  debugOutput += '音频目录: my-music/\\n';
  debugOutput += '出现: ' + files.length + ' 个音频文件\\n';
  debugOutput += '──────────────────────────\\n';
  debugOutput += debugInfo.join('\\n');
  debugDiv.textContent = debugOutput;
})();
</script>

</body>
</html>'''

class MusicStreamingHandler(SimpleHTTPRequestHandler):
    # 音频文件扩展名
    AUDIO_EXTS = {'.mp3', '.flac', '.ogg', '.wav'}
    
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Range')
        self.end_headers()

    def scan_directory(self, dir_path, max_depth=5):
        """递归扫描目录，返回音频文件列表"""
        audio_files = []
        
        def _scan(current_path, depth):
            if depth > max_depth:
                return
            
            try:
                entries = os.listdir(current_path)
                for entry in sorted(entries):
                    full_path = os.path.join(current_path, entry)
                    
                    if os.path.isdir(full_path):
                        _scan(full_path, depth + 1)
                    elif os.path.isfile(full_path):
                        # 检查扩展名
                        _, ext = os.path.splitext(entry.lower())
                        if ext in self.AUDIO_EXTS:
                            # 转换为相对路径（相对于服务器根目录）
                            rel_path = os.path.relpath(full_path, os.getcwd())
                            # 确保使用正斜杠
                            rel_path = rel_path.replace('\\\\', '/')
                            audio_files.append({
                                'name': entry,
                                'path': '/' + rel_path
                            })
            except PermissionError:
                pass
            except Exception as e:
                print(f'扫描目录出错 {current_path}: {e}')
        
        _scan(dir_path, 0)
        return audio_files

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        
        # API接口：获取音频文件列表
        if path == '/api/list':
            music_dir = os.path.join(os.getcwd(), 'my-music')
            if os.path.exists(music_dir):
                files = self.scan_directory(music_dir)
            else:
                files = []
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(files, ensure_ascii=False).encode('utf-8'))
            return
        
        # 返回播放器页面
        if path == '/' or path == '/index.html' or path == '/music-player.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))
            return
        
        # 处理文件请求（支持Range）
        file_path = self.translate_path(self.path)
        range_header = self.headers.get('Range')
        
        if os.path.isdir(file_path):
            super().do_GET()
            return
        
        if os.path.isfile(file_path) and range_header:
            try:
                file_size = os.path.getsize(file_path)
                
                range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
                if not range_match:
                    self.send_response(200)
                    self.send_header('Content-Type', self.guess_type(file_path))
                    self.send_header('Content-Length', str(file_size))
                    self.end_headers()
                    with open(file_path, 'rb') as f:
                        self.copyfile(f, self.wfile)
                    return
                
                start = int(range_match.group(1))
                end_str = range_match.group(2)
                
                if end_str:
                    end = min(int(end_str), file_size - 1)
                else:
                    end = file_size - 1
                
                if start >= file_size or end >= file_size or start > end:
                    self.send_response(416)
                    self.send_header('Content-Range', f'bytes */{file_size}')
                    self.end_headers()
                    return
                
                content_length = end - start + 1
                
                self.send_response(206)
                self.send_header('Content-Type', self.guess_type(file_path))
                self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                self.send_header('Content-Length', str(content_length))
                self.end_headers()
                
                with open(file_path, 'rb') as f:
                    f.seek(start)
                    remaining = content_length
                    while remaining > 0:
                        try:
                            chunk_size = min(65536, remaining)
                            data = f.read(chunk_size)
                            if not data:
                                break
                            self.wfile.write(data)
                            remaining -= len(data)
                        except (BrokenPipeError, ConnectionResetError):
                            break
                return
                
            except Exception as e:
                print(f'处理Range请求出错: {e}')
                self.send_error(500, f'Server Error: {str(e)}')
                return
        
        if os.path.isfile(file_path):
            self.send_response(200)
            self.send_header('Content-Type', self.guess_type(file_path))
            self.send_header('Content-Length', str(os.path.getsize(file_path)))
            self.end_headers()
            with open(file_path, 'rb') as f:
                self.copyfile(f, self.wfile)
            return
        
        super().do_GET()

if __name__ == '__main__':
    port = 55555
    
    server = HTTPServer(('0.0.0.0', port), MusicStreamingHandler)
    print(f'板栗网页播放器(MUSIC)已启动')
    print(f'访问地址: http://0.0.0.0:{port}')
    print(f'当前目录: {os.getcwd()}')
    print(f'音频目录(相对目录中): ./my-music/')
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n服务器已停止')
        server.server_close()
