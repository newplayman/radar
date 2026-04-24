from banker_radar.collectors.okx_market import parse_okx_oi_change


def test_parse_okx_oi_change_accepts_cli_list_schema():
    rows = [{"instId": "ESP-USDT-SWAP", "pxChgPct": "21.7150", "oiDeltaPct": "10.7832", "fundingRate": "-0.00774719", "volUsd24h": "8845783.52", "oiUsd": "1348727.36"}]

    features = parse_okx_oi_change(rows)

    assert features[0].symbol == "ESP-USDT-SWAP"
    assert features[0].price_change_pct == 21.715
    assert round(features[0].funding_rate_pct, 4) == -0.7747
