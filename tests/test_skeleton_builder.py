import importlib.util
from types import SimpleNamespace
from unittest import TestCase


def load_build_bone_transforms():
    spec = importlib.util.spec_from_file_location(
        "skeleton_builder",
        "io_soulworker/file_import/model/skeleton_builder.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module.build_bone_transforms


class TranslationMatrix:

    def __init__(self, x, y, z):
        self.translation = (x, y, z)

    def __matmul__(self, other):
        ax, ay, az = self.translation
        bx, by, bz = other.translation

        return TranslationMatrix(ax + bx, ay + by, az + bz)

    def to_translation(self):
        return self.translation


class TestSkeletonBuilder(TestCase):

    def test_build_bone_transforms_uses_parent_names_and_world_matrices(self):
        build_bone_transforms = load_build_bone_transforms()

        root_matrix = TranslationMatrix(1.0, 0.0, 0.0)
        child_local_matrix = TranslationMatrix(0.0, 2.0, 0.0)

        bones = [
            SimpleNamespace(id=0, name="Root", parent_id=-1,
                            local_matrix=root_matrix),
            SimpleNamespace(id=1, name="Child", parent_id=0,
                            local_matrix=child_local_matrix),
        ]

        transforms = build_bone_transforms(
            bones,
            local_matrix_of=lambda bone: bone.local_matrix,
        )

        self.assertEqual(transforms[0].name, "Root")
        self.assertIsNone(transforms[0].parent_name)
        self.assertEqual(transforms[1].name, "Child")
        self.assertEqual(transforms[1].parent_name, "Root")
        self.assertEqual(transforms[1].matrix.to_translation(), (1.0, 2.0, 0.0))
