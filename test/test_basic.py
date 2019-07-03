import sys
import os
import pytest
from subprocess import run

import asv_bwrap.main
from asv_bwrap.main import toml


def run_asv_bwrap(argv, check=True, redirect=None):
    old_stdout = sys.stdout
    redirect_file = None
    if redirect:
        redirect_file = open(redirect, 'w')
        sys.stdout = redirect_file

    try:
        try:
            asv_bwrap.main.main(list(argv))
        except SystemExit as err:
            if check:
                assert err.code == 0
            return err.code
    finally:
        if redirect_file is not None:
            redirect_file.close()
        sys.stdout = old_stdout


@pytest.fixture
def base_fixture(monkeypatch, tmpdir):
    monkeypatch.chdir(tmpdir)
    monkeypatch.setenv('GIT_CEILING_DIRECTORIES', str(tmpdir))


@pytest.fixture
def simple_fixture(base_fixture):
    # Setup outpit
    os.makedirs('output.git')
    run(['git', '-C', 'output.git', 'init', '--bare'])

    # Generate default config
    run_asv_bwrap(["--sample-config"], redirect="config.toml")

    # Edit config
    with open("config.toml", "r") as f:
        config = toml.load(f)
    config['upload'] = 'output.git'
    with open("config.toml", "w") as f:
        toml.dump(config, f)


def test_basic(simple_fixture):
    run_asv_bwrap(["config.toml", 'run', '--quick'])
