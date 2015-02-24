import os
import tempfile
import sys
import shutil

import mock
import nose.tools

import snapshotter


def _this_directory():
    """Return this Python module's directory as a string."""
    return os.path.split(sys.modules[__name__].__file__)[0]


class TestCLI(object):

    """Tests for the parse_cli() function."""

    def test_with_no_src_or_dest_args(self):
        nose.tools.assert_raises(
            snapshotter.CommandLineArgumentsError, snapshotter.parse_cli,
            args=[])

    def test_with_no_dest_arg(self):
        nose.tools.assert_raises(
            snapshotter.CommandLineArgumentsError, snapshotter.parse_cli,
            args=["/home/fred"])

    def test_with_default_options(self):
        src, dest, debug, compress, fuzzy, progress, exclude = (
            snapshotter.parse_cli(args=["/home/fred", "/media/backup"]))
        assert src == "/home/fred"
        assert dest == "/media/backup"
        assert debug is False
        assert compress is True
        assert fuzzy is True
        assert progress is True
        assert exclude is None

    def test_dry_run(self):
        for option in ("-n", "--dry-run"):
            _, _, debug, _, _, _, _ = snapshotter.parse_cli(
                args=[option, "/home/fred", "/media/backup"])
            assert debug is True


class TestIsRemote(object):

    """Unit tests for the is_remote() function."""

    pass


class TestParseRsyncArg(object):

    """Unit tests for the parse_rsync_arg() function."""

    pass


class TestFunctional(object):

    """Functional tests that actually run rsync and other commands."""

    @mock.patch("snapshotter.snapshotter._datetime")
    def test_functional(self, mock_datetime_function):
        """One functional test that actually calls rsync and copies files."""
        datetime = "2015-02-23T18_58_02"
        mock_datetime_function.return_value = datetime

        try:
            dest = tempfile.mkdtemp()
            src = os.path.join(_this_directory(), "test_data")

            snapshotter.snapshot(src, dest)

            snapshot_dir = os.path.join(dest, datetime + ".snapshot")
            assert os.path.isdir(snapshot_dir)

            for file_ in os.listdir(src):
                assert os.path.isfile(os.path.join(snapshot_dir, file_))

            latest_symlink = os.path.join(dest, "latest.snapshot")
            assert os.path.islink(latest_symlink)
            assert os.path.realpath(latest_symlink) == snapshot_dir
        finally:
            shutil.rmtree(dest)


def _get_args(call_args):
    """Return the arg string passed to a mock _run() function."""
    positional_args, keyword_args = call_args
    assert keyword_args == {}
    assert len(positional_args) == 1
    return positional_args[0]


class TestSnapshot(object):

    """Tests for the snapshot() function."""

    def setup(self):
        """Patch the _run() and _datetime() functions."""
        self.run_patcher = mock.patch('snapshotter.snapshotter._run')
        self.mock_run_function = self.run_patcher.start()
        self.mock_run_function.return_value = 0

        self.datetime_patcher = mock.patch('snapshotter.snapshotter._datetime')
        self.mock_datetime_function = self.datetime_patcher.start()
        self.datetime = "2015-02-23T18_58_02"
        self.mock_datetime_function.return_value = self.datetime

    def teardown(self):
        self.run_patcher.stop()
        self.datetime_patcher.stop()

    def test_passing_dry_run_to_rsync(self):
        """snapshot() should pass -n/--dry-run on to rsync."""
        src = "/home/fred"
        dst = "/media/backup"

        snapshotter.snapshot(src, dst, debug=True)

        assert self.mock_run_function.call_count == 1, (
            "When snapshot() is given the -n/--dry-run arg it should only run "
            "one command (rsync) - the mv command shouldn't be run")
        args = _get_args(self.mock_run_function.call_args)
        assert "--dry-run" in args, (
            "snapshot() should pass the -n/--dry-run argument on to rsync")

    def test_not_passing_dry_run_to_rsync(self):
        """If --n isn't given to snapshotter it shouldn't be given to rsync."""
        src = "/home/fred"
        dst = "/media/backup"

        snapshotter.snapshot(src, dst, debug=False)

        assert self.mock_run_function.call_count == 2, (
            "Both the rsync and mv commands should be run")
        args = _get_args(self.mock_run_function.call_args_list[0])
        assert "--dry-run" not in args

    def test_without_trailing_slash(self):
        """A trailing / should be appened to SRC if not given."""
        src = "/home/fred"  # No trailing slash.
        dst = "/media/backup"

        snapshotter.snapshot(src, dst)

        args = _get_args(self.mock_run_function.call_args_list[0])
        assert "/home/fred/" in args

    def test_with_trailing_slash(self):
        """A trailing / is given it should be left there."""
        src = "/home/fred/"  # Trailing slash.
        dst = "/media/backup"

        snapshotter.snapshot(src, dst)

        args = _get_args(self.mock_run_function.call_args_list[0])
        assert "/home/fred/" in args

    def test_rsync_error(self):
        """snapshot() should raise RsyncError if rsync exits with non-zero."""
        self.mock_run_function.return_value = 11
        src = "/home/fred"
        dst = "/media/backup"

        try:
            snapshotter.snapshot(src, dst, debug=True)
            assert False, "snapshot() should have raised an exception"
        except snapshotter.RsyncError as err:
            assert err.message == 11

    def test_link_dest(self):
        """The right --link-dest=... arg should be given to rsync."""
        src = "/home/fred"
        dst = "/media/backup"

        snapshotter.snapshot(src, dst)

        args = _get_args(self.mock_run_function.call_args_list[0])
        link_dest_args = [
            a for a in args.split() if a.startswith("--link-dest")]
        assert len(link_dest_args) == 1
        link_dest_arg = link_dest_args[0]
        name, value = link_dest_arg.split("=")
        assert value == "../latest.snapshot"

    def test_relative_local_to_relative_local(self):
        """Test backing up a relative local dir to a relative local dir."""
        src = "Mail"
        dst = "Mail.snapshots"

        snapshotter.snapshot(src, dst)

        args = _get_args(self.mock_run_function.call_args_list[0])
        src_arg = args.split()[-2]
        dst_arg = args.split()[-1]
        assert src_arg == "'Mail/'"
        assert dst_arg == os.path.join(os.getcwd(), dst, "incomplete.snapshot")

    def test_relative_local_to_absolute_local(self):
        """Test backing up a relative local dir to an absolute local dir."""
        src = "Music"
        dst = "/media/backup/Music.snapshots"

        snapshotter.snapshot(src, dst)

        args = _get_args(self.mock_run_function.call_args_list[0])
        src_arg = args.split()[-2]
        dst_arg = args.split()[-1]
        assert src_arg == "'Music/'"
        assert dst_arg == "/media/backup/Music.snapshots/incomplete.snapshot"

    def test_tilde_in_backup_source(self):
        """Test giving a SRC dir with a ~ in it."""
        src = "~"
        dst = "/media/SNAPSHOTS"

        snapshotter.snapshot(src, dst)

        args = _get_args(self.mock_run_function.call_args_list[0])
        src_arg = args.split()[-2]
        dst_arg = args.split()[-1]
        assert src_arg == "'~/'"

    def test_root_as_source(self):
        """Test giving / as the SRC dir."""
        src = "/"
        dst = "/media/SNAPSHOTS"

        snapshotter.snapshot(src, dst)

        args = _get_args(self.mock_run_function.call_args_list[0])
        src_arg = args.split()[-2]
        dst_arg = args.split()[-1]
        assert src_arg == "'/'"
        assert dst_arg == "/media/SNAPSHOTS/incomplete.snapshot"

    def test_with_remote_dest(self):
        src = "Documents"
        dst = "seanh@mydomain.org:Snapshots/Documents"

        snapshotter.snapshot(src, dst)

        expected_destination = os.path.join(dst, "incomplete.snapshot")
        args = _get_args(self.mock_run_function.call_args_list[0])
        dst_arg = args.split()[-1]
        assert dst_arg == "{dst}".format(dst=expected_destination)

    def test_with_remote_source(self):
        src = "seanh@mydomain.org:Documents"
        dst = "Snapshots/Documents"

        snapshotter.snapshot(src, dst)

        args = _get_args(self.mock_run_function.call_args_list[0])
        src_arg = args.split()[-2]
        assert src_arg == "'{src}/'".format(src=src)

    def test_mv_command(self):
        src = "Mail"
        dst = "Mail.snapshots"

        snapshotter.snapshot(src, dst)

        args = _get_args(self.mock_run_function.call_args_list[1])
        mv, rm, ln = [arg.strip() for arg in args.split('&&')]

        # The absolute path to the incomplete.snapshot dir, no trailing /.
        incomplete_dir = os.path.join(
            os.path.abspath(dst), "incomplete.snapshot")

        # The absolute path to the latest.snapshot symlink.
        latest = os.path.join(
            os.path.abspath(dst), "latest.snapshot")

        # The absolute path to the YYYY-MM-DDTHH_MM_SS.snapshot dir,
        # no trailing /.
        snapshot_dir = os.path.join(
            os.path.abspath(dst), self.datetime + ".snapshot")

        assert mv == "mv {incomplete} {snapshot}".format(
            incomplete=incomplete_dir, snapshot=snapshot_dir)

        assert rm == "rm -f {latest}".format(latest=latest)

        assert ln == "ln -s {snapshot} {latest}".format(
            snapshot=self.datetime + ".snapshot", latest=latest)

    def test_mv_command_with_remote_dest(self):
        src = "Mail"
        dst = "you@yourdomain.org:/path/to/snapshots"

        snapshotter.snapshot(src, dst)

        args = _get_args(self.mock_run_function.call_args_list[1])

        incomplete_dir = "/path/to/snapshots/incomplete.snapshot"
        latest_symlink = "/path/to/snapshots/latest.snapshot"
        snapshot_dir = "/path/to/snapshots/" + self.datetime + ".snapshot"
        expected_args = (
            'ssh you@yourdomain.org '
            '"mv {incomplete} {snapshot} && '
            'rm -f {latest} && '
            'ln -s {datetime}.snapshot {latest}"'.format(
                incomplete=incomplete_dir, latest=latest_symlink,
                snapshot=snapshot_dir, datetime=self.datetime))
        assert args == expected_args

    def test_mv_command_with_remote_dest_with_no_user(self):
        src = "Mail"
        dst = "yourdomain.org:/path/to/snapshots"

        snapshotter.snapshot(src, dst)

        args = _get_args(self.mock_run_function.call_args_list[1])

        incomplete_dir = "/path/to/snapshots/incomplete.snapshot"
        latest_symlink = "/path/to/snapshots/latest.snapshot"
        snapshot_dir = "/path/to/snapshots/" + self.datetime + ".snapshot"
        expected_args = (
            'ssh yourdomain.org '
            '"mv {incomplete} {snapshot} && '
            'rm -f {latest} && '
            'ln -s {datetime}.snapshot {latest}"'.format(
                incomplete=incomplete_dir, latest=latest_symlink,
                snapshot=snapshot_dir, datetime=self.datetime))
        assert args == expected_args

    def test_mv_command_fails(self):
        """snapshot() should raise if the mv command exits with non-zero."""
        src = "Mail"
        dst = "Mail.snapshots"

        def _run(command):
            if command.startswith("mv "):
                return 1
            else:
                return 0

        self.mock_run_function.side_effect = _run

        try:
            snapshotter.snapshot(src, dst)
            assert False, "snapshot() should have raised an exception"
        except snapshotter.MoveError as err:
            assert err.message == 1
