from bpy.types import Panel


class OutObjectPanelFeatures(Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Features"
    bl_parent_id = "FILE_PT_operator"

    @classmethod
    def poll(cls, context):
        space_data = context.space_data
        active_operator = space_data.active_operator

        return active_operator.bl_idname == "IO_SOULWORKER_OT_import"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        space_data = context.space_data
        active_operator = space_data.active_operator

        layout.prop(active_operator, 'is_create_collection')
