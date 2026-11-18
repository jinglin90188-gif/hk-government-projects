import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from scripts import daily_news as news
from scripts import send_daily_news as mail
from scripts.news_run_mode import mode

NOW = datetime(2026, 11, 18, 14, 0, tzinfo=ZoneInfo('Asia/Hong_Kong'))


def row(title='运输署推出自动驾驶测试平台', url='https://www.info.gov.hk/gia/general/202611/18/P1.htm', date=None):
    return news.record(title, url, (date or NOW - timedelta(hours=1)).isoformat(), news.SOURCES[0], '运输署宣布自动驾驶平台测试安排，将分阶段验证系统运作。')


class NewsTests(unittest.TestCase):
    def test_rss_parses_publisher_date_and_chinese(self):
        xml = '<rss><channel><item><title>無人機測試</title><link>https://www.info.gov.hk/a.htm</link><pubDate>Wed, 18 Nov 2026 04:00:00 GMT</pubDate><description>&lt;p&gt;測試安排&lt;/p&gt;</description></item></channel></rss>'
        r = news.parse_rss(xml, news.SOURCES[0])[0]
        self.assertEqual(r['title'], '无人机测试')
        self.assertEqual(r['published_at'], '2026-11-18T12:00:00+08:00')

    def test_bad_page_is_not_empty_news(self):
        with self.assertRaises(ValueError):
            news.parse_rss('<html>登录</html>', news.SOURCES[0])

    def test_date_freshness_future_and_missing(self):
        old = row(date=NOW - timedelta(hours=49))
        future = row(date=NOW + timedelta(minutes=5))
        missing = {**row(), 'published_at': ''}
        self.assertEqual(news.select_news([old, future, missing], NOW), [])
        self.assertEqual(len(news.select_news([row()], NOW)), 1)

    def test_tracking_links_and_fragments_are_deduplicated(self):
        a = row(url='https://www.info.gov.hk/news?id=1&utm_source=abc#top')
        b = row(url='https://www.info.gov.hk/news?id=1')
        self.assertEqual(a['id'], b['id'])
        self.assertEqual(len(news.select_news([a, b], NOW)), 1)

    def test_same_headline_different_project_numbers_remain_separate(self):
        self.assertEqual(len(news.select_news([
            row('自动驾驶第1期项目计划', url='https://www.info.gov.hk/1'),
            row('自动驾驶第2期项目计划', url='https://www.info.gov.hk/2')], NOW)), 2)

    def test_non_official_and_script_links_are_not_collected(self):
        self.assertEqual(news.canonical_url('javascript:alert(1)'), '')
        self.assertEqual(news.canonical_url('https://127.0.0.1/internal'), '')

    def test_government_body_without_paragraph_tags_is_read(self):
        response = MagicMock()
        response.headers = {'Content-Type': 'text/html'}
        response.content = '<span id="pressrelease">運輸署啟動智慧交通系統測試。<br>將分階段進行。</span>'.encode()
        with patch.object(news, 'get', return_value=response):
            self.assertIn('运输署启动智慧交通系统测试', news.article_text(row()))

    def test_legislative_brief_uses_answer_not_question(self):
        response = MagicMock()
        response.headers = {'Content-Type': 'text/html'}
        response.content = '<span id="pressrelease">以下是議員提問和局長答覆：問題：機場有什麼安排？答覆：機場管理局正測試智能接駁系統，並將於明年檢視成效。</span>'.encode()
        with patch.object(news, 'get', return_value=response):
            body = news.article_text(row())
        self.assertNotIn('问题', body)
        self.assertTrue(news.source_excerpt(body).startswith('机场管理局'))

    def test_translated_duplicate_headlines(self):
        a = row('無人機任務管理系統啟動測試')
        b = row('无人机任务管理系统启动测试', url='https://news.rthk.hk/other')
        self.assertEqual(len(news.select_news([a, b], NOW)), 1)

    def test_excludes_routine_accidents_and_unrelated(self):
        self.assertFalse(news.topic('机场附近交通意外造成挤塞'))
        self.assertFalse(news.topic('食物安全中心公布检查结果', '人工智能'))
        self.assertTrue(news.topic('低空经济培训课程正式推出'))
        self.assertTrue(news.topic('运输及物流局公布交通政策研究'))

    def test_maximum_ten_not_minimum_ten(self):
        rows = [row('自动驾驶第' + str(i) + '期项目计划', url='https://www.info.gov.hk/' + str(i)) for i in range(20)]
        selected = news.select_news(rows, NOW)
        self.assertLessEqual(len(selected), 10)
        self.assertEqual(len(news.select_news([row()], NOW)), 1)

    def test_known_news_not_fabricated_as_new_and_ai_is_cached(self):
        r = row()
        previous = {**r, 'first_seen': '2026-11-17T14:00:00+08:00', 'summary_kind': 'ai', 'summary': '已生成摘要'}
        result = news.select_news([r], NOW, {r['id']: previous})[0]
        self.assertFalse(result['new'])
        self.assertEqual(result['first_seen'], previous['first_seen'])
        self.assertEqual(result['summary'], '已生成摘要')

    def test_missing_ai_is_explicitly_an_excerpt(self):
        result = news.summarize(row(), '运输署宣布启动自动驾驶测试，研究远程接管平台的技术要求。', config={})
        self.assertEqual(result['summary_kind'], 'excerpt')

    def test_ai_requires_verifiable_evidence(self):
        config = {'NEWS_AI_API_KEY': 'test-only', 'NEWS_AI_BASE_URL': 'https://example.test/v1', 'NEWS_AI_MODEL': 'test-model'}
        response = MagicMock()
        response.json.return_value = {'choices': [{'message': {'content': json.dumps({'summary': '运输署启动自动驾驶平台测试，分阶段验证远程接管能力。', 'evidence': '启动自动驾驶平台测试'})}}]}
        with patch.object(news.requests, 'post', return_value=response):
            result = news.summarize(row(), '运输署启动自动驾驶平台测试，分阶段验证远程接管能力。', config)
            self.assertEqual(result['summary_kind'], 'ai')
            with self.assertRaisesRegex(ValueError, '证据'):
                news.summarize(row(), '这里是另一篇没有相应证据的文章。', config)

    def test_ai_cannot_send_key_to_plain_http(self):
        with self.assertRaises(ValueError):
            news.summarize(row(), '有正文内容', {'NEWS_AI_API_KEY': 'test-only', 'NEWS_AI_BASE_URL': 'http://example.test/v1', 'NEWS_AI_MODEL': 'test'})

    def test_all_sources_failed_preserves_last_success_time(self):
        previous = {'updated_at': '2026-11-17T14:00:00+08:00', 'items': [row()]}
        result = news.make_snapshot([], [{'status': 'failed'}], NOW, previous)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['updated_at'], previous['updated_at'])
        self.assertEqual(result['items'], previous['items'])
        self.assertIn('不能据此判断', result['message'])

    def test_partial_sources_with_no_news_do_not_recycle_old(self):
        result = news.make_snapshot([], [{'status': 'parsed'}, {'status': 'failed'}], NOW, {'items': [row()]})
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['items'], [])

    def test_mtr_list_extracts_date_and_pdf_link(self):
        content = '<table><tr><td>18/11/2026</td><td><a href="/pdf/a.pdf">港鐵智能檢測系統測試</a></td></tr></table>'
        result = news.parse_list(content, news.SOURCES[4])
        self.assertEqual(result[0]['published_at'][:10], '2026-11-18')
        self.assertEqual(result[0]['source_url'], 'https://www.mtr.com.hk/pdf/a.pdf')

    def test_airport_list_parses_nearest_date(self):
        content = '<ul><li><a href="/tc/media-centre/press-release/2026/pr_1">機場無人車</a><span>2026/11/18</span></li></ul>'
        self.assertEqual(news.parse_list(content, news.SOURCES[3])[0]['title'], '机场无人车')

    def test_render_escapes_html(self):
        r = row(); r['summary'] = '<script>bad()</script>'
        content = news.render_digest({'date': '2026-11-18', 'items': [r]})
        self.assertNotIn('<script>', content)
        self.assertIn('原文提要', content)

    def test_scheduler_preserves_morning_and_afternoon_jobs(self):
        self.assertEqual(mode('schedule', '0 8 * * *'), {'projects': True, 'news': False})
        self.assertEqual(mode('schedule', '0 14 * * *'), {'projects': False, 'news': True})
        self.assertEqual(mode('workflow_dispatch', requested='news'), {'projects': False, 'news': True})


class MailTests(unittest.TestCase):
    def test_duplicate_stale_failed_or_archived_news_not_sent(self):
        r = row()
        data = {'date': NOW.date().isoformat(), 'status': 'ok', 'items': [r]}
        self.assertEqual(len(mail.eligible_items(data, {}, NOW)), 1)
        self.assertEqual(mail.eligible_items(data, {'sent': {r['id']: NOW.isoformat()}}, NOW), [])
        self.assertEqual(mail.eligible_items({**data, 'status': 'failed'}, {}, NOW), [])
        self.assertEqual(mail.eligible_items({**data, 'date': '2026-11-17'}, {}, NOW), [])

    def test_missing_configuration_or_insecure_port_does_not_send(self):
        with patch.object(mail.smtplib, 'SMTP_SSL') as smtp:
            with self.assertRaises(ValueError):
                mail.send({'date': '2026-11-18'}, [row()], {})
            smtp.assert_not_called()
        with self.assertRaises(ValueError):
            mail.send({'date': '2026-11-18'}, [row()], {'SMTP_HOST': 'test', 'SMTP_USER': 'test', 'SMTP_PASSWORD': 'test', 'NEWS_MAIL_TO': 'test', 'SMTP_PORT': '25'})

    def test_mail_default_is_disabled(self):
        with patch.dict(mail.os.environ, {}, clear=True), patch.object(mail, 'send') as send:
            self.assertEqual(mail.main(), 0)
            send.assert_not_called()


if __name__ == '__main__':
    unittest.main()
