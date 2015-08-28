import sys


if sys.version_info[0] == 2:
    PY2, PY3 = True, False
elif sys.version_info[0] == 3:
    PY2, PY3 = False, True


try:
    STDOUT_ENCODING = sys.stdout.encoding or sys.getdefaultencoding()
except AttributeError:
    STDOUT_ENCODING = sys.getdefaultencoding()
