import socket
import uvicorn
from cradleecho.config import settings

def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    ip = get_lan_ip()
    print(f"Starting Cribby daemon on http://{ip}:{settings.port}")
    uvicorn.run("cradleecho.main:app", host=settings.host, port=settings.port)
