#!/usr/bin/env python3
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import re

HTML_PAGE = '''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>滚木网页播放器(VIDEO)</title>
</head>
<body>

<video id="player" controls style="width:100%;max-width:800px;display:block;"></video>
<br>
<div id="filename"></div>
<br>
<div id="filelist"></div>
<br>
<div id="debug" style="white-space:pre-wrap;font-family:monospace;background:#f4f4f4;padding:8px;"></div>

<script>
const player = document.getElementById('player');
const nameBox = document.getElementById('filename');
const fileListDiv = document.getElementById('filelist');
const debugDiv = document.getElementById('debug');

const baseDir = location.pathname.substring(0, location.pathname.lastIndexOf('/') + 1);
const videoDir = baseDir + 'VIDEO/';
const videoExts = ['.mp4', '.webm', '.mov', '.avi', '.mkv', '.flv', '.wmv'];
let allVideoFiles = [];
let debugInfo = [];

function playFile(path) {
  const fileName = decodeURIComponent(path.substring(path.lastIndexOf('/') + 1));
  nameBox.textContent = fileName;
  player.src = path;
  player.load();
  player.play().catch(err => console.warn('播放请求被服务器抛弃，变成滚木了:', err));
}

async function scanDirectory(dirPath) {
  try {
    const response = await fetch(dirPath);
    if (!response.ok) {
      debugInfo.push('[HTTP ' + response.status + '] 无法访问目录: ' + dirPath);
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
        await scanDirectory(fullPath);
        continue;
      }

      const ext = decodedFileName.substring(decodedFileName.lastIndexOf('.')).toLowerCase();
      if (videoExts.includes(ext)) {
        allVideoFiles.push({ name: decodedFileName, path: fullPath });
      } else {
        debugInfo.push('[其他] ' + fullPath);
      }
    }
  } catch (err) {
    debugInfo.push('你的目录是变成了滚木吗？(我们找不着了): ' + dirPath + ' — ' + err.message);
  }
}

(async () => {
  debugInfo.push('扫描视频目录: ' + videoDir);
  debugInfo.push('正在扫描...');
  
  await scanDirectory(videoDir);

  allVideoFiles.sort((a, b) => a.name.localeCompare(b.name));

  if (allVideoFiles.length === 0) {
    fileListDiv.textContent = '未找到视频文件';
  } else {
    fileListDiv.innerHTML = '';
    allVideoFiles.forEach(file => {
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
  debugOutput += '视频目录: ' + videoDir + '\\n';
  debugOutput += '出现: ' + allVideoFiles.length + ' 个视频文件\\n';
  debugOutput += '──────────────────────────\\n';
  debugOutput += debugInfo.join('\\n');
  debugDiv.textContent = debugOutput;
})();
</script>

</body>
</html>'''

class StreamingHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.send_header('Accept-Ranges', 'bytes')
        super().end_headers()

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))
            return
        
        range_header = self.headers.get('Range')
        file_path = self.translate_path(self.path)
        
        if os.path.isfile(file_path) and range_header:
            range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
            if range_match:
                start = int(range_match.group(1))
                end_str = range_match.group(2)
                
                file_size = os.path.getsize(file_path)
                
                if end_str:
                    end = min(int(end_str), file_size - 1)
                else:
                    end = file_size - 1
                
                self.send_response(206)
                self.send_header('Content-Type', self.guess_type(file_path))
                self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                self.send_header('Content-Length', str(end - start + 1))
                self.end_headers()
                
                with open(file_path, 'rb') as f:
                    f.seek(start)
                    remaining = end - start + 1
                    while remaining > 0:
                        chunk_size = min(8192, remaining)
                        data = f.read(chunk_size)
                        if not data:
                            break
                        self.wfile.write(data)
                        remaining -= len(data)
                return
        
        super().do_GET()

if __name__ == '__main__':
    port = 11452
    server = HTTPServer(('0.0.0.0', port), StreamingHandler)
    print(f'滚木网页播放器服务器启动: http://0.0.0.0:{port}')
    print(f'滚木滚木')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n服务器停止')
        server.server_close()
