export PATH="/usr/lib/ccache:/usr/local/lib/f90cache:/usr/lib64/ccache:/usr/local/lib64/f90cache:$PATH"
export CCACHE_UNIFY=1
export CCACHE_SLOPPINESS=file_macro,time_macros
export CCACHE_COMPRESS=1
export CCACHE_MAXSIZE=1G
export OPT="-O2"
export FOPT="-O2"
export NPY_NUM_BUILD_JOBS=2
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OMP_NUM_THREADS=1
export SOURCE_DATE_EPOCH=1506870070

run() { echo; echo "sandbox\$" "$@"; "$@"; }

# Strip Python CFLAGS bad for ccache / old code
if [ -x "$HOME/env/bin/python" ]; then
    PY_CFLAGS=$($HOME/env/bin/python -c 'import sysconfig; print(sysconfig.get_config_var("CFLAGS"))')
else
    PY_CFLAGS=$(python -c 'import sysconfig; print(sysconfig.get_config_var("CFLAGS"))')
fi
CFLAGS=$(echo "$PY_CFLAGS" | sed -E -e 's/(-flto|-Werror=[a-z=-]*|-g[0-9]*|-fpedantic-errors)( |$)/ /g;')
export CFLAGS
export NPY_DISTUTILS_APPEND_FLAGS=0
