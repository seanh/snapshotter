from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import print_function

import os
import tempfile
import sys
import shutil

import mock
import nose.tools

from snapshotter import snapshotter


def _this_directory():
    """Return this Python module's directory as a string."""
    return os.path.split(sys.modules[__name__].__file__)[0]


class TestRun(object):

    """Unit tests for the _run() function."""

    def test_success_with_stdout(self):
        output = snapshotter._run("echo foo".split())
        assert output == "foo\n"

    def test_failed_command(self):
        command = "rsync --foobar"
        try:
            snapshotter._run(command.split())
            assert False, "We shouldn't get here"
        except snapshotter.CalledProcessError as err:
            assert err.command == command
            assert err.output.startswith("rsync: --foobar: unknown option")
            assert err.exit_value == 1

    def test_command_does_not_exist(self):
        nose.tools.assert_raises(
            snapshotter.NoSuchCommandError, snapshotter._run, "bar")

    @mock.patch("subprocess.check_output")
    def test_debug(self, mock_check_output_function):
        """_run() should not call check_output() if debug is True."""
        snapshotter._run("command", debug=True)

        assert not mock_check_output_function.called


class TestRsync(object):

    """Unit tests for the _rsync() function."""

    @mock.patch("snapshotter.snapshotter._run")
    def test_rsync_raises_NoSpaceLeftOnDevice(self, mock_run_function):
        """NoSpaceLeftOnDeviceError should be raised for rsync no space error.

        If rsync exits with status 11 and a "No space left on device" error,
        _rsync() should raise NoSpaceLeftOnDeviceError.

        """
        mock_run_function.side_effect = snapshotter.CalledProcessError(
            command="rsync ...",
            output='rsync: write failed on "/media/seanh/foo/Hypothesis/Co-'
                   'ment ~ Philippe Aigrain @ I Annotate 2014 (HD).mp4": No '
                   'space left on device (28)\n'
                   'rsync error: error in file IO (code 11) at receiver.c(389)'
                   ' [receiver=3.1.0]',
            exit_value=11)

        nose.tools.assert_raises(
            snapshotter.NoSpaceLeftOnDeviceError,
            snapshotter._rsync, "source", "dest")

    @mock.patch("snapshotter.snapshotter._run")
    def test_rsync_raises_CalledProcessError(self, mock_run_function):
        """CalledProcessError should be raised for other rsync errors.

        If rsync exits with any status 11 and something other than a
        "no space left on device" error, _rsync() should raise
        CalledProcessError.

        """
        mock_run_function.side_effect = snapshotter.CalledProcessError(
            command="rsync ...",
            output="Some other rsync error",
            exit_value=11)

        nose.tools.assert_raises(
            snapshotter.CalledProcessError,
            snapshotter._rsync, "source", "dest")

    @mock.patch("snapshotter.snapshotter._run")
    def test_rsync_raises_CalledProcessError_other_exit_value(
            self, mock_run_function):
        """CalledProcessError should be raised for other rsync errors.

        If rsync exits with a non-zero status other than 11, _rsync() should
        raise CalledProcessError.

        """
        mock_run_function.side_effect = snapshotter.CalledProcessError(
            command="rsync ...",
            output="Some other rsync error",
            exit_value=13)

        nose.tools.assert_raises(
            snapshotter.CalledProcessError,
            snapshotter._rsync, "source", "dest")


class TestCLI(object):

    """Tests for the parse_cli() function."""

    def test_with_no_src_or_dest_args(self):
        nose.tools.assert_raises(
            snapshotter.CommandLineArgumentsError, snapshotter._parse_cli,
            args=[])

    def test_with_no_dest_arg(self):
        nose.tools.assert_raises(
            snapshotter.CommandLineArgumentsError, snapshotter._parse_cli,
            args=["/home/fred"])

    def test_with_default_options(self):
        src, dest, debug, _, _ = (
            snapshotter._parse_cli(args=["/home/fred", "/media/backup"]))
        assert src == "/home/fred"
        assert dest == "/media/backup"
        assert debug is False

    def test_dry_run(self):
        for option in ("-n", "--dry-run"):
            _, _, debug, _, _ = snapshotter._parse_cli(
                args=[option, "/home/fred", "/media/backup"])
            assert debug is True

    def test_extra_args(self):
        _, _, _, _, extra_args = (
            snapshotter._parse_cli(
                args=["--foo=fred", "-x", "/home/fred", "/media/backup"]))
        assert extra_args == ["--foo=fred", "-x"]


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
    positional_args, _ = call_args
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

        args = _get_args(self.mock_run_function.call_args_list[0])
        assert "--dry-run" in args, (
            "snapshot() should pass the -n/--dry-run argument on to rsync")
        for call in self.mock_run_function.call_args_list[1:]:
            assert call[1].get("debug") is True

    def test_not_passing_dry_run_to_rsync(self):
        """If --n isn't given to snapshotter it shouldn't be given to rsync."""
        src = "/home/fred"
        dst = "/media/backup"

        snapshotter.snapshot(src, dst, debug=False)

        assert self.mock_run_function.call_count == 4, (
            "We expect 4 commands to be run: rsync, mv, rm, ln")
        args = _get_args(self.mock_run_function.call_args_list[0])
        assert "--dry-run" not in args

    def test_without_trailing_slash(self):
        """A trailing / should be appened to the source path if not given."""
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
        """Should raise CalledProcessError if rsync exits with non-zero."""
        self.mock_run_function.side_effect = snapshotter.CalledProcessError(
            "command", "output", 11)
        src = "/home/fred"
        dst = "/media/backup"

        try:
            snapshotter.snapshot(src, dst, debug=True)
            assert False, "snapshot() should have raised an exception"
        except snapshotter.CalledProcessError as err:
            assert err.output == "output 11"

    def test_link_dest(self):
        """The right --link-dest=... arg should be given to rsync."""
        src = "/home/fred"
        dst = "/media/backup"

        snapshotter.snapshot(src, dst)

        args = _get_args(self.mock_run_function.call_args_list[0])
        link_dest_args = [
            a for a in args if a.startswith("--link-dest")]
        assert len(link_dest_args) == 1
        link_dest_arg = link_dest_args[0]
        _, value = link_dest_arg.split("=")
        assert value == "../latest.snapshot"

    def test_relative_local_to_relative_local(self):
        """Test backing up a relative local dir to a relative local dir."""
        src = "Mail"
        dst = "Mail.snapshots"

        snapshotter.snapshot(src, dst)

        args = _get_args(self.mock_run_function.call_args_list[0])
        src_arg = args[-2]
        dst_arg = args[-1]
        assert src_arg == "Mail/"
        assert dst_arg == os.path.join(os.getcwd(), dst, "incomplete.snapshot")

    def test_relative_local_to_absolute_local(self):
        """Test backing up a relative local dir to an absolute local dir."""
        src = "Music"
        dst = "/media/backup/Music.snapshots"

        snapshotter.snapshot(src, dst)

        args = _get_args(self.mock_run_function.call_args_list[0])
        src_arg = args[-2]
        dst_arg = args[-1]
        assert src_arg == "Music/"
        assert dst_arg == "/media/backup/Music.snapshots/incomplete.snapshot"

    def test_tilde_in_backup_source(self):
        """Test giving a source path with a ~ in it."""
        src = "~"
        dst = "/media/SNAPSHOTS"

        snapshotter.snapshot(src, dst)

        args = _get_args(self.mock_run_function.call_args_list[0])
        src_arg = args[-2]
        assert src_arg == "~/"

    def test_root_as_source(self):
        """Test giving / as the source path."""
        src = "/"
        dst = "/media/SNAPSHOTS"

        snapshotter.snapshot(src, dst)

        args = _get_args(self.mock_run_function.call_args_list[0])
        src_arg = args[-2]
        dst_arg = args[-1]
        assert src_arg == "/"
        assert dst_arg == "/media/SNAPSHOTS/incomplete.snapshot"

    def test_with_remote_dest(self):
        src = "Documents"
        dst = "seanh@mydomain.org:Snapshots/Documents"

        snapshotter.snapshot(src, dst)

        expected_destination = os.path.join(dst, "incomplete.snapshot")
        args = _get_args(self.mock_run_function.call_args_list[0])
        dst_arg = args[-1]
        assert dst_arg == "{dst}".format(dst=expected_destination)

    def test_with_remote_source(self):
        src = "seanh@mydomain.org:Documents"
        dst = "Snapshots/Documents"

        snapshotter.snapshot(src, dst)

        args = _get_args(self.mock_run_function.call_args_list[0])
        src_arg = args[-2]
        assert src_arg == "{src}/".format(src=src)

    def test_mv_command(self):
        src = "Mail"
        dst = "Mail.snapshots"

        snapshotter.snapshot(src, dst)

        mv = ' '.join(self.mock_run_function.call_args_list[1][0][0])
        rm = ' '.join(self.mock_run_function.call_args_list[2][0][0])
        ln = ' '.join(self.mock_run_function.call_args_list[3][0][0])

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

        incomplete_dir = "/path/to/snapshots/incomplete.snapshot"
        snapshot_dir = "/path/to/snapshots/" + self.datetime + ".snapshot"
        mv = ' '.join(self.mock_run_function.call_args_list[1][0][0])
        expected_call = (
            'ssh you@yourdomain.org mv {incomplete} {snapshot}'.format(
                incomplete=incomplete_dir, snapshot=snapshot_dir))
        assert mv == expected_call

    # TODO: Test the rm and ln commands with remote destinations as well.

    def test_mv_command_with_remote_dest_with_no_user(self):
        src = "Mail"
        dst = "yourdomain.org:/path/to/snapshots"

        snapshotter.snapshot(src, dst)

        incomplete_dir = "/path/to/snapshots/incomplete.snapshot"
        snapshot_dir = "/path/to/snapshots/" + self.datetime + ".snapshot"
        mv = ' '.join(self.mock_run_function.call_args_list[1][0][0])
        expected_call = (
            'ssh yourdomain.org '
            'mv {incomplete} {snapshot}'.format(
                incomplete=incomplete_dir, snapshot=snapshot_dir))
        assert mv == expected_call

    # TODO: Same test for rm and ln

    def test_mv_command_fails(self):
        """snapshot() should raise if the mv command exits with non-zero."""
        src = "Mail"
        dst = "Mail.snapshots"

        self.mock_run_function.side_effect = snapshotter.CalledProcessError(
            "command", "output", 25)

        try:
            snapshotter.snapshot(src, dst)
            assert False, "snapshot() should have raised an exception"
        except snapshotter.CalledProcessError as err:
            assert err.output == "output 25"

    def test_extra_args_are_passed_on_to_rsync(self):
        extra_args = ["-v", "--info=progress2"]

        snapshotter.snapshot("src", "dest", extra_args=extra_args)

        for arg in extra_args:
            assert arg in self.mock_run_function.call_args_list[0][0][0]


class TestRemovingOldSnapshots(object):

    """Tests for removing old snapshots when out of space for new ones."""

    def setup(self):
        self.run_patcher = mock.patch('snapshotter.snapshotter._run')
        self.mock_run_function = self.run_patcher.start()
        self.mock_run_function.return_value = 0

        self.rsync_patcher = mock.patch('snapshotter.snapshotter._rsync')
        self.mock_rsync_function = self.rsync_patcher.start()

        self.rm_patcher = mock.patch('snapshotter.snapshotter._rm')
        self.mock_rm_function = self.rm_patcher.start()

        self.ls_snapshots_patcher = mock.patch(
            'snapshotter.snapshotter._ls_snapshots')
        self.mock_ls_snapshots_function = self.ls_snapshots_patcher.start()

    def teardown(self):
        self.run_patcher.stop()
        self.rsync_patcher.stop()
        self.rm_patcher.stop()
        self.ls_snapshots_patcher.stop()

    def test_removing_oldest_snapshot(self):
        """If out of space it should remove oldest snapshot and rerun rsync."""
        snapshots = [
            "2015-03-05T16_23_12.snapshot",
            "2015-03-05T16_24_15.snapshot",
            "2015-03-05T16_25_09.snapshot",
            "2015-03-05T16_27_09.snapshot",
            "2015-03-05T16_28_09.snapshot",
            "2015-03-05T16_29_09.snapshot",
        ]
        self.mock_ls_snapshots_function.return_value = snapshots

        rsync_returns = [snapshotter.NoSpaceLeftOnDeviceError(), None]

        def rsync(*args, **kwargs):
            result = rsync_returns.pop(0)
            if isinstance(result, Exception):
                raise result
            else:
                return result
        self.mock_rsync_function.side_effect = rsync

        snapshotter.snapshot("source", "destination")

        assert self.mock_rm_function.call_count == 2
        assert self.mock_rm_function.call_args_list[0] == mock.call(
            '2015-03-05T16_23_12.snapshot', None, None, debug=False,
            directory=True)

        assert self.mock_rsync_function.call_count == 2

    def test_removing_multiple_snapshots(self):
        """If out of space it should remove oldest snapshot and rerun rsync."""
        snapshots = [
            "2015-03-05T16_23_12.snapshot",
            "2015-03-05T16_24_15.snapshot",
            "2015-03-05T16_25_09.snapshot",
            "2015-03-05T16_27_09.snapshot",
            "2015-03-05T16_28_09.snapshot",
            "2015-03-05T16_29_09.snapshot",
        ]
        self.mock_ls_snapshots_function.return_value = snapshots

        rsync_returns = [
            snapshotter.NoSpaceLeftOnDeviceError(),
            snapshotter.NoSpaceLeftOnDeviceError(),
            snapshotter.NoSpaceLeftOnDeviceError(),
            None]

        def rsync(*args, **kwargs):
            result = rsync_returns.pop(0)
            if isinstance(result, Exception):
                raise result
            else:
                return result
        self.mock_rsync_function.side_effect = rsync

        def rm(*args, **kwargs):
            snapshots.pop(0)
        self.mock_rm_function.side_effect = rm

        snapshotter.snapshot("source", "destination")

        assert self.mock_rm_function.call_count == 4
        assert self.mock_rm_function.call_args_list[0] == mock.call(
            '2015-03-05T16_23_12.snapshot', None, None, debug=False,
            directory=True)
        assert self.mock_rm_function.call_args_list[1] == mock.call(
            '2015-03-05T16_24_15.snapshot', None, None, debug=False,
            directory=True)
        assert self.mock_rm_function.call_args_list[2] == mock.call(
            '2015-03-05T16_25_09.snapshot', None, None, debug=False,
            directory=True)

        assert self.mock_rsync_function.call_count == 4

    def test_too_few_snapshots(self):
        """It should crash if not enough space and too few snapshots to remove.

        """
        snapshots = [
            "2015-03-05T16_23_12.snapshot",
            "2015-03-05T16_24_15.snapshot",
        ]
        self.mock_ls_snapshots_function.return_value = snapshots

        self.mock_rsync_function.side_effect = (
            snapshotter.NoSpaceLeftOnDeviceError)

        nose.tools.assert_raises(
            snapshotter.NoMoreSnapshotsToRemoveError,
            snapshotter.snapshot, "source", "destination")

    def test_too_few_snapshots_after_removing_two(self):
        snapshots = [
            "2015-03-05T16_23_12.snapshot",
            "2015-03-05T16_24_15.snapshot",
            "2015-03-05T16_25_09.snapshot",
            "2015-03-05T16_27_09.snapshot",
            "2015-03-05T16_28_09.snapshot",
        ]
        self.mock_ls_snapshots_function.return_value = snapshots

        self.mock_rsync_function.side_effect = (
            snapshotter.NoSpaceLeftOnDeviceError)

        def rm(*args, **kwargs):
            snapshots.pop(0)
        self.mock_rm_function.side_effect = rm

        nose.tools.assert_raises(
            snapshotter.NoMoreSnapshotsToRemoveError,
            snapshotter.snapshot, "source", "destination")

        assert self.mock_rm_function.call_count == 2
        assert self.mock_rm_function.call_args_list[0] == mock.call(
            '2015-03-05T16_23_12.snapshot', None, None, debug=False,
            directory=True)
        assert self.mock_rm_function.call_args_list[1] == mock.call(
            '2015-03-05T16_24_15.snapshot', None, None, debug=False,
            directory=True)

        assert self.mock_rsync_function.call_count == 3

    def test_with_no_snapshots(self):
        self.mock_ls_snapshots_function.return_value = []

        self.mock_rsync_function.side_effect = (
            snapshotter.NoSpaceLeftOnDeviceError)

        nose.tools.assert_raises(
            snapshotter.NoMoreSnapshotsToRemoveError,
            snapshotter.snapshot, "source", "destination")

    def test_other_rsync_error(self):
        snapshots = [
            "2015-03-05T16_23_12.snapshot",
            "2015-03-05T16_24_15.snapshot",
            "2015-03-05T16_25_09.snapshot",
            "2015-03-05T16_27_09.snapshot",
            "2015-03-05T16_28_09.snapshot",
        ]
        self.mock_ls_snapshots_function.return_value = snapshots

        self.mock_rsync_function.side_effect = snapshotter.CalledProcessError(
            "rsync ...", "error", 23)

        def rm(*args, **kwargs):
            snapshots.pop(0)
        self.mock_rm_function.side_effect = rm

        nose.tools.assert_raises(
            snapshotter.CalledProcessError,
            snapshotter.snapshot, "source", "destination")
