from mathutils import Vector

from io_soulworker.core.vis_color import VisColor


class ShaderParamString(dict):

    def __init__(self, line: str):

        rows = line.split(';')

        for row in rows:
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
                    self['material_params'] = Vector(value.split(','))

                # AlphaThreshold=0.25
                case 'AlphaThreshold':
                    self['alpha_threshold'] = float(value)

                # ToonTexture=Character\Common_Textures\ToonTexture.dds
                case 'ToonTexture':
                    self['ToonTexture'] = value

                # OutlineThickness=0.012
                case 'OutlineThickness':
                    self['OutlineThickness'] = float(value)

                # OutlineColor=0,0,0,1
                case 'OutlineColor':
                    [r, g, b, a] = value.split(',')
                    self['OutlineColor'] = VisColor(r, g, b, a)

                # DiffuseHue=1.2
                case 'DiffuseHue':
                    self['DiffuseHue'] = float(value)

                # HairColor=0.9411765,0.7921569,0.5490196,1
                case 'HairColor':
                    [r, g, b, a] = value.split(',')
                    self['HairColor'] = VisColor(r, g, b, a)

                # ShadowColor=0.8039216,0.09803922,0.09803922,0.254902
                case 'ShadowColor':
                    [r, g, b, a] = value.split(',')
                    self['ShadowColor'] = VisColor(r, g, b, a)

                # HairDarknessColor=0.7843137,0.5176471,0.3647059,1
                case 'HairDarknessColor':
                    [r, g, b, a] = value.split(',')
                    self['HairDarknessColor'] = VisColor(r, g, b, a)

                # MaskTexture=Character\Player\PC_A\Textures\PC_A_Parts_Default_Hair_01_Mask_01.dds
                case 'MaskTexture':
                    self['MaskTexture'] = value

                # globalAlpha=1
                case 'globalAlpha':
                    self['globalAlpha'] = value

                # LightVec=-1,1,-1
                case 'LightVec':
                    self['LightVec'] = Vector(value.split(','))
            pass
