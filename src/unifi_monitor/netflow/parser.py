# parser.py -- IPFIX/NetFlow packet parser
# Handles IPFIX v10 (UCG-Max native format) and NetFlow v5/v9.
# UCG-Max sends mixed template/data packets -- each IPFIX set is parsed
# independently to avoid failing the whole packet on one unknown template.

from __future__ import annotations

import logging
import socket
import struct

import netflow
from netflow.ipfix import IPFIXHeader, IPFIXSet, IPFIXTemplateError, IPFIXTemplateNotRecognized

log = logging.getLogger(__name__)

PROTO_MAP = {1: "ICMP", 6: "TCP", 17: "UDP", 47: "GRE", 50: "ESP", 58: "ICMPv6"}


def int_to_ipv4(val: int) -> str:
    if val == 0:
        return "0.0.0.0"
    try:
        return socket.inet_ntoa(struct.pack("!I", val & 0xFFFFFFFF))
    except (struct.error, OSError):
        return str(val)


def int_to_ipv6(val: int) -> str:
    if val == 0:
        return "::"
    try:
        return socket.inet_ntop(socket.AF_INET6, val.to_bytes(16, "big"))
    except (struct.error, OSError, OverflowError):
        return str(val)


def extract_flow_fields(flow) -> dict:
    """Normalize a parsed flow record into a flat dict."""
    data = flow.data if hasattr(flow, "data") else flow
    if not isinstance(data, dict):
        data = {a: getattr(flow, a) for a in dir(flow) if not a.startswith("_")} if flow else {}

    ip_ver = data.get("ipVersion", 4)
    if ip_ver == 6:
        src_raw = data.get("sourceIPv6Address", 0)
        dst_raw = data.get("destinationIPv6Address", 0)
        src_ip = int_to_ipv6(src_raw) if isinstance(src_raw, int) else str(src_raw)
        dst_ip = int_to_ipv6(dst_raw) if isinstance(dst_raw, int) else str(dst_raw)
    else:
        src_raw = data.get("sourceIPv4Address", data.get("IPV4_SRC_ADDR", 0))
        dst_raw = data.get("destinationIPv4Address", data.get("IPV4_DST_ADDR", 0))
        src_ip = int_to_ipv4(src_raw) if isinstance(src_raw, int) else str(src_raw)
        dst_ip = int_to_ipv4(dst_raw) if isinstance(dst_raw, int) else str(dst_raw)

    return {
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "src_port": int(data.get("sourceTransportPort", data.get("L4_SRC_PORT", 0)) or 0),
        "dst_port": int(data.get("destinationTransportPort", data.get("L4_DST_PORT", 0)) or 0),
        "protocol": int(data.get("protocolIdentifier", data.get("PROTOCOL", 0)) or 0),
        "bytes": int(data.get("octetDeltaCount", data.get("IN_BYTES", 0)) or 0),
        "packets": int(data.get("packetDeltaCount", data.get("IN_PKTS", 0)) or 0),
    }


def parse_packet(data: bytes, templates: dict) -> list[dict]:
    """Parse a NetFlow/IPFIX UDP packet into a list of flow dicts.

    Args:
        data: Raw UDP payload
        templates: Mutable template cache dict (persists across calls)

    Returns:
        List of normalized flow dicts with keys:
        src_ip, dst_ip, src_port, dst_port, protocol, bytes, packets
    """
    if len(data) < 4:
        return []

    version = struct.unpack("!H", data[:2])[0]
    if version == 10:
        return _parse_ipfix(data, templates)
    else:
        return _parse_netflow(data, templates)


def _parse_netflow(data: bytes, templates: dict) -> list[dict]:
    try:
        export = netflow.parse_packet(data, templates)
        return [extract_flow_fields(f) for f in export.flows]
    except (struct.error, ValueError, KeyError) as e:
        log.debug("NetFlow parse error: %s", e)
        return []


def _parse_ipfix(data: bytes, templates: dict) -> list[dict]:
    ipfix_templates = templates.setdefault("ipfix", {})

    if len(data) < IPFIXHeader.size:
        return []

    header = IPFIXHeader(data[: IPFIXHeader.size])
    offset = IPFIXHeader.size
    flows = []

    while offset < header.length and offset < len(data):
        if offset + 4 > len(data):
            break
        set_id, set_len = struct.unpack("!HH", data[offset : offset + 4])
        if set_len < 4:
            break

        set_data = data[offset : offset + set_len]
        offset += set_len

        try:
            ipfix_set = IPFIXSet(set_data, ipfix_templates)
            if ipfix_set.is_template:
                ipfix_templates.update(ipfix_set.templates)
                for tid in list(ipfix_templates):
                    if ipfix_templates[tid] is None:
                        del ipfix_templates[tid]
            elif ipfix_set.is_data and ipfix_set.records:
                for flow in ipfix_set.records:
                    flows.append(extract_flow_fields(flow))
        except (IPFIXTemplateNotRecognized, IPFIXTemplateError):
            pass
        except (struct.error, ValueError, KeyError) as e:
            log.debug("IPFIX set error: %s", e)

    return flows
