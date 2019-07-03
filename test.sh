set -e -o pipefail -x
python3.5 -mpytest test/
python3.6 -mpytest test/
python3.7 -mpytest test/
