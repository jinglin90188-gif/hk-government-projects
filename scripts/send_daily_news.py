"""Opt-in SMTP delivery; never enable without the user's mailbox configuration."""
import json
import os
import smtplib
import ssl
import sys
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.daily_news import render_digest, write_json


def eligible_items(data, ledger, now):
    if data.get('status') not in ('ok', 'partial') or data.get('date') != now.date().isoformat():
        return []
    sent = ledger.get('sent', {})
    return [r for r in data.get('items', []) if r['id'] not in sent
            and timedelta(0) <= now - datetime.fromisoformat(r['published_at']) <= timedelta(hours=48)]


def send(data, items, env):
    required = ['SMTP_HOST', 'SMTP_USER', 'SMTP_PASSWORD', 'NEWS_MAIL_TO']
    missing = [k for k in required if not env.get(k)]
    if missing:
        raise ValueError('邮件尚未配置：' + ', '.join(missing))
    port = int(env.get('SMTP_PORT') or '465')
    if port not in (465, 587):
        raise ValueError('只支持加密SMTP端口465或587')
    msg = EmailMessage()
    msg['Subject'] = '香港交通科技每日新闻｜' + data['date'] + '｜' + str(len(items)) + '条'
    msg['From'] = env['SMTP_USER']
    msg['To'] = env['NEWS_MAIL_TO']
    msg.set_content('\n\n'.join(r['title'] + '\n' + r.get('summary', '') + '\n' + r['source_url'] for r in items))
    msg.add_alternative(render_digest(data, items), subtype='html')
    context = ssl.create_default_context()
    client = smtplib.SMTP_SSL(env['SMTP_HOST'], port, timeout=30, context=context) if port == 465 else smtplib.SMTP(env['SMTP_HOST'], port, timeout=30)
    with client as smtp:
        if port == 587:
            smtp.starttls(context=context)
        smtp.login(env['SMTP_USER'], env['SMTP_PASSWORD'])
        refused = smtp.send_message(msg)
        if refused:
            raise RuntimeError('收件服务器未接受全部收件人')


def main():
    if os.environ.get('NEWS_MAIL_ENABLED', '').lower() != 'true':
        print('邮件未启用：仅更新网站，未发送邮件。')
        return 0
    data = json.loads((ROOT / 'dist/news.json').read_text(encoding='utf-8'))
    path = ROOT / 'state/news-mail.json'
    ledger = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'sent': {}}
    now = datetime.now(ZoneInfo('Asia/Hong_Kong'))
    items = eligible_items(data, ledger, now)
    if not items:
        print('没有未发送的新鲜新闻，本次不发送。')
        return 0
    # Persist only after SMTP has accepted the message. SMTP cannot guarantee
    # exactly-once delivery if a runner dies after send and before ledger commit.
    send(data, items, os.environ)
    ledger.setdefault('sent', {}).update({r['id']: now.isoformat() for r in items})
    write_json(path, ledger)
    print('邮件已被发件服务器接受，共 ' + str(len(items)) + ' 条。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
