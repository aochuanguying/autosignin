import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    # 采集间隔（秒）
    poll_interval: int = int(os.getenv("POLL_INTERVAL", "15"))

    # 主路由
    router_host: str = os.getenv("ROUTER_HOST", "192.168.50.1")
    router_ssh_port: int = int(os.getenv("ROUTER_SSH_PORT", "22"))
    router_ssh_user: str = os.getenv("ROUTER_SSH_USER", "admin")
    router_ssh_password: str = os.getenv("ROUTER_SSH_PASSWORD", "")
    router_ssh_key: str = os.getenv("ROUTER_SSH_KEY", "")

    # 旁路由
    gateway_host: str = os.getenv("GATEWAY_HOST", "192.168.50.2")
    gateway_ssh_port: int = int(os.getenv("GATEWAY_SSH_PORT", "22"))
    gateway_ssh_user: str = os.getenv("GATEWAY_SSH_USER", "root")
    gateway_ssh_password: str = os.getenv("GATEWAY_SSH_PASSWORD", "")
    gateway_ssh_key: str = os.getenv("GATEWAY_SSH_KEY", "")

    # NAS 群晖
    nas_host: str = os.getenv("NAS_HOST", "192.168.50.50")
    nas_port: int = int(os.getenv("NAS_PORT", "8088"))
    nas_scheme: str = os.getenv("NAS_SCHEME", "https")
    nas_user: str = os.getenv("NAS_USER", "admin")
    nas_password: str = os.getenv("NAS_PASSWORD", "")

    @property
    def nas_base_url(self) -> str:
        return f"{self.nas_scheme}://{self.nas_host}:{self.nas_port}"

    # X5-Server
    x5server_ip: str = os.getenv("X5SERVER_IP", "192.168.50.10")
    x5server_ssh_password: str = os.getenv("X5SERVER_SSH_PASSWORD", "")

    # 光猫（ONT/ONU）
    ont_host: str = os.getenv("ONT_HOST", "192.168.1.1")
    ont_telnet_port: int = int(os.getenv("ONT_TELNET_PORT", "23"))
    ont_user: str = os.getenv("ONT_USER", "admin")
    ont_password: str = os.getenv("ONT_PASSWORD", "")

    # 交换机
    switch_host: str = os.getenv("SWITCH_HOST", "192.168.10.12")
    switch_user: str = os.getenv("SWITCH_USER", "admin")
    switch_password: str = os.getenv("SWITCH_PASSWORD", "admin")

    # 连通性探测 URL
    probe_google: str = os.getenv("PROBE_GOOGLE", "https://www.google.com")
    probe_baidu: str = os.getenv("PROBE_BAIDU", "https://www.baidu.com")
    probe_office: str = os.getenv("PROBE_OFFICE", "http://10.19.0.1")

    # SSH 超时（秒）
    ssh_timeout: int = int(os.getenv("SSH_TIMEOUT", "5"))

    # HTTP 探测超时（秒）
    probe_timeout: int = int(os.getenv("PROBE_TIMEOUT", "10"))


settings = Settings()
