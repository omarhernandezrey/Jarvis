import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "install.sh"
INSTALL_PS1 = REPO_ROOT / "install.ps1"
MAKEFILE = REPO_ROOT / "Makefile"


def test_install_sh_exists_and_is_executable():
    assert INSTALL_SH.is_file()
    assert os.access(INSTALL_SH, os.X_OK)


def test_install_sh_has_valid_syntax():
    result = subprocess.run(
        ["bash", "-n", str(INSTALL_SH)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_install_sh_checks_python_version():
    content = INSTALL_SH.read_text()
    assert "3.11" in content


def test_install_sh_checks_ollama():
    content = INSTALL_SH.read_text()
    assert "ollama" in content


def test_install_sh_installs_requirements():
    content = INSTALL_SH.read_text()
    assert "requirements.txt" in content


def test_install_sh_never_runs_sudo_or_apt():
    # El script puede sugerir el comando `sudo apt install ...` dentro de un
    # echo, pero nunca debe ejecutarlo el mismo (ninguna linea de codigo,
    # fuera de un echo/printf, puede empezar con sudo o apt).
    for line in INSTALL_SH.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith(("echo", "printf", "#")):
            continue
        assert not stripped.startswith("sudo"), f"ejecuta sudo directamente: {line!r}"
        assert not stripped.startswith("apt "), f"ejecuta apt directamente: {line!r}"


def test_install_ps1_exists():
    assert INSTALL_PS1.is_file()


def test_install_ps1_checks_python_version():
    content = INSTALL_PS1.read_text()
    assert "3.11" in content


def test_install_ps1_checks_ollama():
    content = INSTALL_PS1.read_text()
    assert "ollama" in content


def test_install_ps1_installs_requirements():
    content = INSTALL_PS1.read_text()
    assert "requirements.txt" in content


def test_install_ps1_documents_untested_on_real_windows():
    # No hay maquina Windows ni interprete de PowerShell en este entorno de
    # desarrollo para probar install.ps1 de verdad (ver Tarea 4.1 del plan):
    # el script debe dejarlo dicho explicitamente, no fingir que se probo.
    content = INSTALL_PS1.read_text().lower()
    assert "no se ha podido ejecutar ni probar" in content


def test_makefile_exists():
    assert MAKEFILE.is_file()


def test_makefile_has_required_targets():
    content = MAKEFILE.read_text()
    for target in ("install:", "run:", "test:", "lint:", "clean:"):
        assert target in content


def test_makefile_targets_dry_run_cleanly():
    for target in ("install", "run", "test", "lint"):
        result = subprocess.run(
            ["make", "-n", target],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"make -n {target} failed: {result.stderr}"
