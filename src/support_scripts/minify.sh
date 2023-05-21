#!/bin/bash
#
# Minifier for HTML, CSS and JavaScript files.
#
# For JS and CSS, it uses these online minifiers:
# JS: https://www.toptal.com/developers/javascript-minifier/documentation/curl
# CSS: https://www.toptal.com/developers/cssminifier/documentation/curl
#
# For HTML, a custom sed scripts is used.
#
# The only argument is the name of a file to minify, and the minified version
# will be printed on stdout.
#

ME=$(basename $0)
INFILE="$1"

if [ ! -f "$INFILE" ]; then
    cat << _EOF_

ERROR: No input file, or file does not exist.

Usage: $ME file

Where:
    file: The path to the HTML, CSS or JS file to minify.

_EOF_
    
    exit 1
fi

FTYPE=${INFILE##*.}
if [ "$FTYPE" = "html" ]; then
    sed -e 's/^\s\+//' -e 's/\s\+$//' -e '/^\s*$/d' ${INFILE}
elif [ "$FTYPE" = "css" ]; then
    curl -X POST -s --data-urlencode "input@${INFILE}" https://www.toptal.com/developers/cssminifier/api/raw
elif [ "$FTYPE" = "js" ]; then
    curl -X POST -s --data-urlencode "input@${INFILE}" https://www.toptal.com/developers/javascript-minifier/api/raw
else
    echo -e "\nNot a known file type: $INFILE\n"
    exit 2
fi
