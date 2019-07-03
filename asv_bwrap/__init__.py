"""
Manage running Airspeed Velocity (asv) benchmarks in a lightweight
Bubblewrap sandbox.
"""

_version = "0.1.dev0"

if "dev" in _version:
    def get_git_version():
        # If in git checkout, add version suffix
        import subprocess, re
        from os.path import join, exists, dirname, abspath
        base_dir = join(abspath(dirname(__file__)), "..")
        if exists(join(base_dir, ".git")) and exists(join(base_dir, "pyproject.toml")):
            try:
                r = subprocess.run(["git", "rev-parse", "HEAD"], stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, check=True)
            except subprocess.CalledProcessError:
                return ""
            out = r.stdout.decode("ascii", errors="replace").strip()
            m = re.match("^[a-f0-9]{40,40}$", out)
            if m:
                return "+" + out[:8]
        return ""

    _version += get_git_version()

__version__ = _version
