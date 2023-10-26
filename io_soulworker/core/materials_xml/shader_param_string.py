from mathutils import Vector

from io_soulworker.core.vis_color import VisColor


class ShaderParamString(dict):

    def __init__(self, line: str):

        rows = line.split(';')

        for row in rows:
            if (row == ''):
                continue

            [name, value] = row.split('=')

            match name:

                # CullMode=back
                case 'CullMode':
                    self['cull_mode'] = value

                # DepthWrite=true
                case 'DepthWrite':
                    self['depth_write'] = bool(value)

                # PassType=pre_basepass
                case 'PassType':
                    self['pass_type'] = value

                # MaterialParams=0,2,-0.03,-0.015
                case 'MaterialParams':
                    values = [float(v) for v in value.split(',')]
                    self['material_params'] = Vector(values)

                # AlphaThreshold=0.25
                case 'AlphaThreshold':
                    self['alpha_threshold'] = float(value)

                # ToonTexture=Character\Common_Textures\ToonTexture.dds
                case 'ToonTexture':
                    self['toon_texture'] = value

                # OutlineThickness=0.012
                case 'OutlineThickness':
                    self['outline_thickness'] = float(value)

                # OutlineColor=0,0,0,1
                case 'OutlineColor':
                    values = [int(v) for v in value.split(',')]
                    self['outline_color'] = VisColor(*values)

                # DiffuseHue=1.2
                case 'DiffuseHue':
                    self['diffuse_hue'] = float(value)

                # HairColor=0.9411765,0.7921569,0.5490196,1
                case 'HairColor':
                    values = [float(v) for v in value.split(',')]
                    self['hair_color'] = VisColor(*values)

                # ShadowColor=0.8039216,0.09803922,0.09803922,0.254902
                case 'ShadowColor':
                    values = [float(v) for v in value.split(',')]
                    self['shadow_color'] = VisColor(*values)

                # HairDarknessColor=0.7843137,0.5176471,0.3647059,1
                case 'HairDarknessColor':
                    values = [float(v) for v in value.split(',')]
                    self['hair_darkness_color'] = VisColor(*values)

                # MaskTexture=Character\Player\PC_A\Textures\PC_A_Parts_Default_Hair_01_Mask_01.dds
                case 'MaskTexture':
                    self['mask_texture'] = value

                # globalAlpha=1
                case 'globalAlpha':
                    self['global_alpha'] = value

                # LightVec=-1,1,-1
                case 'LightVec':
                    values = [int(v) for v in value.split(',')]
                    self['light_vec'] = Vector(values)
