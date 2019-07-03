import re
import subprocess
from os.path import join, exists, dirname, relpath, normpath


try:
    from pkg_resources import get_distribution
except ImportError:
    pkg_resources = None


base_dir = join(dirname(__file__), "..")


def _get_git_version_suffix(base_version):
    # If in git checkout, add version suffix
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


def _get_pkg_version_suffix(base_version):
    # If installed package, get version
    try:
        d = get_distribution('asv_bwrap')
    except:
        return ""

    if normpath(d.location) != normpath(base_dir):
        return ""

    if d.version.startswith(base_version):
        m = re.match("^[+-]([a-f0-9]{8,8})$", d.version[len(base_version):])
        if m:
            return "+" + m.group(1)

    return ""


def _get_dir_version_suffix(base_version):
    # sdist
    name = dirname(normpath(base_dir))
    expected = 'asv-bwrap-' + base_version + '+'

    if name.startswith(expected):
        m = re.match("^[+-]([a-f0-9]{8,8})$", name[len(expected):])
        if m:
            return "+" + m.group(1)

    return ""


def get_dev_version_suffix(base_version):
    return (_get_git_version_suffix(base_version) or
            _get_pkg_version_suffix(base_version) or
            _get_dir_version_suffix(base_version) or "")
