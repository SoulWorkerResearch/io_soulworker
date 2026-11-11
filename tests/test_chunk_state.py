from __future__ import annotations

from contextlib import contextmanager
from enum import Enum
from io import BytesIO
from pathlib import Path
from struct import pack
from tempfile import TemporaryDirectory
from unittest import SkipTest, TestCase


class TestChunkState(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        try:
            import mathutils  # noqa: F401
        except ImportError as exc:
            raise SkipTest("requires mathutils") from exc

    @contextmanager
    def _reader(self, data: bytes):
        from io_soulworker.core.binary_reader import BinaryReader

        with TemporaryDirectory() as folder:
            path = Path(folder) / "chunk.bin"
            path.write_bytes(data)

            with BinaryReader(path) as reader:
                yield reader

    def test_bbbx_entities_keep_their_own_boxes(self):
        from io_soulworker.chunks.bbbx_chunk import BBBXChunk

        boxes = [
            (-1.0, -2.0, -3.0, 1.0, 2.0, 3.0),
            (-4.0, -5.0, -6.0, 4.0, 5.0, 6.0),
            (-7.0, -8.0, -9.0, 7.0, 8.0, 9.0),
        ]
        data = pack("<H", len(boxes)) + b"".join(
            pack("<6f", *box) for box in boxes)

        with self._reader(data) as reader:
            chunk = BBBXChunk.from_reader(reader)

        self.assertEqual(len(chunk.values), len(boxes))

        for entity, box in zip(chunk.values, boxes):
            self.assertEqual(tuple(entity.bounds.min), box[:3])
            self.assertEqual(tuple(entity.bounds.max), box[3:])

        self.assertIsNot(chunk.values[0].bounds, chunk.values[1].bounds)

    def test_effect_config_with_one_entry_round_trips(self):
        from io_soulworker.core.binary_writer import BinaryWriter
        from io_soulworker.core.vis_mesh_effect import (
            VisEffectConfig_cl as EffectConfigItem,
        )
        from io_soulworker.core.vis_mesh_effect_config import (
            VisEffectConfig_cl,
        )

        def string(value: bytes) -> bytes:
            return pack("<I", len(value)) + value

        data = pack("<H", 1) + string(b"Shaders.ShaderLib") + \
            string(b"Diffuse") + string(b"Color=1;") + pack("<I", 5)

        with self._reader(data) as reader:
            config = VisEffectConfig_cl.from_reader(reader)

        self.assertEqual(len(config.values), 1)

        item = config.values[0]
        self.assertIsInstance(item, EffectConfigItem)
        self.assertEqual(item.shader_library_name, "Shaders.ShaderLib")
        self.assertEqual(item.effect_name, "Diffuse")
        self.assertEqual(item.effect_params, "Color=1;")
        self.assertEqual(item.creation_flags, 5)

        stream = BytesIO()
        writer = BinaryWriter(stream)
        config.write(writer)
        writer.flush()

        self.assertEqual(stream.getvalue(), data)

    def test_no_class_attribute_holds_mutable_state(self):
        from importlib import import_module
        from inspect import isclass
        from pkgutil import iter_modules

        from mathutils import Euler, Matrix, Quaternion, Vector

        import io_soulworker.chunks
        import io_soulworker.core
        from io_soulworker.core.data_exchange import DataExchange_cl
        from io_soulworker.core.vis_color import VisColor

        mutable = (
            list, dict, set, bytearray, DataExchange_cl, VisColor,
            Vector, Matrix, Quaternion, Euler,
        )

        names = [
            module.name for module in iter_modules(
                list(io_soulworker.chunks.__path__), "io_soulworker.chunks.")
        ] + [
            module.name for module in iter_modules(
                list(io_soulworker.core.__path__), "io_soulworker.core.")
            if module.name.rpartition(".")[2].startswith("vis_")
        ]

        self.assertTrue(names)

        def shared_attributes(cls, module_name: str):
            if issubclass(cls, Enum):
                return

            for name, value in vars(cls).items():
                if name.startswith("__"):
                    continue

                if isclass(value):
                    if value.__module__ == module_name:
                        yield from shared_attributes(value, module_name)
                elif isinstance(value, mutable):
                    yield f"{cls.__qualname__}.{name}"

        offenders = []

        for name in names:
            module = import_module(name)

            for value in vars(module).values():
                if isclass(value) and value.__module__ == name:
                    offenders.extend(shared_attributes(value, name))

        self.assertEqual(offenders, [])
