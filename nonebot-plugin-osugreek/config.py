from pydantic import BaseModel


class Config(BaseModel):
    """osugreek插件配置"""
    # RGB分离强度 (范围1-20, 默认4)
    osugreek_chromatic_intensity: int = 4
    # 故障效果强度 (范围0-5, 默认0, 0表示无故障效果)
    osugreek_glitch_intensity: int = 0
    # GIF压缩: 最长边像素上限 (0=不限制)
    osugreek_gif_max_size: int = 800
    # GIF压缩: 最多保留帧数 (0=不限制)
    osugreek_gif_max_frames: int = 30
    # GIF压缩: 输出调色板颜色数上限 (0=不限制)
    osugreek_gif_colors: int = 128