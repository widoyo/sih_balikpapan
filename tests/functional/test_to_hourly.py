import datetime
from app.cli import to_hourly, append_to_hourly, append_to_daily
from flask import json

def test_process_to_hourly():
    """
    GIVEN data dari primabot, string JSON
    WHEN data diterima dari MQTT
    THEN outputkan JSON {"sampling": int(menit=0), "sn"}
    """
    GIVEN = '{"device": "primaBot/2002-2/0.6", "sampling": 1657612200, "distance": 4692, "signal_quality": 31, "battery": 9.96, "up_since": 1642763400, "time_set_at": 1657600500, "temperature": 40.66, "pressure": 994.12, "altitude": 160.51, "sensor": "Maxbotix"}'
    out = to_hourly(GIVEN)
    assert type(out) == type({})
    assert type(out.get("sampling")) == type(10.0)
    assert datetime.datetime.fromtimestamp(int(out.get("sampling"))).minute == 0
    assert type(out.get('sn') == type(''))
    assert len(out.get('sn')) >= 2
    print(out)

def test_append_to_hourly():
    """
    GIVEN data dari primabot, string JSON
    WHEN data diterima dari MQTT
    THEN outputkan JSON {"sampling": int(menit=0), "sn"}
    """
    GIVEN = '{"device": "primaBot/2002-2/0.6", "sampling": 1657612200, "distance": 4692, "signal_quality": 31, "battery": 9.96, "up_since": 1642763400, "time_set_at": 1657600500, "temperature": 40.66, "pressure": 994.12, "altitude": 160.51, "sensor": "Maxbotix"}'
    out = append_to_hourly(GIVEN)
    assert type(out) == type({})    