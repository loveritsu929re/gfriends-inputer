# -*- coding: utf-8 -*-
"""XSlist 的 Scrapling 浏览器会话管理。"""

import atexit
import threading

from lxml import etree


def parse_xslist_details(html_text):
    """按 XSlist 当前详情页结构提取演员资料字段。"""
    html = etree.HTML(html_text)
    if html is None:
        return {}

    detail_nodes = html.xpath('//p[contains(., "出生:") and contains(., "罩杯:")]')
    if not detail_nodes:
        return {}

    detail_texts = detail_nodes[0].xpath('descendant-or-self::text()')
    detail_dict = {}
    for index, raw_info in enumerate(detail_texts):
        info = raw_info.strip()
        if ':' not in info:
            continue

        key, value = (part.strip() for part in info.split(':', 1))
        if not value and index + 1 < len(detail_texts):
            value = detail_texts[index + 1].strip()
        if key and value and value.lower() != 'n/a':
            detail_dict[key] = value
    return detail_dict


class XslistSession:
    """懒加载并全程复用一个可处理 Cloudflare 挑战的浏览器会话。"""

    def __init__(self, proxy=None, session_factory=None):
        self.proxy = proxy
        self.session = None
        self._session_factory = session_factory
        self._lock = threading.RLock()
        self._close_registered = False

    def _ensure_session(self):
        if self.session is not None:
            return self.session

        if self._session_factory is None:
            try:
                from scrapling.fetchers import StealthySession
            except Exception as error:
                message = (
                    "加载 Scrapling 失败，请先安装 requirements.txt 中的依赖，"
                    "并运行 `scrapling install` 安装浏览器组件"
                )
                raise ImportError(message) from error
            self._session_factory = StealthySession

        session = self._session_factory(
            headless=True,
            solve_cloudflare=True,
            humanize=True,
            proxy=self.proxy,
            geoip=True,
        )
        session.__enter__()
        self.session = session
        if not self._close_registered:
            atexit.register(self.close)
            self._close_registered = True
        return session

    def fetch(self, url):
        """使用同一浏览器上下文获取页面，返回最终 URL 和文本正文。"""
        with self._lock:
            response = self._ensure_session().fetch(url)
            body = response.body
            if isinstance(body, bytes):
                body = body.decode("utf-8", errors="replace")
            return str(response.url), body

    def close(self):
        """关闭浏览器会话，避免进程退出后遗留 Chromium。"""
        with self._lock:
            session, self.session = self.session, None
            if session is None:
                return
            try:
                session.__exit__(None, None, None)
            except Exception:
                pass
