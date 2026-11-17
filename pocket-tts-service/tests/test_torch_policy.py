from pocket_local.torch_policy import cpu_build_ok


def test_cpu_suffix_without_cuda_is_accepted():
    ok, _reason = cpu_build_ok("2.5.1+cpu", None)
    assert ok is True


def test_pypi_cuda_wheel_and_rocm_are_rejected():
    assert cpu_build_ok("2.5.1+cu124", "12.4")[0] is False
    assert cpu_build_ok("2.5.1", None)[0] is False
    assert cpu_build_ok("2.5.1+cpu", "12.4")[0] is False
    assert cpu_build_ok("2.6.0+rocm6.2", None)[0] is False


def test_prepare_script_installs_cpu_torch_before_the_requirements():
    script = (__import__("pathlib").Path(__file__).resolve().parents[1] / "prepare-pocket.sh").read_text(encoding="utf-8")
    commands = [line.strip() for line in script.splitlines() if "pip install" in line]
    cpu = next(index for index, line in enumerate(commands) if "--index-url https://download.pytorch.org/whl/cpu" in line)
    requirements = next(index for index, line in enumerate(commands) if "-r requirements.txt" in line)
    assert cpu < requirements
    assert all("--extra-index-url" not in line for line in commands)
