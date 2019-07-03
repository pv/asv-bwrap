#!/usr/bin/python3
"""
%(prog)s [OPTIONS] config.toml ASV_RUN_ARGS...

Manage running ASV benchmarks in a lightweight Bubblewrap
sandbox.

Collects results and HTML output to a {workdir}/results Git
repository, which is optionally pushed to a remote repository.

examples:
  %(prog)s --sample-config > config.toml
  %(prog)s --shell config.toml
  %(prog)s --upload config.toml run --steps=11 NEW
"""

import os
import sys
import argparse
import subprocess
import shlex
import shutil
import contextlib
import termios
from pathlib import Path, PurePath

import qtoml as toml
import lockfile


SAMPLE_CONFIG = r'''
# Sample configuration file for asv_bwrap

# Work directory (where output etc. goes), relative to this file
dir = "./workdir"

# Git repository url or path to upload results to.  This repository
# will be cloned (outside sandbox) and benchmark results and generated
# html will be copied to it and committed.  Results go to 'master'
# branch; html pages replaces 'gh-pages'.
#
# With --upload, results are uploaded.
#
# If not given, a local repository is used instead.
upload = ""

# SSH deploy key for uploading results. Not available inside sandbox.
# If empty, not used.
ssh_key = ""

# List of files to copy to the sandbox directory (on each run)
copy_files = []

# List of directories and files to expose (read-only) inside the sandbox.
expose = ["/etc/resolv.conf",
          "/etc/nsswitch.conf",
          "/etc/alternatives",
          "/etc/pki",
          "/usr",
          "/usr/local",
          "/bin",
          "/lib",
          "/lib64"]

#
# Bash scripts to run inside the sandbox, in a sandbox dir.  HOME
# etc. are set to point to the sandbox directory, and the filesystem
# namespace is temporary and separate from the host system, except for the
# /home/{sandbox,html,results} directories.
#

[scripts]

# To run before other scripts
preamble = """
set -e -o pipefail

export REPO_URL="https://github.com/airspeed-velocity/asv.git"
export REPO_SUBDIR="."

source "$HOME/asv-bwrap-scripts/preamble1.sh"
"""

# To run when setting up the sandbox the first time
setup = """
run python3 -mvenv env
source env/bin/activate
run pip install asv virtualenv Cython
"""

# Default run script
#
# The asv 'results' directory should be symlinked to /home/results,
# and asv html output should be copied to /home/html.
run = """
source "$HOME/env/bin/activate"
source "$HOME/asv-bwrap-scripts/run1.sh"
"""
'''


def main():
    parser = argparse.ArgumentParser(usage=__doc__.strip())
    parser.add_argument("config_file", metavar="config.toml",
                        help="Configuration file to use.")
    parser.add_argument("command", nargs=argparse.REMAINDER, metavar="ASV_RUN_ARGS",
                        help="Arguments passed to the sandbox script")
    parser.add_argument("--sample-config", action=PrintSampleConfig,
                        help="Print a sample configuration file to stdout.")
    parser.add_argument("--upload", action="store_true",
                        help="After running, upload results.")
    parser.add_argument("--reset", action="store_true",
                        help="Clear sandbox before running.")
    parser.add_argument("--shell", action="store_true",
                        help="Start shell inside sandbox.")
    args = parser.parse_args()

    try:
        with open(args.config_file, "r") as f:
            config = parse_config(toml.load(f))
    except (ValueError, IOError) as err:
        print("error: in {!r}: {!s}".format(args.config_file, err),
              file=sys.stderr)
        sys.exit(1)

    os.chdir(Path(args.config_file).parent.absolute())

    base_dir = Path(config["dir"])

    if not base_dir.is_dir():
        os.makedirs(base_dir)

    with lockfile.LockFile(base_dir / "lock"):
        with save_terminal():
            do_run(args.command, config, upload=args.upload,
                   reset=args.reset, shell=args.shell)
            sys.exit(0)


def do_run(command, config, upload=False, reset=False, shell=False):
    base_dir = Path(config["dir"])
    sandbox_dir = base_dir / "sandbox"
    results_dir = base_dir / "results"
    html_dir = base_dir / "html"
    temp_dir = sandbox_dir / "tmp"
    script_dir = sandbox_dir / "asv-bwrap-scripts"
    script_src_dir = Path(__file__).parent / "scripts"

    if config["ssh_key"]:
        os.environ["GIT_SSH_COMMAND"] = "ssh -i " + shlex.quote(config["ssh_key"])

    if config["upload"]:
        upload_repo = config["upload"]
        if Path(upload_repo).exists() or (Path(upload_repo) / "refs").is_dir():
            upload_repo = Path(upload_repo).absolute()
    else:
        upload_repo = None

    # Clear sandbox if requested
    if reset:
        if sandbox_dir.exists():
            shutil.rmtree(sandbox_dir)

    # Setup results dir
    if not results_dir.is_dir():
        if upload_repo:
            run_git(["clone", upload_repo, results_dir], Path("."))
        else:
            os.makedirs(results_dir)
            try:
                run_git(["init"], results_dir)
            except:
                shutil.rmtree(results_dir)
                raise
    else:
        if upload_repo:
            r = run_git(["remote", "set-url", "origin", upload_repo], results_dir, check=False)
            if r.returncode != 0:
                run_git(["remote", "add", "origin", upload_repo], results_dir)
            run_git(["reset", "--hard"], results_dir)
            run_git(["fetch", "origin"], results_dir)
            r = run_git(["rev-parse", "origin/master"], results_dir, check=False, silent=True)
            if r.returncode == 0:
                run_git(["merge", "--ff-only", "origin/master"], results_dir)

    r = run_git(["rev-parse", "master"], results_dir, check=False, silent=True)
    if r.returncode == 0:
        run_git(["checkout", "master"], results_dir)

    # Create directories
    new_sandbox = not sandbox_dir.is_dir()
    for path in [sandbox_dir, html_dir, temp_dir, results_dir / "results"]:
        if not path.is_dir():
            os.makedirs(path)

    # Copy scripts
    if not script_dir.is_dir():
        os.makedirs(script_dir)

    for src in script_src_dir.glob('*.sh'):
        dst = script_dir / src.name
        shutil.copyfile(src, dst)

    # Copy files
    for fn in config["copy_files"]:
        fn = Path(fn)
        dst = sandbox_dir / fn.name
        if fn.is_dir():
            shutil.copytree(fn, dst)
        else:
            shutil.copyfile(fn, dst)

    # Create sandbox
    if new_sandbox:
        spawn_sandbox_script(base_dir, config["scripts"]["setup"], [], expose=config["expose"],
                             preamble=config["scripts"]["preamble"])

    # Run
    if shell:
        spawn_sandbox_script(base_dir, "exec bash", [], expose=config["expose"],
                             preamble=config["scripts"]["preamble"])
        return
    else:
        spawn_sandbox_script(base_dir, config["scripts"]["run"], command, expose=config["expose"],
                             preamble=config["scripts"]["preamble"])

    # Commit results and html
    run_git(["add", "-A", "results"], results_dir)
    run_git(["commit", "-q", "-m", "New results"], results_dir, check=False)

    run_git(["clean", "-f", "-d", "-x"], results_dir)
    run_git(["branch", "-D", "gh-pages"], results_dir, check=False)
    run_git(["checkout", "--orphan", "gh-pages"], results_dir)

    for fn in os.listdir(html_dir):
        src = html_dir / fn
        dst = results_dir / fn
        if src.is_dir():
            shutil.copytree(src, dst)
        elif src.is_file():
            shutil.copyfile(src, dst)

    run_git(["add", "-A", "."], results_dir)
    run_git(["commit", "-q", "-m", "Regenerate HTML"], results_dir)

    run_git(["checkout", "master"], results_dir)
    
    # Upload
    if upload and upload_repo:
        run_git(["push", "origin", "master"], results_dir)
        run_git(["push", "-f", "origin", "gh-pages"], results_dir)


def spawn_sandbox_script(base_dir, script, args, expose, preamble):
    with open(base_dir / "sandbox" / "_run_cmd.sh", "w") as f:
        f.write(preamble)
        f.write("\n\n")
        f.write(script)

    shell = shutil.which("bash")

    bwrap_args = [
        "--unshare-all",
        "--share-net",
        "--new-session",
        "--die-with-parent",
        "--proc", "/proc",
        "--dev", "/dev",
    ]

    rw_expose = [
        (base_dir / "sandbox", "/home/sandbox"),
        (base_dir / "results" / "results", "/home/results"),
        (base_dir / "html", "/home/html"),
    ]

    for src, dst in rw_expose:
        if os.path.exists(src):
            bwrap_args += ["--bind", src, dst]

    for fn in expose:
        if os.path.exists(fn):
            bwrap_args += ["--ro-bind", fn, fn]

    bwrap_args += [
        "--chdir", "/home/sandbox",
        "--setenv", "HOME", "/home/sandbox",
        "--setenv", "TMPDIR", "/home/sandbox/tmp",
        shell, "_run_cmd.sh"
    ]

    bwrap_args += list(args)

    run(["bwrap"] + bwrap_args, check=True)


def run_git(args, repo_dir, check=True, silent=False):
    env = dict(os.environ)
    env["GIT_CEILING_DIRECTORIES"] = repo_dir.absolute()
    if silent:
        kwargs = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        kwargs = {}
    return run(["git", "-C", repo_dir] + args, env=env, check=check, **kwargs)


def run(cmd, *args, **kwargs):
    cmd_str = " ".join(shlex.quote(str(c)) for c in cmd)
    if "cwd" in kwargs:
        cmd_str = "(cd {}; {})".format(shlex.quote(kwargs["cwd"]), cmd_str)
    cmd_str = "\n$ " + cmd_str
    print(cmd_str)
    try:
        return subprocess.run(cmd, *args, **kwargs)
    except KeyboardInterrupt:
        print("\nerror: interrupted")
        sys.exit(2)
    except subprocess.CalledProcessError as err:
        print("\nerror: command exit status {}".format(err.returncode))
        sys.exit(1)


@contextlib.contextmanager
def save_terminal():
    """
    Restore terminal input state e.g. if sandbox shell changes it
    """
    if not sys.stdin.isatty():
        yield
        return

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)

    try:
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSANOW, old)


def parse_config(config, schema=None, keys=()):
    config = dict(config)

    if schema is None:
        schema = toml.loads(SAMPLE_CONFIG)

    parsed = {}

    for key, value in schema.items():
        if key not in config:
            if isinstance(value, (bool, int)):
                parsed[key] = value
            else:
                parsed[key] = type(value)()
        elif isinstance(config[key], type(value)):
            if isinstance(value, dict):
                parsed[key] = parse_config(config.pop(key), value,
                                           keys=keys + (key,))
            else:
                parsed[key] = config.pop(key)
        else:
            raise ValueError("in {!r}: invalid value {!r}".format(
                list(keys + (key,)), value))

    if config:
        raise ValueError("in {!r}: unknown options {!r}".format(
            list(keys), sorted(config.keys())))

    return parsed


class PrintSampleConfig(argparse.Action):
    def __init__(self, option_strings, dest, help=None):
        super().__init__(option_strings, dest, nargs=0, help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        print(SAMPLE_CONFIG.lstrip())
        sys.exit(0)


if __name__ == "__main__":
    main()
