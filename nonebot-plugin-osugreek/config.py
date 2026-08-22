from pydantic import BaseModel, Field


class Config(BaseModel):
    """osugreek插件配置"""
    osugreek_group_blacklist: list[str | int] = Field(default_factory=list)
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
    # 自动osugreek: 可用名称列表（如 "afdan/10dan"），为空则关闭
    osugreek_auto_names: list[str] = Field(default_factory=list)
    # 自动osugreek: 触发白名单（QQ号，字符串或数字均可），仅白名单内用户发送正方形图片才会触发
    osugreek_auto_whitelist: list[str | int] = Field(default_factory=list)
    # 自动osugreek: 触发概率 (0-1, 默认0.1)
    osugreek_auto_probability: float = 0.1