from nonebot import get_plugin_config, require, on_command, on_message
import nonebot.exception
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageEvent, MessageSegment
from nonebot.rule import Rule
from PIL import Image, ImageChops, ImageFilter, ImageSequence
import aiohttp
import random
from io import BytesIO
from pathlib import Path

require("nonebot_plugin_localstore")
_Ecache_dir = None


def _get_cache_dir() -> Path:
    """获取当前插件的缓存目录"""
    global _Ecache_dir
    if _Ecache_dir is None:
        import nonebot_plugin_localstore as store
        _Ecache_dir = store.get_plugin_cache_dir()
        _Ecache_dir.mkdir(parents=True, exist_ok=True)
    return _Ecache_dir


from .config import Config

plugin_config = get_plugin_config(Config)
osugreek = on_command("osugreek", aliases={"希腊字母", "og"}, priority=5, block=False)


def _has_image(event: GroupMessageEvent) -> bool:
    """自动触发规则：群消息中包含图片。"""
    return any(seg.type == "image" for seg in event.message)


# 自动 osugreek：群内发送正方形图片时按概率触发（静默发送，不回复）
auto_osugreek = on_message(rule=Rule(_has_image), priority=50, block=False)

# 希腊字母图片目录
GREEK_IMAGE_DIR = Path(__file__).parent / "images"
GREEK_IMAGE_DIR.mkdir(exist_ok=True)

folder_prefix = "📁 "
child_prefix = "｜ "


def get_available_images() -> list[str]:
    """递归获取所有可用图片名称。

    名称格式：
        ${文件夹名称}/${图片名称去掉.png}
    """
    available = []

    for image_path in GREEK_IMAGE_DIR.rglob("*.png"):
        relative_path = image_path.relative_to(GREEK_IMAGE_DIR)

        # 排除直接位于 images 根目录下的情况
        # 如果以后存在 images/foo.png，则名称为 foo
        if relative_path.parent == Path("."):
            name = relative_path.stem
        else:
            name = f"{relative_path.parent}/{relative_path.stem}"

        available.append(name)

    available.sort()
    return available


def find_image_path(image_name: str) -> tuple[Path | None, list[Path]]:
    """根据图片名称查找图片。

    返回：
        (图片路径, 空列表)
            找到唯一图片

        (None, 多个匹配路径)
            图片名称存在歧义，需要指定完整路径

        (None, 空列表)
            图片不存在

    例如：
        zeta
        -> (images/osudan/zeta.png, [])

        pm
        -> (None, [
            images/arc_clear/pm.png,
            images/arc_text/pm.png
        ])

        arc_text/pm
        -> (images/arc_text/pm.png, [])
    """

    # ---------------------------------------------------------
    # 1.首先尝试完整路径匹配
    # ---------------------------------------------------------
    exact_path = GREEK_IMAGE_DIR / f"{image_name}.png"

    if exact_path.is_file():
        return exact_path, []

    # ---------------------------------------------------------
    # 2.没有完整路径匹配，则搜索所有同名文件
    # ---------------------------------------------------------
    candidates = []

    for image_path in GREEK_IMAGE_DIR.rglob(f"{Path(image_name).name}.png"):
        relative_path = image_path.relative_to(GREEK_IMAGE_DIR)

        # 忽略以下划线开头的文件/目录
        if any(part.startswith("_") for part in relative_path.parts):
            continue

        # 只接受真正的文件名匹配
        if image_path.stem == image_name:
            candidates.append(image_path)

    # ---------------------------------------------------------
    # 3.唯一匹配
    # ---------------------------------------------------------
    if len(candidates) == 1:
        return candidates[0], []

    # ---------------------------------------------------------
    # 4.多个匹配，产生歧义
    # ---------------------------------------------------------
    if len(candidates) > 1:
        candidates.sort()
        return None, candidates

    # ---------------------------------------------------------
    # 5.完全不存在
    # ---------------------------------------------------------
    return None, []


def get_available_images_tree() -> str:
    """以类似 tree 的格式返回所有可用图片名称，每行最多50个字符。"""
    tree: dict[str, list[str]] = {}

    for image_path in GREEK_IMAGE_DIR.rglob("*.png"):
        relative_path = image_path.relative_to(GREEK_IMAGE_DIR)

        # 隐藏以下划线开头的文件或目录
        if any(part.startswith("_") for part in relative_path.parts):
            continue

        if relative_path.parent == Path("."):
            tree.setdefault("", []).append(relative_path.stem)
        else:
            folder = relative_path.parent.as_posix()
            tree.setdefault(folder, []).append(relative_path.stem)

    def split_images(images: list[str], max_length: int = 50) -> list[str]:
        """将图片名称按长度拆分成多行。"""
        lines = []
        current_line = ""

        for image in sorted(images):
            if not current_line:
                current_line = image
                continue

            candidate = f"{current_line}, {image}"

            if len(candidate) > max_length:
                lines.append(current_line)
                current_line = image
            else:
                current_line = candidate

        if current_line:
            lines.append(current_line)

        return lines

    lines = []

    # 根目录下的图片
    root_images = tree.get("", [])
    if root_images:
        image_lines = split_images(root_images)

        for image_line in image_lines:
            lines.append(f"{child_prefix}{image_line}")

    # 子目录
    folders = sorted(folder for folder in tree if folder)

    for folder in folders:
        lines.append(f"{folder_prefix}{folder}/")

        image_lines = split_images(tree[folder])

        for image_line in image_lines:
            lines.append(f"{child_prefix}{image_line}")

    return "\n".join(lines)


def add_chromatic_aberration(image: Image.Image, intensity: int | None = None) -> Image.Image:
    """色散效果"""
    if intensity is None:
        intensity = plugin_config.osugreek_chromatic_intensity

    # 强度范围到1-20
    intensity = max(1, min(20, intensity))

    r, g, b = image.split()[:3]

    r_offset = ImageChops.offset(r, -intensity, -intensity)
    g_offset = ImageChops.offset(g, 0, 0)
    b_offset = ImageChops.offset(b, intensity, intensity)

    if len(image.split()) == 4:
        a = image.split()[3]
        return Image.merge("RGBA", (r_offset, g_offset, b_offset, a))
    else:
        return Image.merge("RGB", (r_offset, g_offset, b_offset))


def add_glitch_effect(image: Image.Image, intensity: int | None = None) -> Image.Image:
    """故障效果"""
    if intensity is None:
        intensity = plugin_config.osugreek_glitch_intensity

    # 强度范围0-5
    intensity = max(0, min(5, intensity))

    if intensity == 0:
        return image.copy()

    width, height = image.size
    glitched = image.copy()

    # 根据强度决定故障效果的程度
    if intensity >= 1:
        # 水平偏移故障
        num_shifts = min(3, max(1, intensity))
        for _ in range(num_shifts):
            max_shift = max(5, int(width * 0.1 * intensity / 5))
            shift_amount = random.randint(2, max_shift)
            shift_direction = random.choice([-1, 1])

            min_shift_height = height // 20
            max_shift_height = height // 6 + (height // 12) * (intensity - 1)
            shift_height = random.randint(min_shift_height, max_shift_height)
            shift_y = random.randint(0, height - shift_height)

            region = glitched.crop((0, shift_y, width, shift_y + shift_height))
            glitched.paste(region, (shift_amount * shift_direction, shift_y))

    if intensity >= 2:
        # 噪点效果
        base_noise = 50
        noise_intensity = base_noise * (intensity ** 2)
        for _ in range(noise_intensity):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255), 255)
            glitched.putpixel((x, y), color)

        # 噪点块效果
        if intensity >= 3:
            num_blocks = random.randint(1, intensity - 1)
            for _ in range(num_blocks):
                block_width = random.randint(5, 20)
                block_height = random.randint(5, 20)
                block_x = random.randint(0, width - block_width)
                block_y = random.randint(0, height - block_height)

                for bx in range(block_width):
                    for by in range(block_height):
                        if random.random() < 0.7:
                            px = min(block_x + bx, width - 1)
                            py = min(block_y + by, height - 1)
                            color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255), 255)
                            glitched.putpixel((px, py), color)

    if intensity >= 3:
        # 扫描线效果
        scanline_spacing = random.randint(8 - intensity, 15 - intensity)
        scanline_probability = 0.15 + (intensity - 3) * 0.05

        for y in range(0, height, scanline_spacing):
            if random.random() < scanline_probability:
                line_height = random.randint(1, 2)
                line_region = glitched.crop((0, y, width, y + line_height))
                # 扫描线亮度随强度变化
                brightness = 150 + (intensity - 3) * 25
                line_region = ImageChops.multiply(line_region, Image.new("RGBA", (width, line_height),
                                                                         (brightness, brightness, brightness, 255)))
                glitched.paste(line_region, (0, y))

    if intensity >= 4:
        # 扭曲效果
        # 高斯模糊
        blur_radius = 0.5 + (intensity - 4) * 0.5
        glitched = glitched.filter(ImageFilter.GaussianBlur(radius=blur_radius))

        # 颜色偏移扭曲
        if intensity >= 5:
            if len(glitched.split()) >= 3:
                r, g, b = glitched.split()[:3]
                offset_x = random.randint(-3, 3)
                offset_y = random.randint(-3, 3)

                r_offset = ImageChops.offset(r, offset_x, offset_y)
                b_offset = ImageChops.offset(b, -offset_x, -offset_y)

                if len(glitched.split()) == 4:
                    a = glitched.split()[3]
                    glitched = Image.merge("RGBA", (r_offset, g, b_offset, a))
                else:
                    glitched = Image.merge("RGB", (r_offset, g, b_offset))

    return glitched


def resize_greek_image(greek_img: Image.Image, original_width: int, original_height: int) -> Image.Image:
    """调整字母图片大小"""
    greek_w, greek_h = greek_img.size
    min_original_dimension = min(original_width, original_height)
    target_size = int(min_original_dimension * 1.8)
    scale_ratio = target_size / max(greek_w, greek_h)
    new_width = int(greek_w * scale_ratio)
    new_height = int(greek_h * scale_ratio)
    if new_width < 200:
        new_width = 200
        new_height = int(greek_h * (200 / greek_w))
    return greek_img.resize((new_width, new_height), Image.Resampling.LANCZOS)


def extract_gif_frames(img: Image.Image) -> tuple[list[Image.Image], list[int]]:
    """提取 GIF 的所有完整帧与每帧时长(ms)。

    Pillow 加载 GIF 时已按 disposal 模式把局部帧合成到完整画布上，
    因此这里逐帧转换为 RGBA 即可，输出帧与肉眼看到的画面一致。
    """
    frames: list[Image.Image] = []
    durations: list[int] = []

    for frame in ImageSequence.Iterator(img):
        duration = frame.info.get("duration")
        durations.append(int(duration) if duration else 100)
        frames.append(frame.convert("RGBA"))

    return frames, durations


def downsample_frames(
        frames: list[Image.Image],
        durations: list[int],
        max_frames: int,
) -> tuple[list[Image.Image], list[int]]:
    """把帧均匀抽样到 max_frames 帧，被丢弃帧的时长并入保留帧，总时长不变。"""
    total = len(frames)
    new_frames: list[Image.Image] = []
    new_durations: list[int] = []

    bucket_size = total / max_frames
    for i in range(max_frames):
        start = int(round(i * bucket_size))
        end = total if i == max_frames - 1 else int(round((i + 1) * bucket_size))
        if end <= start:
            end = min(start + 1, total)
        representative = (start + end - 1) // 2
        new_frames.append(frames[representative])
        new_durations.append(sum(durations[start:end]))

    return new_frames, new_durations


def compress_gif_frames(
        frames: list[Image.Image],
        durations: list[int],
        max_size: int | None = None,
        max_frames: int | None = None,
) -> tuple[list[Image.Image], list[int]]:
    """压缩 GIF 帧：限制帧数并等比缩小最长边，降低处理与发送开销。

    在逐帧加效果之前调用，画面变小、帧数变少后处理更快、输出更小；
    抽帧时合并时长，动画总时长保持不变。
    """
    if max_size is None:
        max_size = plugin_config.osugreek_gif_max_size
    if max_frames is None:
        max_frames = plugin_config.osugreek_gif_max_frames

    # 帧数上限
    if max_frames > 0 and len(frames) > max_frames:
        frames, durations = downsample_frames(frames, durations, max_frames)

    # 最长边上限
    if max_size > 0:
        width, height = frames[0].size
        longest = max(width, height)
        if longest > max_size:
            scale = max_size / longest
            new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
            frames = [frame.resize(new_size, Image.Resampling.LANCZOS) for frame in frames]

    return frames, durations


def save_animated_gif(
        frames: list[Image.Image],
        durations: list[int],
        loop: int = 0,
        colors: int | None = None,
) -> BytesIO:
    """将处理后的帧保存为动画 GIF，保留每帧时长与循环设置。

    colors: 输出调色板颜色数上限，超过则量化压缩；0/None 表示不限制。
    量化放在效果之后，避免故障噪点重新引入超出上限的颜色。
    """
    if colors:
        frames = [
            frame.quantize(colors=colors, method=Image.Quantize.FASTOCTREE).convert("RGBA")
            for frame in frames
        ]

    buffer = BytesIO()

    frames[0].save(
        buffer,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=loop,
        disposal=2,
    )
    buffer.seek(0)
    return buffer


def overlay_greek(image: Image.Image, greek_img: Image.Image) -> Image.Image:
    """将希腊字母图片居中叠加到图片上。"""
    orig_w, orig_h = image.size
    greek_w, greek_h = greek_img.size
    x = (orig_w - greek_w) // 2
    y = (orig_h - greek_h) // 2
    combined = Image.new("RGBA", image.size)
    combined.paste(image, (0, 0))
    combined.paste(greek_img, (x, y), greek_img)
    return combined


def process_frame(
        frame: Image.Image,
        greek_img: Image.Image,
        chromatic_intensity: int,
        glitch_intensity: int | None,
) -> Image.Image:
    """对单帧依次应用色散、故障效果，最后叠加希腊字母。"""
    if chromatic_intensity > 0:
        frame = add_chromatic_aberration(frame, intensity=chromatic_intensity)
    if glitch_intensity is not None and glitch_intensity > 0:
        frame = add_glitch_effect(frame, glitch_intensity)
    return overlay_greek(frame, greek_img)


def process_image_bytes(
        img_data: bytes,
        greek_img_path: Path,
        chromatic_intensity: int | None = None,
        glitch_intensity: int | None = None,
) -> bytes:
    """对图片字节应用色散/故障效果并叠加希腊字母，返回输出图片字节。

    动图输出 GIF（压缩后逐帧处理），静态图输出 JPEG。
    """
    if chromatic_intensity is None:
        chromatic_intensity = 4

    with Image.open(BytesIO(img_data)) as img:
        if getattr(img, "is_animated", False):
            loop = img.info.get("loop", 0)
            frames, durations = extract_gif_frames(img)
            frames, durations = compress_gif_frames(frames, durations)

            greek_img = Image.open(greek_img_path).convert("RGBA")
            greek_img = resize_greek_image(greek_img, frames[0].width, frames[0].height)

            processed_frames = [
                process_frame(frame, greek_img, chromatic_intensity, glitch_intensity)
                for frame in frames
            ]
            return save_animated_gif(
                processed_frames,
                durations,
                loop,
                plugin_config.osugreek_gif_colors,
            ).getvalue()

        greek_img = Image.open(greek_img_path).convert("RGBA")
        greek_img = resize_greek_image(greek_img, img.width, img.height)
        combined = process_frame(
            img.convert("RGBA"),
            greek_img,
            chromatic_intensity,
            glitch_intensity,
        )

    with BytesIO() as buffer:
        combined.convert("RGB").save(buffer, format="JPEG", quality=90)
        return buffer.getvalue()


def should_be_auto_osugreeked(img_data: bytes) -> bool:
    """判断图片字节是否为正方形（静态/动态均取整体尺寸）。"""
    try:
        with Image.open(BytesIO(img_data)) as img:
            return img.width not in [866, 1280, 1028]
    except Exception:
        return False


@osugreek.handle()
async def handle_osugreek(bot: Bot, event: MessageEvent):
    msg_text = event.get_plaintext().strip()
    command_parts = msg_text.split()

    greek_name = ""
    chromatic_intensity = None
    glitch_intensity = None

    if len(command_parts) > 1:
        greek_name = command_parts[1]

    param_index = 2
    if param_index < len(command_parts) and command_parts[param_index].isdigit():
        chromatic_intensity = int(command_parts[param_index])
        param_index += 1

    if param_index < len(command_parts) and command_parts[param_index].isdigit():
        glitch_intensity = int(command_parts[param_index])

    if greek_name == "help" or not greek_name:
        help_text = "用法：/osugreek <名称> [色散强度, 0~20] [故障强度, 0~5]"
        await bot.send(event, help_text)
        tree = get_available_images_tree()
        await bot.send(event, f"可用的名称有:\n{tree}")
        return
    image_msg = None
    for seg in event.message:
        if seg.type == "image":
            image_msg = seg
            break
    if not image_msg and hasattr(event, 'reply') and event.reply:
        for seg in event.reply.message:
            if seg.type == "image":
                image_msg = seg
                break
    if not image_msg:
        await bot.send(event, "请发送一张图片或回复一张图片", reply_message=True)
        return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_msg.data["url"]) as resp:
                if resp.status != 200:
                    await bot.send(event, "图片下载失败", reply_message=True)
                    return
                img_data = await resp.read()
    except Exception as e:
        await bot.send(event, f"图片下载失败: {e}", reply_message=True)
        return
    try:
        greek_img_path, ambiguous_paths = find_image_path(greek_name)

        if greek_img_path is None:
            if ambiguous_paths:
                candidates = "\n".join(
                    f"{child_prefix}{path.relative_to(GREEK_IMAGE_DIR).with_suffix('')}"
                    for path in ambiguous_paths
                )

                await bot.send(
                    event,
                    f"{greek_name} 存在多个匹配：\n{candidates}",
                    reply_message=True
                )
            else:
                tree = get_available_images_tree()

                await bot.send(
                    event,
                    f"未找到 {greek_name}\n可用的名称有:\n{tree}",
                    reply_message=True
                )

            return

        output = process_image_bytes(
            img_data,
            greek_img_path,
            chromatic_intensity,
            glitch_intensity,
        )
    except nonebot.exception.NetworkError as _:
        raise
    except Exception as e:
        await bot.send(event, f"图片处理失败: {str(e)}", reply_message=True)
        raise

    await bot.send(event, MessageSegment.image(output), reply_message=True)
    # finally:
    #     if temp_output_path and temp_output_path.exists():
    #         asyncio.create_task(cleanup_temp_file(temp_output_path))


@auto_osugreek.handle()
async def handle_auto_osugreek(bot: Bot, event: GroupMessageEvent):
    """群内发送正方形图片时，按概率随机套用 osugreek 效果并直接发送。

    全程静默：概率未通过、不在白名单、非正方形或处理失败均不提示。
    """
    # 概率判断（默认10%）
    if random.random() >= plugin_config.osugreek_auto_probability:
        return
    # 白名单判断（兼容字符串/数字两种写法）
    if (
            str(event.user_id) not in plugin_config.osugreek_auto_whitelist
            and event.user_id not in plugin_config.osugreek_auto_whitelist
    ):
        return
    # 名称列表为空则功能关闭
    if not plugin_config.osugreek_auto_names:
        return

    image_msg = None
    for seg in event.message:
        if seg.type == "image":
            image_msg = seg
            break
    if not image_msg or "url" not in image_msg.data:
        return

    # 段内元数据明确不是正方形时直接跳过，避免多余下载
    seg_w = image_msg.data.get("width")
    seg_h = image_msg.data.get("height")
    if seg_w is not None and seg_h is not None:
        try:
            if int(seg_w) != int(seg_h):
                return
        except (TypeError, ValueError):
            pass

    # 下载图片
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_msg.data["url"]) as resp:
                if resp.status != 200:
                    return
                img_data = await resp.read()
    except Exception:
        return

    # 正方形校验（静态/动态均取整体尺寸）
    if not should_be_auto_osugreeked(img_data):
        return

    # 随机选取名称并处理，失败静默
    try:
        greek_name = random.choice(plugin_config.osugreek_auto_names)
        greek_img_path, _ = find_image_path(greek_name)
        if greek_img_path is None:
            return
        output = process_image_bytes(img_data, greek_img_path)
        await bot.send(event, MessageSegment.image(output))
    except Exception:
        return
