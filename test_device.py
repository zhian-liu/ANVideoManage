"""
设备连接测试脚本
用于诊断设备离线问题
"""
import socket
import sys

def test_port(host, port, protocol):
    """测试端口连接"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((host, port))
        sock.close()

        if result == 0:
            print(f"✅ {protocol} 端口 {port} 可访问")
            return True
        else:
            print(f"❌ {protocol} 端口 {port} 无法访问")
            return False
    except Exception as e:
        print(f"❌ {protocol} 端口 {port} 测试失败: {e}")
        return False

def main():
    host = "10.17.0.139"

    print(f"正在测试设备: {host}\n")
    print("=" * 50)

    # 测试常见端口
    ports = [
        (80, "HTTP/ONVIF"),
        (554, "RTSP"),
        (8554, "RTSP (备用)"),
        (8000, "HTTP (备用)"),
        (8080, "HTTP (备用)"),
    ]

    results = {}
    for port, protocol in ports:
        results[port] = test_port(host, port, protocol)

    print("\n" + "=" * 50)
    print("\n📊 测试总结:")
    print("-" * 50)

    open_ports = [p for p, status in results.items() if status]
    if open_ports:
        print(f"✅ 可访问的端口: {', '.join(map(str, open_ports))}")
    else:
        print("❌ 所有测试端口都无法访问")

    print("\n💡 建议:")
    if not any(results.values()):
        print("  • 检查设备是否真的在线")
        print("  • 检查防火墙设置")
        print("  • 确认 IP 地址是否正确")
    elif results.get(80):
        print("  • HTTP/ONVIF 端口可访问，尝试访问:")
        print(f"    http://{host}")

    if not results.get(554) and not results.get(8554):
        print("  • RTSP 端口不可访问，可能原因:")
        print("    - RTSP 服务未启动")
        print("    - 端口号不是标准的 554/8554")
        print("    - 需要在设备上启用 RTSP")

if __name__ == "__main__":
    main()
