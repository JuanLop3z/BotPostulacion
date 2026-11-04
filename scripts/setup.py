"""Reproducible local setup. Never overwrites secrets or an existing environment."""
import argparse
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(arguments: list[str], cwd: Path = ROOT) -> None:
    subprocess.run(arguments, cwd=cwd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Configurar AutoJob AI localmente")
    parser.add_argument("--skip-install", action="store_true", help="Usar las dependencias ya instaladas")
    parser.add_argument("--env-only", action="store_true", help="Preparar secretos y directorios para Docker, sin instalar nada")
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        raise SystemExit("Se requiere Python 3.12 o superior")
    for directory in ("storage/cv", "storage/reports", "storage/screenshots"):
        (ROOT / directory).mkdir(parents=True, exist_ok=True)
    env_path = ROOT / ".env"
    if not env_path.exists():
        template = (ROOT / ".env.example").read_text(encoding="utf-8")
        template = template.replace("replace-with-a-random-private-value-at-least-32-characters", secrets.token_urlsafe(48))
        template = template.replace("POSTGRES_PASSWORD=local-only-change-me", "POSTGRES_PASSWORD=" + secrets.token_urlsafe(32))
        env_path.write_text(template, encoding="utf-8")
        if os.name != "nt":
            env_path.chmod(0o600)
        print("Creado .env con secretos aleatorios; no se mostrarán en consola.")
    if args.env_only:
        print("Configuración lista para docker compose up --build.")
        return
    venv = ROOT / ".venv"
    if not venv.is_dir():
        run([sys.executable, "-m", "venv", str(venv)])
    python = str(venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
    if not args.skip_install:
        run([python, "-m", "pip", "install", "--no-cache-dir", "-c", "backend/requirements.lock", "-e", "backend[dev]"])
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
        if npm is None:
            raise SystemExit("Instala Node.js 22+ y vuelve a ejecutar el script")
        run([npm, "ci", "--cache", ".npm-cache", "--no-audit", "--no-fund"], ROOT / "frontend")
    run([python, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"])
    print("Configuración lista. Consulta README.md para iniciar API y dashboard en dos terminales.")


if __name__ == "__main__":
    main()
