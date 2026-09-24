from datetime import datetime, timedelta, timezone
import pytest
from app.analysis.status import days_remaining, expiration_status
from app.config import DEFAULTS


@pytest.mark.parametrize("days,expected", [(61, "OK"), (60, "INFO"), (31, "INFO"),
    (30, "WARNING"), (15, "WARNING"), (14, "CRITICAL"), (0, "CRITICAL"), (-1, "EXPIRED"), (None, "ERROR")])
def test_boundaries(days, expected):
    assert expiration_status(days) == expected


def test_custom_and_floor():
    config = dict(DEFAULTS, threshold_info=40)
    assert expiration_status(45, config) == "OK"
    assert expiration_status(45, dict(DEFAULTS, threshold_warning=50)) == "WARNING"
    with pytest.raises(ValueError):
        expiration_status(45, dict(config, threshold_warning=50))
    now = datetime.now(timezone.utc)
    assert days_remaining(now - timedelta(seconds=1), now) == -1
    assert days_remaining(now + timedelta(hours=23), now) == 0
