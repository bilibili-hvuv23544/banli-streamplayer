#!/usr/bin/env python3
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import os
import re
import urllib.parse

CONFIG_FILE = 'config-video.txt'
VIDEO_DIR = 'VIDEO'

#有一小段用了AI写的代码，2026年11月23日在人工智能课写的代码，实在是没时间了，叫豆包帮我写了一小点，然后我改进了
#config-video.txt格式是这样的:
#video_dir=/storage/emulated/0/VIDEO
#不要写相对路径
#你个扎啤
#此为板栗网页播放器v2，更新内容:
#读取外部文件config.txt从而配置音乐/视频目录，你要使用绝对目录，而并非相对目录
#将原本的HTTPServer这种的单阻塞，换为了ThreadingHTTPServer，仅支持3.7以上的版本了

#这段豆包写的
def resolve_video_path(path):
    path = path.strip()
    
    if re.match(r'^[a-zA-Z]:[/\\\\]', path):
        return os.path.normpath(path)
    elif path.startswith('/'):
        return os.path.normpath(path)
    else:
        return os.path.normpath(os.path.join(os.getcwd(), path))

def load_config():
    global VIDEO_DIR
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip().lower()
                            value = value.strip()
                            if key == 'video_dir':
                                VIDEO_DIR = resolve_video_path(value)
                        else:
                            VIDEO_DIR = resolve_video_path(line)
            print(f'[配置] 已读取配置文件: {CONFIG_FILE}')
            print(f'[配置] 视频目录: {VIDEO_DIR}')
        else:
            print(f'[配置] 未找到 {CONFIG_FILE}，使用默认目录: {VIDEO_DIR}')
            VIDEO_DIR = os.path.normpath(os.path.join(os.getcwd(), VIDEO_DIR))
    except Exception as e:
        print(f'[配置] 读取配置文件出错: {e}')
        VIDEO_DIR = os.path.normpath(os.path.join(os.getcwd(), 'VIDEO'))

load_config()
print(f'[配置] 最终视频目录: {VIDEO_DIR}')
#下面人写的

HTML_PAGE = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>板栗网页播放器(VIDEO)</title>
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

function playFile(path) {{
  const fileName = decodeURIComponent(path.substring(path.lastIndexOf('/') + 1));
  nameBox.textContent = fileName;
  player.src = path;
  player.load();
  player.play().catch(err => console.warn('播放请求被服务器抛弃，变成滚木了:', err));
}}

async function scanDirectory(dirPath) {{
  try {{
    const response = await fetch(dirPath);
    if (!response.ok) {{
      debugInfo.push('[HTTP ' + response.status + '] 无法访问目录: ' + dirPath);
      return;
    }}
    
    const html = await response.text();
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    const links = doc.querySelectorAll('a');

    for (const link of links) {{
      const href = link.getAttribute('href');
      if (!href || href === './' || href === '../') continue;

      const fullPath = dirPath + href;
      const decodedFileName = decodeURIComponent(href);

      if (href.endsWith('/')) {{
        debugInfo.push('[目录] ' + fullPath);
        await scanDirectory(fullPath);
        continue;
      }}

      const ext = decodedFileName.substring(decodedFileName.lastIndexOf('.')).toLowerCase();
      if (videoExts.includes(ext)) {{
        allVideoFiles.push({{ name: decodedFileName, path: fullPath }});
      }} else {{
        debugInfo.push('[其他] ' + fullPath);
      }}
    }}
  }} catch (err) {{
    debugInfo.push('你的目录是变成了滚木吗？(我们找不着了): ' + dirPath + ' — ' + err.message);
  }}
}}

(async () => {{
  debugInfo.push('扫描视频目录: ' + videoDir);
  debugInfo.push('正在扫描...');
  
  await scanDirectory(videoDir);

  allVideoFiles.sort((a, b) => a.name.localeCompare(b.name));

  if (allVideoFiles.length === 0) {{
    fileListDiv.textContent = '未找到视频文件';
  }} else {{
    fileListDiv.innerHTML = '';
    allVideoFiles.forEach(file => {{
      const link = document.createElement('a');
      link.href = '#';
      link.textContent = file.name;
      link.style.display = 'inline-block';
      link.style.marginBottom = '4px';
      link.addEventListener('click', (e) => {{
        e.preventDefault();
        playFile(file.path);
      }});
      fileListDiv.appendChild(link);
      fileListDiv.appendChild(document.createElement('br'));
    }});
  }}

  let debugOutput = '===== 调试输出 =====\\n';
  debugOutput += '基准目录: ' + baseDir + '\\n';
  debugOutput += '视频目录: ' + videoDir + '\\n';
  debugOutput += '出现: ' + allVideoFiles.length + ' 个视频文件\\n';
  debugOutput += '──────────────────────────\\n';
  debugOutput += debugInfo.join('\\n');
  debugDiv.textContent = debugOutput;
}})();
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

    def translate_path(self, path):
        path = path.split('?', 1)[0]
        path = path.split('#', 1)[0]
        path = urllib.parse.unquote(path)
        path = os.path.normpath(path)
        
        words = [w for w in path.split('/') if w]
        
        if words and words[0] == 'VIDEO':
            rel_path = '/'.join(words[1:])
            result = os.path.join(VIDEO_DIR, rel_path)
            return result
        
        return os.path.join(os.getcwd(), path.lstrip('/'))

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
    server = ThreadingHTTPServer(('0.0.0.0', port), StreamingHandler)
    print(f'板栗网页播放器启动: http://0.0.0.0:{port}')
    print(f'视频目录: {VIDEO_DIR}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n服务器停止')
        server.server_close()