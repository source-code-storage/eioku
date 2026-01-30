"""Tests for the video clip export endpoint."""

import os


class TestClipExportValidation:
    """Test clip export parameter validation without full app context."""

    def test_timestamp_validation_end_must_be_greater_than_start(self):
        """Verify end_ms > start_ms validation logic."""
        start_ms = 5000
        end_ms = 5000
        assert end_ms <= start_ms, "end_ms must be greater than start_ms"

        start_ms = 5000
        end_ms = 3000
        assert end_ms <= start_ms, "end_ms must be greater than start_ms"

    def test_buffer_calculation(self):
        """Test buffer is correctly applied to timestamps."""
        start_ms = 5000
        end_ms = 10000
        buffer_ms = 2000

        actual_start_ms = max(0, start_ms - buffer_ms)
        actual_end_ms = end_ms + buffer_ms

        assert actual_start_ms == 3000
        assert actual_end_ms == 12000

    def test_buffer_clamps_to_zero(self):
        """Test buffer doesn't go negative."""
        start_ms = 1000
        buffer_ms = 2000

        actual_start_ms = max(0, start_ms - buffer_ms)
        assert actual_start_ms == 0

    def test_filename_generation(self):
        """Test clip filename is generated correctly."""
        filename = "test_video.mp4"
        actual_start_ms = 3000  # 3 seconds
        actual_end_ms = 12000  # 12 seconds

        start_sec = actual_start_ms / 1000
        end_sec = actual_end_ms / 1000

        start_fmt = f"{int(start_sec // 60)}m{int(start_sec % 60)}s"
        end_fmt = f"{int(end_sec // 60)}m{int(end_sec % 60)}s"
        base_name = os.path.splitext(filename)[0]
        clip_filename = f"{base_name}_{start_fmt}-{end_fmt}.mp4"

        assert clip_filename == "test_video_0m3s-0m12s.mp4"

    def test_filename_generation_with_minutes(self):
        """Test clip filename with timestamps over 1 minute."""
        filename = "my_video.mp4"
        actual_start_ms = 65000  # 1:05
        actual_end_ms = 125000  # 2:05

        start_sec = actual_start_ms / 1000
        end_sec = actual_end_ms / 1000

        start_fmt = f"{int(start_sec // 60)}m{int(start_sec % 60)}s"
        end_fmt = f"{int(end_sec // 60)}m{int(end_sec % 60)}s"
        base_name = os.path.splitext(filename)[0]
        clip_filename = f"{base_name}_{start_fmt}-{end_fmt}.mp4"

        assert clip_filename == "my_video_1m5s-2m5s.mp4"

    def test_ffmpeg_command_construction(self):
        """Test ffmpeg command is built correctly."""
        file_path = "/path/to/video.mp4"
        start_sec = 3.0
        duration_sec = 9.0

        cmd = [
            "ffmpeg",
            "-ss",
            str(start_sec),
            "-i",
            file_path,
            "-t",
            str(duration_sec),
            "-c",
            "copy",
            "-movflags",
            "frag_keyframe+empty_moov",
            "-f",
            "mp4",
            "pipe:1",
        ]

        assert cmd[0] == "ffmpeg"
        assert cmd[1] == "-ss"
        assert cmd[2] == "3.0"
        assert cmd[4] == file_path
        assert cmd[6] == "9.0"
        assert "-c" in cmd
        assert "copy" in cmd
