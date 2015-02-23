#!/usr/bin/env python
"""
A script for making incremental snapshot backups of directories using rsync.
See README.markdown for instructions.

"""
import datetime
import sys
import os
import logging
import subprocess
from optparse import OptionParser


def _run(command):
    """Run the given command as a subprocess.

    We wrap subprocess.call() in our own function to make it easy for tests
    to patch it.

    """
    return subprocess.call(command, shell=True)


def _datetime():
    """Return the current datetime as a string.

    We wrap datetime.datetime.now() instead of calling it directly to make
    it easy for tests to patch it.

    """
    return datetime.datetime.now().strftime("%Y-%m-%dT%H_%M_%S")


def is_remote(arg):
    """Return True if the given SRC or DEST argument specifies a remote path,
    False if it specifies a local path.

    """
    # If it has a : before the first / then it's a remote path.
    return ':' in arg.split('/')[0]

def parse_rsync_arg(arg):
    """Parse the given SRC or DEST argument and return tuple containing its
    user, host and path parts:

    user    :       The username in a remote path spec.
                            'seanh' in 'seanh@mydomain.org:/path/to/backups'.
                            None if arg is a local path or a remote path without a
                            username.
    host    :       The hostname in a remote path spec.
                            'mydomain.org' in 'seanh@mydomain.org:/path/to/backups'.
                            None if arg is a local path.
    path    :       The path in a local or remote path spec.
                            '/path/to/backups' in the remote path 'seanh@mydomain.org:/path/to/backups'.
                            '/media/BACKUP' in the local path '/media/BACKUP'.

    """
    logger = logging.getLogger("snapshotter.parse_rsync_arg")
    logger.debug("Parsing rsync arg %s" % arg)
    parts = {}
    if is_remote(arg):
        logger.debug("This is a remote path")
        before_first_colon, after_first_colon = arg.split(':',1)
        if '@' in before_first_colon:
            logger.debug("User is specified in the path")
            user = before_first_colon.split('@')[0]
        else:
            logger.debug("User is not specified in the path")
            user = None
        host = before_first_colon.split('@')[-1]
        path = after_first_colon
    else:
        logger.debug("This is a local path.")
        user = None
        host = None
        path = os.path.abspath(os.path.expanduser(arg))
    logger.debug("User: %s" % user)
    logger.debug("Host: %s" % host)
    logger.debug("Path: %s" % path)
    return user,host,path


class RsyncError(Exception):

    """Raised if rsync exits with non-zero status."""

    pass


class MoveError(Exception):

    """Raised if the `mv ... && rm ... && ln ...` command exits non-zero."""

    pass


def snapshot(SRC, DEST, debug=False, compress=True, fuzzy=True, progress=True,
             exclude=None):
    logger = logging.getLogger("snapshotter.snapshot")

    if debug:
        logging.basicConfig(level=logging.DEBUG)

    # Make sure SRC ends with / because this affects how rsync behaves.
    if not SRC.endswith(os.sep):
        SRC += os.sep

    logger.debug("SRC is: %s" % SRC)
    logger.debug("DEST is: %s" % DEST)

    date = _datetime()
    logger.debug("date is: %s" % date)

    user,host,snapshots_root = parse_rsync_arg(DEST)

    # Construct the list of options to be passed to rsync.
    rsync_options = ['--archive', # Copy recursively and preserve times, permissions, symlinks, etc.
        '--partial',
        '--partial-dir=partially_transferred_files', # Keep partially transferred files if the transfer is interrupted
        '--one-file-system', # Don't cross filesystem boundaries
        '--delete', # Delete extraneous files from dest dirs
        '--delete-excluded', # Also delete excluded files from dest dirs
        '--itemize-changes', # Output a change-summary for all updates
        '--link-dest=../latest.snapshot', # Make hard-links to the previous snapshot, if any
        '--human-readable', # Output numbers in a human-readable format
        '--quiet', # Suppress non-error output messages
        # '-F', # Enable per-directory .rsync-filter files.
        ]
    if compress:
        rsync_options.append('--compress') # Compress files during transfer
    if fuzzy:
        rsync_options.append('--fuzzy') # Look for basis files for any destination files that are missing
    if progress:
        rsync_options.append('--progress') # Print progress while transferring files
    if os.path.isfile(os.path.expanduser("~/.snapshotter/excludes")):
        rsync_options.append('--exclude-from=$HOME/.snapshotter/excludes') # Read exclude patterns from file
    if debug:
        rsync_options.append('--dry-run')
    if exclude is not None:
        for pattern in exclude:
            rsync_options.append("--exclude '%s'" % pattern)

    # Construct the rsync command.
    rsync_cmd = "rsync %s '%s' " % (' '.join(rsync_options),SRC)
    if host is not None:
        if user is not None:
            rsync_cmd += "%s@" % user
        rsync_cmd += "%s:" % host
    rsync_cmd += "%s/incomplete.snapshot" % snapshots_root

    # Construct the `mv && rm && ln` command to be executed after the rsync
    # command completes successfully.
    mv_cmd = ""
    if host is not None:
        mv_cmd += "ssh "
        if user is not None:
            mv_cmd += "%s@" % user
        mv_cmd += '%s "' % host
    mv_cmd += "mv %s/incomplete.snapshot %s/%s.snapshot " % (snapshots_root,snapshots_root,date)    
    mv_cmd += "&& rm -f %s/latest.snapshot " % snapshots_root
    mv_cmd += "&& ln -s %s.snapshot %s/latest.snapshot" % (date,snapshots_root)
    if host is not None:
        mv_cmd += '"'

    print rsync_cmd
    exit_status = _run(rsync_cmd)
    if exit_status != 0:
        raise RsyncError(exit_status)

    if not debug:
        print mv_cmd
        exit_status = _run(mv_cmd)
        if exit_status != 0:
            raise MoveError(exit_status)


class CommandLineArgumentsError(Exception):
    pass


def parse_cli(args=None):
    """Parse the command-line arguments."""
    if args is None:
        args = sys.argv[1:]

    parser = OptionParser(usage="usage: %prog [options] SRC DEST")
    parser.add_option(
        '-d', '--debug', '-n', '--dry-run', dest='debug', action='store_true',
        default=False,
        help="Perform a trial-run with no changes made (pass the --dry-run "
             "option to rsync)")
    parser.add_option(
        '--no-compress', dest='compress', action='store_false', default=True,
        help="Do not compress file data during transfer (do not pass the "
             "--compress argument to rsync)")
    parser.add_option(
        '--no-fuzzy', dest='fuzzy', action='store_false', default=True,
        help="Do not look for basis files for destination files that are "
             "missing (do not pass the --fuzzy argument to rsync)")
    parser.add_option(
        '--no-progress', dest='progress', action='store_false', default=True,
        help="Do not show progress during transfer (do not pass the "
             "--progress argument to rsync)")
    parser.add_option(
        '--exclude', type='string', dest='exclude', metavar="PATTERN",
        action='append',
        help="Exclude files matching PATTERN, e.g. --exclude '.git/*' (see "
             "the --exclude option in `man rsync`)")
    (options, args) = parser.parse_args(args)

    if len(args) != 2:
        raise CommandLineArgumentsError(parser.get_usage())

    src = args[0]
    dest = args[1]
    return (src, dest, options.debug, options.compress, options.fuzzy,
            options.progress, options.exclude)


def main():
    try:
        src, dest, debug, compress, fuzzy, progress, exclude = parse_cli()
    except CommandLineArgumentsError as err:
        sys.exit(err.message)
    try:
        snapshot(src, dest, debug, compress, fuzzy, progress, exclude)
    except (RsyncError, MoveError) as err:
        sys.exit(err.message)


if __name__ == "__main__":
    main()
