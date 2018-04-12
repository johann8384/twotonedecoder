#!/bin/bash

usage() { echo "Usage: $0 [-t <string>] -w <string>" 1>&2; exit 1; }

while getopts ":t:w:" o; do
    case "${o}" in
        t)
            t=${OPTARG}
            ;;
        w)
            w=${OPTARG}
            ;;
        *)
            usage
            ;;
    esac
done
shift $((OPTIND-1))

if [ -z "${w}" ]; then
    usage
fi

if [ -z "${t}" ]; then
    t=$w
fi

echo "t = ${t}"
echo "w = ${w}"
faad -o $t.wav $w
sox $t.wav $t-trim.wav silence -l 1 0.1 1% -1 2.0 1

