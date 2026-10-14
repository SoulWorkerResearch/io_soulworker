from __future__ import annotations

import struct
from unittest import TestCase

from io_soulworker.core.varchive.objects import (
    ModelSerializationProxy,
    SequenceSetSerializationProxy,
)
from io_soulworker.core.varchive.reader import VArchiveReader
from io_soulworker.core.varchive.registry import build_serializers
from io_soulworker.core.varchive.serializers import (
    serialize_model_serialization_proxy,
    serialize_sequence_set_proxy,
)


def _string_binary(value: str) -> bytes:
    raw = value.encode("cp949")

    return struct.pack("<i", len(raw)) + raw


def _new_class_object(class_name: str, payload: bytes) -> bytes:
    """Encode a first-seen typed object (``NEW_CLASS_TAG`` + payload)."""

    name = class_name.encode("ascii")
    header = struct.pack("<IHH", 0xFFFFFFFF, 0, len(name)) + name

    return header + payload


class TestModelSerializationProxy(TestCase):

    def test_reads_dynamic_mesh_path(self) -> None:

        path = r"Character\Object\OBJ_0321_SG_Moving_Cube_01\OBJ_0321_SG_Moving_Cube_01.model"
        data = _string_binary(path) + struct.pack("<i", 0)

        ar = VArchiveReader(
            data,
            loading_version=30,
            use_object_lengths=False,
            has_per_object_range=False,
            serializers=build_serializers(),
        )
        obj = ModelSerializationProxy()
        serialize_model_serialization_proxy(ar, obj)

        self.assertEqual(obj.path, path)
        self.assertEqual(obj.sequence_set_paths, [])

    def test_reads_nested_sequence_set_paths(self) -> None:

        model_path = r"Character\NPC\NPC_0001_Mirium\NPC_0001_Mirium.model"
        anim_path = r"Character\NPC\NPC_0001_Mirium\NPC_0001_Mirium.anim"
        nested = _new_class_object(
            "VSequenceSetSerializationProxy",
            _string_binary(anim_path),
        )
        data = _string_binary(model_path) + struct.pack("<i", 1) + nested

        ar = VArchiveReader(
            data,
            loading_version=30,
            use_object_lengths=False,
            has_per_object_range=False,
            serializers=build_serializers(),
        )
        obj = ModelSerializationProxy()
        serialize_model_serialization_proxy(ar, obj)

        self.assertEqual(obj.path, model_path)
        self.assertEqual(obj.sequence_set_paths, [anim_path])

    def test_sequence_set_proxy_reads_path(self) -> None:

        anim_path = r"Models\MissingModel.anim"
        ar = VArchiveReader(
            _string_binary(anim_path),
            loading_version=30,
            use_object_lengths=False,
            has_per_object_range=False,
            serializers=build_serializers(),
        )
        obj = SequenceSetSerializationProxy()
        serialize_sequence_set_proxy(ar, obj)

        self.assertEqual(obj.path, anim_path)
