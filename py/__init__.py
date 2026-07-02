from .api.capabilities import NODE_PREFIX
from .nodes import Sora2ImageToVideoNode, Sora2TextToVideoNode


def _node_name(label):
    return f"{NODE_PREFIX} {label}"


NODE_CLASS_MAPPINGS = {
    _node_name("Text to Video"): Sora2TextToVideoNode,
    _node_name("Image to Video"): Sora2ImageToVideoNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {key: key for key in NODE_CLASS_MAPPINGS}
