import pytest
from app.analysis.hostname import match_hostname


@pytest.mark.parametrize("host,dns,ips,cn,expected", [
    ("a.test", ["a.test"], [], None, True),
    ("A.TEST.", ["a.test"], [], None, True),
    ("a.test", ["*.test"], [], None, True),
    ("test", ["*.test"], [], None, False),
    ("a.b.test", ["*.test"], [], None, False),
    ("abc.test", ["a*.test"], [], None, False),
    ("a.test", [], [], "a.test", True),
    ("a.test", ["b.test"], [], "a.test", False),
    ("a.test", [], ["127.0.0.1"], "a.test", False),
    ("127.0.0.1", [], ["127.0.0.1"], None, True),
    ("127.0.0.1", ["127.0.0.1"], [], "127.0.0.1", False),
    ("127.0.0.1", [], [], "127.0.0.1", True),
    ("2001:db8::1", [], ["2001:0db8:0:0:0:0:0:1"], None, True),
    ("пример.рф", ["xn--e1afmkfd.xn--p1ai"], [], None, True),
])
def test_hostname(host, dns, ips, cn, expected):
    assert match_hostname(host, dns, ips, cn) is expected
