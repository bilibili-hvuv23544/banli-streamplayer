#!/usr/bin/env python3
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import re
import urllib.parse

HTML_PAGE = '''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>滚木网页播放器(MUSIC)</title>
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
</head>
<body>

<audio id="player" controls style="width:100%%;max-width:600px;"></audio>
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

const baseDir = location.pathname.substring(0, location.pathname.lastIndexOf('/') + 1);
const musicDir = baseDir + 'my-music/';
const defaultCover = baseDir + 'default/No-Cover.webp';

const audioExts = ['.mp3', '.flac', '.ogg', '.wav'];
let allAudioFiles = [];
let debugInfo = [];

function showDefault() {
  coverBox.innerHTML = '<img src="' + defaultCover + '" style="max-width:300px;">';
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

async function scanDirectory(dirPath, depth = 0) {
  if (depth > 5) {
    debugInfo.push('[跳过] 超过最大深度: ' + dirPath);
    return;
  }
  
  try {
    const response = await fetch(dirPath, {
      cache: 'no-store',
      headers: {
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache'
      }
    });
    
    if (!response.ok) {
      debugInfo.push('[HTTP ' + response.status + '] 无法访问: ' + dirPath);
      return;
    }
    
    const html = await response.text();
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    const links = doc.querySelectorAll('a');

    for (const link of links) {
      const href = link.getAttribute('href');
      if (!href || href === './' || href === '../') continue;

      const fullPath = dirPath + href;
      const decodedFileName = decodeURIComponent(href);

      if (href.endsWith('/')) {
        debugInfo.push('[目录] ' + fullPath);
        await scanDirectory(fullPath, depth + 1);
        continue;
      }

      const ext = decodedFileName.substring(decodedFileName.lastIndexOf('.')).toLowerCase();
      if (audioExts.includes(ext)) {
        allAudioFiles.push({ name: decodedFileName, path: fullPath });
      } else {
        debugInfo.push('[其他] ' + fullPath);
      }
    }
  } catch (err) {
    debugInfo.push('[错误] ' + dirPath + ' — ' + err.message);
  }
}

(async () => {
  debugInfo.push('扫描音频目录: ' + musicDir);
  debugInfo.push('正在扫描...');
  
  await scanDirectory(musicDir);

  allAudioFiles.sort((a, b) => a.name.localeCompare(b.name));

  if (allAudioFiles.length === 0) {
    fileListDiv.textContent = '未找到音频文件';
  } else {
    fileListDiv.innerHTML = '';
    allAudioFiles.forEach(file => {
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
  }

  let debugOutput = '===== 调试输出 =====\\n';
  debugOutput += '基准目录: ' + baseDir + '\\n';
  debugOutput += '音频目录: ' + musicDir + '\\n';
  debugOutput += '出现: ' + allAudioFiles.length + ' 个音频文件\\n';
  debugOutput += '──────────────────────────\\n';
  debugOutput += debugInfo.join('\\n');
  debugDiv.textContent = debugOutput;
})();
</script>

</body>
</html>'''

class MusicStreamingHandler(SimpleHTTPRequestHandler):
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

    def do_GET(self):
            parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        
        if path == '/' or path == '/index.html' or path == '/music-player.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))
            return
            
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
    import sys
    
    port = 20001  # 换个端口避免冲突
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f'端口号无效，使用默认端口 {port}')
    
    server = HTTPServer(('0.0.0.0', port), MusicStreamingHandler)
    print(f'滚木网页播放器(MUSIC)启动成功!')
    print(f'访问地址: http://0.0.0.0:{port}')
    print(f'当前目录: {os.getcwd()}')
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n 服务器已停止')
        server.server_close()
