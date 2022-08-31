# -*- coding: utf-8 -*-

from maya import cmds
import pyblish.api
import openpype.api
from openpype.pipeline.publish import ValidateMeshOrder


class ValidateUnrealMeshTriangulated(pyblish.api.InstancePlugin):
    """Validate if mesh is made of triangles for Unreal Engine"""

    order = ValidateMeshOrder
    hosts = ["maya"]
    families = ["staticMesh"]
    category = "geometry"
    label = "Mesh is Triangulated"
    actions = [openpype.hosts.maya.api.action.SelectInvalidAction]
    active = False

    @classmethod
    def get_invalid(cls, instance):
        invalid = []
        meshes = cmds.ls(instance, type="mesh", long=True)
        for mesh in meshes:
            faces = cmds.polyEvaluate(mesh, f=True)
            tris = cmds.polyEvaluate(mesh, t=True)
            if faces != tris:
                invalid.append(mesh)

        return invalid

    def process(self, instance):
        invalid = self.get_invalid(instance)
        assert len(invalid) == 0, (
            "Found meshes without triangles")
