from threading import Thread
from flask import current_app, render_template
from flask_mail import Message
from app import mail
import logging
logging.basicConfig(level=logging.DEBUG)


def send_async_email(app, msg):
    with app.app_context():
        mail.send(msg)


def send_email(to, subject, template, **kwargs):
    app = current_app._get_current_object()
    msg = Message(app.config['RANDOMIST_MAIL_SUBJECT_PREFIX'] + ' ' + subject,
                  sender=app.config['RANDOMIST_MAIL_SENDER'], recipients=[to])
    msg.body = render_template(template + '.txt', **kwargs)
    msg.html = render_template(template + '.html', **kwargs)
    Thread(target=send_async_email, args=[app, msg]).start()

