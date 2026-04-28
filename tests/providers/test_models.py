from cstation.providers.base import VPS, VPSStatus


def test_vps_has_expected_fields():
    vps = VPS(
        provider="hetzner",
        id="123",
        name="sg07",
        region="hel1",
        status=VPSStatus.RUNNING,
        ipv4="1.2.3.4",
    )
    assert vps.name == "sg07"
    assert vps.status.value == "running"

