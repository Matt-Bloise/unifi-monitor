# test_parser.py -- Tests for NetFlow/IPFIX parser utilities

from unifi_monitor.netflow.parser import PROTO_MAP, extract_flow_fields, int_to_ipv4, int_to_ipv6


class TestIPConversion:
    def test_ipv4_zero(self):
        assert int_to_ipv4(0) == "0.0.0.0"

    def test_ipv4_loopback(self):
        # 127.0.0.1 = 0x7F000001
        assert int_to_ipv4(0x7F000001) == "127.0.0.1"

    def test_ipv4_private(self):
        # 192.168.1.1 = 0xC0A80101
        assert int_to_ipv4(0xC0A80101) == "192.168.1.1"

    def test_ipv6_zero(self):
        assert int_to_ipv6(0) == "::"

    def test_ipv6_loopback(self):
        assert int_to_ipv6(1) == "::1"


class TestExtractFlowFields:
    def test_ipv4_flow(self):
        data = {
            "sourceIPv4Address": 0xC0A80101,  # 192.168.1.1
            "destinationIPv4Address": 0x08080808,  # 8.8.8.8
            "sourceTransportPort": 54321,
            "destinationTransportPort": 443,
            "protocolIdentifier": 6,
            "octetDeltaCount": 1500,
            "packetDeltaCount": 10,
        }

        class FakeFlow:
            pass

        flow = FakeFlow()
        flow.data = data

        result = extract_flow_fields(flow)
        assert result["src_ip"] == "192.168.1.1"
        assert result["dst_ip"] == "8.8.8.8"
        assert result["src_port"] == 54321
        assert result["dst_port"] == 443
        assert result["protocol"] == 6
        assert result["bytes"] == 1500
        assert result["packets"] == 10

    def test_legacy_field_names(self):
        data = {
            "IPV4_SRC_ADDR": 0xC0A80101,
            "IPV4_DST_ADDR": 0x08080808,
            "L4_SRC_PORT": 12345,
            "L4_DST_PORT": 80,
            "PROTOCOL": 17,
            "IN_BYTES": 500,
            "IN_PKTS": 3,
        }

        class FakeFlow:
            pass

        flow = FakeFlow()
        flow.data = data

        result = extract_flow_fields(flow)
        assert result["src_ip"] == "192.168.1.1"
        assert result["dst_port"] == 80
        assert result["protocol"] == 17
        assert result["bytes"] == 500

    def test_missing_fields_default_to_zero(self):
        class FakeFlow:
            pass

        flow = FakeFlow()
        flow.data = {}

        result = extract_flow_fields(flow)
        assert result["src_ip"] == "0.0.0.0"
        assert result["dst_ip"] == "0.0.0.0"
        assert result["src_port"] == 0
        assert result["dst_port"] == 0
        assert result["protocol"] == 0
        assert result["bytes"] == 0
        assert result["packets"] == 0


class TestProtoMap:
    def test_known_protocols(self):
        assert PROTO_MAP[6] == "TCP"
        assert PROTO_MAP[17] == "UDP"
        assert PROTO_MAP[1] == "ICMP"
