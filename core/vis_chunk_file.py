from io_soulworker.core.vis_chunk_tag import VisChunkTag
from io import BufferedReader
from io import SEEK_SET
from pathlib import Path
from struct import unpack


class VisChunkFile(object):
    def __init__(self, path: Path) -> None:
        self.path = path

    def on_chunk_start(self, chunk: int, model: BufferedReader) -> None:
        raise NotImplementedError("chunk: %d" % chunk)

    def run(self) -> None:
        with open(self.path, "rb") as model:
            token, version, contains, emitter = unpack(
                "<4s H H I", model.read(12))

            assert token == b"VBIN"
            assert version == 0
            assert contains == 1
            assert emitter == 0

            while True:
                open_chunk_id, = unpack("<I", model.read(4))
                length, = unpack("<I", model.read(4))
                tell = model.tell()

                chunk_name = (open_chunk_id).to_bytes(4, "big").decode("ascii")
                print("chunk: ", chunk_name)

                self.on_chunk_start(open_chunk_id, model)

                model.seek(tell + length, SEEK_SET)

                chunkName1, = unpack("<i", model.read(4))
                close_chunk_name, = unpack("<I", model.read(4))
                tag, = unpack("<i", model.read(4))

                if tag == VisChunkTag.EOF:
                    break
