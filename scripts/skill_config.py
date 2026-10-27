"""스킬 루트의 config.env(git 무시)를 읽는다. 외부 의존성이 없어 모든 스크립트가 쓴다."""
import os

CONFIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.env")


def load_config(path=CONFIG):
    """config.env 값을 환경변수가 없을 때만 채운다. 파일이 없으면 아무것도 하지 않는다."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), os.path.expanduser(v.strip().strip('"').strip("'")))
