#!/usr/bin/env python3
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import os
import re
import json
import urllib.parse

#有一小段用了AI写的代码，2026年11月25日在学校机房写的代码，实在是没时间了，叫豆包帮我写了一小点，然后我改进了
#config.txt格式是这样的:
#music_dir=/storage/emulated/0/Music/my-music
#不要写相对路径
#你个扎啤
#此为板栗播放器v2，更新内容:
#读取外部文件config.txt从而配置音乐目录，你要使用绝对目录，而并非相对目录
#将原本的HTTPServer这种的单阻塞，换为了ThreadingHTTPServer，仅支持3.7以上的版本了

CONFIG_FILE = 'config.txt'
MUSIC_DIR = 'my-music'  

#本段为人工智能写的代码，人工改进
def resolve_music_path(path):
    path = path.strip()
    if re.match(r'^[a-zA-Z]:[/\\\\]', path):
        return os.path.normpath(path)
    elif path.startswith('/'):
        return os.path.normpath(path)
    else:
        return os.path.normpath(os.path.join(os.getcwd(), path))

def load_config():
    global MUSIC_DIR
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
                            if key == 'music_dir':
                                MUSIC_DIR = resolve_music_path(value)
                        else:
                            MUSIC_DIR = resolve_music_path(line)
            print(f'[配置] 已读取配置文件: {CONFIG_FILE}')
            print(f'[配置] 音乐目录: {MUSIC_DIR}')
        else:
            print(f'[配置] 未找到 {CONFIG_FILE}，使用默认目录: {MUSIC_DIR}')
            MUSIC_DIR = os.path.normpath(os.path.join(os.getcwd(), MUSIC_DIR))
    except Exception as e:
        print(f'[配置] 读取配置文件出错: {e}')
        MUSIC_DIR = os.path.normpath(os.path.join(os.getcwd(), 'my-music'))

load_config()
print(f'[配置] 最终音乐目录: {MUSIC_DIR}')

#下面全是人写的了

HTML_PAGE = f'''<!DOCTYPE html>
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
import {{ parseBlob }} from 'https://cdn.jsdelivr.net/npm/music-metadata@9/+esm';

const player = document.getElementById('player');
const coverBox = document.getElementById('cover');
const nameBox = document.getElementById('filename');
const fileListDiv = document.getElementById('filelist');
const debugDiv = document.getElementById('debug');

const audioExts = ['.mp3', '.flac', '.ogg', '.wav'];
let debugInfo = [];

function showDefault() {{
  coverBox.innerHTML = '<img src="/default/No-Cover.webp" style="max-width:300px;">';
}}

function playFile(path) {{
  const fileName = decodeURIComponent(path.substring(path.lastIndexOf('/') + 1));
  nameBox.textContent = fileName;
  player.src = path;
  player.load();
  player.play().catch(err => console.warn('播放请求被服务器抛弃，变成滚木了:', err));

  fetch(path)
    .then(r => r.blob())
    .then(blob => parseBlob(blob))
    .then(meta => {{
      const pic = meta.common.picture && meta.common.picture[0];
      if (pic) {{
        const url = URL.createObjectURL(new Blob([pic.data], {{ type: pic.format }}));
        coverBox.innerHTML = '<img src="' + url + '" style="max-width:300px;">';
      }} else {{
        showDefault();
      }}
    }})
    .catch(() => showDefault());
}}

// 通过API获取文件列表
async function loadFileList() {{
  try {{
    const response = await fetch('/api/list');
    if (!response.ok) {{
      debugInfo.push('[错误] 获取文件列表失败: HTTP ' + response.status);
      return [];
    }}
    const data = await response.json();
    return data;
  }} catch (err) {{
    debugInfo.push('[错误] 获取文件列表失败: ' + err.message);
    return [];
  }}
}}

(async () => {{
  debugInfo.push('正在通过API获取文件列表...');
  
  const files = await loadFileList();
  
  if (files.length === 0) {{
    fileListDiv.textContent = '未找到音频文件';
    debugInfo.push('未找到任何音频文件');
  }} else {{
    fileListDiv.innerHTML = '';
    files.forEach(file => {{
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
    debugInfo.push('找到 ' + files.length + ' 个音频文件');
  }}

  let debugOutput = '===== 调试输出 =====\\n';
  debugOutput += '音频目录: {MUSIC_DIR}\\n';
  debugOutput += '出现: ' + files.length + ' 个音频文件\\n';
  debugOutput += '──────────────────────────\\n';
  debugOutput += debugInfo.join('\\n');
  debugDiv.textContent = debugOutput;
}})();
</script>

</body>
</html>'''

class MusicStreamingHandler(SimpleHTTPRequestHandler):
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

    def translate_path(self, path):
        if path.startswith('/api/'):
            return path
        
        path = path.split('?', 1)[0]
        path = path.split('#', 1)[0]
        path = urllib.parse.unquote(path)
        path = os.path.normpath(path)
        
        words = [w for w in path.split('/') if w]
        
        if words and words[0] == 'my-music':
            rel_path = '/'.join(words[1:])
            result = os.path.join(MUSIC_DIR, rel_path)
            return result
        
        return os.path.join(os.getcwd(), path.lstrip('/'))

    def scan_directory(self, dir_path, max_depth=5):
        audio_files = []
        
        print(f'[扫描] 开始扫描目录: {dir_path}')
        print(f'[扫描] 目录是否存在: {os.path.exists(dir_path)}')
        
        if not os.path.exists(dir_path):
            print(f'[扫描] 目录不存在！')
            return audio_files
        
        # 列出顶层目录内容看看
        try:
            top_entries = os.listdir(dir_path)
            print(f'[扫描] 顶层目录内容 ({len(top_entries)} 项):')
            for e in top_entries[:20]:
                full = os.path.join(dir_path, e)
                etype = '目录' if os.path.isdir(full) else '文件'
                print(f'  [{etype}] {e}')
            if len(top_entries) > 20:
                print(f'  ... 还有 {len(top_entries) - 20} 项')
        except Exception as e:
            print(f'[扫描] 列出目录失败: {e}')
        
        def _scan(current_path, depth):
            if depth > max_depth:
                return
            
            try:
                entries = os.listdir(current_path)
                print(f'[扫描] {"  " * depth}进入目录: {current_path} (depth={depth}, {len(entries)}项)')
                for entry in sorted(entries):
                    full_path = os.path.join(current_path, entry)
                    
                    if os.path.isdir(full_path):
                        _scan(full_path, depth + 1)
                    elif os.path.isfile(full_path):
                        _, ext = os.path.splitext(entry.lower())
                        if ext in self.AUDIO_EXTS:
                            rel_path = os.path.relpath(full_path, MUSIC_DIR)
                            rel_path = rel_path.replace('\\\\', '/')
                            audio_files.append({
                                'name': entry,
                                'path': '/my-music/' + rel_path
                            })
                            print(f'[扫描] {"  " * depth}发现音频: {entry} -> /my-music/{rel_path}')
                        else:
                            print(f'[扫描] {"  " * depth}跳过文件(扩展名不符): {entry} (ext={ext})')
            except PermissionError:
                print(f'[扫描] {"  " * depth}权限不足: {current_path}')
            except Exception as e:
                print(f'[扫描] {"  " * depth}扫描目录出错 {current_path}: {e}')
        
        _scan(dir_path, 0)
        print(f'[扫描] 扫描完成，共找到 {len(audio_files)} 个音频文件')
        return audio_files

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        
        if path == '/favicon.ico':
            self.send_response(302)
            self.send_header('Location', '/default/favicon.webp')
            self.end_headers()
            return
        
        if path == '/api/list':
            print(f'[API] 收到文件列表请求')
            if os.path.exists(MUSIC_DIR):
                files = self.scan_directory(MUSIC_DIR)
                print(f'[API] 返回 {len(files)} 个文件')
            else:
                print(f'[API] 音乐目录不存在: {MUSIC_DIR}')
                files = []
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(files, ensure_ascii=False).encode('utf-8'))
            return
        
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
                    end = min(file_size - 1, 3145728)
                
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
                            chunk_size = min(102400, remaining)
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
    from http.server import HTTPServer
    
    port = 55556
    
    server = ThreadingHTTPServer(('0.0.0.0', port), MusicStreamingHandler)
    print(f'板栗网页播放器(MUSIC)已启动')
    print(f'访问地址: http://0.0.0.0:{port}')
    print(f'当前目录: {os.getcwd()}')
    print(f'音乐目录: {MUSIC_DIR}')
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n服务器已停止')
        server.server_close()
