from unittest.mock import patch
from app.config import AppConfig
from app.serial_worker import SerialParser


def parser():
    p = SerialParser(AppConfig())
    p.feed_line(b'#fs=1000,columns=n,ecg,emg_raw,emg_env\r\n')
    return p


def test_valid_and_bad_frames():
    p = parser()
    assert p.feed_line(b'12,0,1023,32\r\n') == (12, 0, 1023, 32)
    for line in (b'1,2,3', b'1,x,3,4', b'2,1024,1,2', b'3,-1,1,2', b'4,1,2,3,4', b'\xff'):
        assert p.feed_line(line) is None
    assert p.stats.invalid == 6
    assert p.stats.received == 1


def test_gaps_resets_wrap_and_normalized_time():
    p = parser()
    for line in ('4294967293,1,2,3', '0,1,2,3', '3,1,2,3', '1,1,2,3'):
        p.feed_line(line)
    assert p.stats.lost == 4
    assert p.stats.resets == 1
    assert p.normalized_index == 7
    assert p.normalized_index / p.sample_rate == 0.007
    assert p.feed_line('1,1,2,3') is None
    assert p.stats.invalid == 1


def test_effective_frequency_uses_clock():
    p = parser()
    with patch('app.serial_worker.time.monotonic', side_effect=[10.0, 10.5, 11.0]):
        p.feed_line('5,1,2,3')
        p.feed_line('105,1,2,3')
        p.feed_line('106,1,2,3')
    assert p.stats.effective_fs == 2.0
    assert p.stats.lost == 99


def test_metadata_validation_and_missing_header():
    p = SerialParser(AppConfig())
    assert p.feed_line('#fs=0,columns=n,ecg,emg_raw,emg_env') is None
    assert p.stats.invalid == 1
    p.feed_line('#fs=1000,columns=n,ecg,emg_raw,emg_env')
    assert p.metadata_seen
    q = SerialParser(AppConfig())
    assert q.feed_line('0,1,2,3') == (0, 1, 2, 3)


def test_disconnect_flushes_complete_pending_frames(monkeypatch):
    from app.serial_worker import SerialWorker
    class FakePort:
        def __init__(self, *args, **kwargs):
            self.calls = 0
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def reset_input_buffer(self):
            return None
        @property
        def in_waiting(self):
            return 100
        def read(self, size):
            self.calls += 1
            if self.calls == 1:
                return b'#fs=1000,columns=n,ecg,emg_raw,emg_env\n0,1,2,3\n1,2,3,4\n2,3'
            raise OSError('desconectado')
    monkeypatch.setattr('app.serial_worker.serial.Serial', FakePort)
    worker = SerialWorker(AppConfig(), 'fake')
    blocks, errors = [], []
    worker.block_ready.connect(blocks.append)
    worker.error.connect(errors.append)
    worker.run()
    assert len(blocks) == 1 and len(blocks[0]) == 2
    assert errors and 'desconectado' in errors[0]
