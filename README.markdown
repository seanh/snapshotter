[![Build Status](https://travis-ci.org/seanh/snapshotter.svg)](https://travis-ci.org/seanh/snapshotter)
[![Coverage Status](https://img.shields.io/coveralls/seanh/snapshotter.svg)](https://coveralls.io/r/seanh/snapshotter)

Snapshotter
===========

Snapshotter provides a simple, configuration-free `snapshotter SRC DEST`
command that makes incremental, snapshot backups of directories. It uses rsync
to do the actual copying and has high test coverage.


Requirements
------------

[rsync](https://rsync.samba.org/) and [Python](https://www.python.org/) 2.7,
3.2, 3.3, 3.4 or 3.5.


Installation
------------

    sudo pip install snapshotter


Usage
-----

To backup a local source directory to a local target directory:

    snapshotter /path/to/source/dir/to/backup /path/to/backup/destination

To backup a remote directory to a local directory:

    snapshotter you@yourdomain.org:/path/to/source /path/to/backup/destination

To backup a local directory to a remote directory:

    snapshotter /path/to/source you@yourdomain.org:/path/to/snapshots

See `man rsync` for complete documentation of the syntax for specifying local
and remote paths.

You don't need to worry about whether local or remote source or destination
paths have a trailing `/` or not - Snapshotter will do the right thing.

Each time you want to make another backup just run the same snapshotter command
again. Snapshotter will create snapshots like this in the destination
directory:

    /path/to/backup/destination/
        latest.snapshot/
        2011-04-03T23_55_37.snapshot/
        2011-03-03T23_36_50.snapshot/
        2011-02-03T23_35_13.snapshot/

`latest.snapshot` is a symlink to the most recent snapshot directory, in this
case `2011-04-03T23_55_37.snapshot`.

Each snapshot directory contains a complete copy of the source directory, but
any files that had not changed since the previous snapshot are *hard linked* to
their corresponding files in the previous snapshot. This means that:

* The amount of new disk space used by each new snapshot is only equal to the
  size of the files that have changed or are new since the last snapshot.

* The amount of data transferred to make each new snapshot is only equal to the
  size of the files that have changed or are new since the last snapshot,
  compressed.

* Old snapshots can be deleted without harming new snapshots at all -
  each snapshot is an independent complete copy.

  (But _don't modify files in snapshots_, not even their metadata such as permissions,
  as this will also modify the file in any other snapshots that have hardlinks to it.)
  
Backups don't cross filesystem boundaries. For each mount-point encountered in
the source directory there'll be just an empty directory in the snapshot.
This means you can backup your entire filesystem to an external drive with a
command like `sudo snapshotter / /media/SNAPSHOTS` and it won't try to
recursively backup `/media/SNAPSHOTS` into `/media/SNAPSHOTS`.

If symlinks are encountered in the source directory the symlinks themselves are
copied to the snapshot, not the files or directories that the symlinks refer
to.


### Recovering Files from Snapshots

To restore selected files just copy them back from a snapshot directory to the
live system. To restore an entire snapshot just copy the entire snapshot
directory back to the live system.


### Resuming Backups

If a `snapshotter` command is interrupted for any reason (e.g. you `Ctrl-c` it)
just run the same command again to resume making the snapshot where you left
off.

Snapshots are written to an `incomplete.snapshot` directory in the destination
directory first and then moved to a `YYYY-MM-DDTHH_MM_SS.snapshot` directory
when complete. If a snapshot is interrupted the `incomplete.snapshot` directory
will be left behind and used to resume the snapshot if you run it again.


### Suspend After Backup

You can put your computer to sleep automatically after a backup finishes simply
by chaining two commands in a shell:

    snapshotter [OPTIONS] <SRC> <DST>; suspend
    
Where `suspend` is a script on your `PATH` that suspends your computer without
requiring sudo powers. On Ubuntu 14.04 this works for me:

    #!/bin/sh -e
    dbus-send --system --print-reply --dest="org.freedesktop.UPower" /org/freedesktop/UPower org.freedesktop.UPower.Suspend


Options
-------

To do a dry-run (just print out what would be done, but don't actually copy any
files) do:

    snapshotter --dry-run SRC DEST

Snapshotter automatically deletes your oldest snapshots when necessary to make
space for a new snapshot. By default it will always keep at least 3 snapshots.
To change this number use the `--min-snapshots` argument:

    snapshotter --min-snapshots 10 SRC DEST

You can pass any rsync options to snapshotter and it will pass them on to
rsync. For example:

    snapshotter --exclude='*~' SRC DEST

See `man rsync` for all the available options.

For complete documentation of Snapshotter's command-line interface run:

    snapshotter -h

* * *

Snapshotter is inspired by Michael Jakl's
"Time Machine for every Unix out there":

<http://blog.interlinked.org/tutorials/rsync_time_machine.html>  
<http://blog.interlinked.org/tutorials/rsync_addendum.yaml.html>
