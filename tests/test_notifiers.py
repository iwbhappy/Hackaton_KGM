from unittest.mock import Mock
import httpx
from pydantic import SecretStr

from app.config import Settings
from app.notifiers.email import EmailNotifier
from app.notifiers.telegram import TelegramNotifier
from app.notifiers.teams import TeamsNotifier


def test_http_transports_escape_and_check_response(monkeypatch):
    response=httpx.Response(200,json={"ok":True},request=httpx.Request("POST","https://example.test"))
    post=Mock(return_value=response)
    monkeypatch.setattr(httpx,"post",post)
    TelegramNotifier("dummy-token","123").send("Тест","<script> & owner")
    assert post.call_args.kwargs["json"]["parse_mode"] == "HTML"
    assert "&lt;script&gt;" in post.call_args.kwargs["json"]["text"]
    post.return_value=httpx.Response(200,text="1",request=httpx.Request("POST","https://example.test"))
    TeamsNotifier("https://example.test/hook").send("Тест","Сводка")
    assert post.call_args.kwargs["json"]["@type"] == "MessageCard"


def test_email_starttls(monkeypatch):
    smtp=Mock(); connection=smtp.return_value.__enter__=Mock(return_value=Mock())
    smtp.return_value.__exit__=Mock()
    connection.return_value.send_message.return_value={}
    monkeypatch.setattr("smtplib.SMTP",smtp)
    config=Settings(_env_file=None,smtp_host="test",smtp_user="user",smtp_password=SecretStr("secret"),smtp_from="a@test",smtp_to="b@test")
    EmailNotifier(config).send("Тест","Сводка")
    connection.return_value.starttls.assert_called_once()
    connection.return_value.login.assert_called_once_with("user","secret")
