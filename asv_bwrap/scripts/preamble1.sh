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

run() { echo; echo "sandbox\$" "$@"; "$@"; }

# Strip Python CFLAGS bad for ccache / old code
PY_CFLAGS=$(python -c 'import sysconfig; print(sysconfig.get_config_var("CFLAGS"))')
CFLAGS=$(echo "$PY_CFLAGS" | sed -E -e 's/(-flto|-Werror=[a-z=-]*|-g[0-9]*|-fpedantic-errors)( |$)/ /g;')
export CFLAGS
export NPY_DISTUTILS_APPEND_FLAGS=0
