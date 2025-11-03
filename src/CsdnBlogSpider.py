# encoding:utf-8
__author__ = 'Sun'

import re
import urllib.request
import urllib
import queue
import threading
import os
import ssl, certifi, urllib.request

task_queue = queue.Queue()   # ← 改名，别覆盖模块名
visited = set()
cnt = 0

class CsdnBlogSpider(threading.Thread):
	def __init__(self, task_queue, opener, blog_name):
		super().__init__(daemon=True)     # 直接用 daemon=True
		self.queue = task_queue
		self.opener = opener
		self.blog_name = blog_name
		self.lock = threading.Lock()

	def save_data(self, data, filename):
		blog_dir = os.path.join(os.path.abspath('.'), 'blog')
		os.makedirs(blog_dir, exist_ok=True)
		try:
			with open(os.path.join(blog_dir, f'{filename}.html'), 'wb') as fout:
				fout.write(data)
		except IOError as e:
			print(e)

	def find_title(self, data: bytes) -> str:
		s = data.decode('utf-8', errors='ignore')
		m = re.search(r'<title[^>]*>(.*?)</title>', s, flags=re.IGNORECASE | re.DOTALL)
		if not m:
			return 'untitled'
		# 去掉多余空白
		title = m.group(1).strip()
		# 简单清理 HTML 实体 & 多余换行
		title = re.sub(r'\s+', ' ', title)
		return title or 'untitled'


	def safe_filename(self, title: str, url: str, maxlen: int = 80) -> str:
		# 1) 提取文章ID做后缀，保证唯一性
		m = re.search(r'/article/details/(\d+)', url)
		id_suffix = m.group(1) if m else ''

		# 2) 清洗标题为文件名安全字符
		#    仅保留中英文、数字、空格和常见分隔符；其他替换为下划线
		safe = re.sub(r'[^\w\u4e00-\u9fa5 \-_.]+', '_', title, flags=re.UNICODE)
		safe = safe.strip(' ._-') or 'untitled'

		# 3) 截断（保留末尾 id 作为区分）
		if id_suffix:
			base = f"{safe}"
			# 预留一个连字符和id长度
			reserve = 1 + len(id_suffix)
			if len(base) > maxlen - reserve:
				base = base[:maxlen - reserve].rstrip(' ._-')
			safe = f"{base}-{id_suffix}"
		else:
			if len(safe) > maxlen:
				safe = safe[:maxlen].rstrip(' ._-')

		# 4) 避免空名
		return safe or (id_suffix if id_suffix else 'untitled')

	def run(self):
		global cnt, visited
		while True:
			url = self.queue.get()
			with self.lock:
				cnt += 1
				print('已经抓取：' + str(cnt - 1) + ' 正在抓取---->' + url)
			try:
				res = self.opener.open(url, timeout=30)
				data = res.read()
			except Exception as e:
				if hasattr(e, 'reason'):
					print('reason:', e.reason)
				elif hasattr(e, 'code'):
					print('error code:', e.code)
				with self.lock:
					cnt -= 1
				self.queue.task_done()
				continue

			title = self.find_title(data)
			fname = self.safe_filename(title, url)
			self.save_data(data, fname)


			html = data.decode('utf-8', errors='ignore')

			# 用原始字符串 + re.escape 防止 blog_name 中的特殊字符破坏正则
			pattern = re.compile(r'/' + re.escape(self.blog_name) + r'/article/details/\d+')
			for u in pattern.findall(html):
				full = 'https://blog.csdn.net' + u
				if full not in visited:
					self.queue.put(full)
					visited.add(full)

			self.queue.task_done()

def init(name, number=10):
	global cnt, visited
	import ssl, certifi, urllib.request

	blog_name = name.lower()
	th_num = int(number)

	# 用 HTTPS
	url = f'https://blog.csdn.net/{blog_name}/'

	# 配置 HTTPS 证书
	ctx = ssl.create_default_context(cafile=certifi.where())
	opener = urllib.request.build_opener(
		urllib.request.HTTPSHandler(context=ctx),
		urllib.request.HTTPHandler(),
	)
	opener.addheaders = [
		('User-Agent',
		 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
		 '(KHTML, like Gecko) Chrome/120.0 Safari/537.36')
	]
	urllib.request.install_opener(opener)

	# 初始化队列与状态
	task_queue.put(url)
	visited = {url}
	cnt = 0

	for _ in range(th_num):
		t = CsdnBlogSpider(task_queue, opener, blog_name)
		t.daemon = True
		t.start()

	task_queue.join()
	print('--------end!!!-----')
	print('共抓取:' + str(cnt))

if __name__ == '__main__':
	init()
