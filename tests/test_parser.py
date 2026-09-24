import pytest

from app.parser import parse_targets


@pytest.mark.parametrize("text,host,port,sni", [
    ("portal.company.kz", "portal.company.kz", 443, "portal.company.kz"),
    ("portal.company.kz:8443", "portal.company.kz", 8443, "portal.company.kz"),
    ("https://portal.company.kz/path", "portal.company.kz", 443, "portal.company.kz"),
    ("https://portal.company.kz:8443/path", "portal.company.kz", 8443, "portal.company.kz"),
    ("10.0.0.5", "10.0.0.5", 443, None),
    ("10.0.0.5:8443", "10.0.0.5", 8443, None),
    ("[2001:db8::1]:443", "2001:db8::1", 443, None),
    ("2001:db8::1", "2001:db8::1", 443, None),
    ("PORTAL.Company.kz.", "portal.company.kz", 443, "portal.company.kz"),
    ("пример.рф", "xn--e1afmkfd.xn--p1ai", 443, "xn--e1afmkfd.xn--p1ai"),
])
def test_formats(text, host, port, sni):
    result = parse_targets(text)
    assert not result.errors
    target, = result.targets
    assert (target.host, target.port, target.sni) == (host, port, sni)


def test_networks_limits_duplicates_and_errors():
    result = parse_targets("# comment\n\n10.0.0.0/30\n10.0.0.1\n10.1.0.0/16\nbad host")
    assert [t.host for t in result.targets] == ["10.0.0.1", "10.0.0.2"]
    assert [e["line"] for e in result.errors] == [5, 6]
    assert len(parse_targets("10.0.0.0/31").targets) == 2
    assert len(parse_targets("10.0.0.1/32").targets) == 1
    assert len(parse_targets("10.0.0.0/22").targets) == 1022
    assert parse_targets("::/0").errors
    assert parse_targets("10.0.0.0/30", max_targets=1).errors


@pytest.mark.parametrize("delimiter", [";", ","])
def test_csv_bom_and_metadata(delimiter):
    text = "\ufefftarget;service_name;owner;criticality\r\nvpn.lab.local;VPN;Иванов;critical\n"
    text += "vpn.lab.local;;;\nvalid.lab.local;;;\n"
    result = parse_targets(text.replace(";", delimiter), "targets.csv")
    assert not result.errors
    assert len(result.targets) == 2
    assert result.targets[0].owner == "Иванов"
    assert result.targets[0].criticality == "critical"
    assert result.targets[1].owner is None


@pytest.mark.parametrize("text", ["bad host", "https://", "ftp://test.local", "user:pass@test.local",
                                   "test.local:0", "test.local:65536", "test.local:abc",
                                   "999.1.1.1", "-bad.local", "[bad]:443", "foo:"])
def test_invalid_lines_do_not_crash(text):
    result = parse_targets(text + "\nvalid.lab.local")
    assert result.errors[0]["line"] == 1
    assert len(result.targets) == 1


def test_csv_header_and_limits():
    assert parse_targets("host,owner\nfoo,bar", "x.csv").errors
    assert parse_targets("x" * (1024 * 1024 + 1)).errors
    result = parse_targets("target;criticality\nfoo;invalid\nbar;high;extra", "x.csv")
    assert len(result.errors) == 2
