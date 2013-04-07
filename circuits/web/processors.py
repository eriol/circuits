import re

from .headers import HeaderElement
from .parsers import MultipartParser
from .parsers import QueryStringParser


def process_multipart(request, params):
    headers = request.headers

    ctype = headers.elements("Content-Type")
    if ctype:
        ctype = ctype[0]
    else:
        ctype = HeaderElement.from_str("application/x-www-form-urlencoded")

    ib = ""
    if "boundary" in ctype.params:
        # http://tools.ietf.org/html/rfc2046#section-5.1.1
        # "The grammar for parameters on the Content-type field is such that it
        # is often necessary to enclose the boundary parameter values in quotes
        # on the Content-type line"
        ib = ctype.params["boundary"].strip("\"")

    if not re.match("^[ -~]{0,200}[!-~]$", ib):
        raise ValueError("Invalid boundary in multipart form: %r" % (ib,))

    parser = MultipartParser(request.body, ib)
    for part in parser:
        if part.filename or not part.is_buffered():
            params[part.name] = part
        else:
            params[part.name] = part.value


def process_urlencoded(request, params):
    params.update(QueryStringParser(request.qs).result)
    params.update(QueryStringParser(request.body.getvalue()).result)


def process(request, params):
    ctype = request.headers.get("Content-Type")
    if not ctype:
        return

    mtype, mencoding = ctype.split("/", 1) if "/" in ctype else (ctype, None)

    if mtype == "multipart":
        process_multipart(request, params)
    elif mtype == "application" and mencoding == "x-www-form-urlencoded":
        process_urlencoded(request, params)
