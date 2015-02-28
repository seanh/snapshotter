[![Build Status](https://travis-ci.org/seanh/snapshotter.svg)](https://travis-ci.org/seanh/snapshotter)
[![Coverage Status](https://img.shields.io/coveralls/seanh/snapshotter.svg)](https://coveralls.io/r/seanh/snapshotter)


Snapshotter
===========

A script for making incremental snapshot backups of directories using rsync,
inspired by Michael Jakl's "Time Machine for every Unix out there":

<http://blog.interlinked.org/tutorials/rsync_time_machine.html>  
<http://blog.interlinked.org/tutorials/rsync_addendum.yaml.html>

I wanted a simple-as-possible `snapshotter SRC DEST` command that I could use
to backup any local or remote SRC directory to any local or remote DEST
directory, either from the command-line or from cron, that would make
simple snapshot incremental backups and not require any configuration,
or any command-line options or tricky arguments to remember. It needs to
be as simple as possible so that I can use it without thinking,
otherwise it won't get used.

Michael Jakl's shell script was just a little too simple to be useful. I
needed the script to accept SRC and DEST as command-line arguments, and
to automagically figure out whether SRC and DEST are local or remote and
behave accordingly. My Bourne shell scripting ability was not up to the
task, so I wrote it in Python instead.

Snapshotter is just a simple wrapper script for the rsync command, so it's very
reliable and works almost anywhere.

Usage
-----

	snapshotter [options] SRC DEST

Makes a snapshot backup of SRC inside DEST. Running the same snapshotter command
repeatedly creates incremental, snapshot backups of SRC inside DEST:

	DEST/
		latest.snapshot/
		2011-04-03T23_55_37.snapshot/
		2011-03-03T23_36_50.snapshot/
		2011-02-03T23_35_13.snapshot/
		.
		.
		.

`latest.snapshot` is a symlink to the most recent snapshot directory, in this
case `2011-04-03T23_55_37.snapshot`.

Each snapshot directory contains a complete copy of the SRC directory (but
hardlinks are used between snapshots to save bandwidth and storage space).
However the backup _does not cross filesystem boundaries_ within SRC, for each
mount-point encountered in SRC there will be just an empty directory in DEST.
If symlinks are encountered in SRC, the symlinks themselves are copied to the
snapshot, not the files or directories that the symlinks refer to.

To restore selected files just copy them back from a snapshot directory to the
live system. To restore an entire snapshot just copy the entire snapshot
directory back to the live system.

Old snapshots (or selected files within old snapshots) can be deleted without
affecting newer snapshots.

Either SRC or DEST (but not both) can be a remote directory, e.g.:
`you@yourdomain.org:/path/to/snapshots`.

If a snapshotter command is interrupted the transferred files will be stored in an
`incomplete.snapshot` directory in DEST, and the backup can be resumed by
running the same command again.

To exclude files from being backed up list them in a file at
`$HOME/.backup/excludes` on the machine that is running the snapshotter command, one
rsync exclude pattern per line.

Advantages
----------

+	**Super simple backup.**
	Just type: `snapshotter SRC DEST`.

+	**Super simple restore.**
	Just copy files back from snapshot directories.

+	**Local and remote**
	SRC and DEST are supported. You can backup a remote directory to a local
	one, backup a local directory to a remote one, or backup a local directory
	to another local directory (but you cannot backup a remote directory to
	another remote directory).

+	**Resumes interrupted backups.**
    Just run the same snapshotter command again.

+	**You can specify exclude patterns** for files to be excluded from the
	snapshots.

+	**Efficient with bandwidth.**
	Only the differences between files are transferred, and these are
	compressed.

+	**Somewhat efficient with storage space.**

	Uses rsync's `--link-dest` option so that in each new snapshot, files that
	have not changed since the previous snapshot will be hardlinks to their
	counterparts in the previous snapshot.  This means that although each
	snapshot directory contains a complete copy of the SRC directory, and older
	snapshots can always be deleted without harming newer snapshots, the amount
	of additional storage space taken by each new snapshot is only equal to the
	size of the files that changed since the previous snapshot.

	However, when a file has changed a complete new copy of that file (not a
	diff) will be stored in the new snapshot. If a file has been moved or
	renamed rsync _may_ be able to find a basis for the file in the previous
	snapshot, or it may backup a complete new copy of the file. If you restore
	a file from a snapshot older than the latest snapshot and then do another
	backup, a complete new copy of the file will be stored in the new snapshot.

Disadvantages
-------------

-	Does not compress snapshots.
	You could use a compression tool to compress old snapshots afterwards, but the
	latest snapshot has to be left uncompressed so that it can be compared to
	the current SRC directory when making the next snapshot.
-	Does not encrypt snapshots.
	You could use an encrypted filesystem for DEST and get encryption that way.
-	Does not do deduplication.

Example Commands
----------------

Backup a local directory to a local directory:

	snapshotter Mail Mail.snapshots

Backup a local directory to a local external drive:

	snapshotter Music /media/BACKUP/Music.snapshots

Backup your entire home directory to an external drive:

	snapshotter ~ /media/SNAPSHOTS

Backup your entire system to an external drive:

	sudo snapshotter / /media/SNAPSHOTS

(Because the backup does not cross filesystem boundaries, this will not attempt
to recursively backup /media/SNAPSHOTS into /media/SNAPSHOTS, but note that any
other mounted filesystems will not be backed up either.)

Backup a local directory to a remote directory:

	snapshotter Documents seanh@mydomain.org:Snapshots/Documents

Backup a remote directory to a local directory:

	snapshotter seanh@mydomain.org:Documents Snapshots/Documents

Make a local backup of your SDF homedir:

	snapshotter you@sdf.lonestar.org Snapshots/sdf.lonestar.org

Options
-------

`-d` or `--debug` or `-n` or `--dry-run`  
Perform a trial-run with no changes made, passes the `--dry-run` option to rsync.
